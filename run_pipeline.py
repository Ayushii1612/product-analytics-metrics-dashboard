"""
run_pipeline.py
───────────────
Master pipeline that runs all 4 modules in sequence.

Usage:
    python run_pipeline.py              # Run all modules
    python run_pipeline.py --module 1   # Run specific module
    python run_pipeline.py --skip-gen   # Skip data generation (if already done)
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

def banner(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def run_full_pipeline(skip_generation: bool = False, module: int = None):
    start_time = datetime.now()
    banner("🚀 Product Analytics Pipeline — Starting")

    # ── Data Generation ──────────────────────────────────
    if not skip_generation and (module is None or module == 0):
        banner("📊 Step 0: Dataset Generation (2M sessions)")
        from python.simulation.generate_dataset import simulate_sessions, save_dataset
        df = simulate_sessions()
        save_dataset(df)
    else:
        print("\n⏭️  Skipping data generation (--skip-gen)")
        import pandas as pd
        parquet_path = Path("data/raw/sessions.parquet")
        if not parquet_path.exists():
            print("  ❌ No dataset found! Run without --skip-gen first.")
            sys.exit(1)

    # ── Module 1 ─────────────────────────────────────────
    if module is None or module == 1:
        banner("📐 Module 1: North Star Metrics Framework")
        from python.analysis.module1_north_star import run as run_m1
        run_m1()

    # ── Module 2 ─────────────────────────────────────────
    if module is None or module == 2:
        banner("🔍 Module 2: Metric Drop Diagnosis")
        from python.analysis.module2_metric_drop import run as run_m2
        run_m2()

    # ── Module 3 ─────────────────────────────────────────
    if module is None or module == 3:
        banner("🚀 Module 3: Feature Launch Impact")
        from python.analysis.module3_feature_launch import run as run_m3
        run_m3()

    # ── Module 4 ─────────────────────────────────────────
    if module is None or module == 4:
        banner("📡 Module 4: Anomaly Detection + Dashboard")
        from python.analysis.module4_anomaly_detection import run as run_m4
        run_m4()

    # ── ML Segmentation ──────────────────────────────────
    if module is None or module == 5:
        banner("🤖 ML: User Segmentation (K-Means)")
        from python.ml.user_segmentation import run as run_ml
        run_ml()

    # ── Done ─────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).seconds
    banner(f"✅ Pipeline Complete — {elapsed}s elapsed")

    print("\n📁 Output files:")
    print("  data/raw/sessions.parquet          — Full 2M session dataset")
    print("  data/raw/sessions.csv              — 100K sample for Excel")
    print("  data/exports/daily_kpis.csv        — Dashboard data (Power BI)")
    print("  data/exports/metrics_tree.json     — North star tree")
    print("  data/exports/anomaly_events.csv    — Anomaly log")
    print("  data/exports/user_segments.csv     — K-Means segments")
    print("  data/exports/feature_launch_tracker.csv")
    print("  reports/module1_north_star_metrics.xlsx")
    print("  reports/module2_diagnosis_report.xlsx")
    print("  reports/module2_diagnosis_report.txt")
    print("  reports/module3_feature_launch_report.xlsx")
    print("  reports/module3_feature_launch_report.txt")
    print("  reports/weekly_insights.txt        — Claude API summaries")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Product Analytics Pipeline")
    parser.add_argument("--skip-gen", action="store_true",
                        help="Skip dataset generation (uses existing data)")
    parser.add_argument("--module", type=int, choices=[1, 2, 3, 4, 5],
                        help="Run only a specific module (1-5)")
    args = parser.parse_args()

    run_full_pipeline(
        skip_generation=args.skip_gen,
        module=args.module,
    )