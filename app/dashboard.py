
"""AIML-01 | Real-Time Fraud Detection Dashboard"""

import sys
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import db
from graph_rings import detect, evaluate


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Sentinel | Fraud Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --------------------------------------------------
# CUSTOM DARK FINTECH THEME
# --------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: #080d19;
    color: #e8edf7;
}

[data-testid="stSidebar"] {
    background: #0d1424;
    border-right: 1px solid #202b42;
}

[data-testid="stSidebar"] * {
    color: #dce6f7;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

h1, h2, h3 {
    color: #f1f5ff !important;
    font-weight: 700 !important;
}

p, label, span {
    color: #b8c5d9;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #131e32, #10192a);
    border: 1px solid #263957;
    padding: 20px;
    border-radius: 14px;
}

[data-testid="stMetricLabel"] {
    color: #9fb0ca !important;
}

[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-weight: 800;
}

[data-testid="stMetricDelta"] {
    color: #34d399 !important;
}

.stButton > button {
    background: #1769e0;
    color: white;
    border: none;
    border-radius: 9px;
    font-weight: 600;
    min-height: 40px;
}

.stButton > button:hover {
    background: #3185ff;
    color: white;
}

[data-testid="stDataFrame"] {
    border: 1px solid #263957;
    border-radius: 12px;
}

div[data-baseweb="select"] > div {
    background: #121d30;
    border-color: #30415e;
}

hr {
    border-color: #263957;
}

.hero {
    background: linear-gradient(110deg, #132744, #10203b 60%, #142c50);
    border: 1px solid #294a75;
    padding: 27px;
    border-radius: 17px;
    margin-bottom: 25px;
}

.hero-title {
    font-size: 27px;
    font-weight: 800;
    color: #ffffff;
}

.hero-subtitle {
    color: #a9c0e2;
    font-size: 13px;
    margin-top: 7px;
}

.section-label {
    color: #70aaff;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.status-pill {
    display: inline-block;
    padding: 6px 12px;
    background: #123a32;
    color: #52e0ae;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

conn = db.connect()

df = pd.read_sql("SELECT * FROM txns", conn)


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:
    st.markdown("## 🛡️ SENTINEL")
    st.caption("FRAUD INTELLIGENCE PLATFORM")

    st.divider()

    page = st.radio(
        "NAVIGATION",
        [
            "Overview",
            "Transactions",
            "Fraud Rings",
            "Model Analytics"
        ],
        label_visibility="visible"
    )

    st.divider()

    st.markdown("### System status")
    st.markdown(
        '<span class="status-pill">● MONITORING</span>',
        unsafe_allow_html=True
    )

    st.caption("AIML-01 | Fraud Detection Engine")
    st.caption("Real-time monitoring dashboard")


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.markdown("""
<div class="hero">
    <div class="section-label">FINANCIAL SECURITY / ANALYTICS</div>
    <div class="hero-title">Fraud Intelligence Center</div>
    <div class="hero-subtitle">
        Monitor suspicious transactions, investigate fraud cases,
        and analyze model performance.
    </div>
</div>
""", unsafe_allow_html=True)


if df.empty:
    st.warning(
        "No scored transactions available. "
        "Start the API and run stream_sim.py to generate transactions."
    )
    st.stop()


# --------------------------------------------------
# KPI METRICS
# --------------------------------------------------

total = len(df)
pending = int((df.status == "pending").sum())
blocked = int((df.decision == "block").sum())
fraud = int((df.status == "confirmed_fraud").sum())

p95 = float(df.latency_ms.quantile(0.95))

c1, c2, c3, c4 = st.columns(4)

c1.metric("TOTAL TRANSACTIONS", f"{total:,}")
c2.metric("PENDING REVIEW", f"{pending:,}")
c3.metric("BLOCKED TRANSACTIONS", f"{blocked:,}")
c4.metric("P95 LATENCY", f"{p95:.2f} ms")


st.divider()


# --------------------------------------------------
# OVERVIEW
# --------------------------------------------------

if page == "Overview":

    st.markdown("### Security Overview")
    st.caption("Current transaction monitoring statistics")

    left, right = st.columns(2)

    with left:
        st.markdown("#### Transaction Decisions")

        decision_counts = (
            df["decision"]
            .value_counts()
            .rename_axis("Decision")
            .to_frame("Transactions")
        )

        st.bar_chart(decision_counts)

    with right:
        st.markdown("#### Risk Score Distribution")

        risk_data = pd.cut(
            df["score"],
            bins=[-0.001, 0.02, 0.9, 1.0],
            labels=["Low Risk", "Medium Risk", "High Risk"]
        )

        risk_counts = (
            risk_data.value_counts()
            .reindex(["Low Risk", "Medium Risk", "High Risk"], fill_value=0)
            .to_frame("Transactions")
        )

        st.bar_chart(risk_counts)

    st.divider()

    st.markdown("#### Recent Transactions")

    recent = df.sort_values(
        "score", ascending=False
    ).head(10)

    st.dataframe(
        recent[
            [
                "txn_id",
                "account_id",
                "amount",
                "country",
                "score",
                "decision",
                "status"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# TRANSACTION INVESTIGATION
# --------------------------------------------------

elif page == "Transactions":

    st.markdown("### Transaction Investigation")

    q = df[df.status == "pending"].sort_values(
        "score", ascending=False
    )

    st.caption(f"{len(q)} transactions waiting for analyst review")

    if q.empty:
        st.success("No pending transactions. Review queue is clear.")

    else:
        case_map = q.set_index("txn_id")

        pick = st.selectbox(
            "Select a transaction",
            q.txn_id.head(200),
            format_func=lambda t: (
                f"{t} | Risk {case_map.loc[t, 'score']:.3f}"
            )
        )

        row = case_map.loc[pick]

        a, b = st.columns(2)

        with a:
            st.markdown("#### Transaction Details")

            st.write({
                "Transaction ID": pick,
                "Account ID": row["account_id"],
                "Device ID": row["device_id"],
                "Merchant Category": row["merchant_cat"],
                "Amount": row["amount"],
                "Country": row["country"],
                "Channel": row["channel"],
                "Decision": row["decision"]
            })

        with b:
            st.markdown("#### Risk Assessment")

            st.metric("Risk Score", f"{row['score']:.4f}")

            reasons = row["reasons"]

            if isinstance(reasons, str):
                reasons = json.loads(reasons)

            st.write("Why flagged:")
            st.write(", ".join(reasons) if reasons else "No reasons available")

        st.divider()

        x, y = st.columns(2)

        with x:
            if st.button("Confirm Fraud", type="primary", use_container_width=True):
                db.set_status(conn, pick, "confirmed_fraud")
                st.rerun()

        with y:
            if st.button("Dismiss False Positive", use_container_width=True):
                db.set_status(conn, pick, "dismissed")
                st.rerun()

    st.divider()

    st.markdown("#### Pending Case Queue")

    st.dataframe(
        q[
            [
                "txn_id",
                "account_id",
                "amount",
                "country",
                "score",
                "decision"
            ]
        ].head(100),
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# FRAUD RING DETECTION
# --------------------------------------------------

elif page == "Fraud Rings":

    st.markdown("### Fraud Ring Intelligence")

    st.caption(
        "Accounts connected through shared devices in flagged transactions."
    )

    rings, graph = detect(conn)

    if not rings:
        st.info("No fraud rings detected yet.")

    else:

        ring_data = pd.DataFrame([
            {
                **r,
                "accounts": len(r["accounts"]),
                "devices": len(r["devices"])
            }
            for r in rings
        ])

        st.dataframe(
            ring_data,
            use_container_width=True,
            hide_index=True
        )

        rid = st.selectbox(
            "Select fraud ring",
            [r["ring_id"] for r in rings]
        )

        ring = next(r for r in rings if r["ring_id"] == rid)

        sub = graph.subgraph(
            [f"acct:{a}" for a in ring["accounts"]]
            + [f"dev:{d}" for d in ring["devices"]]
        )

        fig, ax = plt.subplots(figsize=(10, 6))

        fig.patch.set_facecolor("#10192a")
        ax.set_facecolor("#10192a")

        pos = nx.spring_layout(sub, seed=1)

        nx.draw_networkx(
            sub,
            pos,
            ax=ax,
            node_size=650,
            font_size=8,
            font_color="white",
            node_color=[
                "#ef4444" if n.startswith("dev:") else "#2386ff"
                for n in sub.nodes()
            ],
            edge_color="#64748b",
            width=1.5
        )

        ax.axis("off")

        st.pyplot(fig)
        plt.close(fig)

        st.caption(
            "Blue nodes represent accounts. Red nodes represent devices."
        )

        evaluation = evaluate(conn, rings)

        if evaluation:
            st.write(
                "Simulation planted-ring evaluation:",
                evaluation
            )


# --------------------------------------------------
# MODEL ANALYTICS
# --------------------------------------------------

elif page == "Model Analytics":

    st.markdown("### Model Performance Analytics")

    metrics_path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "metrics.json"
    )

    if metrics_path.exists():

        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        display_metrics = {
            k: v for k, v in metrics.items()
            if k != "feature_importance(gain)"
        }

        st.markdown("#### Model Evaluation Metrics")
        st.json(display_metrics)

        importance = metrics.get("feature_importance(gain)", {})

        if importance:

            st.markdown("#### Feature Importance")

            importance_series = pd.Series(
                importance,
                dtype=float
            ).sort_values(ascending=True)

            st.bar_chart(importance_series)

    else:
        st.warning("Model metrics file not found.")

    st.divider()

    st.markdown("#### Scoring Latency")

    latency = df.latency_ms.quantile([0.5, 0.95, 0.99]).round(3)

    a, b, c = st.columns(3)

    a.metric("P50 Latency", f"{latency.loc[0.5]:.3f} ms")
    b.metric("P95 Latency", f"{latency.loc[0.95]:.3f} ms")
    c.metric("P99 Latency", f"{latency.loc[0.99]:.3f} ms")

    st.caption(
        "Latency values are server-side measurements from scored transactions."
    )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "SENTINEL FRAUD INTELLIGENCE | AIML-01 | "
    "Machine Learning Based Transaction Monitoring"
)
