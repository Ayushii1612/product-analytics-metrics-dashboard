# Product-Analytics-Metrics-Dashboard
This project replicates the day-to-day work of a product analyst at an e-commerce company. It starts by simulating 2 million user sessions using Python Faker across a 6-month period, with real-world events deliberately injected — a 15% conversion rate drop caused by a tracking bug, a new checkout feature launch with measurable uplift, and a seasonal traffic spike during Holi festival. The dataset includes fields like device, location, traffic source, product category, funnel steps, revenue, and page load time. From this foundation, four analytical modules are built: a North Star metrics framework with a two-level driver tree, a structured 5-step metric drop diagnosis system covering statistical verification, dimension slicing, timeline analysis, root cause isolation, and INR business impact calculation, a feature launch impact analysis using two-proportion z-tests with 95% confidence intervals and guardrail metric checks, and a daily anomaly detection system using Z-score with 7-day rolling averages.

The project goes beyond analysis and covers the full data stack. All SQL logic is written in DuckDB using window functions, CTEs, cohort queries, and funnel analysis — mirroring real analyst workflows. Machine learning is applied through K-Means clustering to segment 973K users into 4 business-friendly personas including High-Value Loyal Buyers and One-Time Browsers. Every module exports formatted Excel reports and structured text diagnosis reports ready for stakeholder sharing. The entire pipeline is tied together in a 5-page interactive Power BI dashboard showing the CR trend line, anomaly alert table, pre vs post feature launch comparison, and user segment charts. The project is fully modular and runs end-to-end with a single command, making it a strong portfolio piece for product analyst and data analyst roles.

# Features
* Simulates 2 million e-commerce sessions with injected metric drop, feature launch, and seasonal events
* 5-step metric drop diagnosis with statistical significance testing and INR business impact
* Feature launch analysis with z-test, 95% confidence intervals, and guardrail metric validation
* Z-score anomaly detection with 7-day rolling average baseline
* K-Means user segmentation producing 4 business-friendly personas
* SQL queries using window functions, CTEs, cohort analysis, and funnel queries
* Automated Excel reports with conditional formatting for each module
* 5-page interactive Power BI dashboard with trend lines, anomaly table, launch tracker, and segment charts
* Fully modular pipeline — run all modules or individual ones via command line

# Tech Stack
* Python — Pandas, NumPy, SciPy, StatsModels, Scikit-learn, Faker
* SQL — DuckDB with window functions and CTEs
* Machine Learning — K-Means clustering, Silhouette scoring
* Statistics — Z-test, Welch t-test, confidence intervals, Z-score anomaly detection
* Power BI — 5-page interactive dashboard
* Excel — openpyxl formatted reports
* Environment — python-dotenv, pyarrow, DuckDB

# Project Structure
```
product-analytics-metrics-dashboard/
├── config/settings.py
├── python/
│   ├── simulation/generate_dataset.py
│   ├── analysis/module1_north_star.py
│   ├── analysis/module2_metric_drop.py
│   ├── analysis/module3_feature_launch.py
│   ├── analysis/module4_anomaly_detection.py
│   └── ml/user_segmentation.py
├── sql/
│   ├── module1/north_star_metrics.sql
│   ├── module2/metric_drop_diagnosis.sql
│   ├── module3/feature_launch_analysis.sql
│   └── module4/anomaly_detection.sql
├── dashboard/powerbi-setup.md
├── reports/
├── data/
├── run_pipeline.py
├── requirements.txt
└── README.md
```
