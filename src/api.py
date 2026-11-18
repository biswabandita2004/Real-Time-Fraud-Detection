"""Real-time scoring API.  uvicorn api:app --port 8100   (run from src/)
POST /score  {txn_id, ts, account_id, device_id, merchant_id, merchant_cat, amount, country, channel}
-> {score, decision: approve|review|block, reasons, latency_ms}"""
import json
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel
import db
from features import FeatureState, FEATURES

ART = Path(__file__).resolve().parents[1] / "artifacts"
DATA = Path(os.getenv("TXN_DATA", Path(__file__).resolve().parents[1] / "data" / "transactions.parquet"))
WARM_FRAC = float(os.getenv("WARM_FRAC", "0.8"))      # replay the first 80% of history so live features have context

state = FeatureState()
lock = threading.Lock()
model = lgb.Booster(model_file=str(ART / "model.txt"))
thr = json.load(open(ART / "thresholds.json"))
conn = db.connect()


@asynccontextmanager
async def lifespan(app):
    if DATA.exists() and WARM_FRAC > 0:
        df = pd.read_parquet(DATA).sort_values("ts")
        for r in df.iloc[:int(len(df) * WARM_FRAC)].to_dict("records"):
            state.features(r)
    yield

app = FastAPI(title="Fraud scoring", lifespan=lifespan)


class Txn(BaseModel):
    txn_id: str
    ts: float
    account_id: str
    device_id: str
    merchant_id: str = ""
    merchant_cat: str
    amount: float
    country: str
    channel: str
    label_fraud: int | None = None      # simulator only: ground truth for evaluation
    label_ring: int | None = None


def reasons_for(x):
    contrib = model.predict(x[None], pred_contrib=True)[0][:-1]
    top = np.argsort(-contrib)[:3]
    return [f"{FEATURES[i]}={x[i]:.4g}" for i in top if contrib[i] > 0]


@app.get("/health")
def health():
    return {"ok": True, "thresholds": thr, "accounts_in_state": len(state.n)}


@app.post("/score")
def score(t: Txn):
    t0 = time.perf_counter()
    with lock:                                   # per-process state must be updated in time order
        x = state.features(t.model_dump())
    p = float(model.predict(x[None])[0])
    decision = "block" if p >= thr["block"] else "review" if p >= thr["review"] else "approve"
    reasons = reasons_for(x) if decision != "approve" else []
    ms = (time.perf_counter() - t0) * 1000
    row = {**t.model_dump(), "score": p, "decision": decision, "reasons": json.dumps(reasons),
           "status": "pending" if decision != "approve" else "auto_approved", "latency_ms": ms}
    db.insert(conn, row)
    return {"txn_id": t.txn_id, "score": p, "decision": decision, "reasons": reasons, "latency_ms": ms}
