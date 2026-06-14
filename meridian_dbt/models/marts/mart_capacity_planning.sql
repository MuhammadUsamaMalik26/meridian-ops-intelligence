-- Mart: capacity planning
-- Daily case volume (disputes + AML alerts) vs agent capacity, by team.

with agents as (
    select * from {{ ref('stg_agents') }}
),

team_capacity as (
    select team, sum(capacity_per_day) as total_capacity_per_day, count(*) as agent_count
    from agents
    group by team
),

dispute_volume as (
    select
        raised_date as case_date,
        'disputes' as team,
        count(*) as case_volume
    from {{ ref('stg_disputes') }}
    group by raised_date
),

alert_volume as (
    select
        cast(alert_ts as date) as case_date,
        'fraud_ops' as team,
        count(*) as case_volume
    from {{ ref('stg_aml_alerts') }}
    group by cast(alert_ts as date)
),

combined_volume as (
    select * from dispute_volume
    union all
    select * from alert_volume
)

select
    cv.case_date,
    cv.team,
    cv.case_volume,
    tc.total_capacity_per_day,
    tc.agent_count,
    round(cv.case_volume * 1.0 / nullif(tc.total_capacity_per_day, 0), 3) as utilisation_rate,
    case
        when cv.case_volume > tc.total_capacity_per_day then 1 else 0
    end as is_over_capacity
from combined_volume cv
left join team_capacity tc on cv.team = tc.team
order by cv.case_date, cv.team
