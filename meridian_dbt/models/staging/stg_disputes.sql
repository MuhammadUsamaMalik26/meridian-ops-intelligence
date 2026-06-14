-- Staging: disputes
-- Light cleanup of raw dispute records.

select
    dispute_id,
    transaction_id,
    user_id,
    raised_date,
    raised_ts,
    reason,
    resolution_date,
    resolution_time_hours,
    outcome,
    assigned_agent_id
from raw.fact_disputes
