-- Mart: transaction monitoring summary
-- Rule-by-rule hit rates, overlap with the ML-derived is_flagged signal, and
-- merchant/geography risk breakdowns. Primary table for the Transaction
-- Monitoring dashboard page.

with tx_features as (
    select * from {{ ref('int_transaction_fraud_features') }}
),

by_merchant as (
    select
        merchant_category,
        count(*) as total_transactions,
        sum(is_flagged) as flagged_transactions,
        round(sum(is_flagged) * 1.0 / count(*), 4) as flag_rate,
        round(avg(amount_gbp), 2) as avg_amount_gbp
    from tx_features
    group by merchant_category
),

rule_performance as (
    select
        'velocity' as rule_name, sum(rule_velocity) as transactions_triggered,
        sum(case when rule_velocity = 1 and is_flagged = 1 then 1 else 0 end) as true_positives
    from tx_features
    union all
    select
        'structuring', sum(rule_structuring),
        sum(case when rule_structuring = 1 and is_flagged = 1 then 1 else 0 end)
    from tx_features
    union all
    select
        'high_risk_geography', sum(rule_high_risk_geography),
        sum(case when rule_high_risk_geography = 1 and is_flagged = 1 then 1 else 0 end)
    from tx_features
    union all
    select
        'round_amount', sum(rule_round_amount),
        sum(case when rule_round_amount = 1 and is_flagged = 1 then 1 else 0 end)
    from tx_features
    union all
    select
        'large_amount_new_account', sum(rule_large_amount_new_account),
        sum(case when rule_large_amount_new_account = 1 and is_flagged = 1 then 1 else 0 end)
    from tx_features
    union all
    select
        'high_risk_merchant_anomaly', sum(rule_high_risk_merchant_anomaly),
        sum(case when rule_high_risk_merchant_anomaly = 1 and is_flagged = 1 then 1 else 0 end)
    from tx_features
),

overall_summary as (
    select
        count(*) as total_transactions,
        sum(is_flagged) as total_flagged,
        round(sum(is_flagged) * 1.0 / count(*), 4) as overall_flag_rate,
        sum(any_rule_triggered) as transactions_with_any_rule,
        sum(case when any_rule_triggered = 1 and is_flagged = 1 then 1 else 0 end) as rules_caught_flagged,
        sum(case when any_rule_triggered = 0 and is_flagged = 1 then 1 else 0 end) as ml_only_caught_flagged
    from tx_features
)

select
    'merchant_breakdown' as report_section,
    merchant_category as dimension,
    total_transactions as metric_1,
    flagged_transactions as metric_2,
    flag_rate as metric_3,
    avg_amount_gbp as metric_4,
    null as metric_5,
    null as metric_6
from by_merchant

union all

select
    'rule_performance' as report_section,
    rule_name as dimension,
    transactions_triggered as metric_1,
    true_positives as metric_2,
    round(true_positives * 1.0 / nullif(transactions_triggered, 0), 4) as metric_3,
    null as metric_4,
    null as metric_5,
    null as metric_6
from rule_performance

union all

select
    'overall' as report_section,
    'all_transactions' as dimension,
    total_transactions as metric_1,
    total_flagged as metric_2,
    overall_flag_rate as metric_3,
    transactions_with_any_rule as metric_4,
    rules_caught_flagged as metric_5,
    ml_only_caught_flagged as metric_6
from overall_summary

-- Column legend by report_section:
--   merchant_breakdown: metric_1=total_transactions, metric_2=flagged_transactions,
--                        metric_3=flag_rate, metric_4=avg_amount_gbp
--   rule_performance:   metric_1=transactions_triggered, metric_2=true_positives,
--                        metric_3=precision
--   overall:            metric_1=total_transactions, metric_2=total_flagged,
--                        metric_3=overall_flag_rate, metric_4=transactions_with_any_rule,
--                        metric_5=rules_caught_flagged, metric_6=ml_only_caught_flagged
