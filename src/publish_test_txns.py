"""Publish the held-out transactions to Kafka (keyed by account_id) to drive kafka_worker.py.
  python publish_test_txns.py --n 5000"""
import argparse
import json
import os
import pandas as pd
from confluent_kafka import Producer

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="../data/transactions.parquet")
ap.add_argument("--n", type=int, default=5000)
a = ap.parse_args()
df = pd.read_parquet(a.data).sort_values("ts")
test = df.iloc[int(len(df) * .8):].head(a.n)
p = Producer({"bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")})
cols = ["txn_id", "ts", "account_id", "device_id", "merchant_id", "merchant_cat", "amount", "country", "channel"]
for r in test.to_dict("records"):
    p.produce("transactions", json.dumps({c: r[c] for c in cols}).encode(), key=r["account_id"].encode())
    p.poll(0)
p.flush()
print("published", len(test))
