"""Hardened scoring API.   uvicorn api_prod:create_app --factory --host 0.0.0.0 --port 8100 --workers 2
Environment: API_KEYS (comma separated, REQUIRED), REDIS_URL, MODEL_PATH, THRESHOLDS_PATH, ALLOW_NO_AUTH=1 (dev only)
Endpoints: POST /v1/score | GET /healthz (liveness) | GET /readyz (Redis + model) | GET /metrics (Prometheus)"""
import hmac
import json
import logging
import os
import time
from pathlib import Path
import redis
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import db
from schemas import Txn
from scoring import InFlight, Scorer
from state_redis import RedisFeatureState

ART = Path(__file__).resolve().parents[1] / "artifacts"
log = logging.getLogger("fraud")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def make_sink():
    conn = db.connect()

    def sink(row):
        try:
            db.insert(conn, row)
        except Exception:
            log.exception(json.dumps({"event": "sink_failed", "txn_id": row.get("txn_id")}))
    return sink


def create_app(scorer=None, api_keys=None, sink=None):
    if scorer is None:
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True, socket_timeout=0.5)
        scorer = Scorer.from_files(os.getenv("MODEL_PATH", ART / "model.txt"), os.getenv("THRESHOLDS_PATH", ART / "thresholds.json"), RedisFeatureState(r))
    if api_keys is None:
        api_keys = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
    if not api_keys and os.getenv("ALLOW_NO_AUTH") != "1":
        raise RuntimeError("API_KEYS is empty. Refusing to start an unauthenticated scoring API (set ALLOW_NO_AUTH=1 for local dev).")
    sink = sink or make_sink()

    reg = CollectorRegistry()
    m_dec = Counter("fraud_decisions_total", "Decisions", ["decision"], registry=reg)
    m_err = Counter("fraud_errors_total", "Errors", ["kind"], registry=reg)
    m_deg = Counter("fraud_degraded_total", "Rule-fallback decisions", registry=reg)
    m_lat = Histogram("fraud_score_latency_seconds", "Scoring latency", buckets=(.001, .0025, .005, .01, .025, .05, .1, .25), registry=reg)

    def auth(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
        if api_keys and not (x_api_key and any(hmac.compare_digest(x_api_key, k) for k in api_keys)):
            raise HTTPException(401, "invalid or missing API key")

    app = FastAPI(title="Fraud scoring", version=scorer.version)

    @app.post("/v1/score", dependencies=[Depends(auth)])
    def score(t: Txn, bg: BackgroundTasks):
        try:
            res = scorer.score(t.model_dump())
        except InFlight:
            m_err.labels("in_flight").inc()
            raise HTTPException(409, "transaction is already being processed")
        except Exception:
            m_err.labels("unavailable").inc()
            log.exception(json.dumps({"event": "score_failed", "txn_id": t.txn_id}))
            raise HTTPException(503, "scoring unavailable, retry")
        if not res["duplicate"]:
            m_dec.labels(res["decision"]).inc()
            m_lat.observe(res["latency_ms"] / 1000)
            if res["degraded"]:
                m_deg.inc()
            bg.add_task(sink, {**t.model_dump(), "score": res["score"], "decision": res["decision"], "reasons": json.dumps(res["reasons"]),
                               "status": "pending" if res["decision"] != "approve" else "auto_approved", "latency_ms": res["latency_ms"],
                               "label_fraud": None, "label_ring": None})
        log.info(json.dumps({"event": "scored", "txn_id": t.txn_id, "decision": res["decision"], "score": round(res["score"], 4),
                             "ms": round(res["latency_ms"], 2), "model": res["model_version"], "duplicate": res["duplicate"]}))
        return res

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/readyz")
    def readyz():
        try:
            scorer.r.ping()
        except Exception:
            raise HTTPException(503, "redis unavailable")
        return {"ok": True, "model_version": scorer.version, "thresholds": scorer.thr}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(reg), media_type=CONTENT_TYPE_LATEST)

    return app
