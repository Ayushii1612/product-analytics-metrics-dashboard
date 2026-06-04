"""
python/analysis/module4_anomaly_detection.py

Module 4: Anomaly Detection + Executive Dashboard Data Prep
  • Compute daily KPIs with 7-day rolling averages
  • Detect anomalies using Z-score (threshold = 2σ)
  • Export clean data for Power BI / Tableau
  • Generate weekly insight summaries via Claude API
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pandas as pd
import numpy as np
from pathlib import Path
import json
import anthropic

from config.settings import SIMULATION, ANOMALY_Z_THRESHOLD, MOVING_AVG_WINDOW, ANTHROPIC_API_KEY


# ─── Load Data ───────────────────────────────────────────
def load_data() -> pd.DataFrame:
    path = Path(__file__).parent.parent.parent / "data" / "raw" / "sessions.parquet"
    df = pd.read_parquet(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"]      = pd.to_datetime(df["date"])
    return df


# ─── Daily KPIs ──────────────────────────────────────────
def compute_daily_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates session data into daily KPIs used in the executive dashboard.
    """
    daily = (
        df.groupby("date")
          .agg(
              sessions          = ("session_id", "count"),
              conversions       = ("converted", "sum"),
              total_revenue     = ("revenue", "sum"),
              avg_page_load_ms  = ("page_load_ms", "mean"),
              bounce_count      = ("bounced", "sum"),
          )
          .reset_index()
    )

    daily["conversion_rate"]    = daily["conversions"] / daily["sessions"]
    daily["bounce_rate"]        = daily["bounce_count"] / daily["sessions"]
    daily["revenue_per_session"] = daily["total_revenue"] / daily["sessions"]
    daily["avg_steps"] = (
        df.groupby("date")["steps_completed"].mean().values
    )

    # Rolling averages (7-day)
    for col in ["conversion_rate", "revenue_per_session", "avg_page_load_ms", "bounce_rate"]:
        daily[f"{col}_7d_ma"] = (
            daily[col].rolling(MOVING_AVG_WINDOW, min_periods=1).mean()
        )

    # Rolling std (for Z-score)
    for col in ["conversion_rate", "revenue_per_session"]:
        daily[f"{col}_7d_std"] = (
            daily[col].rolling(MOVING_AVG_WINDOW, min_periods=2).std()
        )

    # Z-scores
    daily["cr_zscore"]  = (
        (daily["conversion_rate"] - daily["conversion_rate_7d_ma"])
        / daily["conversion_rate_7d_std"].replace(0, np.nan)
    ).round(3)
    daily["rps_zscore"] = (
        (daily["revenue_per_session"] - daily["revenue_per_session_7d_ma"])
        / daily["revenue_per_session_7d_std"].replace(0, np.nan)
    ).round(3)

    # Anomaly flags
    daily["cr_anomaly"]  = daily["cr_zscore"].abs() > ANOMALY_Z_THRESHOLD
    daily["rps_anomaly"] = daily["rps_zscore"].abs() > ANOMALY_Z_THRESHOLD

    # Format columns
    daily["conversion_rate"]         = daily["conversion_rate"].round(6)
    daily["bounce_rate"]             = daily["bounce_rate"].round(6)
    daily["revenue_per_session"]     = daily["revenue_per_session"].round(2)
    daily["avg_page_load_ms"]        = daily["avg_page_load_ms"].round(1)
    daily["total_revenue"]           = daily["total_revenue"].round(2)

    return daily


# ─── Driver Health ────────────────────────────────────────
def compute_driver_health(df: pd.DataFrame) -> dict:
    """
    Computes health status for each Level 1 driver to display in the metrics tree.
    Returns a dict suitable for dashboard visualisation.
    """
    overall_cr = df["converted"].mean()
    avg_load   = df["page_load_ms"].mean()
    bounce_rate = df["bounced"].mean()

    drivers = {
        "north_star": {
            "name"  : "Conversion Rate",
            "value" : round(overall_cr * 100, 3),
            "unit"  : "%",
            "status": "healthy" if overall_cr >= 0.03 else "at_risk",
        },
        "page_experience": {
            "name"  : "Page Experience",
            "status": "at_risk" if avg_load > 2500 else "healthy",
            "sub_drivers": {
                "page_load_speed"  : {"value": round(avg_load, 0), "unit": "ms",
                                      "status": "at_risk" if avg_load > 2500 else "healthy"},
                "bounce_rate"      : {"value": round(bounce_rate * 100, 2), "unit": "%",
                                      "status": "at_risk" if bounce_rate > 0.40 else "healthy"},
                "mobile_experience": {"value": round(df[df["device"]=="mobile"]["converted"].mean()*100,3),
                                      "unit": "%", "status": "healthy"},
            },
        },
        "price_value": {
            "name"  : "Price & Value",
            "status": "healthy",
            "sub_drivers": {
                "revenue_per_session": {"value": round(df["revenue"].mean(), 2), "unit": "₹",
                                        "status": "healthy"},
                "electronics_cr"     : {"value": round(df[df["product_category"]=="Electronics"]["converted"].mean()*100,3),
                                        "unit": "%", "status": "healthy"},
            },
        },
        "discovery": {
            "name"  : "Discovery",
            "status": "healthy",
            "sub_drivers": {
                "organic_share": {"value": round(len(df[df["traffic_source"]=="organic_search"])/len(df)*100,1),
                                  "unit": "%", "status": "healthy"},
                "paid_cr"      : {"value": round(df[df["traffic_source"]=="paid_search"]["converted"].mean()*100,3),
                                  "unit": "%", "status": "healthy"},
            },
        },
        "product_quality": {
            "name"  : "Product Quality",
            "status": "healthy",
            "sub_drivers": {
                "avg_steps_completed": {"value": round(df["steps_completed"].mean(), 2),
                                        "unit": "steps", "status": "healthy"},
            },
        },
    }
    return drivers


# ─── Feature Launch Tracker ───────────────────────────────
def compute_feature_tracker(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Shows daily CR trend around the feature launch for the dashboard.
    """
    launch_dt = pd.Timestamp(SIMULATION["feature_launch_date"])
    window    = pd.Timedelta(days=21)

    mask = (daily["date"] >= launch_dt - window) & (daily["date"] <= launch_dt + window)
    tracker = daily[mask][["date", "conversion_rate", "conversion_rate_7d_ma",
                            "sessions", "total_revenue"]].copy()
    tracker["period"] = tracker["date"].apply(
        lambda d: "pre_launch" if d < launch_dt else "post_launch"
    )
    return tracker


# ─── Export for Dashboard ─────────────────────────────────
def export_dashboard_data(daily: pd.DataFrame, driver_health: dict,
                          feature_tracker: pd.DataFrame) -> None:
    out_dir = Path(__file__).parent.parent.parent / "data" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Daily KPIs CSV (for Power BI)
    daily_path = out_dir / "daily_kpis.csv"
    daily.to_csv(daily_path, index=False)
    print(f"  ✓ Daily KPIs CSV → {daily_path}")

    # Anomaly events
    anomalies = daily[daily["cr_anomaly"] | daily["rps_anomaly"]][
        ["date", "conversion_rate", "cr_zscore", "total_revenue", "rps_zscore"]
    ]
    anomaly_path = out_dir / "anomaly_events.csv"
    anomalies.to_csv(anomaly_path, index=False)
    print(f"  ✓ Anomaly events CSV → {anomaly_path}  ({len(anomalies)} anomalies)")

    # Driver health JSON
    health_path = out_dir / "driver_health.json"
    with open(health_path, "w") as f:
        json.dump(driver_health, f, indent=2, default=str)
    print(f"  ✓ Driver health JSON → {health_path}")

    # Feature launch tracker
    tracker_path = out_dir / "feature_launch_tracker.csv"
    feature_tracker.to_csv(tracker_path, index=False)
    print(f"  ✓ Feature tracker CSV → {tracker_path}")


# ─── Claude API: Weekly Insight Summary ──────────────────
def generate_weekly_insights(daily: pd.DataFrame, week_number: int = 1) -> str:
    """
    Uses the Anthropic Claude API to generate a plain-English weekly insight summary.
    week_number: 1-indexed week to summarise (from start of dataset).
    """
    if not ANTHROPIC_API_KEY:
        return "⚠️  ANTHROPIC_API_KEY not set. Add it to .env to enable weekly insights."

    # Get the specified week's data
    all_weeks = daily.copy()
    all_weeks["week_num"] = (
        (all_weeks["date"] - all_weeks["date"].min()).dt.days // 7 + 1
    )
    week_data = all_weeks[all_weeks["week_num"] == week_number]

    if len(week_data) == 0:
        return f"No data found for week {week_number}."

    # Build a structured context string for Claude
    week_start = str(week_data["date"].min().date())
    week_end   = str(week_data["date"].max().date())
    avg_cr     = week_data["conversion_rate"].mean() * 100
    avg_rps    = week_data["revenue_per_session"].mean()
    total_rev  = week_data["total_revenue"].sum()
    avg_load   = week_data["avg_page_load_ms"].mean()
    anomalies  = week_data[week_data["cr_anomaly"]]["date"].tolist()

    context = f"""
Weekly Analytics Summary — {week_start} to {week_end}

Key Metrics:
- Average Daily Conversion Rate: {avg_cr:.3f}%
- Average Revenue Per Session: ₹{avg_rps:.2f}
- Total Weekly Revenue: ₹{total_rev:,.0f}
- Average Page Load Time: {avg_load:.0f}ms
- Anomaly Days (CR spike/drop > 2σ): {len(anomalies)} day(s)
- Anomaly Dates: {[str(d.date()) for d in anomalies] if anomalies else 'None'}

Historical Baseline:
- Overall avg CR: {daily['conversion_rate'].mean()*100:.3f}%
- Overall avg RPS: ₹{daily['revenue_per_session'].mean():.2f}

Feature Launch: New checkout launched {SIMULATION['feature_launch_date']}
Drop Event: 15% CR drop on {SIMULATION['drop_event_date']} (tracked error)
"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": (
                "You are a senior product analyst writing a weekly executive briefing. "
                "Based on the following metrics data, write a concise (150-200 word) "
                "weekly insight summary. Use plain English. Highlight what's working, "
                "what needs attention, and one specific recommended action. "
                "Do NOT use bullet points — write in paragraph form.\n\n"
                + context
            ),
        }],
    )
    return message.content[0].text


def save_weekly_insights(daily: pd.DataFrame) -> None:
    print("  ⏭️  Weekly insights skipped (Claude API disabled)")


# ─── Main ────────────────────────────────────────────────
def run():
    print("\n📡  Module 4: Anomaly Detection + Executive Dashboard")
    print("─" * 50)

    df    = load_data()
    daily = compute_daily_kpis(df)

    # Print anomaly summary
    cr_anomalies = daily[daily["cr_anomaly"]]
    print(f"\n  Total days tracked   : {len(daily)}")
    print(f"  CR anomaly days      : {len(cr_anomalies)}")
    print(f"  Anomaly dates:\n  {list(cr_anomalies['date'].dt.date)}")

    driver_health   = compute_driver_health(df)
    feature_tracker = compute_feature_tracker(daily)

    export_dashboard_data(daily, driver_health, feature_tracker)
    save_weekly_insights(daily)

    print("\n✅  Module 4 complete!\n")
    return daily, driver_health


if __name__ == "__main__":
    run()