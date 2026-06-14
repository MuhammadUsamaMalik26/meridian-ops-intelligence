-- Staging: subscriptions
-- Light cleanup of raw subscription lifecycle data.

select
    subscription_id,
    user_id,
    plan,
    monthly_price_gbp,
    subscription_start,
    subscription_end,
    is_active,
    billing_cycle,
    payment_method
from raw.fact_subscriptions
