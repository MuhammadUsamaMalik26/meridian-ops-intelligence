# Meridian Ops Intelligence

**A simulated fintech operations analytics platform for a UK neobank — transaction
monitoring, fraud/AML detection, dispute resolution, and capacity planning.**

Built to demonstrate the kind of analytics stack used by Operations Analytics
teams at fintechs: SQL/Python data pipelines, dbt-based transformations,
rule-based + ML transaction monitoring, and stakeholder-facing dashboards.

---

## Business Context

Meridian sits inside a UK neobank's Operations function, covering:

- **Transaction monitoring** — rule-based AML checks + an ML fraud model
- **Disputes** — resolution time, SLA performance, outcome rates
- **Capacity planning** — case volume vs agent capacity by team
- **Case note automation** — proof-of-concept LLM-assisted case write-ups

This project evolved from an earlier growth-analytics build (acquisition funnel,
cohort retention, RFM segmentation, MRR) — that data and those views are retained
as a secondary "Legacy / Growth" section in the dashboard, since they share the
same underlying user/transaction dataset.

---

## Stack

| Layer | Tool |
|---|---|
| Warehouse | DuckDB (local; SQL maps to Snowflake/BigQuery patterns) |
| Transforms | dbt (staging → intermediate → marts) |
| ML | Python, scikit-learn (logistic regression vs random forest) |
| Dashboard | Streamlit + Plotly |
| Data generation | Python (faker), with engineered fraud/AML signal |

---

## Project Structure

```
meridian-ops-intelligence/
├── data/
│   ├── raw/                          # Synthetic CSVs
│   └── meridian.duckdb               # Local warehouse (generated)
├── meridian_dbt/
│   ├── models/
│   │   ├── staging/                  # Light cleanup of raw tables
│   │   ├── intermediate/             # Feature engineering (fraud features, alert enrichment)
│   │   └── marts/                    # Business-facing tables
│   ├── dbt_project.yml
│   └── profiles.yml
├── ml/
│   ├── fraud_model.py                # Champion/challenger fraud model
│   └── output/                       # Model artefacts (generated)
├── generate_data.py                  # Synthetic data generator
├── load_db.py                        # Raw CSV → DuckDB loader
├── app.py                            # Streamlit dashboard
└── requirements.txt
```

---

## Data Model

### Raw tables
| Table | Rows | Description |
|---|---|---|
| `dim_users` | 5,000 | User profile, plan, channel, KYC, churn |
| `fact_events` | ~34,000 | Behavioural events |
| `fact_transactions` | ~505,000 | Transactions with engineered fraud-risk features |
| `fact_subscriptions` | ~2,300 | Paid plan lifecycle |
| `dim_agents` | 24 | Ops agents across fraud_ops, disputes, kyc_review teams |
| `fact_disputes` | ~4,300 | Customer disputes, linked to flagged transactions |
| `fact_aml_alerts` | ~11,600 | Rule-based + ML-derived AML/fraud alerts |

### Fraud signal design
`is_flagged` (4.4% of transactions) is driven by engineered risk factors rather
than random assignment: amount relative to a user's baseline spend, high-risk
merchant categories (crypto exchange, gambling, money service business),
transaction velocity, new-account anomalies, high-risk geography, and
structuring patterns. This gives the ML model genuine, learnable signal.

### dbt layers
- **Staging** — 7 models, light cleanup + 19 data tests (uniqueness, not-null, accepted values)
- **Intermediate** — `int_transaction_fraud_features` (rule-trigger flags, amount-to-baseline
  ratio, risk encodings), `int_aml_alerts_enriched` (alerts joined with transaction + agent context)
- **Marts** — `mart_transaction_monitoring`, `mart_fraud_alerts`, `mart_disputes_sla`,
  `mart_capacity_planning`, plus legacy `mart_funnel_acquisition`, `mart_cohort_retention`,
  `mart_customer_segments`, `mart_mrr_monthly`

---

## Fraud Detection Model

Champion/challenger comparison on `int_transaction_fraud_features`:

| Model | AUC |
|---|---|
| **Random Forest (champion)** | **0.885** |
| Logistic Regression (challenger) | 0.863 |

**Feature selection note:** rule-trigger flags (`rule_velocity`, `rule_structuring`,
etc.) and `rules_triggered_count`/`any_rule_triggered` are deliberately excluded
from the model's features — they're derived from logic that overlaps with how
`is_flagged` itself is generated, which would cause target leakage. Only
observable, pre-decision features are used (amount, baseline ratio, velocity,
merchant/geography risk flags, transaction type).

**Top features:** `amount_to_baseline_ratio`, `amount_gbp`, `is_high_risk_merchant`,
`is_late_night`, and merchant-category dummies for crypto/gambling/MSB.

### Rules vs ML coverage
The 6 rule-based AML checks (velocity, structuring, high-risk geography, round
amount, large-amount-new-account, high-risk-merchant-anomaly) catch ~51.5% of
flagged transactions; the remaining ~48.5% are caught only by the ML model —
roughly even coverage, supporting running both in parallel rather than relying
on either alone.

---

## Key Findings (Sample Data)

| Metric | Value |
|---|---|
| Fraud flag rate | 4.37% |
| Highest-risk merchant categories | crypto_exchange (11.6%), money_service_business (10.9%), gambling (10.3%) |
| Dispute rate | 0.86% of transactions |
| Most-disputed reason | fraud_claim (highest volume + longest resolution time) |
| Fastest-resolving dispute reason | duplicate_charge (highest upheld rate — candidate for automation) |
| AML alerts | 11,602 (55% closed, 22% escalated, 15% open, 8% SAR filed) |

---

## Running Locally

```bash
git clone <repo-url>
cd meridian-ops-intelligence

pip install -r requirements.txt

python generate_data.py              # creates data/raw/*.csv
python load_db.py                    # loads raw data into DuckDB

cd meridian_dbt
DBT_PROFILES_DIR=. dbt run            # builds staging/intermediate/marts
DBT_PROFILES_DIR=. dbt test           # runs data tests
cd ..

python ml/fraud_model.py              # trains champion/challenger fraud model

streamlit run app.py                  # launches dashboard
```

The Streamlit app will auto-run the above setup steps on first launch if the
database, dbt models, or trained model aren't present. **First load takes
roughly 2 minutes** (data generation, dbt build, model training) — subsequent
loads are fast since the warehouse and model are cached on disk.

---

## Deploying

When deploying to Streamlit Community Cloud, the working directory and any
generated files (`data/`, `meridian_dbt/target/`, `ml/output/`) persist for the
lifetime of the app instance, so the ~2 minute cold-start cost is paid once per
deployment/restart, not per visitor.

---

## Dashboard Pages

1. **Ops Overview** — top-line KPIs, alert status/rule distribution
2. **Transaction Monitoring** — model performance (ROC, feature importance),
   rules-vs-ML coverage, merchant risk, alert queue
3. **Disputes** — SLA performance, resolution time and outcomes by reason
4. **Capacity Planning** — case volume vs agent capacity by team
5. **Case Note Generator** — proof-of-concept automation for draft case notes
6. *(Legacy / Growth)* Acquisition Funnel, Cohort Retention, Customer Segments, MRR

---

## About

Built by Muhammad Usama | MSc Financial Technology, University of Exeter (Distinction)
[LinkedIn](https://linkedin.com/in/muhammadusamamalik) ·
[Portfolio](https://github.com/MuhammadUsamaMalik26)
