-- sql/module3/feature_launch_analysis.sql
-- Module 3: Pre/Post Feature Launch SQL Analysis

-- ── Pre vs Post Conversion Rate ──────────────────────────
SELECT
    CASE
        WHEN DATE_TRUNC('day',timestamp) < DATE '2024-05-01' THEN 'pre_launch'
        ELSE 'post_launch'
    END                                         AS period,
    COUNT(*)                                    AS sessions,
    SUM(converted)                              AS conversions,
    ROUND(AVG(converted)*100, 4)               AS cr_pct,
    ROUND(AVG(revenue), 2)                      AS revenue_per_session_inr,
    ROUND(AVG(page_load_ms), 1)                AS avg_load_ms,
    ROUND(AVG(bounced)*100, 3)                 AS bounce_rate_pct
FROM sessions
WHERE DATE_TRUNC('day',timestamp) BETWEEN DATE '2024-04-01' AND DATE '2024-05-31'
  -- Exclude the drop event window
  AND DATE_TRUNC('day',timestamp) NOT BETWEEN DATE '2024-04-10' AND DATE '2024-04-12'
GROUP BY 1
ORDER BY 1 DESC;


-- ── Weekly Trend Around Launch ────────────────────────────
SELECT
    DATE_TRUNC('week', timestamp)::DATE         AS week_start,
    COUNT(*)                                    AS sessions,
    ROUND(AVG(converted)*100, 4)               AS cr_pct,
    ROUND(AVG(revenue), 2)                      AS rps_inr,
    ROUND(AVG(page_load_ms), 1)                AS avg_load_ms,
    CASE
        WHEN DATE_TRUNC('week',timestamp) < DATE '2024-04-28' THEN 'pre_launch'
        ELSE 'post_launch'
    END                                         AS period
FROM sessions
WHERE DATE_TRUNC('day',timestamp) BETWEEN DATE '2024-04-01' AND DATE '2024-05-31'
  AND DATE_TRUNC('day',timestamp) NOT BETWEEN DATE '2024-04-10' AND DATE '2024-04-12'
GROUP BY DATE_TRUNC('week', timestamp)
ORDER BY week_start;


-- ── Device-Level Impact ───────────────────────────────────
SELECT
    device,
    ROUND(AVG(CASE WHEN DATE_TRUNC('day',timestamp) < DATE '2024-05-01' THEN converted END)*100,4) AS pre_cr_pct,
    ROUND(AVG(CASE WHEN DATE_TRUNC('day',timestamp) >= DATE '2024-05-01' THEN converted END)*100,4) AS post_cr_pct,
    ROUND(
        (AVG(CASE WHEN DATE_TRUNC('day',timestamp) >= DATE '2024-05-01' THEN converted END)
       - AVG(CASE WHEN DATE_TRUNC('day',timestamp) < DATE '2024-05-01' THEN converted END))
        * 100, 4
    )                                           AS lift_pp
FROM sessions
WHERE DATE_TRUNC('day',timestamp) BETWEEN DATE '2024-04-01' AND DATE '2024-05-31'
  AND DATE_TRUNC('day',timestamp) NOT BETWEEN DATE '2024-04-10' AND DATE '2024-04-12'
GROUP BY device
ORDER BY device;