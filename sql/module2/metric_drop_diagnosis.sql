-- sql/module2/metric_drop_diagnosis.sql
-- Module 2: Metric Drop Diagnosis — SQL queries for each investigation step

-- ── Step 1: Verify Drop — Baseline vs Drop Day ────────────
WITH baseline AS (
    SELECT
        'baseline_7d'               AS period,
        COUNT(*)                    AS sessions,
        SUM(converted)              AS conversions,
        ROUND(AVG(converted)*100,4) AS cr_pct
    FROM sessions
    WHERE DATE_TRUNC('day', timestamp) BETWEEN
          DATE '2024-04-03' AND DATE '2024-04-09'
),
drop_day AS (
    SELECT
        'drop_day'                  AS period,
        COUNT(*)                    AS sessions,
        SUM(converted)              AS conversions,
        ROUND(AVG(converted)*100,4) AS cr_pct
    FROM sessions
    WHERE DATE_TRUNC('day', timestamp) = DATE '2024-04-10'
)
SELECT * FROM baseline
UNION ALL
SELECT * FROM drop_day;


-- ── Step 2a: Slice by Device ──────────────────────────────
SELECT
    device,
    -- Baseline
    ROUND(AVG(CASE WHEN DATE_TRUNC('day',timestamp) BETWEEN DATE '2024-04-03' AND DATE '2024-04-09'
                   THEN converted END)*100, 4) AS baseline_cr_pct,
    -- Drop day
    ROUND(AVG(CASE WHEN DATE_TRUNC('day',timestamp) = DATE '2024-04-10'
                   THEN converted END)*100, 4) AS drop_day_cr_pct,
    -- Absolute change
    ROUND(
        AVG(CASE WHEN DATE_TRUNC('day',timestamp) = DATE '2024-04-10' THEN converted END)
      - AVG(CASE WHEN DATE_TRUNC('day',timestamp) BETWEEN DATE '2024-04-03' AND DATE '2024-04-09' THEN converted END),
    6) * 100                                    AS absolute_change_pp
FROM sessions
WHERE DATE_TRUNC('day', timestamp) BETWEEN DATE '2024-04-03' AND DATE '2024-04-10'
GROUP BY device
ORDER BY absolute_change_pp;


-- ── Step 2b: Slice by Location ────────────────────────────
SELECT
    location,
    ROUND(AVG(CASE WHEN DATE_TRUNC('day',timestamp) BETWEEN DATE '2024-04-03' AND DATE '2024-04-09'
                   THEN converted END)*100,4)   AS baseline_cr_pct,
    ROUND(AVG(CASE WHEN DATE_TRUNC('day',timestamp) = DATE '2024-04-10'
                   THEN converted END)*100,4)   AS drop_day_cr_pct
FROM sessions
WHERE DATE_TRUNC('day', timestamp) BETWEEN DATE '2024-04-03' AND DATE '2024-04-10'
GROUP BY location
ORDER BY drop_day_cr_pct ASC;


-- ── Step 2c: Slice by Category ────────────────────────────
SELECT
    product_category,
    ROUND(AVG(CASE WHEN DATE_TRUNC('day',timestamp) BETWEEN DATE '2024-04-03' AND DATE '2024-04-09'
                   THEN converted END)*100,4)   AS baseline_cr_pct,
    ROUND(AVG(CASE WHEN DATE_TRUNC('day',timestamp) = DATE '2024-04-10'
                   THEN converted END)*100,4)   AS drop_day_cr_pct,
    COUNT(CASE WHEN DATE_TRUNC('day',timestamp) = DATE '2024-04-10' THEN 1 END) AS drop_day_sessions
FROM sessions
WHERE DATE_TRUNC('day', timestamp) BETWEEN DATE '2024-04-03' AND DATE '2024-04-10'
GROUP BY product_category
ORDER BY drop_day_cr_pct ASC;


-- ── Step 3: Hourly Timeline on Drop Day ──────────────────
SELECT
    EXTRACT(HOUR FROM timestamp)::INT           AS hour,
    COUNT(*)                                    AS sessions,
    SUM(converted)                              AS conversions,
    ROUND(AVG(converted)*100, 4)               AS cr_pct,
    ROUND(AVG(page_load_ms), 1)                AS avg_load_ms
FROM sessions
WHERE DATE_TRUNC('day', timestamp) = DATE '2024-04-10'
GROUP BY EXTRACT(HOUR FROM timestamp)
ORDER BY hour;


-- ── Step 5: Business Impact Calculation ──────────────────
WITH baseline_rps AS (
    SELECT AVG(revenue) AS baseline_revenue_per_session
    FROM sessions
    WHERE DATE_TRUNC('day', timestamp) BETWEEN DATE '2024-04-03' AND DATE '2024-04-09'
),
drop_window AS (
    SELECT
        COUNT(*)        AS sessions,
        SUM(revenue)    AS actual_revenue,
        AVG(revenue)    AS actual_rps
    FROM sessions
    WHERE DATE_TRUNC('day', timestamp) BETWEEN DATE '2024-04-10' AND DATE '2024-04-12'
)
SELECT
    drop_window.sessions,
    ROUND(drop_window.actual_revenue, 2)        AS actual_revenue_inr,
    ROUND(baseline_rps.baseline_revenue_per_session * drop_window.sessions, 2) AS expected_revenue_inr,
    ROUND(
        (baseline_rps.baseline_revenue_per_session - drop_window.actual_rps)
        * drop_window.sessions, 2
    )                                           AS lost_revenue_inr
FROM drop_window CROSS JOIN baseline_rps;


-- ── Cohort Analysis: Day-1 Retention ─────────────────────
WITH first_session AS (
    SELECT
        user_id,
        MIN(DATE_TRUNC('day', timestamp)::DATE) AS first_date
    FROM sessions
    GROUP BY user_id
),
cohort_sessions AS (
    SELECT
        fs.user_id,
        fs.first_date,
        DATE_TRUNC('day', s.timestamp)::DATE    AS session_date,
        (DATE_TRUNC('day', s.timestamp)::DATE - fs.first_date) AS days_since_first
    FROM sessions s
    JOIN first_session fs ON s.user_id = fs.user_id
)
SELECT
    first_date                                  AS cohort_date,
    COUNT(DISTINCT user_id)                     AS cohort_size,
    COUNT(DISTINCT CASE WHEN days_since_first > 0 THEN user_id END)  AS returned_users,
    ROUND(
        COUNT(DISTINCT CASE WHEN days_since_first > 0 THEN user_id END) * 100.0
        / COUNT(DISTINCT user_id), 2
    )                                           AS retention_rate_pct
FROM cohort_sessions
GROUP BY first_date
HAVING COUNT(DISTINCT user_id) >= 50
ORDER BY cohort_date
LIMIT 30;