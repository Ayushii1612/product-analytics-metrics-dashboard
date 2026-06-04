"""
config/settings.py
Central configuration for the Product Analytics project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ──────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent.parent
DATA_DIR        = BASE_DIR / "data"
RAW_DIR         = DATA_DIR / "raw"
PROCESSED_DIR   = DATA_DIR / "processed"
EXPORTS_DIR     = DATA_DIR / "exports"
REPORTS_DIR     = BASE_DIR / "reports"

# ─── Database ────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", str(PROCESSED_DIR / "analytics.duckdb"))

# ─── API Keys ────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ─── Simulation Parameters ───────────────────────────────
SIMULATION = {
    "total_sessions"    : 2_000_000,
    "start_date"        : "2024-01-01",
    "end_date"          : "2024-06-30",
    "base_conversion_rate": 0.035,       # 3.5% baseline
    "avg_revenue"       : 1250,          # INR per converted session
    "random_seed"       : 42,

    # Drop event: 15% conversion drop on April 10
    "drop_event_date"   : "2024-04-10",
    "drop_magnitude"    : 0.15,          # 15% relative drop
    "drop_duration_days": 3,

    # Feature launch: new checkout on May 1
    "feature_launch_date": "2024-05-01",
    "feature_uplift"     : 0.12,         # 12% improvement
    "feature_rollout_pct": 1.0,          # 100% rollout

    # Seasonal pattern: Holi festival bump in March
    "seasonal_bump_start": "2024-03-20",
    "seasonal_bump_end"  : "2024-03-27",
    "seasonal_multiplier": 1.45,
}

# ─── Devices, Geos, Categories, Sources ──────────────────
DEVICES   = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [0.62, 0.30, 0.08]

GEOS = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
]
GEO_WEIGHTS = [0.18, 0.17, 0.15, 0.10, 0.09, 0.08, 0.07, 0.06, 0.05, 0.05]

CATEGORIES = ["Electronics", "Fashion", "Home & Kitchen", "Beauty", "Sports", "Books"]
CATEGORY_WEIGHTS = [0.28, 0.25, 0.18, 0.12, 0.10, 0.07]

TRAFFIC_SOURCES = ["organic_search", "paid_search", "social", "email", "direct", "referral"]
TRAFFIC_WEIGHTS = [0.30, 0.22, 0.18, 0.12, 0.10, 0.08]

# ─── Analysis Parameters ─────────────────────────────────
ANOMALY_Z_THRESHOLD   = 2.0      # z-score threshold for anomaly alerts
MOVING_AVG_WINDOW     = 7        # 7-day rolling window
SIGNIFICANCE_LEVEL    = 0.05     # 95% confidence
MIN_SAMPLE_SIZE       = 1000     # minimum sample for statistical tests

# ─── Business Impact ─────────────────────────────────────
BUSINESS = {
    "avg_daily_sessions" : 10_959,   # ~2M / 182 days
    "avg_revenue_per_session": 43.75,  # 3.5% CR × ₹1250
}