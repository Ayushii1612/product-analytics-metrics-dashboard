-- sql/module1/north_star_metrics.sql
-- Module 1: North Star Metrics Framework
-- Run against DuckDB after loading sessions.parquet
-- Usage: duckdb data/processed/analytics.duckdb < sql/module1/north_star_metrics.sql

-- ── 0. Load the dataset ──────────────────────────────────
CREATE OR REPLACE TABLE sessions AS
SELECT * FROM parquet_scan('data/raw/sessions.parquet');

-- ── 1. North Star: Overall Conversion Rate ────────────────
SELECT
    'North Star Metric'                         AS metric_name,
    COUNT(*)                                    AS total_sessions,
    SUM(converted)                              AS total_conversions,
    ROUND(AVG(converted) * 100, 3)              AS conversion_rate_pct,
    ROUND(SUM(revenue), 2)                      AS total_revenue_inr,
    ROUND(AVG(revenue), 2)                      AS revenue_per_session_inr
FROM sessions;


-- ── 2. Daily Conversion Rate (for trend line) ────────────
SELECT
    DATE_TRUNC('day', timestamp)::DATE          AS date,
    COUNT(*)                                    AS sessions,
    SUM(converted)                              AS conversions,
    ROUND(AVG(converted) * 100, 4)             AS cr_pct,
    ROUND(SUM(revenue), 2)                      AS daily_revenue,
    -- 7-day rolling average using window function
    ROUND(AVG(AVG(converted)) OVER (
        ORDER BY DATE_TRUNC('day', timestamp)
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) * 100, 4)                                 AS cr_7d_rolling_avg_pct
FROM sessions
GROUP BY DATE_TRUNC('day', timestamp)
ORDER BY date;


-- ── 3. Level 1 Driver: Page Experience ───────────────────
SELECT
    'Page Experience'                           AS driver,
    ROUND(AVG(page_load_ms), 1)                AS avg_page_load_ms,
    ROUND(AVG(bounced) * 100, 3)               AS bounce_rate_pct,
    ROUND(AVG(CASE WHEN device='mobile'  THEN converted END) * 100, 4) AS mobile_cr_pct,
    ROUND(AVG(CASE WHEN device='desktop' THEN converted END) * 100, 4) AS desktop_cr_pct,
    ROUND(
        (AVG(CASE WHEN device='desktop' THEN converted END)
        - AVG(CASE WHEN device='mobile'  THEN converted END)) * 100,
    4)                                          AS mobile_gap_pp
FROM sessions;


-- ── 4. Level 1 Driver: Discovery (Traffic Mix) ────────────
SELECT
    traffic_source,
    COUNT(*)                                    AS sessions,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS traffic_share_pct,
    ROUND(AVG(converted) * 100, 4)             AS cr_pct,
    ROUND(SUM(revenue), 2)                      AS revenue
FROM sessions
GROUP BY traffic_source
ORDER BY sessions DESC;


-- ── 5. Level 1 Driver: Product Quality (Category CR) ──────
SELECT
    product_category,
    COUNT(*)                                    AS sessions,
    SUM(converted)                              AS conversions,
    ROUND(AVG(converted) * 100, 4)             AS cr_pct,
    ROUND(AVG(CASE WHEN converted=1 THEN revenue END), 2) AS avg_order_value_inr
FROM sessions
GROUP BY product_category
ORDER BY cr_pct DESC;


-- ── 6. Funnel Analysis: Steps Completion ──────────────────
WITH funnel AS (
    SELECT
        steps_completed,
        COUNT(*) AS users_at_step,
        SUM(converted) AS converters
    FROM sessions
    GROUP BY steps_completed
)
SELECT
    steps_completed,
    users_at_step,
    ROUND(users_at_step * 100.0 / SUM(users_at_step) OVER(), 2) AS pct_of_sessions,
    -- Step-over-step drop-off
    ROUND(
        (users_at_step - LAG(users_at_step) OVER (ORDER BY steps_completed))
        * 100.0
        / LAG(users_at_step) OVER (ORDER BY steps_completed),
    2)                                          AS pct_change_vs_prev_step
FROM funnel
ORDER BY steps_completed;