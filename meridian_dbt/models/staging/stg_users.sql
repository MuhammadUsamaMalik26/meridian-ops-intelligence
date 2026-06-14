-- Staging: users
-- Light cleanup of raw user dimension, no business logic.

select
    user_id,
    signup_date,
    acquisition_channel,
    plan,
    age_band,
    region,
    is_churned,
    churn_date,
    kyc_passed,
    referral_code,
    account_age_days_at_end
from raw.dim_users
