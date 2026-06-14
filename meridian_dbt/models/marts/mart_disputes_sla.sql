-- Mart: disputes SLA & outcomes
-- Resolution time, SLA breach rate, and outcome distribution by reason/team.

with disputes as (
    select * from {{ ref('stg_disputes') }}
),

agents as (
    select * from {{ ref('stg_agents') }}
),

enriched as (
    select
        d.*,
        a.team as agent_team,
        a.shift as agent_shift,
        case when d.resolution_time_hours > 72 then 1 else 0 end as is_sla_breach
    from disputes d
    left join agents a on d.assigned_agent_id = a.agent_id
)

select
    reason,
    count(*) as total_disputes,
    round(avg(resolution_time_hours), 1) as avg_resolution_hours,
    sum(is_sla_breach) as sla_breaches,
    round(sum(is_sla_breach) * 1.0 / count(*), 4) as sla_breach_rate,
    sum(case when outcome = 'upheld' then 1 else 0 end) as upheld_count,
    sum(case when outcome = 'rejected' then 1 else 0 end) as rejected_count,
    sum(case when outcome = 'partial' then 1 else 0 end) as partial_count,
    round(sum(case when outcome = 'upheld' then 1 else 0 end) * 1.0 / count(*), 4) as upheld_rate
from enriched
group by reason
order by total_disputes desc
