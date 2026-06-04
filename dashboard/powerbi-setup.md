// ── North Star: Conversion Rate ─────────────────────
Conversion Rate =
DIVIDE(
    SUMX(Sessions, Sessions[converted]),
    COUNTROWS(Sessions),
    0
)

// ── 7-Day Rolling Average CR ────────────────────────
CR 7D Rolling Avg =
CALCULATE(
    [Conversion Rate],
    DATESINPERIOD(DailyKPIs[date], LASTDATE(DailyKPIs[date]), -7, DAY)
)

// ── CR vs Baseline (alert color) ───────────────────
CR vs Baseline =
VAR CurrentCR = [Conversion Rate]
VAR BaselineCR = CALCULATE([Conversion Rate], ALL(DailyKPIs))
RETURN DIVIDE(CurrentCR - BaselineCR, BaselineCR, 0)

// ── Revenue Per Session ─────────────────────────────
Revenue Per Session =
DIVIDE(
    SUM(Sessions[revenue]),
    COUNTROWS(Sessions),
    0
)

// ── Anomaly Flag ────────────────────────────────────
Has Anomaly =
IF(
    COUNTROWS(FILTER(AnomalyEvents, AnomalyEvents[date] = MAX(DailyKPIs[date]))) > 0,
    "🚨 ANOMALY",
    "✅ Normal"
)

// ── Feature Launch Lift ─────────────────────────────
Launch Lift % =
VAR PostCR = CALCULATE([Conversion Rate], FeatureLaunch[period] = "post_launch")
VAR PreCR  = CALCULATE([Conversion Rate], FeatureLaunch[period] = "pre_launch")
RETURN DIVIDE(PostCR - PreCR, PreCR, 0)