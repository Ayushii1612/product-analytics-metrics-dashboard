"""
python/ml/user_segmentation.py

Machine Learning: K-Means User Segmentation
  • Aggregate user-level features from session data
  • Run K-Means (k=4) to identify user personas
  • Name and characterise each segment
  • Export segment assignments for dashboard
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings("ignore")


# ─── Load + Aggregate User-Level Features ────────────────
def build_user_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates session-level data into one row per user with features:
      - total_sessions, conversion_rate, total_revenue, avg_steps
      - preferred_device, preferred_category, avg_page_load
    """
    user = df.groupby("user_id").agg(
        total_sessions      = ("session_id", "count"),
        total_conversions   = ("converted", "sum"),
        total_revenue       = ("revenue", "sum"),
        avg_steps           = ("steps_completed", "mean"),
        avg_page_load_ms    = ("page_load_ms", "mean"),
        days_active         = ("date", "nunique"),
    ).reset_index()

    user["conversion_rate"]    = user["total_conversions"] / user["total_sessions"]
    user["revenue_per_session"] = user["total_revenue"] / user["total_sessions"]

    # Most common device per user
    user_device = (
        df.groupby(["user_id", "device"])
          .size()
          .reset_index(name="cnt")
          .sort_values("cnt", ascending=False)
          .drop_duplicates("user_id")[["user_id", "device"]]
          .rename(columns={"device": "primary_device"})
    )
    user = user.merge(user_device, on="user_id", how="left")

    # One-hot encode device for clustering
    user = pd.get_dummies(user, columns=["primary_device"], prefix="device")
    for col in ["device_mobile", "device_desktop", "device_tablet"]:
        if col not in user.columns:
            user[col] = 0

    return user


# ─── Determine Optimal K ──────────────────────────────────
def find_optimal_k(X_scaled: np.ndarray, k_range: range = range(2, 8)) -> int:
    """
    Uses silhouette score to choose the best k. Returns recommended k.
    """
    scores = {}
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        scores[k] = silhouette_score(X_scaled, labels)
    best_k = max(scores, key=scores.get)
    print(f"  Silhouette scores: {scores}")
    print(f"  Recommended k = {best_k} (score={scores[best_k]:.4f})")
    return best_k


# ─── Run K-Means ──────────────────────────────────────────
def run_kmeans(user: pd.DataFrame, k: int = 4) -> tuple[pd.DataFrame, KMeans]:
    features = [
        "total_sessions", "conversion_rate", "revenue_per_session",
        "avg_steps", "days_active",
        "device_mobile", "device_desktop",
    ]
    X = user[features].fillna(0)

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    user["segment_id"] = km.fit_predict(X_scaled)

    # Silhouette for chosen k
    sil = silhouette_score(X_scaled, user["segment_id"])
    print(f"  Silhouette score (k={k}): {sil:.4f}")

    return user, km


# ─── Name Segments ────────────────────────────────────────
def name_segments(user: pd.DataFrame) -> pd.DataFrame:
    """
    Automatically assigns a business-friendly name to each cluster
    based on its centroid characteristics.
    """
    profile = (
        user.groupby("segment_id")
            .agg(
                count            = ("user_id", "count"),
                avg_sessions     = ("total_sessions", "mean"),
                avg_cr           = ("conversion_rate", "mean"),
                avg_revenue      = ("revenue_per_session", "mean"),
                avg_days_active  = ("days_active", "mean"),
            )
    )

    segment_names = {}
    for seg_id, row in profile.iterrows():
        if row["avg_cr"] > 0.06 and row["avg_revenue"] > 60:
            name = "High-Value Loyal Buyers"
        elif row["avg_cr"] > 0.03 and row["avg_sessions"] > 3:
            name = "Engaged Regular Shoppers"
        elif row["avg_cr"] < 0.01 and row["avg_sessions"] < 2:
            name = "One-Time Browsers"
        else:
            name = "Window Shoppers (Retargetable)"
        segment_names[seg_id] = name

    user["segment_name"] = user["segment_id"].map(segment_names)
    profile["segment_name"] = profile.index.map(segment_names)

    return user, profile


# ─── Export ───────────────────────────────────────────────
def export_segments(user: pd.DataFrame, profile: pd.DataFrame) -> None:
    out_dir = Path(__file__).parent.parent.parent / "data" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)

    user[["user_id", "segment_id", "segment_name",
          "total_sessions", "conversion_rate", "revenue_per_session",
          "days_active"]].to_csv(out_dir / "user_segments.csv", index=False)
    print(f"  ✓ User segments → {out_dir / 'user_segments.csv'}")

    profile.to_csv(out_dir / "segment_profiles.csv")
    print(f"  ✓ Segment profiles → {out_dir / 'segment_profiles.csv'}")

    # Print profile
    print("\n  Segment Profiles:")
    print(profile[["segment_name", "count", "avg_cr", "avg_revenue", "avg_sessions"]].to_string())


# ─── Main ────────────────────────────────────────────────
def run():
    print("\n🤖  ML Module: K-Means User Segmentation")
    print("─" * 50)

    path = Path(__file__).parent.parent.parent / "data" / "raw" / "sessions.parquet"
    df   = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])

    print(f"  Sessions loaded: {len(df):,}")
    print("  Building user features...")

    user = build_user_features(df)
    print(f"  Unique users: {len(user):,}")

    user = user.sample(n=min(100_000, len(user)), random_state=42).reset_index(drop=True)

    user, km = run_kmeans(user, k=4)
    user, profile = name_segments(user)
    export_segments(user, profile)

    print("\n✅  Segmentation complete!\n")
    return user, profile


if __name__ == "__main__":
    run()