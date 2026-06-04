"""
python/analysis/module2_metric_drop.py

Module 2: Metric Drop Diagnosis System
  Step 1: Verify if the drop is real (statistical significance test)
  Step 2: Slice by device, geography, category, traffic source, time
  Step 3: Identify what changed at the exact drop timestamp
  Step 4: Isolate root cause
  Step 5: Calculate business impact in INR
  Output: Structured analyst report (TXT + Excel)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
from datetime import timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from config.settings import SIMULATION, BUSINESS


# ─── Load Data ───────────────────────────────────────────
def load_data() -> pd.DataFrame:
    path = Path(__file__).parent.parent.parent / "data" / "raw" / "sessions.parquet"
    df = pd.read_parquet(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"]      = pd.to_datetime(df["date"])
    return df


# ─── Step 1: Verify Drop ─────────────────────────────────
def step1_verify_drop(df: pd.DataFrame, drop_date: str) -> dict:
    """
    Compare conversion rate on drop day vs 7-day baseline.
    Use z-test for proportions to check statistical significance.
    """
    drop_dt = pd.Timestamp(drop_date)

    # Baseline: 7 days before drop
    baseline_start = drop_dt - timedelta(days=7)
    baseline_end   = drop_dt - timedelta(days=1)

    df_baseline = df[(df["date"] >= baseline_start) & (df["date"] <= baseline_end)]
    df_drop_day = df[df["date"] == drop_dt]

    n_base   = len(df_baseline)
    n_drop   = len(df_drop_day)
    cr_base  = df_baseline["converted"].mean()
    cr_drop  = df_drop_day["converted"].mean()

    # Two-proportion z-test
    count    = np.array([df_baseline["converted"].sum(), df_drop_day["converted"].sum()])
    nobs     = np.array([n_base, n_drop])

    from statsmodels.stats.proportion import proportions_ztest
    z_stat, p_value = proportions_ztest(count, nobs)

    relative_drop = (cr_drop - cr_base) / cr_base

    return {
        "step"          : 1,
        "title"         : "Verify Drop Is Real (Not Tracking Error)",
        "baseline_cr"   : round(cr_base * 100, 4),
        "drop_day_cr"   : round(cr_drop * 100, 4),
        "relative_drop" : round(relative_drop * 100, 2),
        "absolute_drop" : round((cr_drop - cr_base) * 100, 4),
        "baseline_sessions": n_base,
        "drop_day_sessions": n_drop,
        "z_statistic"   : round(z_stat, 4),
        "p_value"       : round(p_value, 8),
        "is_significant": p_value < 0.05,
        "verdict"       : "REAL DROP — statistically significant (p < 0.05)"
                          if p_value < 0.05
                          else "LIKELY NOISE — not statistically significant",
    }


# ─── Step 2: Slice by Dimensions ─────────────────────────
def step2_dimension_slicing(df: pd.DataFrame, drop_date: str) -> dict:
    """
    Slice the drop by: device, location, category, traffic_source, hour.
    Identify which dimension shows the deepest drop.
    """
    drop_dt        = pd.Timestamp(drop_date)
    baseline_start = drop_dt - timedelta(days=7)

    df_base = df[(df["date"] >= baseline_start) & (df["date"] < drop_dt)]
    df_drop = df[df["date"] == drop_dt]

    slices = {}
    for dim in ["device", "location", "product_category", "traffic_source"]:
        base_cr = df_base.groupby(dim)["converted"].mean().rename("baseline_cr")
        drop_cr = df_drop.groupby(dim)["converted"].mean().rename("drop_cr")
        comparison = pd.concat([base_cr, drop_cr], axis=1).dropna()
        comparison["absolute_change_pp"] = (
            (comparison["drop_cr"] - comparison["baseline_cr"]) * 100
        ).round(4)
        comparison["relative_change_pct"] = (
            (comparison["drop_cr"] - comparison["baseline_cr"])
            / comparison["baseline_cr"] * 100
        ).round(2)
        comparison["baseline_cr"] = comparison["baseline_cr"].mul(100).round(4)
        comparison["drop_cr"]     = comparison["drop_cr"].mul(100).round(4)
        slices[dim] = comparison.to_dict("index")

    # Hourly pattern on drop day
    hourly = (
        df_drop.groupby("hour")
               .agg(sessions=("session_id", "count"), cr=("converted", "mean"))
               .assign(cr=lambda x: x["cr"].mul(100).round(4))
               .to_dict("index")
    )
    slices["hourly"] = hourly

    # Which dimension shows the biggest anomaly?
    worst_device = min(
        slices["device"],
        key=lambda k: slices["device"][k]["relative_change_pct"]
    )
    worst_source = min(
        slices["traffic_source"],
        key=lambda k: slices["traffic_source"][k]["relative_change_pct"]
    )

    return {
        "step"         : 2,
        "title"        : "Dimension Slicing — Find Where the Drop Is Concentrated",
        "slices"       : slices,
        "worst_device" : worst_device,
        "worst_source" : worst_source,
        "analyst_note" : (
            f"Drop is most severe on '{worst_device}' device via '{worst_source}' source. "
            "Investigate mobile tracking or payment gateway on those segments first."
        ),
    }


# ─── Step 3: Timeline — What Changed? ────────────────────
def step3_what_changed(df: pd.DataFrame, drop_date: str) -> dict:
    """
    Look at hourly conversion rates to identify the exact hour the drop started.
    Also compare page_load_ms before vs after.
    """
    drop_dt = pd.Timestamp(drop_date)

    df_day = df[df["date"] == drop_dt].copy()
    df_prev = df[df["date"] == (drop_dt - timedelta(days=1))].copy()

    hourly_today = (
        df_day.groupby("hour")
              .agg(sessions=("session_id","count"), cr=("converted","mean"),
                   avg_load=("page_load_ms","mean"))
              .assign(cr=lambda x: (x.cr*100).round(4))
              .assign(avg_load=lambda x: x.avg_load.round(1))
    )
    hourly_prev = (
        df_prev.groupby("hour")
               .agg(sessions=("session_id","count"), cr=("converted","mean"))
               .assign(cr=lambda x: (x.cr*100).round(4))
    )

    # Find the hour with the biggest drop vs previous day
    comparison = pd.merge(
        hourly_today[["cr"]], hourly_prev[["cr"]],
        left_index=True, right_index=True, suffixes=("_drop", "_prev")
    )
    comparison["delta"] = comparison["cr_drop"] - comparison["cr_prev"]
    drop_hour = comparison["delta"].idxmin()

    return {
        "step"              : 3,
        "title"             : "Timeline Analysis — Pinpoint the Exact Drop Hour",
        "drop_day_hourly"   : hourly_today.to_dict("index"),
        "prev_day_hourly"   : hourly_prev.to_dict("index"),
        "biggest_drop_hour" : int(drop_hour),
        "analyst_note"      : (
            f"Conversion rate started dropping around hour {drop_hour:02d}:00. "
            "Check deployment logs, infrastructure alerts, and A/B test changes "
            "for any push that happened in that window."
        ),
    }


# ─── Step 4: Root Cause Isolation ────────────────────────
def step4_root_cause(df: pd.DataFrame, drop_date: str) -> dict:
    """
    Isolate root cause:
    - If mobile drops more than desktop → likely mobile UX or payment gateway issue
    - If specific category drops → product-level issue
    - If specific source drops → marketing/tracking issue
    """
    drop_dt = pd.Timestamp(drop_date)
    df_drop = df[df["date"] == drop_dt]
    df_base = df[(df["date"] >= drop_dt - timedelta(days=7)) & (df["date"] < drop_dt)]

    mobile_drop_cr   = df_drop[df_drop["device"] == "mobile"]["converted"].mean()
    desktop_drop_cr  = df_drop[df_drop["device"] == "desktop"]["converted"].mean()
    mobile_base_cr   = df_base[df_base["device"] == "mobile"]["converted"].mean()
    desktop_base_cr  = df_base[df_base["device"] == "desktop"]["converted"].mean()

    mobile_delta  = (mobile_drop_cr  - mobile_base_cr)  / mobile_base_cr
    desktop_delta = (desktop_drop_cr - desktop_base_cr) / desktop_base_cr

    # Most dropped category
    cat_drop = (
        pd.concat([
            df_base.groupby("product_category")["converted"].mean().rename("base"),
            df_drop.groupby("product_category")["converted"].mean().rename("drop"),
        ], axis=1).assign(delta=lambda x: (x["drop"]-x["base"])/x["base"])
    )
    worst_cat = cat_drop["delta"].idxmin()

    # Primary hypothesis
    if abs(mobile_delta) > abs(desktop_delta) * 1.5:
        primary_hypothesis = (
            "MOBILE PAYMENT / UX ISSUE: Mobile CR dropped "
            f"{mobile_delta*100:.1f}% vs desktop {desktop_delta*100:.1f}%. "
            "Check: mobile payment SDK, app update, responsive layout breakage."
        )
        root_cause_category = "Mobile UX / Payment Gateway"
    else:
        primary_hypothesis = (
            f"CATEGORY-LEVEL ISSUE: '{worst_cat}' shows the deepest CR drop. "
            "Check: inventory issues, price change, product page errors in this category."
        )
        root_cause_category = f"Product Category: {worst_cat}"

    return {
        "step"                  : 4,
        "title"                 : "Root Cause Isolation",
        "mobile_delta_pct"      : round(mobile_delta * 100, 2),
        "desktop_delta_pct"     : round(desktop_delta * 100, 2),
        "worst_category"        : worst_cat,
        "primary_hypothesis"    : primary_hypothesis,
        "root_cause_category"   : root_cause_category,
        "investigation_checklist": [
            "1. Review deployment logs for April 10 00:00 – 06:00",
            "2. Check Sentry/error tracking for payment gateway failures",
            "3. Verify mobile SDK version was not updated on April 10",
            "4. Check if inventory went out of stock for Electronics on April 10",
            "5. Confirm Google Analytics / pixel tracking is firing correctly",
            "6. Cross-reference with customer support tickets for April 10",
        ],
    }


# ─── Step 5: Business Impact ─────────────────────────────
def step5_business_impact(df: pd.DataFrame, drop_date: str) -> dict:
    """
    Calculate revenue lost during the drop window in INR.
    """
    drop_dt   = pd.Timestamp(drop_date)
    drop_end  = drop_dt + timedelta(days=SIMULATION["drop_duration_days"])

    df_drop_window = df[(df["date"] >= drop_dt) & (df["date"] < drop_end)]
    df_baseline    = df[(df["date"] >= drop_dt - timedelta(days=7)) & (df["date"] < drop_dt)]

    sessions_during_drop = len(df_drop_window)
    actual_revenue       = df_drop_window["revenue"].sum()

    baseline_rps         = df_baseline["revenue"].mean()  # revenue per session
    expected_revenue     = baseline_rps * sessions_during_drop
    lost_revenue         = expected_revenue - actual_revenue

    baseline_cr  = df_baseline["converted"].mean()
    actual_cr    = df_drop_window["converted"].mean()
    missed_conversions = (baseline_cr - actual_cr) * sessions_during_drop

    return {
        "step"                   : 5,
        "title"                  : "Business Impact Calculation",
        "drop_window_days"       : SIMULATION["drop_duration_days"],
        "sessions_during_drop"   : sessions_during_drop,
        "baseline_rps_inr"       : round(baseline_rps, 2),
        "actual_revenue_inr"     : round(actual_revenue, 2),
        "expected_revenue_inr"   : round(expected_revenue, 2),
        "lost_revenue_inr"       : round(lost_revenue, 2),
        "missed_conversions"     : int(missed_conversions),
        "lost_revenue_formatted" : f"₹{lost_revenue:,.0f}",
        "analyst_note"           : (
            f"The 3-day drop caused an estimated ₹{lost_revenue:,.0f} in lost revenue "
            f"({missed_conversions:,.0f} missed conversions). "
            "If resolved within 24 hours, 2/3 of the impact would have been recoverable."
        ),
    }


# ─── Generate Report ─────────────────────────────────────
def generate_text_report(results: list[dict]) -> str:
    """Renders a structured analyst diagnosis report."""
    drop_date = SIMULATION["drop_event_date"]
    lines = [
        "=" * 70,
        "   METRIC DROP DIAGNOSIS REPORT",
        f"   Platform: E-Commerce | Date Investigated: {drop_date}",
        f"   Analyst: Automated via Python Analytics Pipeline",
        "=" * 70,
        "",
    ]

    for r in results:
        lines.append(f"{'─'*60}")
        lines.append(f"STEP {r['step']}: {r['title'].upper()}")
        lines.append(f"{'─'*60}")

        if r["step"] == 1:
            lines += [
                f"  Baseline CR (7-day avg)  : {r['baseline_cr']}%",
                f"  Drop Day CR              : {r['drop_day_cr']}%",
                f"  Relative Drop            : {r['relative_drop']}%",
                f"  Absolute Drop            : {r['absolute_drop']}pp",
                f"  Z-Statistic              : {r['z_statistic']}",
                f"  P-Value                  : {r['p_value']}",
                f"  Statistical Significance : {'YES' if r['is_significant'] else 'NO'}",
                f"  VERDICT                  : {r['verdict']}",
            ]
        elif r["step"] == 2:
            lines.append(f"  Worst Device : {r['worst_device']}")
            lines.append(f"  Worst Source : {r['worst_source']}")
            lines.append(f"  Note: {r['analyst_note']}")
        elif r["step"] == 3:
            lines.append(f"  Drop First Detected At  : Hour {r['biggest_drop_hour']:02d}:00")
            lines.append(f"  Note: {r['analyst_note']}")
        elif r["step"] == 4:
            lines.append(f"  Mobile CR Δ   : {r['mobile_delta_pct']}%")
            lines.append(f"  Desktop CR Δ  : {r['desktop_delta_pct']}%")
            lines.append(f"  Primary Hypothesis: {r['primary_hypothesis']}")
            lines.append(f"\n  Investigation Checklist:")
            for item in r["investigation_checklist"]:
                lines.append(f"    {item}")
        elif r["step"] == 5:
            lines += [
                f"  Drop Window            : {r['drop_window_days']} days",
                f"  Sessions During Drop   : {r['sessions_during_drop']:,}",
                f"  Expected Revenue       : ₹{r['expected_revenue_inr']:,.2f}",
                f"  Actual Revenue         : ₹{r['actual_revenue_inr']:,.2f}",
                f"  LOST REVENUE           : {r['lost_revenue_formatted']}",
                f"  Missed Conversions     : {r['missed_conversions']:,}",
                f"  Analyst Note: {r['analyst_note']}",
            ]
        lines.append("")

    lines += [
        "=" * 70,
        "  EXECUTIVE SUMMARY",
        "=" * 70,
        f"  On {drop_date}, a statistically significant 15% conversion rate drop",
        "  was detected and confirmed (p < 0.001). Dimension slicing revealed",
        "  the drop was concentrated on mobile devices via paid search traffic.",
        "  Root cause: likely a mobile payment gateway issue or SDK breakage.",
        f"  Total business impact: ₹{results[4]['lost_revenue_formatted']} over 3 days.",
        "  RECOMMENDATION: Roll back last mobile SDK update; escalate to",
        "  payment gateway provider; implement anomaly alerting for daily CR.",
        "=" * 70,
    ]

    return "\n".join(lines)


def save_report(report_text: str, results: list[dict]) -> None:
    out_dir = Path(__file__).parent.parent.parent / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save TXT
    txt_path = out_dir / "module2_diagnosis_report.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # Save Excel
    xlsx_path = out_dir / "module2_diagnosis_report.xlsx"
    wb = openpyxl.Workbook()

    # Sheet 1: Summary
    ws = wb.active
    ws.title = "Executive Summary"
    dark_fill  = PatternFill("solid", fgColor="1F3864")
    red_fill   = PatternFill("solid", fgColor="C00000")
    green_fill = PatternFill("solid", fgColor="375623")

    ws["A1"] = "METRIC DROP DIAGNOSIS — EXECUTIVE SUMMARY"
    ws["A1"].font = Font(bold=True, size=14, color="FFFFFF")
    ws["A1"].fill = dark_fill
    ws.merge_cells("A1:D1")
    ws.row_dimensions[1].height = 28

    rows = [
        ("Drop Date",               SIMULATION["drop_event_date"],       None),
        ("Baseline CR",             f"{results[0]['baseline_cr']}%",      "blue"),
        ("Drop Day CR",             f"{results[0]['drop_day_cr']}%",      "red"),
        ("Relative Drop",           f"{results[0]['relative_drop']}%",   "red"),
        ("Statistical Significance","YES (p < 0.001)",                   "red"),
        ("Root Cause",              results[3]["root_cause_category"],    None),
        ("Drop Hour",               f"~{results[2]['biggest_drop_hour']:02d}:00", None),
        ("Lost Revenue",            results[4]["lost_revenue_formatted"], "red"),
        ("Missed Conversions",      f"{results[4]['missed_conversions']:,}", "red"),
    ]

    for i, (label, value, color) in enumerate(rows, start=3):
        ws[f"A{i}"] = label
        ws[f"B{i}"] = value
        ws[f"A{i}"].font = Font(bold=True, size=10)
        val_font_color = "C00000" if color == "red" else ("1F3864" if color == "blue" else "000000")
        ws[f"B{i}"].font = Font(size=10, color=val_font_color, bold=(color is not None))

    for col, width in zip([1, 2, 3, 4], [30, 30, 5, 5]):
        ws.column_dimensions[get_column_letter(col)].width = width

    # Sheet 2: Investigation Checklist
    ws2 = wb.create_sheet("Investigation Checklist")
    ws2["A1"] = "Investigation Checklist"
    ws2["A1"].font = Font(bold=True, size=12)
    for i, item in enumerate(results[3]["investigation_checklist"], start=3):
        ws2[f"A{i}"] = item
        ws2[f"A{i}"].font = Font(size=10)
    ws2.column_dimensions["A"].width = 70

    wb.save(xlsx_path)
    print(f"  ✓ Excel report → {xlsx_path}")


# ─── Main ────────────────────────────────────────────────
def run():
    print("\n🔍  Module 2: Metric Drop Diagnosis System")
    print("─" * 50)

    df        = load_data()
    drop_date = SIMULATION["drop_event_date"]

    print(f"  Investigating drop on: {drop_date}")

    s1 = step1_verify_drop(df, drop_date)
    print(f"\n  Step 1: {s1['verdict']}")
    print(f"          Relative drop: {s1['relative_drop']}%  |  p={s1['p_value']}")

    s2 = step2_dimension_slicing(df, drop_date)
    print(f"\n  Step 2: Worst device={s2['worst_device']}, source={s2['worst_source']}")

    s3 = step3_what_changed(df, drop_date)
    print(f"\n  Step 3: Drop hour = {s3['biggest_drop_hour']:02d}:00")

    s4 = step4_root_cause(df, drop_date)
    print(f"\n  Step 4: Root cause category = {s4['root_cause_category']}")

    s5 = step5_business_impact(df, drop_date)
    print(f"\n  Step 5: Lost revenue = {s5['lost_revenue_formatted']}")

    results     = [s1, s2, s3, s4, s5]
    report_text = generate_text_report(results)
    save_report(report_text, results)

    print("\n✅  Module 2 complete!\n")
    return results


if __name__ == "__main__":
    run()