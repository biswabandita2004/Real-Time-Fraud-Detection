"""Analyst dashboard.  From project root:  streamlit run app/dashboard.py
Needs artifacts/cases.db (created by the API + stream_sim.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import streamlit as st
import db
from graph_rings import detect, evaluate

conn = db.connect()
st.set_page_config(page_title="Fraud analyst console", layout="wide")
st.title("Fraud analyst console")
df = pd.read_sql("SELECT * FROM txns", conn)
if df.empty:
    st.warning("No scored transactions yet. Start the API and run stream_sim.py.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Scored transactions", f"{len(df):,}")
c2.metric("Pending review", int((df.status == "pending").sum()))
c3.metric("Blocked", int((df.decision == "block").sum()))
c4.metric("p95 scoring latency (ms)", f"{df.latency_ms.quantile(.95):.2f}")
tab1, tab2, tab3 = st.tabs(["Case queue", "Fraud rings", "Model & latency"])

with tab1:
    q = df[df.status == "pending"].sort_values("score", ascending=False)
    st.caption(f"{len(q)} cases awaiting review, highest risk first")
    if q.empty:
        st.success("Queue is empty.")
    else:
        pick = st.selectbox("Case", q.txn_id.head(200), format_func=lambda t: f"{t} | risk {q.set_index('txn_id').loc[t,'score']:.2f}")
        row = q.set_index("txn_id").loc[pick]
        a, b = st.columns(2)
        a.write({k: row[k] for k in ["account_id", "device_id", "merchant_cat", "amount", "country", "channel", "decision"]})
        b.metric("Risk score", f"{row['score']:.3f}")
        b.write("Why flagged: " + (", ".join(json.loads(row["reasons"])) or "n/a"))
        x, y = st.columns(2)
        if x.button("Confirm fraud", type="primary"):
            db.set_status(conn, pick, "confirmed_fraud"); st.rerun()
        if y.button("Dismiss (false positive)"):
            db.set_status(conn, pick, "dismissed"); st.rerun()
    st.dataframe(q[["txn_id", "account_id", "amount", "country", "score", "decision"]].head(100), hide_index=True)

with tab2:
    rings, g = detect(conn)
    st.caption("Accounts linked through shared devices in flagged transactions (connected components, >= 3 accounts)")
    if not rings:
        st.info("No rings detected yet.")
    else:
        st.dataframe(pd.DataFrame([{**r, "accounts": len(r["accounts"]), "devices": len(r["devices"])} for r in rings]), hide_index=True)
        rid = st.selectbox("Inspect ring", [r["ring_id"] for r in rings])
        r = rings[rid]
        sub = g.subgraph([f"acct:{a}" for a in r["accounts"]] + [f"dev:{d}" for d in r["devices"]])
        fig, ax = plt.subplots(figsize=(6, 4))
        pos = nx.spring_layout(sub, seed=1)
        nx.draw_networkx(sub, pos, ax=ax, node_size=300, font_size=6,
                         node_color=["tab:red" if n.startswith("dev:") else "tab:blue" for n in sub.nodes()])
        ax.axis("off")
        st.pyplot(fig)
        ev = evaluate(conn, rings)
        if ev:
            st.write("Check against planted rings (simulation only):", ev)

with tab3:
    m = Path(__file__).resolve().parents[1] / "artifacts" / "metrics.json"
    if m.exists():
        st.json({k: v for k, v in json.load(open(m)).items() if k != "feature_importance(gain)"})
        st.bar_chart(pd.Series(json.load(open(m))["feature_importance(gain)"]))
    st.write("Scoring latency percentiles (ms, server-side):", df.latency_ms.quantile([.5, .95, .99]).round(3).to_dict())
