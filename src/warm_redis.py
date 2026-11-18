"""Seed Redis with historical state so live features have context (run once after a Redis wipe).
  python warm_redis.py --frac 0.8"""
import argparse
import os
import pandas as pd
import redis
from state_redis import RedisFeatureState

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="../data/transactions.parquet")
ap.add_argument("--frac", type=float, default=0.8)
a = ap.parse_args()
st = RedisFeatureState(redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True))
df = pd.read_parquet(a.data).sort_values("ts")
rows = df.iloc[:int(len(df) * a.frac)].to_dict("records")
for i, r in enumerate(rows):
    st.features(r)
    if i % 10000 == 0:
        print(i, "/", len(rows))
print("warmed", len(rows), "transactions")
