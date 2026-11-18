"""Point-in-time-correct streaming features. The SAME class is used to build training data (by replaying history in
time order) and to score live transactions in the API, so there is no train/serve skew."""
from collections import defaultdict, deque
import math
import numpy as np

CATS = ["grocery", "fuel", "restaurant", "electronics", "travel", "gift_cards", "crypto", "utilities"]
CHANNELS = ["pos", "online", "atm"]
FEATURES = ["amount", "log_amount", "amt_zscore", "txn_1h", "txn_24h", "secs_since_last", "new_device",
            "device_n_accounts", "country_mismatch", "hour", "is_night", "cat", "channel", "acct_txn_count"]


class FeatureState:
    def __init__(self):
        self.ts = defaultdict(deque)            # account -> recent timestamps (24h window)
        self.n = defaultdict(int)               # Welford running stats of amount
        self.mean = defaultdict(float)
        self.m2 = defaultdict(float)
        self.devices = defaultdict(set)         # account -> devices used
        self.dev_accts = defaultdict(set)       # device -> accounts that used it
        self.home = {}                          # account -> first-seen country
        self.last = {}

    def features(self, t):
        """Compute features for txn dict `t` using ONLY past state, then update state."""
        a, ts, amt = t["account_id"], float(t["ts"]), float(t["amount"])
        dq = self.ts[a]
        while dq and dq[0] < ts - 86400:
            dq.popleft()
        n = self.n[a]
        sd = math.sqrt(self.m2[a] / (n - 1)) if n > 2 else 0.0
        z = (amt - self.mean[a]) / sd if sd > 0 else 0.0
        accts = self.dev_accts[t["device_id"]] | {a}
        f = [amt, math.log1p(amt), z, sum(1 for x in dq if x >= ts - 3600), len(dq),
             min(ts - self.last[a], 7 * 86400) if a in self.last else 7 * 86400,
             int(n > 0 and t["device_id"] not in self.devices[a]), len(accts),
             int(a in self.home and t["country"] != self.home[a]), int((ts // 3600) % 24), int(((ts // 3600) % 24) < 6),
             CATS.index(t["merchant_cat"]) if t["merchant_cat"] in CATS else -1,
             CHANNELS.index(t["channel"]) if t["channel"] in CHANNELS else -1, n]
        # ---- update ----
        dq.append(ts)
        self.n[a] = n + 1
        d = amt - self.mean[a]
        self.mean[a] += d / self.n[a]
        self.m2[a] += d * (amt - self.mean[a])
        self.devices[a].add(t["device_id"])
        self.dev_accts[t["device_id"]].add(a)
        self.home.setdefault(a, t["country"])
        self.last[a] = ts
        return np.array(f, dtype=np.float32)
