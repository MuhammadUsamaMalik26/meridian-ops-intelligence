-- Staging: transactions
-- Light cleanup of raw transactions, including engineered fraud signal columns.

select
    transaction_id,
    user_id,
    transaction_date,
    transaction_ts,
    transaction_type,
    amount_gbp,
    merchant_category,
    geography,
    is_late_night,
    is_new_account_tx,
    is_round_amount,
    velocity_count_1h,
    user_baseline_amount,
    is_flagged,
    status
from raw.fact_transactions
