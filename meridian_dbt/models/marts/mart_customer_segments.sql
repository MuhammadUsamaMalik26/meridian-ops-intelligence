-- Mart: customer segments (legacy/secondary)
-- RFM segmentation: Recency, Frequency, Monetary (90-day window).

with rfm as (
    select
        t.user_id,
        max(cast(t.transaction_date as date)) as last_tx_date,
        datediff('day', max(cast(t.transaction_date as date)), current_date) as recency_days,
        count(case when cast(t.transaction_date as date) >= current_date - 90 then 1 end) as frequency_90d,
        sum(case when cast(t.transaction_date as date) >= current_date - 90 then t.amount_gbp end) as monetary_90d
    from {{ ref('stg_transactions') }} t
    where t.status = 'completed'
    group by t.user_id
),

scored as (
    select
        r.*, u.plan, u.acquisition_channel, u.region, u.age_band,
        ntile(5) over (order by recency_days desc) as r_score,
        ntile(5) over (order by frequency_90d)     as f_score,
        ntile(5) over (order by monetary_90d)      as m_score
    from rfm r
    join {{ ref('stg_users') }} u on r.user_id = u.user_id
)

select
    *,
    round((r_score + f_score + m_score) / 3.0, 2) as rfm_avg,
    case
        when r_score >= 4 and f_score >= 4 and m_score >= 4 then 'Champion'
        when r_score >= 3 and f_score >= 3                   then 'Loyal'
        when r_score >= 3 and f_score < 3                     then 'Promising'
        when r_score < 3  and f_score >= 3                    then 'At Risk'
        when r_score < 2  and f_score < 2                     then 'Lost'
        else 'Needs Attention'
    end as segment
from scored
order by rfm_avg desc
