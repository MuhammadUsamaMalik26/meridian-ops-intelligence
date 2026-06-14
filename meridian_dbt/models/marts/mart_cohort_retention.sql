-- Mart: cohort retention (legacy/secondary)
-- Monthly cohorts x 12-month retention grid.

with user_cohorts as (
    select user_id, date_trunc('month', cast(signup_date as date)) as cohort_month
    from {{ ref('stg_users') }}
    where kyc_passed = 1
),

user_activity as (
    select user_id, date_trunc('month', cast(transaction_date as date)) as activity_month
    from {{ ref('stg_transactions') }}
    where status = 'completed'
    group by user_id, date_trunc('month', cast(transaction_date as date))
),

cohort_activity as (
    select
        c.cohort_month,
        datediff('month', c.cohort_month, a.activity_month) as months_since_signup,
        count(distinct a.user_id) as active_users
    from user_cohorts c
    join user_activity a on c.user_id = a.user_id
    group by c.cohort_month, months_since_signup
),

sizes as (
    select cohort_month, count(*) as cohort_size from user_cohorts group by cohort_month
)

select
    ca.cohort_month, s.cohort_size, ca.months_since_signup, ca.active_users,
    round(ca.active_users * 1.0 / nullif(s.cohort_size, 0), 4) as retention_rate
from cohort_activity ca
join sizes s on ca.cohort_month = s.cohort_month
where ca.months_since_signup between 0 and 11
order by ca.cohort_month, ca.months_since_signup
