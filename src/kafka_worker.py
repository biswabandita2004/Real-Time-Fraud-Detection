"""Kafka consumer: transactions -> score -> scored (+ alerts for review/block, dead-letter for bad messages).
Run one process per partition you want to use:  python kafka_worker.py
Env: KAFKA_BOOTSTRAP (localhost:9092), REDIS_URL, IN_TOPIC=transactions, OUT_TOPIC=scored, ALERT_TOPIC=fraud-alerts, DLQ_TOPIC=transactions-dlq
IMPORTANT: the upstream producer must KEY messages by account_id so one account's txns stay ordered on one partition.
Delivery is at-least-once: offsets are committed only after the result is produced, and scoring is idempotent by txn_id.
Failure policy: infrastructure errors crash the process (supervisor restarts it) so uncommitted offsets are redelivered."""
import json
import logging
import os
import signal
import sys
from pydantic import ValidationError
import db
from schemas import Txn

log = logging.getLogger("worker")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def handle_message(scorer, raw: bytes):
    """Pure function (testable without Kafka). Returns (kind, payload) with kind in scored | dlq."""
    try:
        t = Txn.model_validate_json(raw)
    except ValidationError as e:
        return "dlq", {"error": "invalid_message", "detail": json.loads(e.json())[:3], "raw": raw[:500].decode("utf-8", "replace")}
    res = scorer.score(t.model_dump())
    return "scored", {"txn": t.model_dump(), "result": res}


def main():
    from confluent_kafka import Consumer, Producer
    import redis
    from scoring import Scorer
    from state_redis import RedisFeatureState
    from pathlib import Path
    art = Path(__file__).resolve().parents[1] / "artifacts"
    r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    scorer = Scorer.from_files(art / "model.txt", art / "thresholds.json", RedisFeatureState(r))
    conn = db.connect()
    in_t, out_t = os.getenv("IN_TOPIC", "transactions"), os.getenv("OUT_TOPIC", "scored")
    alert_t, dlq_t = os.getenv("ALERT_TOPIC", "fraud-alerts"), os.getenv("DLQ_TOPIC", "transactions-dlq")
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    consumer = Consumer({"bootstrap.servers": bootstrap, "group.id": "fraud-scorers", "enable.auto.commit": False,
                         "auto.offset.reset": "earliest", "max.poll.interval.ms": 60000})
    producer = Producer({"bootstrap.servers": bootstrap, "enable.idempotence": True, "acks": "all"})
    consumer.subscribe([in_t])
    running = {"go": True}
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda *_: running.update(go=False))
    log.info(json.dumps({"event": "worker_started", "model": scorer.version}))
    try:
        while running["go"]:
            msgs = consumer.consume(num_messages=100, timeout=0.5)
            if not msgs:
                continue
            for m in msgs:
                if m.error():
                    log.error(json.dumps({"event": "kafka_error", "err": str(m.error())}))
                    continue
                kind, payload = handle_message(scorer, m.value())
                if kind == "dlq":
                    producer.produce(dlq_t, json.dumps(payload).encode(), key=m.key())
                    continue
                res, t = payload["result"], payload["txn"]
                producer.produce(out_t, json.dumps(res).encode(), key=t["account_id"].encode())
                if res["decision"] != "approve":
                    producer.produce(alert_t, json.dumps({**res, "account_id": t["account_id"], "amount": t["amount"]}).encode(), key=t["account_id"].encode())
                if not res["duplicate"]:
                    db.insert(conn, {**t, "score": res["score"], "decision": res["decision"], "reasons": json.dumps(res["reasons"]),
                                     "status": "pending" if res["decision"] != "approve" else "auto_approved", "latency_ms": res["latency_ms"],
                                     "label_fraud": None, "label_ring": None})
            if producer.flush(10) > 0:                    # not everything delivered -> do NOT commit, crash and replay
                raise RuntimeError("producer flush timed out")
            consumer.commit(asynchronous=False)
    finally:
        consumer.close()
        log.info(json.dumps({"event": "worker_stopped"}))


if __name__ == "__main__":
    sys.exit(main())
