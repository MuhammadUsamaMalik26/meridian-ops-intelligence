-- Mart: acquisition funnel (legacy/secondary)
-- Step-by-step signup-to-activation funnel with conversion rates.

with funnel_steps as (
    select
        user_id,
        max(case when event_name = 'signup_started'       then 1 else 0 end) as did_signup_start,
        max(case when event_name = 'kyc_submitted'        then 1 else 0 end) as did_kyc_submit,
        max(case when event_name = 'kyc_approved'         then 1 else 0 end) as did_kyc_approve,
        max(case when event_name = 'onboarding_completed' then 1 else 0 end) as did_onboard,
        max(case when event_name = 'first_transaction'    then 1 else 0 end) as did_first_tx
    from {{ ref('stg_events') }}
    group by user_id
),

agg as (
    select
        sum(did_signup_start) as s1, sum(did_kyc_submit) as s2,
        sum(did_kyc_approve) as s3, sum(did_onboard) as s4, sum(did_first_tx) as s5
    from funnel_steps
)

select 'signup_started' as step, 1 as ord, s1 as users, 1.0 as pct from agg
union all
select 'kyc_submitted', 2, s2, round(s2 * 1.0 / nullif(s1, 0), 4) from agg
union all
select 'kyc_approved', 3, s3, round(s3 * 1.0 / nullif(s1, 0), 4) from agg
union all
select 'onboarding', 4, s4, round(s4 * 1.0 / nullif(s1, 0), 4) from agg
union all
select 'first_transaction', 5, s5, round(s5 * 1.0 / nullif(s1, 0), 4) from agg
