-- sql/module4/anomaly_detection.sql
-- Module 4: Z-Score Anomaly Detection in SQL using Window Functions

-- ── Daily KPIs with Rolling Mean and Std ─────────────────
WITH daily_kpis AS (
    SELECT
        DATE_TRUNC('day', timestamp)::DATE      AS date,
        COUNT(*)                                AS sessions,
        ROUND(AVG(converted)*100, 6)           AS cr_pct,
        ROUND(AVG(revenue), 2)                  AS rps_inr,
        ROUND(AVG(page_load_ms), 1)            AS avg_load_ms
    FROM sessions
    GROUP BY DATE_TRUNC('day', timestamp)
),
rolling_stats AS (
    SELECT
        date,
        sessions,
        cr_pct,
        rps_inr,
        avg_load_ms,
        -- 7-day rolling mean
        AVG(cr_pct)  OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS cr_rolling_mean,
        AVG(rps_inr) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS rps_rolling_mean,
        -- 7-day rolling std
        STDDEV(cr_pct)  OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS cr_rolling_std,
        STDDEV(rps_inr) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS rps_rolling_std
    FROM daily_kpis
),
z_scored AS (
    SELECT
        *,
        ROUND((cr_pct  - cr_rolling_mean)  / NULLIF(cr_rolling_std,  0), 3) AS cr_zscore,
        ROUND((rps_inr - rps_rolling_mean) / NULLIF(rps_rolling_std, 0), 3) AS rps_zscore
    FROM rolling_stats
)
SELECT
    date,
    sessions,
    cr_pct,
    cr_rolling_mean,
    cr_zscore,
    rps_inr,
    rps_zscore,
    CASE
        WHEN ABS(cr_zscore)  > 2.0 THEN '🚨 CR ANOMALY'
        WHEN ABS(rps_zscore) > 2.0 THEN '🚨 RPS ANOMALY'
        ELSE '✅ Normal'
    END                                         AS alert_status
FROM z_scored
ORDER BY date;


-- ── Anomaly Events Only ───────────────────────────────────
WITH daily_kpis AS (
    SELECT DATE_TRUNC('day',timestamp)::DATE AS date,
           COUNT(*) AS sessions,
           ROUND(AVG(converted)*100,6) AS cr_pct,
           ROUND(AVG(revenue),2) AS rps_inr
    FROM sessions GROUP BY 1
),
z_scored AS (
    SELECT date, sessions, cr_pct, rps_inr,
        ROUND((cr_pct - AVG(cr_pct) OVER(ORDER BY date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING))
            / NULLIF(STDDEV(cr_pct) OVER(ORDER BY date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING), 0), 3) AS cr_z
    FROM daily_kpis
)
SELECT date, sessions, cr_pct, cr_z,
       CASE WHEN cr_z < -2.0 THEN 'DROP' WHEN cr_z > 2.0 THEN 'SPIKE' END AS anomaly_type
FROM z_scored
WHERE ABS(cr_z) > 2.0
ORDER BY date;


-- ── Feature Launch Impact Tracker ─────────────────────────
SELECT
    DATE_TRUNC('day', timestamp)::DATE          AS date,
    ROUND(AVG(converted)*100, 4)               AS daily_cr_pct,
    AVG(AVG(converted)) OVER (
        ORDER BY DATE_TRUNC('day', timestamp)
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) * 100                                     AS cr_7d_ma_pct,
    CASE
        WHEN DATE_TRUNC('day', timestamp) >= DATE '2024-05-01' THEN 1 ELSE 0
    END                                         AS post_launch
FROM sessions
WHERE DATE_TRUNC('day', timestamp) BETWEEN DATE '2024-04-10' AND DATE '2024-05-31'
GROUP BY DATE_TRUNC('day', timestamp)
ORDER BY date;