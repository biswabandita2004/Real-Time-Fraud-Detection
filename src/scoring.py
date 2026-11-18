"""Scoring core shared by the HTTP API and the Kafka worker: idempotency, model call, rule-based fallback."""
import hashlib
import json
import time
from pathlib import Path
import lightgbm as lgb
import numpy as np
from features import FEATURES


class InFlight(Exception):
    """Same txn_id is being processed right now by another worker."""


def file_version(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def rule_decision(x):
    """Used ONLY when the model call fails. Conservative: sends suspicious txns to review, never auto-blocks."""
    f = dict(zip(FEATURES, x))
    risky = f["amt_zscore"] > 4 or (f["new_device"] and f["device_n_accounts"] >= 3) or f["txn_1h"] >= 5
    return ("review" if risky else "approve"), (0.5 if risky else 0.0)


class Scorer:
    def __init__(self, model, thresholds, state, version="unknown"):
        self.model, self.thr, self.state, self.version = model, thresholds, state, version
        self.r = state.r

    @classmethod
    def from_files(cls, model_path, thresholds_path, state):
        return cls(lgb.Booster(model_file=str(model_path)), json.load(open(thresholds_path)), state, file_version(model_path))

    def _reasons(self, x):
        c = self.model.predict(x[None], pred_contrib=True)[0][:-1]
        return [f"{FEATURES[i]}={x[i]:.4g}" for i in np.argsort(-c)[:3] if c[i] > 0]

    def score(self, t):
        key = f"fs:txn:{t['txn_id']}"
        if not self.r.set(key, "pending", nx=True, ex=30):            # idempotency: never score or update state twice
            v = self.r.get(key)
            if v and v != "pending":
                return {**json.loads(v), "duplicate": True}
            raise InFlight(t["txn_id"])
        try:
            t0 = time.perf_counter()
            x = self.state.features(t)                                  # if the feature store is down this raises -> caller returns 503
            degraded = False
            try:
                p = float(self.model.predict(x[None])[0])
                decision = "block" if p >= self.thr["block"] else "review" if p >= self.thr["review"] else "approve"
                reasons = self._reasons(x) if decision != "approve" else []
            except Exception:
                degraded, (decision, p), reasons = True, rule_decision(x), ["model_unavailable:rule_fallback"]
            res = {"txn_id": t["txn_id"], "score": p, "decision": decision, "reasons": reasons, "degraded": degraded,
                   "model_version": self.version, "latency_ms": (time.perf_counter() - t0) * 1000, "duplicate": False}
        except Exception:
            self.r.delete(key)                                          # let the caller retry
            raise
        self.r.set(key, json.dumps(res), ex=86400)
        return res
