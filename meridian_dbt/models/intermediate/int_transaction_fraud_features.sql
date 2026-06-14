-- Intermediate: transaction fraud features
-- One row per transaction, enriched with derived risk features and rule-trigger
-- flags. Feeds both mart_transaction_monitoring (dashboarding) and the fraud
-- ML model training table.

with tx as (
    select * from {{ ref('stg_transactions') }}
),

enriched as (
    select
        tx.*,

        -- Amount-to-baseline ratio: how anomalous is this amount for this user
        round(tx.amount_gbp / nullif(tx.user_baseline_amount, 0), 2) as amount_to_baseline_ratio,

        -- High-risk merchant category flag
        case
            when tx.merchant_category in ('crypto_exchange', 'gambling', 'money_service_business')
            then 1 else 0
        end as is_high_risk_merchant,

        -- High-risk geography flag
        case
            when tx.geography in ('UAE', 'Nigeria', 'Cyprus')
            then 1 else 0
        end as is_high_risk_geography,

        -- Rule trigger flags, mirroring the rule-based AML engine
        case when tx.velocity_count_1h >= 4 then 1 else 0 end as rule_velocity,
        case when tx.amount_gbp >= 900 and tx.amount_gbp < 1000 then 1 else 0 end as rule_structuring,
        case when tx.geography in ('UAE', 'Nigeria', 'Cyprus') then 1 else 0 end as rule_high_risk_geography,
        case when tx.is_round_amount = 1 and tx.amount_gbp >= 100 then 1 else 0 end as rule_round_amount,
        case
            when tx.is_new_account_tx = 1
                and tx.amount_gbp > tx.user_baseline_amount * 8
            then 1 else 0
        end as rule_large_amount_new_account,

        -- High-risk merchant + large amount relative to baseline (covers the
        -- crypto/gambling/MSB anomaly signal that drives much of is_flagged)
        case
            when tx.merchant_category in ('crypto_exchange', 'gambling', 'money_service_business')
                and tx.amount_gbp > tx.user_baseline_amount * 6
            then 1 else 0
        end as rule_high_risk_merchant_anomaly

    from tx
),

rule_summary as (
    select
        *,
        rule_velocity + rule_structuring + rule_high_risk_geography
            + rule_round_amount + rule_large_amount_new_account
            + rule_high_risk_merchant_anomaly as rules_triggered_count,
        case
            when (rule_velocity + rule_structuring + rule_high_risk_geography
                  + rule_round_amount + rule_large_amount_new_account
                  + rule_high_risk_merchant_anomaly) > 0
            then 1 else 0
        end as any_rule_triggered
    from enriched
)

select * from rule_summary
