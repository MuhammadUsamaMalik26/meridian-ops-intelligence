"""
Meridian Ops Intelligence — Synthetic Data Generator
Generates realistic operational data for a UK neobank's Operations function:
users, events, transactions (with learnable fraud signal), subscriptions,
disputes, agents, and AML alerts.

Outputs: CSV files under data/raw/
"""

import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
import os

fake = Faker('en_GB')
np.random.seed(42)
random.seed(42)

OUTPUT_DIR = "data/raw"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Config ───────────────────────────────────────────────────────────────────
N_USERS = 5000
START_DATE = datetime(2023, 1, 1)
END_DATE   = datetime(2024, 6, 30)
DATE_RANGE_DAYS = (END_DATE - START_DATE).days

ACQUISITION_CHANNELS = ["organic_search", "paid_social", "referral", "app_store", "email_campaign"]
CHANNEL_WEIGHTS      = [0.30, 0.25, 0.20, 0.15, 0.10]

PLANS = ["free", "plus", "premium"]
PLAN_WEIGHTS = [0.55, 0.30, 0.15]
PLAN_PRICES  = {"free": 0.0, "plus": 4.99, "premium": 9.99}

UK_REGIONS = [
    "London", "South East", "North West", "Yorkshire", "West Midlands",
    "East of England", "South West", "Scotland", "Wales", "North East"
]

# Geographies used for AML "high risk geography" rule — mix of normal + flagged
TRANSACTION_GEOGRAPHIES = [
    "UK", "UK", "UK", "UK", "UK", "UK", "UK",  # weighted heavily domestic
    "EU", "EU", "US",
    "UAE", "Nigeria", "Cyprus"  # higher-risk flagged geographies for AML rule
]
HIGH_RISK_GEOGRAPHIES = {"UAE", "Nigeria", "Cyprus"}


# ─── 1. dim_users ─────────────────────────────────────────────────────────────
def generate_users(n):
    records = []
    for i in range(1, n + 1):
        signup_offset = random.randint(0, DATE_RANGE_DAYS - 30)
        signup_date   = START_DATE + timedelta(days=signup_offset)
        channel       = random.choices(ACQUISITION_CHANNELS, CHANNEL_WEIGHTS)[0]
        plan          = random.choices(PLANS, PLAN_WEIGHTS)[0]
        age           = random.randint(18, 65)
        region        = random.choice(UK_REGIONS)

        churn_prob = {"free": 0.45, "plus": 0.25, "premium": 0.10}[plan]
        is_churned = random.random() < churn_prob

        churn_date = None
        if is_churned:
            days_active = random.randint(7, min(180, DATE_RANGE_DAYS - signup_offset))
            churn_date  = signup_date + timedelta(days=days_active)

        records.append({
            "user_id":          f"USR{i:05d}",
            "signup_date":      signup_date.date(),
            "acquisition_channel": channel,
            "plan":             plan,
            "age_band":         "18-24" if age < 25 else "25-34" if age < 35 else "35-44" if age < 45 else "45-54" if age < 55 else "55+",
            "region":           region,
            "is_churned":       int(is_churned),
            "churn_date":       churn_date.date() if churn_date else None,
            "kyc_passed":       int(random.random() < 0.88),
            "referral_code":    fake.bothify(text="NP-????-####").upper() if channel == "referral" else None,
            "account_age_days_at_end": (END_DATE - signup_date).days,
        })
    return pd.DataFrame(records)


# ─── 2. fact_events ───────────────────────────────────────────────────────────
EVENT_FUNNEL = [
    "app_opened", "signup_started", "kyc_submitted", "kyc_approved",
    "onboarding_completed", "first_transaction", "feature_viewed",
    "notification_enabled", "referral_sent", "subscription_upgraded",
    "subscription_cancelled", "support_ticket_created"
]

def generate_events(users_df):
    records = []
    event_id = 1

    for _, user in users_df.iterrows():
        signup_dt = datetime.combine(user["signup_date"], datetime.min.time())
        kyc_ok    = bool(user["kyc_passed"])
        plan      = user["plan"]

        base_events = ["app_opened", "signup_started"]
        if kyc_ok:
            base_events += ["kyc_submitted", "kyc_approved", "onboarding_completed"]
            if random.random() < 0.80:
                base_events.append("first_transaction")
            if random.random() < 0.60:
                base_events.append("feature_viewed")
            if random.random() < 0.45:
                base_events.append("notification_enabled")
            if plan != "free" and random.random() < 0.20:
                base_events.append("referral_sent")
            if plan == "free" and random.random() < 0.15:
                base_events.append("subscription_upgraded")
            if user["is_churned"] and random.random() < 0.40:
                base_events.append("support_ticket_created")
            if user["is_churned"] and plan != "free":
                base_events.append("subscription_cancelled")
        else:
            base_events.append("kyc_submitted")

        offset_hours = 0
        for evt in base_events:
            offset_hours += random.randint(1, 48)
            evt_dt = signup_dt + timedelta(hours=offset_hours)
            if evt_dt > END_DATE:
                break
            records.append({
                "event_id":   f"EVT{event_id:07d}",
                "user_id":    user["user_id"],
                "event_name": evt,
                "event_ts":   evt_dt,
                "session_id": fake.uuid4(),
                "platform":   random.choices(["ios", "android", "web"], [0.45, 0.40, 0.15])[0],
                "app_version": random.choice(["2.1.0", "2.2.0", "2.3.1", "2.4.0", "3.0.0"]),
                "country":    "GB",
            })
            event_id += 1

    return pd.DataFrame(records)


# ─── 3. fact_transactions ─────────────────────────────────────────────────────
# Fraud signal design — is_flagged now correlates with engineered risk factors so a
# model can actually learn something. Each factor adds to a risk score; flagging
# probability is a function of that score, not pure random noise.

TRANSACTION_TYPES = ["card_payment", "bank_transfer", "direct_debit", "atm_withdrawal", "p2p_payment"]
TX_WEIGHTS        = [0.50, 0.20, 0.15, 0.08, 0.07]

MERCHANT_CATEGORIES = [
    "groceries", "transport", "dining", "entertainment",
    "utilities", "health", "travel", "retail", "subscriptions",
    "crypto_exchange", "gambling", "money_service_business"
]
# Higher base risk weight for certain categories (AML/fraud typology proxies)
MERCHANT_RISK_WEIGHT = {
    "groceries": 0.0, "transport": 0.0, "dining": 0.0, "entertainment": 0.0,
    "utilities": 0.0, "health": 0.0, "retail": 0.0, "subscriptions": 0.0,
    "travel": 0.05,
    "crypto_exchange": 0.35,
    "gambling": 0.25,
    "money_service_business": 0.30,
}
# Most transactions are domestic; very small share use higher-risk geography pool
MERCHANT_GEO_WEIGHTS = [0.975, 0.025]  # 97.5% "UK", 2.5% drawn from TRANSACTION_GEOGRAPHIES


def generate_transactions(users_df):
    records = []
    tx_id = 1

    active_users = users_df[users_df["kyc_passed"] == 1]

    for _, user in active_users.iterrows():
        signup_dt = datetime.combine(user["signup_date"], datetime.min.time())
        end_dt    = datetime.combine(user["churn_date"], datetime.min.time()) if user["churn_date"] else END_DATE

        active_days = max((end_dt - signup_dt).days, 1)
        avg_monthly = {"free": 8, "plus": 18, "premium": 30}[user["plan"]]
        n_tx = max(1, int(np.random.poisson(avg_monthly * active_days / 30)))

        # Pre-generate a baseline "typical" amount for this user (for anomaly comparison)
        user_baseline_amount = round(random.lognormvariate(3.0, 0.6), 2)

        # Decide if this user is one of a small "bad actor" cohort
        is_structuring_user = random.random() < 0.01   # ~1% of users — structuring pattern
        is_velocity_user    = random.random() < 0.008  # ~0.8% of users — rapid burst pattern

        # Generate raw transaction timestamps first, then sort chronologically so
        # velocity (tx within 1h window) is meaningful
        tx_dts = []
        for _ in range(n_tx):
            offset_days = random.randint(1, active_days)
            tx_dts.append(signup_dt + timedelta(
                days=offset_days, hours=random.randint(0, 23), minutes=random.randint(0, 59)
            ))
        tx_dts.sort()

        # For velocity users, inject a genuine burst: 4-6 tx within ~20 minutes,
        # placed at one random point in their timeline
        if is_velocity_user and n_tx >= 4:
            burst_size = min(n_tx, random.randint(4, 6))
            start_idx = random.randint(0, n_tx - burst_size)
            burst_start = tx_dts[start_idx]
            for b in range(burst_size):
                tx_dts[start_idx + b] = burst_start + timedelta(minutes=random.randint(0, 20))
            tx_dts.sort()

        recent_tx_times = []

        for tx_seq, tx_dt in enumerate(tx_dts):
            tx_type = random.choices(TRANSACTION_TYPES, TX_WEIGHTS)[0]
            merchant_category = random.choice(MERCHANT_CATEGORIES)

            # Geography
            if random.random() < MERCHANT_GEO_WEIGHTS[1]:
                geography = random.choice(TRANSACTION_GEOGRAPHIES)
            else:
                geography = "UK"

            # Amount generation
            if is_structuring_user and random.random() < 0.25:
                # structuring proxy: amounts clustered just under a round £1000 threshold
                amount = round(random.uniform(900, 999.99), 2)
            elif merchant_category in ("crypto_exchange", "gambling", "money_service_business"):
                amount = round(random.lognormvariate(4.5, 1.0), 2)  # larger, riskier amounts
            else:
                amount = round(random.lognormvariate(3.2, 1.1), 2)

            # Time-of-day anomaly: most tx 6am-11pm, small share late night
            is_late_night = tx_dt.hour < 5 or tx_dt.hour >= 23

            # Velocity: count tx in last 60 minutes for this user (chronological now)
            recent_tx_times = [t for t in recent_tx_times if (tx_dt - t).total_seconds() <= 3600]
            velocity_count_1h = len(recent_tx_times)
            recent_tx_times.append(tx_dt)

            # New account flag (transaction within first 14 days of signup)
            offset_days = (tx_dt - signup_dt).days
            is_new_account_tx = offset_days <= 14

            # Round number flag — true round amounts only (e.g. 500.00, 1000.00),
            # not incidental modulo coincidences from lognormal draws
            is_round_amount = int(amount % 50 == 0 and amount >= 100)

            # ── Risk score (drives flagging probability) ────────────────────────
            # Calibrated so overall flag rate lands roughly 1-2%, with risk
            # concentrated in a small number of genuinely anomalous transactions
            risk_score = 0.0
            risk_score += MERCHANT_RISK_WEIGHT.get(merchant_category, 0.0) * 0.15
            risk_score += 0.20 if amount > user_baseline_amount * 10 else 0.0
            risk_score += 0.03 if is_late_night else 0.0
            risk_score += 0.35 if velocity_count_1h >= 4 else 0.0
            risk_score += 0.25 if (is_new_account_tx and amount > user_baseline_amount * 8) else 0.0
            risk_score += 0.10 if geography in HIGH_RISK_GEOGRAPHIES else 0.0
            risk_score += 0.35 if (is_structuring_user and 900 <= amount < 1000) else 0.0
            risk_score += 0.02 if is_round_amount else 0.0

            # Small noise floor for false positives, capped overall
            flag_prob = min(0.90, 0.0005 + risk_score)
            is_flagged = int(random.random() < flag_prob)

            records.append({
                "transaction_id":     f"TX{tx_id:08d}",
                "user_id":            user["user_id"],
                "transaction_date":   tx_dt.date(),
                "transaction_ts":     tx_dt,
                "transaction_type":   tx_type,
                "amount_gbp":         amount,
                "merchant_category":  merchant_category,
                "geography":          geography,
                "is_late_night":      int(is_late_night),
                "is_new_account_tx":  int(is_new_account_tx),
                "is_round_amount":    int(is_round_amount),
                "velocity_count_1h":  velocity_count_1h,
                "user_baseline_amount": user_baseline_amount,
                "is_flagged":         is_flagged,
                "status":             random.choices(["completed", "pending", "failed"], [0.94, 0.04, 0.02])[0],
            })
            tx_id += 1

    return pd.DataFrame(records)


# ─── 4. fact_subscriptions ────────────────────────────────────────────────────
def generate_subscriptions(users_df):
    records = []
    sub_id = 1

    paid_users = users_df[users_df["plan"] != "free"]

    for _, user in paid_users.iterrows():
        signup_dt = datetime.combine(user["signup_date"], datetime.min.time())
        plan      = user["plan"]
        price     = PLAN_PRICES[plan]

        sub_start = signup_dt + timedelta(days=random.randint(1, 14))
        sub_end   = None

        if user["is_churned"] and user["churn_date"]:
            sub_end = datetime.combine(user["churn_date"], datetime.min.time())

        records.append({
            "subscription_id":    f"SUB{sub_id:06d}",
            "user_id":            user["user_id"],
            "plan":               plan,
            "monthly_price_gbp":  price,
            "subscription_start": sub_start.date(),
            "subscription_end":   sub_end.date() if sub_end else None,
            "is_active":          int(sub_end is None),
            "billing_cycle":      "monthly",
            "payment_method":     random.choice(["card", "direct_debit"]),
        })
        sub_id += 1

    return pd.DataFrame(records)


# ─── 5. dim_agents ─────────────────────────────────────────────────────────────
TEAMS = ["fraud_ops", "disputes", "kyc_review"]
SHIFTS = ["early", "day", "late"]

def generate_agents(n_per_team=8):
    records = []
    agent_id = 1
    for team in TEAMS:
        for _ in range(n_per_team):
            records.append({
                "agent_id":        f"AGT{agent_id:04d}",
                "team":            team,
                "shift":           random.choice(SHIFTS),
                "capacity_per_day": random.randint(15, 30) if team != "kyc_review" else random.randint(25, 45),
                "tenure_months":   random.randint(1, 48),
            })
            agent_id += 1
    return pd.DataFrame(records)


# ─── 6. fact_disputes ───────────────────────────────────────────────────────────
DISPUTE_REASONS = [
    "unauthorised_tx", "goods_not_received", "duplicate_charge",
    "fraud_claim", "billing_error"
]
# Resolution time + upheld-rate vary by reason (realistic ops variance)
DISPUTE_REASON_PROFILE = {
    "unauthorised_tx":    {"mean_hours": 48,  "std_hours": 18, "upheld_rate": 0.55},
    "goods_not_received": {"mean_hours": 96,  "std_hours": 36, "upheld_rate": 0.40},
    "duplicate_charge":   {"mean_hours": 24,  "std_hours": 10, "upheld_rate": 0.75},
    "fraud_claim":        {"mean_hours": 72,  "std_hours": 30, "upheld_rate": 0.60},
    "billing_error":      {"mean_hours": 36,  "std_hours": 14, "upheld_rate": 0.70},
}

def generate_disputes(tx_df, agents_df):
    records = []
    dispute_id = 1

    disputes_team_agents = agents_df[agents_df["team"] == "disputes"]["agent_id"].tolist()

    # Disputes drawn from a sample of completed transactions — flagged tx are
    # more likely to generate a dispute (fraud_claim especially)
    completed_tx = tx_df[tx_df["status"] == "completed"].copy()

    for _, tx in completed_tx.iterrows():
        base_prob = 0.004  # ~0.4% baseline dispute rate
        if tx["is_flagged"] == 1:
            base_prob = 0.12  # flagged transactions much more likely to be disputed

        if random.random() < base_prob:
            if tx["is_flagged"] == 1 and random.random() < 0.5:
                reason = "fraud_claim"
            else:
                reason = random.choices(
                    DISPUTE_REASONS,
                    weights=[0.30, 0.25, 0.20, 0.10, 0.15]
                )[0]

            profile = DISPUTE_REASON_PROFILE[reason]
            raised_dt = pd.Timestamp(tx["transaction_ts"]) + timedelta(days=random.randint(0, 5))

            resolution_hours = max(2, np.random.normal(profile["mean_hours"], profile["std_hours"]))
            resolution_dt = raised_dt + timedelta(hours=resolution_hours)

            outcome = "upheld" if random.random() < profile["upheld_rate"] else random.choices(
                ["rejected", "partial"], weights=[0.7, 0.3]
            )[0]

            records.append({
                "dispute_id":          f"DSP{dispute_id:06d}",
                "transaction_id":      tx["transaction_id"],
                "user_id":             tx["user_id"],
                "raised_date":         raised_dt.date(),
                "raised_ts":           raised_dt,
                "reason":              reason,
                "resolution_date":     resolution_dt.date(),
                "resolution_time_hours": round(resolution_hours, 1),
                "outcome":             outcome,
                "assigned_agent_id":   random.choice(disputes_team_agents),
            })
            dispute_id += 1

    return pd.DataFrame(records)


# ─── 7. fact_aml_alerts ──────────────────────────────────────────────────────────
AML_RULES = ["velocity", "structuring", "high_risk_geography", "round_amount", "large_amount_new_account"]

def generate_aml_alerts(tx_df, agents_df):
    records = []
    alert_id = 1

    fraud_team_agents = agents_df[agents_df["team"] == "fraud_ops"]["agent_id"].tolist()

    for _, tx in tx_df.iterrows():
        triggered_rules = []

        if tx["velocity_count_1h"] >= 4:
            triggered_rules.append("velocity")
        if 900 <= tx["amount_gbp"] < 1000 and tx["is_round_amount"] == 0:
            triggered_rules.append("structuring")
        if tx["geography"] in HIGH_RISK_GEOGRAPHIES:
            triggered_rules.append("high_risk_geography")
        if tx["is_round_amount"] == 1 and tx["amount_gbp"] >= 100:
            triggered_rules.append("round_amount")
        if tx["is_new_account_tx"] == 1 and tx["amount_gbp"] > tx["user_baseline_amount"] * 8:
            triggered_rules.append("large_amount_new_account")
        if tx["merchant_category"] in ("crypto_exchange", "gambling", "money_service_business") \
                and tx["amount_gbp"] > tx["user_baseline_amount"] * 6:
            triggered_rules.append("high_risk_merchant_anomaly")

        # Also generate alerts purely from the ML-style is_flagged signal where
        # no rule fired (catches ML-only detections for rules-vs-ML comparison)
        if not triggered_rules and tx["is_flagged"] == 1 and random.random() < 0.15:
            triggered_rules.append("ml_model_only")

        for rule in triggered_rules:
            # Alert score: rough proxy combining flag status + rule type
            base_score = 0.5 + (0.3 if tx["is_flagged"] == 1 else 0.0)
            alert_score = round(min(0.99, base_score + random.uniform(-0.1, 0.15)), 2)

            status = random.choices(
                ["open", "closed", "escalated", "SAR_filed"],
                weights=[0.15, 0.55, 0.22, 0.08]
            )[0]

            review_time = round(max(0.5, np.random.normal(6, 3)), 1) if status != "open" else None

            records.append({
                "alert_id":        f"ALR{alert_id:07d}",
                "transaction_id":  tx["transaction_id"],
                "user_id":         tx["user_id"],
                "rule_triggered":  rule,
                "alert_score":     alert_score,
                "status":          status,
                "reviewed_by":     random.choice(fraud_team_agents) if status != "open" else None,
                "review_time_hours": review_time,
                "alert_ts":        pd.Timestamp(tx["transaction_ts"]),
            })
            alert_id += 1

    return pd.DataFrame(records)


# ─── Run & Save ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating users...")
    users_df = generate_users(N_USERS)
    users_df.to_csv(f"{OUTPUT_DIR}/dim_users.csv", index=False)
    print(f"  -> {len(users_df):,} users")

    print("Generating events...")
    events_df = generate_events(users_df)
    events_df.to_csv(f"{OUTPUT_DIR}/fact_events.csv", index=False)
    print(f"  -> {len(events_df):,} events")

    print("Generating transactions (with engineered fraud signal)...")
    tx_df = generate_transactions(users_df)
    tx_df.to_csv(f"{OUTPUT_DIR}/fact_transactions.csv", index=False)
    print(f"  -> {len(tx_df):,} transactions")

    print("Generating subscriptions...")
    subs_df = generate_subscriptions(users_df)
    subs_df.to_csv(f"{OUTPUT_DIR}/fact_subscriptions.csv", index=False)
    print(f"  -> {len(subs_df):,} subscriptions")

    print("Generating agents...")
    agents_df = generate_agents()
    agents_df.to_csv(f"{OUTPUT_DIR}/dim_agents.csv", index=False)
    print(f"  -> {len(agents_df):,} agents")

    print("Generating disputes...")
    disputes_df = generate_disputes(tx_df, agents_df)
    disputes_df.to_csv(f"{OUTPUT_DIR}/fact_disputes.csv", index=False)
    print(f"  -> {len(disputes_df):,} disputes")

    print("Generating AML/fraud alerts...")
    alerts_df = generate_aml_alerts(tx_df, agents_df)
    alerts_df.to_csv(f"{OUTPUT_DIR}/fact_aml_alerts.csv", index=False)
    print(f"  -> {len(alerts_df):,} alerts")

    print("\nDone. Files saved to data/raw/")

    # ── Sanity checks ────────────────────────────────────────────────────────
    print("\n-- Sanity Checks --------------------------------")
    print(f"Churn rate:          {users_df['is_churned'].mean():.1%}")
    print(f"KYC pass rate:       {users_df['kyc_passed'].mean():.1%}")
    print(f"Avg tx amount:       £{tx_df['amount_gbp'].mean():.2f}")
    print(f"Fraud flag rate:     {tx_df['is_flagged'].mean():.2%}")
    print(f"  by merchant category:")
    print(tx_df.groupby("merchant_category")["is_flagged"].mean().sort_values(ascending=False).round(3).to_string())
    print(f"\nDisputes:            {len(disputes_df):,} ({len(disputes_df)/len(tx_df):.2%} of transactions)")
    print(f"Dispute outcomes:\n{disputes_df['outcome'].value_counts(normalize=True).round(3).to_string()}")
    print(f"\nAML alerts:          {len(alerts_df):,}")
    print(f"Alert rule breakdown:\n{alerts_df['rule_triggered'].value_counts().to_string()}")
    print(f"Alert status breakdown:\n{alerts_df['status'].value_counts(normalize=True).round(3).to_string()}")
