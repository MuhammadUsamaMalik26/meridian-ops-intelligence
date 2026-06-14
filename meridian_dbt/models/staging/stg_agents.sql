-- Staging: agents
-- Light cleanup of raw agent dimension (fraud_ops, disputes, kyc_review teams).

select
    agent_id,
    team,
    shift,
    capacity_per_day,
    tenure_months
from raw.dim_agents
