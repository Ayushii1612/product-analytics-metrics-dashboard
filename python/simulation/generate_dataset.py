"""
python/simulation/generate_dataset.py

Generates 2 million simulated e-commerce sessions using Faker.
Injects:
  • A 15% metric drop event on 2024-04-10 (tracking bug)
  • A feature launch on 2024-05-01 (improved checkout)
  • A seasonal spike around Holi festival (March 20-27)

Output: data/raw/sessions.parquet  (fast columnar format)
        data/raw/sessions.csv      (for Excel / SQL import)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta
from tqdm import tqdm
import random
from pathlib import Path

from config.settings import (
    SIMULATION, DEVICES, DEVICE_WEIGHTS, GEOS, GEO_WEIGHTS,
    CATEGORIES, CATEGORY_WEIGHTS, TRAFFIC_SOURCES, TRAFFIC_WEIGHTS,
)

fake = Faker("en_IN")
np.random.seed(SIMULATION["random_seed"])
random.seed(SIMULATION["random_seed"])

# ─── Date helpers ────────────────────────────────────────
start_dt = pd.Timestamp(SIMULATION["start_date"])
end_dt   = pd.Timestamp(SIMULATION["end_date"])
drop_dt  = pd.Timestamp(SIMULATION["drop_event_date"])
launch_dt = pd.Timestamp(SIMULATION["feature_launch_date"])
seasonal_start = pd.Timestamp(SIMULATION["seasonal_bump_start"])
seasonal_end   = pd.Timestamp(SIMULATION["seasonal_bump_end"])
date_range_days = (end_dt - start_dt).days


def get_conversion_rate(session_date: pd.Timestamp) -> float:
    """
    Returns the effective conversion rate for a given date,
    applying drop, feature launch, and seasonal effects.
    """
    base_cr = SIMULATION["base_conversion_rate"]

    # Seasonal spike (multiplicative)
    if seasonal_start <= session_date <= seasonal_end:
        base_cr *= SIMULATION["seasonal_multiplier"]

    # Feature launch (additive uplift)
    if session_date >= launch_dt:
        base_cr *= (1 + SIMULATION["feature_uplift"])

    # Metric drop event (multiplicative suppression)
    drop_end = drop_dt + timedelta(days=SIMULATION["drop_duration_days"])
    if drop_dt <= session_date < drop_end:
        base_cr *= (1 - SIMULATION["drop_magnitude"])

    return min(base_cr, 1.0)


def simulate_sessions(chunk_size: int = 100_000) -> pd.DataFrame:
    """
    Simulates user sessions in chunks to manage memory.
    Returns a single concatenated DataFrame.
    """
    total = SIMULATION["total_sessions"]
    chunks = []

    print(f"\n🔄  Generating {total:,} sessions in chunks of {chunk_size:,}...")

    # Pre-generate dates weighted by day-of-week (weekends ~30% more traffic)
    dates = pd.date_range(start=start_dt, end=end_dt, freq="D")
    day_weights = np.array([
        1.0 if d.dayofweek < 5 else 1.3 for d in dates
    ])
    day_weights /= day_weights.sum()
    chosen_dates = np.random.choice(dates, size=total, p=day_weights)
    # Add random seconds within the day
    random_seconds = np.random.randint(0, 86400, size=total)
    timestamps = pd.to_datetime(chosen_dates) + pd.to_timedelta(random_seconds, unit="s")

    # Sort for realism
    timestamps = np.sort(timestamps)

    session_ids = [f"S{str(i).zfill(8)}" for i in range(1, total + 1)]

    # User pool (20% of sessions share returning users)
    user_pool_size = int(total * 0.60)
    user_ids_pool  = [f"U{str(i).zfill(7)}" for i in range(1, user_pool_size + 1)]

    print("  ✓ Timestamps generated")

    for chunk_start in tqdm(range(0, total, chunk_size), desc="  Chunks"):
        chunk_end = min(chunk_start + chunk_size, total)
        n = chunk_end - chunk_start

        chunk_ts    = timestamps[chunk_start:chunk_end]
        chunk_sids  = session_ids[chunk_start:chunk_end]
        chunk_uids  = np.random.choice(user_ids_pool, size=n, replace=True)
        chunk_devices   = np.random.choice(DEVICES,   size=n, p=DEVICE_WEIGHTS)
        chunk_geos      = np.random.choice(GEOS,      size=n, p=GEO_WEIGHTS)
        chunk_cats      = np.random.choice(CATEGORIES, size=n, p=CATEGORY_WEIGHTS)
        chunk_sources   = np.random.choice(TRAFFIC_SOURCES, size=n, p=TRAFFIC_WEIGHTS)

        # Funnel steps: 1-5 (1=landing, 5=checkout complete)
        chunk_steps = np.random.choice([1, 2, 3, 4, 5], size=n,
                                        p=[0.35, 0.25, 0.20, 0.12, 0.08])

        # Conversion: depends on steps completed + date-based CR
        crs = np.array([get_conversion_rate(ts) for ts in chunk_ts])
        # Only sessions reaching step 4+ can convert
        step_modifier = np.where(chunk_steps >= 4, 1.0, 0.0)
        # Device modifier: desktop converts better
        device_modifier = np.where(chunk_devices == "desktop", 1.3,
                          np.where(chunk_devices == "tablet", 1.0, 0.8))
        effective_cr = np.clip(crs * step_modifier * device_modifier, 0, 1)
        chunk_converted = np.random.random(n) < effective_cr

        # Revenue: only for converted sessions, lognormal distribution
        base_rev = np.random.lognormal(mean=7.0, sigma=0.5, size=n)  # INR
        chunk_revenue = np.where(chunk_converted, base_rev, 0.0)

        # Page load time (ms): feature launch improves load time
        base_load = np.random.lognormal(mean=7.5, sigma=0.4, size=n)
        load_multiplier = np.where(
            chunk_ts >= launch_dt, 0.85, 1.0  # 15% faster after launch
        )
        chunk_load_time = base_load * load_multiplier

        # Bounce (left at step 1)
        chunk_bounced = (chunk_steps == 1).astype(int)

        df_chunk = pd.DataFrame({
            "session_id"       : chunk_sids,
            "user_id"          : chunk_uids,
            "timestamp"        : chunk_ts,
            "device"           : chunk_devices,
            "location"         : chunk_geos,
            "traffic_source"   : chunk_sources,
            "product_category" : chunk_cats,
            "steps_completed"  : chunk_steps,
            "converted"        : chunk_converted.astype(int),
            "revenue"          : np.round(chunk_revenue, 2),
            "page_load_ms"     : np.round(chunk_load_time, 1),
            "bounced"          : chunk_bounced,
        })

        chunks.append(df_chunk)

    df = pd.concat(chunks, ignore_index=True)
    df["date"] = df["timestamp"].dt.date
    df["week"]  = df["timestamp"].dt.to_period("W").astype(str)
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    df["hour"]  = df["timestamp"].dt.hour

    return df


def save_dataset(df: pd.DataFrame) -> None:
    raw_dir = Path(__file__).parent.parent.parent / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = raw_dir / "sessions.parquet"
    csv_path     = raw_dir / "sessions.csv"

    print("\n💾  Saving dataset...")
    df.to_parquet(parquet_path, index=False)
    print(f"  ✓ Parquet saved → {parquet_path}  ({parquet_path.stat().st_size/1e6:.1f} MB)")

    # Save a CSV sample (100K rows) for Excel
    sample = df.sample(n=100_000, random_state=42)
    sample.to_csv(csv_path, index=False)
    print(f"  ✓ CSV sample (100K rows) saved → {csv_path}")

    # Print dataset summary
    print("\n📊  Dataset Summary:")
    print(f"   Total sessions    : {len(df):,}")
    print(f"   Date range        : {df['date'].min()}  →  {df['date'].max()}")
    print(f"   Overall CR        : {df['converted'].mean()*100:.2f}%")
    print(f"   Total revenue     : ₹{df['revenue'].sum()/1e6:.2f}M")
    print(f"   Unique users      : {df['user_id'].nunique():,}")
    print(f"   Avg page load     : {df['page_load_ms'].mean():.0f}ms")


if __name__ == "__main__":
    df = simulate_sessions()
    save_dataset(df)
    print("\n✅  Dataset generation complete!\n")