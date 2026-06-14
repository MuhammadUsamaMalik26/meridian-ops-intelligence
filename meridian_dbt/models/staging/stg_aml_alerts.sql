-- Staging: AML/fraud alerts
-- Light cleanup of raw rule-based + ML-derived alert records.

select
    alert_id,
    transaction_id,
    user_id,
    rule_triggered,
    alert_score,
    status,
    reviewed_by,
    review_time_hours,
    alert_ts
from raw.fact_aml_alerts
