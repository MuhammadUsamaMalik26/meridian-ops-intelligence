"""
Meridian Ops Intelligence
Streamlit Dashboard — Transaction Monitoring, Disputes, Capacity Planning,
Fraud/AML Detection, and Case Note Automation for a UK neobank Operations team.
"""

import streamlit as st
import duckdb
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import subprocess
import sys
import os
import json
import pickle

# ─── Auto-build database if not present (handles Streamlit Cloud cold start) ──
def run_step(cmd, cwd=None, env=None, spinner_text="Working..."):
    """Run a subprocess step, surfacing stdout/stderr in the app on failure."""
    with st.spinner(spinner_text):
        result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            st.error(f"Step failed: {' '.join(cmd)}")
            st.code(result.stdout[-3000:] + "\n" + result.stderr[-3000:])
            st.stop()

def ensure_database():
    db_path = Path("data/meridian.duckdb")
    raw_path = Path("data/raw/dim_users.csv")

    if not raw_path.exists():
        os.makedirs("data/raw", exist_ok=True)
        run_step(
            [sys.executable, "generate_data.py"],
            spinner_text="Setting up Meridian data — first run only, this takes about 2 minutes "
                          "(generating data, building the analytics layer, training the fraud model)..."
        )

    if not db_path.exists():
        run_step([sys.executable, "load_db.py"], spinner_text="Loading raw data into warehouse...")

    # Check if analytics schema has been built by dbt
    con_check = duckdb.connect(str(db_path), read_only=True)
    try:
        con_check.execute("SELECT 1 FROM analytics.mart_transaction_monitoring LIMIT 1")
        analytics_ready = True
    except Exception:
        analytics_ready = False
    con_check.close()

    if not analytics_ready:
        run_step(
            [sys.executable, "-m", "dbt", "run"],
            cwd="meridian_dbt",
            env={**os.environ, "DBT_PROFILES_DIR": "."},
            spinner_text="Building analytics layer (dbt)..."
        )

    # Train fraud model if not present
    if not Path("ml/output/fraud_model_metrics.json").exists():
        run_step([sys.executable, "ml/fraud_model.py"], spinner_text="Training fraud detection model — first run only...")

ensure_database()

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Meridian Ops Intelligence",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.insight-box {
    background: #0f1319;
    border-left: 3px solid #3b82f6;
    border-radius: 0 8px 8px 0;
    padding: 14px 18px;
    margin: 16px 0;
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.6;
}
.insight-box strong { color: #e2e8f0; }

.section-header {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #4a5568;
    border-bottom: 1px solid #1e2535;
    padding-bottom: 8px;
    margin: 32px 0 20px 0;
}

.legacy-tag {
    font-size: 10px;
    color: #4a5568;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border: 1px solid #2a3044;
    border-radius: 4px;
    padding: 2px 8px;
    margin-left: 8px;
}
</style>
""", unsafe_allow_html=True)

# ─── DB connection ────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    return duckdb.connect("data/meridian.duckdb", read_only=True)

@st.cache_data(ttl=300)
def query(_con, sql):
    return _con.execute(sql).df()

@st.cache_resource
def load_fraud_model():
    with open("ml/output/fraud_model_champion.pkl", "rb") as f:
        return pickle.load(f)

@st.cache_data(ttl=300)
def load_fraud_metrics():
    with open("ml/output/fraud_model_metrics.json") as f:
        return json.load(f)

con = get_connection()

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛰️ Meridian")
    st.markdown("**Ops Intelligence Platform**")
    st.markdown("---")

    page = st.radio(
        "Navigate",
        [
            "Ops Overview",
            "Transaction Monitoring",
            "Disputes",
            "Capacity Planning",
            "Case Note Generator",
            "── Legacy / Growth ──",
            "Acquisition Funnel",
            "Cohort Retention",
            "Customer Segments",
            "Revenue (MRR)",
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown("""
    <div style='font-size:11px; color:#4a5568; line-height:1.8'>
    <b style='color:#6b7a99'>Stack</b><br>
    DuckDB · dbt · SQL<br>
    Python · scikit-learn<br>
    Streamlit · Plotly<br><br>
    <b style='color:#6b7a99'>Data</b><br>
    5,000 users · 505k transactions<br>
    4.3k disputes · 11.6k AML alerts<br>
    Jan 2023 – Jun 2024
    </div>
    """, unsafe_allow_html=True)

# ─── Colour palette ───────────────────────────────────────────────────────────
BLUE   = "#3b82f6"
GREEN  = "#3dd68c"
AMBER  = "#f59e0b"
RED    = "#f87171"
PURPLE = "#a78bfa"
SLATE  = "#94a3b8"
BORDER = "#2a3044"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans", color="#94a3b8", size=12),
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis=dict(gridcolor="#1e2535", linecolor="#2a3044"),
    yaxis=dict(gridcolor="#1e2535", linecolor="#2a3044"),
)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: OPS OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if page == "Ops Overview":
    st.markdown("# Ops Overview")
    st.markdown("Top-line operational KPIs: transaction monitoring, disputes, and case throughput.")

    total_tx     = query(con, "SELECT COUNT(*) FROM raw.fact_transactions").iloc[0, 0]
    flag_rate    = query(con, "SELECT AVG(is_flagged) FROM raw.fact_transactions").iloc[0, 0]
    total_alerts = query(con, "SELECT COUNT(*) FROM raw.fact_aml_alerts").iloc[0, 0]
    open_alerts  = query(con, "SELECT COUNT(*) FROM raw.fact_aml_alerts WHERE status='open'").iloc[0, 0]
    sar_filed    = query(con, "SELECT COUNT(*) FROM raw.fact_aml_alerts WHERE status='SAR_filed'").iloc[0, 0]
    total_disp   = query(con, "SELECT COUNT(*) FROM raw.fact_disputes").iloc[0, 0]
    disp_breach  = query(con, "SELECT AVG(CASE WHEN resolution_time_hours > 72 THEN 1 ELSE 0 END) FROM raw.fact_disputes").iloc[0, 0]
    fraud_auc    = load_fraud_metrics()["champion_auc"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Transactions", f"{total_tx:,}")
        st.metric("Fraud Flag Rate", f"{flag_rate:.2%}")
    with col2:
        st.metric("AML/Fraud Alerts", f"{total_alerts:,}")
        st.metric("Open Alerts", f"{int(open_alerts):,}")
    with col3:
        st.metric("Disputes Raised", f"{total_disp:,}")
        st.metric("Dispute SLA Breach Rate", f"{disp_breach:.1%}", help="Resolution time > 72 hours")
    with col4:
        st.metric("SAR Filed", f"{int(sar_filed):,}")
        st.metric("Fraud Model AUC", f"{fraud_auc:.3f}")

    st.markdown('<div class="section-header">Alert Status & Rule Distribution</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        status_df = query(con, """
            SELECT status, COUNT(*) AS alerts
            FROM raw.fact_aml_alerts GROUP BY 1
        """)
        fig = px.pie(status_df, values="alerts", names="status",
                     color_discrete_sequence=[AMBER, GREEN, RED, PURPLE],
                     title="Alert Status Distribution", hole=0.55)
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(textfont_color="white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        rule_df = query(con, """
            SELECT rule_triggered AS rule, COUNT(*) AS alerts
            FROM raw.fact_aml_alerts GROUP BY 1 ORDER BY 2 DESC
        """)
        fig = px.bar(rule_df, x="alerts", y="rule", orientation="h",
                     color_discrete_sequence=[BLUE],
                     title="Alerts by Rule Triggered")
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    <div class="insight-box">
    <strong>Key finding:</strong> rule-based checks and the ML fraud model show roughly even
    coverage of flagged transactions — each catches a meaningful share the other misses.
    This supports running both in parallel rather than relying on either alone.
    See the Transaction Monitoring page for the full rules-vs-ML breakdown.
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TRANSACTION MONITORING
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Transaction Monitoring":
    st.markdown("# Transaction Monitoring")
    st.markdown("Fraud/AML detection: rule-based engine, ML model performance, and alert queue.")

    metrics = load_fraud_metrics()

    st.markdown('<div class="section-header">Model Performance — Champion vs Challenger</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Champion Model", metrics["champion_model"].replace("_", " ").title())
        st.metric("Champion AUC", f"{metrics['champion_auc']:.4f}")
    with col2:
        st.metric("Challenger Model", metrics["challenger_model"].replace("_", " ").title())
        st.metric("Challenger AUC", f"{metrics['challenger_auc']:.4f}")
    with col3:
        st.metric("Test Set Size", f"{metrics['test_rows']:,}")
        st.metric("Positive Rate", f"{metrics['positive_rate']:.2%}")

    col1, col2 = st.columns(2)
    with col1:
        roc_df = pd.read_csv("ml/output/roc_curve_data.csv")
        fig = go.Figure()
        for model_name, color in [("random_forest", GREEN), ("logistic_regression", BLUE)]:
            sub = roc_df[roc_df["model"] == model_name]
            fig.add_trace(go.Scatter(
                x=sub["fpr"], y=sub["tpr"], mode="lines",
                name=model_name.replace("_", " ").title(),
                line=dict(width=2.5, color=color)
            ))
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                                  name="Random baseline", line=dict(dash="dash", color=SLATE, width=1)))
        fig.update_layout(**PLOTLY_LAYOUT, title="ROC Curve — Champion vs Challenger",
                          xaxis_title="False Positive Rate", yaxis_title="True Positive Rate",
                          legend=dict(orientation="h", y=-0.2, font=dict(color="#94a3b8")))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        importance_df = pd.read_csv("ml/output/feature_importance.csv").head(10)
        fig = px.bar(importance_df.sort_values("importance"), x="importance", y="feature",
                      orientation="h", color_discrete_sequence=[PURPLE],
                      title="Top 10 Feature Importances")
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Rules vs ML — Detection Coverage</div>', unsafe_allow_html=True)

    overall = query(con, """
        SELECT metric_1 AS total_transactions, metric_2 AS total_flagged,
               metric_3 AS flag_rate, metric_4 AS transactions_with_any_rule,
               metric_5 AS rules_caught_flagged, metric_6 AS ml_only_caught_flagged
        FROM analytics.mart_transaction_monitoring WHERE report_section='overall'
    """).iloc[0]

    rules_caught = overall["rules_caught_flagged"]
    ml_only = overall["ml_only_caught_flagged"]
    total_flagged = overall["total_flagged"]

    col1, col2 = st.columns(2)
    with col1:
        coverage_df = pd.DataFrame({
            "channel": ["Caught by rules", "ML-only (rules missed)"],
            "count": [rules_caught, ml_only]
        })
        fig = px.pie(coverage_df, values="count", names="channel",
                      color_discrete_sequence=[BLUE, AMBER], hole=0.55,
                      title="Flagged Transaction Detection Source")
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(textfont_color="white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        rule_perf = query(con, """
            SELECT dimension AS rule, metric_1 AS triggered, metric_2 AS true_positives,
                   metric_3 AS precision
            FROM analytics.mart_transaction_monitoring WHERE report_section='rule_performance'
            ORDER BY triggered DESC
        """)
        fig = px.bar(rule_perf, x="rule", y="precision", color_discrete_sequence=[GREEN],
                      title="Rule Precision (True Positives / Triggered)")
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(marker_line_width=0)
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"""
    <div class="insight-box">
    <strong>Rules vs ML:</strong> rule-based checks catch {rules_caught/total_flagged:.1%} of flagged
    transactions, while {ml_only/total_flagged:.1%} are caught only by the ML model — these are cases
    with no single obvious trigger (e.g. high amount relative to a user's baseline, but below any
    individual rule threshold). <strong>Recommendation:</strong> run both in parallel; rules give
    fast, explainable triage for SAR justification, while the ML model extends coverage to
    cases rules can't articulate as a single condition.
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header">Merchant Category Risk</div>', unsafe_allow_html=True)
    merchant_df = query(con, """
        SELECT dimension AS merchant_category, metric_1 AS total_tx, metric_2 AS flagged_tx,
               metric_3 AS flag_rate, metric_4 AS avg_amount
        FROM analytics.mart_transaction_monitoring WHERE report_section='merchant_breakdown'
        ORDER BY flag_rate DESC
    """)
    fig = px.bar(merchant_df, x="merchant_category", y="flag_rate", color_discrete_sequence=[RED],
                  title="Fraud Flag Rate by Merchant Category")
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_traces(marker_line_width=0)
    fig.update_yaxes(tickformat=".1%")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Alert Queue</div>', unsafe_allow_html=True)
    alert_filter = st.multiselect("Filter by status", ["open", "closed", "escalated", "SAR_filed"],
                                   default=["open", "escalated"])
    if alert_filter:
        status_list = "', '".join(alert_filter)
        alert_queue = query(con, f"""
            SELECT alert_id, transaction_id, user_id, rule_triggered, alert_score, status,
                   reviewer_team, sla_status, amount_gbp, merchant_category, geography
            FROM analytics.mart_fraud_alerts
            WHERE status IN ('{status_list}')
            ORDER BY alert_score DESC LIMIT 200
        """)
        st.dataframe(alert_queue, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DISPUTES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Disputes":
    st.markdown("# Disputes")
    st.markdown("Resolution time, SLA performance, and outcome rates by dispute reason.")

    disp_df = query(con, "SELECT * FROM analytics.mart_disputes_sla")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Disputes", f"{disp_df['total_disputes'].sum():,}")
    with col2:
        avg_res = (disp_df['avg_resolution_hours'] * disp_df['total_disputes']).sum() / disp_df['total_disputes'].sum()
        st.metric("Avg Resolution Time", f"{avg_res:.1f} hrs")
    with col3:
        breach_rate = disp_df['sla_breaches'].sum() / disp_df['total_disputes'].sum()
        st.metric("SLA Breach Rate (>72h)", f"{breach_rate:.1%}")

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(disp_df.sort_values("total_disputes", ascending=True), x="total_disputes", y="reason",
                      orientation="h", color_discrete_sequence=[BLUE],
                      title="Disputes by Reason")
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(disp_df.sort_values("avg_resolution_hours", ascending=True), x="avg_resolution_hours", y="reason",
                      orientation="h", color_discrete_sequence=[AMBER],
                      title="Avg Resolution Time by Reason (hrs)")
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Outcomes by Reason</div>', unsafe_allow_html=True)
    outcome_df = disp_df.melt(
        id_vars=["reason"], value_vars=["upheld_count", "rejected_count", "partial_count"],
        var_name="outcome", value_name="count"
    )
    outcome_df["outcome"] = outcome_df["outcome"].str.replace("_count", "")
    fig = px.bar(outcome_df, x="reason", y="count", color="outcome", barmode="stack",
                  color_discrete_sequence=[GREEN, RED, AMBER],
                  title="Dispute Outcomes by Reason")
    fig.update_layout(**PLOTLY_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Detail</div>', unsafe_allow_html=True)
    st.dataframe(
        disp_df.rename(columns={
            "reason": "Reason", "total_disputes": "Total", "avg_resolution_hours": "Avg Resolution (hrs)",
            "sla_breaches": "SLA Breaches", "sla_breach_rate": "SLA Breach Rate",
            "upheld_count": "Upheld", "rejected_count": "Rejected", "partial_count": "Partial",
            "upheld_rate": "Upheld Rate"
        }),
        use_container_width=True, hide_index=True
    )

    st.markdown("""
    <div class="insight-box">
    <strong>Highest-risk reason:</strong> fraud_claim has both the highest volume and longest
    resolution time among the top categories — consistent with these cases requiring fraud_ops
    involvement alongside the disputes team. Duplicate_charge resolves fastest and has the
    highest upheld rate, suggesting it's largely a data/reconciliation issue rather than a
    genuine dispute — a good candidate for automation (auto-refund on exact duplicate match).
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CAPACITY PLANNING
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Capacity Planning":
    st.markdown("# Capacity Planning")
    st.markdown("Daily case volume vs agent capacity by team.")

    cap_df = query(con, "SELECT * FROM analytics.mart_capacity_planning")
    cap_df["case_date"] = pd.to_datetime(cap_df["case_date"])

    team_filter = st.selectbox("Team", ["fraud_ops", "disputes"])
    team_df = cap_df[cap_df["team"] == team_filter].sort_values("case_date")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Agents on Team", f"{int(team_df['agent_count'].iloc[0])}")
    with col2:
        st.metric("Total Daily Capacity", f"{int(team_df['total_capacity_per_day'].iloc[0]):,}")
    with col3:
        over_cap_days = team_df["is_over_capacity"].sum()
        st.metric("Days Over Capacity", f"{int(over_cap_days)} / {len(team_df)}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=team_df["case_date"], y=team_df["case_volume"],
                             name="Case Volume", line=dict(color=BLUE, width=2)))
    fig.add_trace(go.Scatter(x=team_df["case_date"], y=team_df["total_capacity_per_day"],
                             name="Daily Capacity", line=dict(color=RED, width=1.5, dash="dash")))
    fig.update_layout(**PLOTLY_LAYOUT, title=f"{team_filter.replace('_', ' ').title()} — Case Volume vs Capacity",
                      height=400, legend=dict(orientation="h", y=-0.15, font=dict(color="#94a3b8")))
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.histogram(team_df, x="utilisation_rate", nbins=30, color_discrete_sequence=[PURPLE],
                         title="Utilisation Rate Distribution")
    fig2.update_layout(**PLOTLY_LAYOUT)
    fig2.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown(f"""
    <div class="insight-box">
    <strong>Capacity read:</strong> the {team_filter.replace('_', ' ')} team exceeded daily capacity
    on {int(over_cap_days)} of {len(team_df)} days in the dataset. Days over capacity correlate with
    backlog growth — if this pattern clusters around specific periods (e.g. month-end), it's a
    signal for flexible/surge staffing rather than a permanent headcount increase.
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CASE NOTE GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Case Note Generator":
    st.markdown("# Case Note Generator")
    st.markdown("Proof-of-concept: generate a draft case note for a flagged transaction using an LLM, "
                 "for analyst review before escalation.")

    st.markdown("""
    <div class="insight-box">
    This demonstrates a small automation pattern: structured alert data is passed to an LLM,
    which drafts a case-note summary an analyst can review, edit, and action — reducing manual
    write-up time for routine alerts. The analyst remains in the loop; the LLM drafts, it
    doesn't decide.
    </div>
    """, unsafe_allow_html=True)

    sample_alerts = query(con, """
        SELECT alert_id, transaction_id, user_id, rule_triggered, alert_score,
               amount_gbp, merchant_category, geography, amount_to_baseline_ratio, rules_triggered_count
        FROM analytics.mart_fraud_alerts
        WHERE status = 'open'
        ORDER BY alert_score DESC LIMIT 20
    """)

    selected_alert_id = st.selectbox("Select an open alert", sample_alerts["alert_id"])
    alert_row = sample_alerts[sample_alerts["alert_id"] == selected_alert_id].iloc[0]

    st.markdown('<div class="section-header">Alert Details</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Transaction:** {alert_row['transaction_id']}")
        st.write(f"**User:** {alert_row['user_id']}")
    with col2:
        st.write(f"**Rule triggered:** {alert_row['rule_triggered']}")
        st.write(f"**Alert score:** {alert_row['alert_score']:.2f}")
    with col3:
        st.write(f"**Amount:** £{alert_row['amount_gbp']:.2f}")
        st.write(f"**Merchant category:** {alert_row['merchant_category']}")

    if st.button("Generate case note draft"):
        ratio = alert_row['amount_to_baseline_ratio']
        ratio_text = f"{ratio:.1f}x" if pd.notna(ratio) else "N/A"

        # Template-based draft (no external API call required — illustrates the
        # automation pattern; swap in an LLM API call here for production use)
        draft = (
            f"**Case Note — Alert {alert_row['alert_id']}**\n\n"
            f"Transaction {alert_row['transaction_id']} for user {alert_row['user_id']} was flagged "
            f"by the **{alert_row['rule_triggered']}** rule (alert score {alert_row['alert_score']:.2f}). "
            f"The transaction was £{alert_row['amount_gbp']:.2f} in the **{alert_row['merchant_category']}** "
            f"category, geography **{alert_row['geography']}**, representing **{ratio_text}** the user's "
            f"typical transaction amount. "
            f"{int(alert_row['rules_triggered_count'])} rule(s) triggered in total for this transaction.\n\n"
            f"**Recommendation:** "
            + ("Escalate to Tier 2 review — multiple rule triggers and high alert score indicate "
               "elevated risk." if alert_row['rules_triggered_count'] >= 2 or alert_row['alert_score'] >= 0.7
               else "Standard review — single rule trigger, monitor for repeat patterns on this account.")
        )
        st.markdown('<div class="section-header">Draft Case Note</div>', unsafe_allow_html=True)
        st.markdown(draft)
        st.caption("Draft generated from a template based on alert features. "
                   "In production, this prompt and alert context would be sent to an LLM API "
                   "(e.g. Claude or GPT) for a more natural-language summary, with the analyst "
                   "reviewing and editing before the note is saved to the case record.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ACQUISITION FUNNEL (legacy)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Acquisition Funnel":
    st.markdown("# Acquisition Funnel <span class='legacy-tag'>Legacy / Growth</span>", unsafe_allow_html=True)
    st.markdown("Step-by-step conversion from signup to first transaction.")

    funnel_df = query(con, "SELECT * FROM analytics.mart_funnel_acquisition ORDER BY ord")

    fig = go.Figure(go.Funnel(
        y=funnel_df["step"],
        x=funnel_df["users"],
        textinfo="value+percent initial",
        marker=dict(color=[BLUE, BLUE, GREEN, GREEN, AMBER]),
        connector=dict(line=dict(color=BORDER, width=1))
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title="Signup → Activation Funnel", height=400)
    st.plotly_chart(fig, use_container_width=True)

    funnel_df["conversion_%"] = (funnel_df["pct"] * 100).round(1).astype(str) + "%"
    funnel_df["drop_off"] = (funnel_df["users"].shift(1) - funnel_df["users"]).fillna(0).astype(int)
    st.dataframe(
        funnel_df[["step", "users", "conversion_%", "drop_off"]].rename(columns={
            "step": "Funnel Step", "users": "Users",
            "conversion_%": "% of Top", "drop_off": "Drop-off"
        }),
        use_container_width=True, hide_index=True
    )

    st.markdown('<div class="section-header">Funnel by Channel</div>', unsafe_allow_html=True)

    channel_funnel = query(con, """
        WITH steps AS (
            SELECT e.user_id, u.acquisition_channel,
                MAX(CASE WHEN e.event_name='kyc_approved' THEN 1 ELSE 0 END) AS kyc,
                MAX(CASE WHEN e.event_name='first_transaction' THEN 1 ELSE 0 END) AS activated
            FROM raw.fact_events e
            JOIN raw.dim_users u ON e.user_id = u.user_id
            GROUP BY e.user_id, u.acquisition_channel
        )
        SELECT acquisition_channel AS channel,
               COUNT(*) AS total,
               ROUND(AVG(kyc)*100,1) AS kyc_rate,
               ROUND(AVG(activated)*100,1) AS activation_rate
        FROM steps GROUP BY 1 ORDER BY activation_rate DESC
    """)
    fig2 = px.bar(channel_funnel, x="channel", y=["kyc_rate", "activation_rate"],
                  barmode="group", color_discrete_sequence=[BLUE, GREEN],
                  labels={"value": "Rate (%)", "variable": "Metric"},
                  title="KYC & Activation Rate by Channel")
    fig2.update_layout(**PLOTLY_LAYOUT)
    st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: COHORT RETENTION (legacy)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Cohort Retention":
    st.markdown("# Cohort Retention <span class='legacy-tag'>Legacy / Growth</span>", unsafe_allow_html=True)
    st.markdown("Monthly cohorts tracked across 12 months of transaction activity.")

    cohort_df = query(con, "SELECT * FROM analytics.mart_cohort_retention")
    cohort_df["cohort_month"] = pd.to_datetime(cohort_df["cohort_month"]).dt.strftime("%Y-%m")

    pivot = cohort_df.pivot_table(
        index="cohort_month", columns="months_since_signup", values="retention_rate"
    )

    fig = go.Figure(go.Heatmap(
        z=pivot.values * 100,
        x=[f"Month {c}" for c in pivot.columns],
        y=pivot.index.tolist(),
        colorscale=[[0, "#0d0f14"], [0.3, "#1e3a5f"], [0.6, "#2563eb"], [1.0, "#3dd68c"]],
        text=[[f"{v:.0f}%" if not pd.isna(v) else "" for v in row] for row in pivot.values * 100],
        texttemplate="%{text}",
        textfont=dict(size=10),
        showscale=True,
        colorbar=dict(tickfont=dict(color="#94a3b8"))
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title="Cohort Retention Heatmap", height=480,
                      xaxis=dict(side="top", gridcolor=BORDER),
                      yaxis=dict(autorange="reversed", gridcolor=BORDER))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Month 1 Retention Trend</div>', unsafe_allow_html=True)
    m1 = cohort_df[cohort_df["months_since_signup"] == 1].copy()
    fig2 = px.line(m1, x="cohort_month", y="retention_rate", markers=True,
                   color_discrete_sequence=[GREEN],
                   labels={"retention_rate": "Month 1 Retention", "cohort_month": "Cohort"},
                   title="Month 1 Retention by Cohort")
    fig2.update_layout(**PLOTLY_LAYOUT)
    fig2.update_traces(line_width=2.5)
    fig2.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CUSTOMER SEGMENTS (legacy)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Customer Segments":
    st.markdown("# Customer Segmentation <span class='legacy-tag'>Legacy / Growth</span>", unsafe_allow_html=True)
    st.markdown("RFM-based segmentation: Recency, Frequency, Monetary value (last 90 days).")

    seg_summary = query(con, """
        SELECT segment, COUNT(*) AS users,
               ROUND(AVG(recency_days),0) AS avg_recency_days,
               ROUND(AVG(frequency_90d),1) AS avg_tx_90d,
               ROUND(AVG(monetary_90d),2) AS avg_spend_90d
        FROM analytics.mart_customer_segments
        GROUP BY segment ORDER BY avg_spend_90d DESC
    """)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(seg_summary, values="users", names="segment",
                     color_discrete_sequence=[GREEN, BLUE, PURPLE, AMBER, RED, SLATE],
                     hole=0.5, title="Segment Distribution")
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(textfont_color="white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig2 = px.bar(seg_summary, x="segment", y="avg_spend_90d",
                      color="avg_spend_90d",
                      color_continuous_scale=[[0, "#1e3a5f"], [1, "#3dd68c"]],
                      title="Avg 90-Day Spend by Segment",
                      labels={"avg_spend_90d": "Avg Spend (£)", "segment": ""})
        fig2.update_layout(**PLOTLY_LAYOUT)
        fig2.update_coloraxes(showscale=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-header">Segment Detail</div>', unsafe_allow_html=True)
    st.dataframe(
        seg_summary.rename(columns={
            "segment": "Segment", "users": "Users",
            "avg_recency_days": "Avg Recency (days)",
            "avg_tx_90d": "Avg Tx (90d)", "avg_spend_90d": "Avg Spend £ (90d)"
        }),
        use_container_width=True, hide_index=True
    )

    plan_seg = query(con, """
        SELECT segment, plan, COUNT(*) AS users
        FROM analytics.mart_customer_segments
        GROUP BY segment, plan ORDER BY segment, plan
    """)
    fig3 = px.bar(plan_seg, x="segment", y="users", color="plan",
                  color_discrete_sequence=[SLATE, BLUE, GREEN],
                  title="Segment Composition by Plan",
                  labels={"users": "Users", "segment": ""})
    fig3.update_layout(**PLOTLY_LAYOUT)
    st.plotly_chart(fig3, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: REVENUE (MRR) (legacy)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Revenue (MRR)":
    st.markdown("# Revenue — MRR Tracking <span class='legacy-tag'>Legacy / Growth</span>", unsafe_allow_html=True)
    st.markdown("Monthly Recurring Revenue: new, churned, and net change over time.")

    mrr_df = query(con, "SELECT * FROM analytics.mart_mrr_monthly ORDER BY month")
    mrr_df["month"] = pd.to_datetime(mrr_df["month"])
    mrr_df["cumulative_mrr"] = mrr_df["net_mrr_change"].cumsum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total New MRR", f"£{mrr_df['new_mrr'].sum():,.0f}")
    with col2:
        st.metric("Total Churned MRR", f"£{mrr_df['churned_mrr'].sum():,.0f}")
    with col3:
        net = mrr_df["net_mrr_change"].sum()
        st.metric("Net MRR Growth", f"£{net:,.0f}")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=mrr_df["month"], y=mrr_df["new_mrr"],
                         name="New MRR", marker_color=GREEN, marker_line_width=0))
    fig.add_trace(go.Bar(x=mrr_df["month"], y=-mrr_df["churned_mrr"],
                         name="Churned MRR", marker_color=RED, marker_line_width=0))
    fig.add_trace(go.Scatter(x=mrr_df["month"], y=mrr_df["net_mrr_change"],
                             name="Net MRR", line=dict(color=BLUE, width=2.5),
                             mode="lines+markers"))
    fig.update_layout(**PLOTLY_LAYOUT, barmode="relative",
                      title="Monthly MRR Waterfall", height=400,
                      legend=dict(orientation="h", y=-0.15, font=dict(color="#94a3b8")))
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.area(mrr_df, x="month", y="cumulative_mrr",
                   color_discrete_sequence=[BLUE], title="Cumulative Net MRR",
                   labels={"cumulative_mrr": "Cumulative MRR (£)", "month": ""})
    fig2.update_layout(**PLOTLY_LAYOUT)
    fig2.update_traces(fillcolor="rgba(59,130,246,0.15)", line_width=2)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-header">Monthly Detail</div>', unsafe_allow_html=True)
    display_df = mrr_df.copy()
    display_df["month"] = display_df["month"].dt.strftime("%b %Y")
    st.dataframe(
        display_df[["month", "new_mrr", "new_subscribers", "churned_mrr", "churned_subscribers", "net_mrr_change"]]
        .rename(columns={
            "month": "Month", "new_mrr": "New MRR (£)", "new_subscribers": "New Subs",
            "churned_mrr": "Churned MRR (£)", "churned_subscribers": "Churned Subs",
            "net_mrr_change": "Net Change (£)"
        }).sort_values("Month", ascending=False),
        use_container_width=True, hide_index=True
    )


# ══════════════════════════════════════════════════════════════════════════════
# Divider page placeholder (sidebar separator)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "── Legacy / Growth ──":
    st.markdown("# Legacy / Growth Analytics")
    st.markdown("""
    These pages are carried over from the platform's original growth-analytics scope
    (acquisition, retention, segmentation, MRR). They remain functional and use the same
    underlying user/transaction data, but are secondary to the Ops Intelligence modules
    above. Select a page from the sidebar to view.
    """)

