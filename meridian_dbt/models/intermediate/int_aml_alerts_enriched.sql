-- Intermediate: AML/fraud alerts enriched
-- One row per alert, joined with transaction features and reviewing agent info.

with alerts as (
    select * from {{ ref('stg_aml_alerts') }}
),

tx_features as (
    select * from {{ ref('int_transaction_fraud_features') }}
),

agents as (
    select * from {{ ref('stg_agents') }}
)

select
    a.alert_id,
    a.transaction_id,
    a.user_id,
    a.rule_triggered,
    a.alert_score,
    a.status,
    a.reviewed_by,
    a.review_time_hours,
    a.alert_ts,

    -- Transaction context
    tf.amount_gbp,
    tf.merchant_category,
    tf.geography,
    tf.transaction_type,
    tf.is_flagged as transaction_is_flagged,
    tf.amount_to_baseline_ratio,
    tf.rules_triggered_count,

    -- Reviewing agent context
    ag.team as reviewer_team,
    ag.shift as reviewer_shift

from alerts a
left join tx_features tf on a.transaction_id = tf.transaction_id
left join agents ag on a.reviewed_by = ag.agent_id
