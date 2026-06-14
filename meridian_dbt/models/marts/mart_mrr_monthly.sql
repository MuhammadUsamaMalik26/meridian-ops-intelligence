-- Mart: MRR monthly (legacy/secondary)
-- New MRR, churned MRR, and net change by month.

with new_mrr as (
    select date_trunc('month', cast(subscription_start as date)) as month,
           sum(monthly_price_gbp) as new_mrr, count(*) as new_subs
    from {{ ref('stg_subscriptions') }}
    group by 1
),

churned_mrr as (
    select date_trunc('month', cast(subscription_end as date)) as month,
           sum(monthly_price_gbp) as churned_mrr, count(*) as churned_subs
    from {{ ref('stg_subscriptions') }}
    where subscription_end is not null
    group by 1
)

select
    coalesce(n.month, c.month) as month,
    coalesce(n.new_mrr, 0) as new_mrr,
    coalesce(n.new_subs, 0) as new_subscribers,
    coalesce(c.churned_mrr, 0) as churned_mrr,
    coalesce(c.churned_subs, 0) as churned_subscribers,
    coalesce(n.new_mrr, 0) - coalesce(c.churned_mrr, 0) as net_mrr_change
from new_mrr n
full outer join churned_mrr c on n.month = c.month
order by month
