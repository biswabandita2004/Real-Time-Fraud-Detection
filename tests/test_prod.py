import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import fakeredis
import lightgbm as lgb
import numpy as np
import pytest
from fastapi.testclient import TestClient
from features import FeatureState, FEATURES, CATS, CHANNELS
from state_redis import RedisFeatureState
from scoring import Scorer
from api_prod import create_app
from kafka_worker import handle_message


def random_txns(n=400, seed=1):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        out.append(dict(txn_id=f"T{i}", ts=float(1000 + i * 700 + rng.integers(0, 600)), account_id=f"A{rng.integers(0, 15)}",
                        device_id=f"D{rng.integers(0, 12)}", merchant_id="M1", merchant_cat=str(rng.choice(CATS)),
                        amount=float(rng.lognormal(4, 1)), country=str(rng.choice(["IN", "US", "GB"], p=[.7, .2, .1])),
                        channel=str(rng.choice(CHANNELS))))
    return sorted(out, key=lambda t: t["ts"])


@pytest.fixture
def redis_():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture(scope="module")
def booster():
    rng = np.random.default_rng(0)
    X = rng.random((2000, len(FEATURES)))
    y = (X[:, 0] + rng.random(2000) * 0.2 > 0.9).astype(int)
    return lgb.train(dict(objective="binary", verbose=-1, num_leaves=7), lgb.Dataset(X, y, feature_name=FEATURES), 20)


def make_client(redis_, booster, keys=("secret",), sink=None):
    scorer = Scorer(booster, {"review": 0.3, "block": 0.9}, RedisFeatureState(redis_), "test-v1")
    rows = []
    app = create_app(scorer=scorer, api_keys=list(keys), sink=sink or rows.append)
    return TestClient(app), scorer, rows


def good(**kw):
    t = dict(txn_id="X1", ts=5000.0, account_id="A1", device_id="D1", merchant_id="M1", merchant_cat="grocery", amount=25.0, country="IN", channel="pos")
    t.update(kw)
    return t


def test_redis_features_match_in_memory_features(redis_):
    mem, rds = FeatureState(), RedisFeatureState(redis_)
    for t in random_txns():
        np.testing.assert_allclose(rds.features(t), mem.features(t), rtol=1e-4, atol=1e-4, err_msg=str(t))


def test_auth_required(redis_, booster):
    c, _, _ = make_client(redis_, booster)
    assert c.post("/v1/score", json=good()).status_code == 401
    assert c.post("/v1/score", json=good(), headers={"X-API-Key": "nope"}).status_code == 401
    assert c.post("/v1/score", json=good(), headers={"X-API-Key": "secret"}).status_code == 200


def test_refuses_to_start_without_keys(redis_, booster, monkeypatch):
    monkeypatch.delenv("ALLOW_NO_AUTH", raising=False)
    with pytest.raises(RuntimeError):
        create_app(scorer=Scorer(booster, {"review": .3, "block": .9}, RedisFeatureState(redis_)), api_keys=[], sink=lambda r: None)


@pytest.mark.parametrize("bad", [dict(amount=-5), dict(amount=0), dict(channel="fax"), dict(country="INDIA"), dict(txn_id=""), dict(extra_field=1)])
def test_validation_rejects_bad_input(redis_, booster, bad):
    c, _, _ = make_client(redis_, booster)
    assert c.post("/v1/score", json=good(**bad), headers={"X-API-Key": "secret"}).status_code == 422


def test_idempotent_by_txn_id(redis_, booster):
    c, _, rows = make_client(redis_, booster)
    h = {"X-API-Key": "secret"}
    a = c.post("/v1/score", json=good(), headers=h).json()
    b = c.post("/v1/score", json=good(), headers=h).json()
    assert a["duplicate"] is False and b["duplicate"] is True and a["score"] == b["score"]
    assert len(rows) == 1                                           # stored once
    assert redis_.hget("fs:a:A1", "n") == "1"                       # state updated once


def test_model_failure_falls_back_to_rules(redis_):
    class Broken:
        def predict(self, *a, **k):
            raise RuntimeError("boom")
    scorer = Scorer(Broken(), {"review": .3, "block": .9}, RedisFeatureState(redis_), "bad")
    res = scorer.score(good())
    assert res["degraded"] is True and res["decision"] in ("approve", "review")


def test_feature_store_down_returns_503(booster):
    class DeadRedis:
        def set(self, *a, **k):
            raise ConnectionError("redis down")
    scorer = Scorer(booster, {"review": .3, "block": .9}, RedisFeatureState(DeadRedis()), "v")
    c = TestClient(create_app(scorer=scorer, api_keys=["k"], sink=lambda r: None))
    assert c.post("/v1/score", json=good(), headers={"X-API-Key": "k"}).status_code == 503


def test_health_ready_metrics(redis_, booster):
    c, _, _ = make_client(redis_, booster)
    c.post("/v1/score", json=good(), headers={"X-API-Key": "secret"})
    assert c.get("/healthz").status_code == 200
    assert c.get("/readyz").json()["model_version"] == "test-v1"
    assert "fraud_decisions_total" in c.get("/metrics").text


def test_kafka_handler_valid_and_invalid(redis_, booster):
    _, scorer, _ = make_client(redis_, booster)
    kind, p = handle_message(scorer, json.dumps(good(txn_id="K1")).encode())
    assert kind == "scored" and p["result"]["txn_id"] == "K1"
    kind, p = handle_message(scorer, b'{"txn_id": "K2", "amount": "lots"}')
    assert kind == "dlq" and p["error"] == "invalid_message"
    kind, p = handle_message(scorer, b"not json")
    assert kind == "dlq"
