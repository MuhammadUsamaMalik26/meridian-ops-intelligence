-- Staging: events
-- Light cleanup of raw behavioural events.

select
    event_id,
    user_id,
    event_name,
    event_ts,
    session_id,
    platform,
    app_version,
    country
from raw.fact_events
