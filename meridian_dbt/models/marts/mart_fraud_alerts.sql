-- Mart: fraud/AML alerts
-- Alert-level table for the Transaction Monitoring dashboard's alert queue
-- view, plus summary stats by rule and status.

with alerts as (
    select * from {{ ref('int_aml_alerts_enriched') }}
)

select
    alert_id,
    transaction_id,
    user_id,
    rule_triggered,
    alert_score,
    status,
    reviewed_by,
    reviewer_team,
    reviewer_shift,
    review_time_hours,
    alert_ts,
    amount_gbp,
    merchant_category,
    geography,
    transaction_type,
    transaction_is_flagged,
    amount_to_baseline_ratio,
    rules_triggered_count,

    -- SLA flag: alerts open or escalated for review_time > 24h considered breach
    -- (review_time_hours is null for open alerts, so treat those separately)
    case
        when status = 'open' then 'pending_review'
        when review_time_hours > 24 then 'sla_breach'
        else 'within_sla'
    end as sla_status

from alerts
