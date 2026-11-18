"""Synthetic card-transaction generator with planted fraud rings (so ring detection can be scored).
For a more 'real' dataset swap in PaySim/Kaggle credit-card data and keep the same column names:
txn_id, ts, account_id, device_id, merchant_id, merchant_cat, amount, country, channel, is_fraud, ring_id."""
import argparse
import numpy as np
import pandas as pd

CATS = ["grocery", "fuel", "restaurant", "electronics", "travel", "gift_cards", "crypto", "utilities"]
CHANNELS = ["pos", "online", "atm"]
COUNTRIES = ["IN", "US", "GB", "SG", "AE"]


def generate(n_accounts=3000, n_txn=120_000, n_rings=15, seed=7, days=30):
    rng = np.random.default_rng(seed)
    acc = np.array([f"A{i:05d}" for i in range(n_accounts)])
    home = rng.choice(COUNTRIES, n_accounts, p=[.8, .08, .05, .04, .03])
    avg_amt = rng.lognormal(3.8, 0.5, n_accounts)
    # each legit account has 1 device; ~4% of devices are shared by a family (noise for ring detection)
    dev = np.array([f"D{i:05d}" for i in range(n_accounts)])
    share = rng.random(n_accounts) < 0.04
    dev[share] = dev[np.maximum(np.arange(n_accounts)[share] - 1, 0)]
    merchants = np.array([f"M{i:04d}" for i in range(400)])
    merch_cat = rng.choice(CATS, 400, p=[.25, .12, .2, .1, .08, .05, .05, .15])

    a = rng.integers(0, n_accounts, n_txn)
    t = rng.uniform(0, days * 86400, n_txn)
    hour = ((t // 3600) % 24)
    m = rng.integers(0, 400, n_txn)
    amount = rng.lognormal(np.log(avg_amt[a]), 0.6)
    country = np.where(rng.random(n_txn) < 0.97, home[a], rng.choice(COUNTRIES, n_txn))
    df = pd.DataFrame({"ts": t, "account_id": acc[a], "device_id": dev[a], "merchant_id": merchants[m], "merchant_cat": merch_cat[m],
                       "amount": amount.round(2), "country": country, "channel": rng.choice(CHANNELS, n_txn, p=[.5, .45, .05]),
                       "is_fraud": 0, "ring_id": -1})

    # ---- planted rings: 4-9 accounts sharing 1-2 devices, bursts of high-value night-time foreign txns ----
    extra, ring_rows = 0, []
    for r in range(n_rings):
        members = rng.choice(n_accounts, rng.integers(4, 10), replace=False)
        ring_devs = [f"RD{r:03d}_{k}" for k in range(rng.integers(1, 3))]
        start = rng.uniform(0, (days - 2) * 86400)
        for acct in members:
            for _ in range(rng.integers(3, 8)):
                ts = start + rng.uniform(0, 36 * 3600)
                ring_rows.append({"ts": ts, "account_id": acc[acct], "device_id": rng.choice(ring_devs),
                                  "merchant_id": rng.choice(merchants[merch_cat == "gift_cards"] if (merch_cat == "gift_cards").any() else merchants),
                                  "merchant_cat": rng.choice(["gift_cards", "crypto", "electronics"]),
                                  "amount": round(float(rng.lognormal(6.0, 0.4)), 2), "country": rng.choice(["US", "AE", "SG"]),
                                  "channel": "online", "is_fraud": 1, "ring_id": r})
    # ---- lone fraudsters (no ring): stolen card used abroad at odd hours ----
    for _ in range(int(n_txn * 0.004)):
        acct = rng.integers(0, n_accounts)
        ring_rows.append({"ts": rng.uniform(0, days * 86400), "account_id": acc[acct], "device_id": f"X{rng.integers(0, 10**6):06d}",
                          "merchant_id": rng.choice(merchants), "merchant_cat": rng.choice(["electronics", "crypto", "travel"]),
                          "amount": round(float(rng.lognormal(5.5, 0.6)), 2), "country": rng.choice(["US", "AE", "GB"]),
                          "channel": "online", "is_fraud": 1, "ring_id": -1})
    df = pd.concat([df, pd.DataFrame(ring_rows)], ignore_index=True).sort_values("ts").reset_index(drop=True)
    df.insert(0, "txn_id", [f"T{i:07d}" for i in range(len(df))])
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../data/transactions.parquet")
    a = ap.parse_args()
    d = generate()
    d.to_parquet(a.out, index=False)
    print(f"{len(d):,} txns | fraud rate {d.is_fraud.mean():.2%} | ring txns {(d.ring_id >= 0).sum()} | rings {d.ring_id.max() + 1}")
