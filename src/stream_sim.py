
"""Replay held-out transactions against the fraud scoring API."""

import argparse
import time
import os
import httpx
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8100")
ap.add_argument("--data", default="data/transactions.parquet")
ap.add_argument("--n", type=int, default=5000)
a = ap.parse_args()

api_key = os.getenv("API_KEY")
if not api_key:
    raise RuntimeError("API_KEY environment variable is not set.")

df = pd.read_parquet(a.data).sort_values("ts")
test = df.iloc[int(len(df) * 0.8):]

# Include fraud rows and up to n legitimate rows.
test = pd.concat([
    test[test.is_fraud == 1],
    test[test.is_fraud == 0].head(a.n)
]).sort_values("ts")

lat_e2e, lat_srv = [], []
counts = {"approve": 0, "flagged": 0}

headers = {"X-API-Key": api_key}

with httpx.Client(
    base_url=a.url,
    timeout=30,
    headers=headers
) as c:
    for r in test.to_dict("records"):
        payload = {
            k: r[k] for k in [
                "txn_id", "ts", "account_id", "device_id",
                "merchant_id", "merchant_cat", "amount",
                "country", "channel"
            ]
        }

        t0 = time.perf_counter()
        response = c.post("/v1/score", json=payload)
        response.raise_for_status()
        res = response.json()

        if "latency_ms" not in res:
            raise RuntimeError(f"API response missing latency_ms: {res}")

        lat_e2e.append((time.perf_counter() - t0) * 1000)
        lat_srv.append(res["latency_ms"])

        decision = res.get("decision", "approve")
        counts["flagged" if decision != "approve" else "approve"] += 1

pct = lambda values, q: float(np.percentile(values, q))

print(
    f"{len(lat_e2e)} transactions | "
    f"Server latency p50={pct(lat_srv, 50):.2f} ms "
    f"p95={pct(lat_srv, 95):.2f} ms "
    f"p99={pct(lat_srv, 99):.2f} ms | "
    f"HTTP latency p50={pct(lat_e2e, 50):.2f} ms "
    f"p95={pct(lat_e2e, 95):.2f} ms | "
    f"Flagged={counts['flagged']} | "
    f"Approved={counts['approve']}"
)
