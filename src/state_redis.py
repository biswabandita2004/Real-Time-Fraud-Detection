"""Redis-backed feature state: same features as features.FeatureState (a test proves they match), but shared by every
API worker / Kafka consumer and it survives restarts. Use a Redis with persistence (appendonly yes)."""
import math
import time
import uuid
from contextlib import contextmanager
import numpy as np
from features import CATS, CHANNELS

TTL = 30 * 86400


class RedisFeatureState:
    def __init__(self, r):
        self.r = r                      # redis.Redis(decode_responses=True)

    @contextmanager
    def _locked(self, account, wait=2.0):
        """Per-account lock so two concurrent txns of one account cannot read stale state.
        (Simple SET NX lock; acceptable for this load. For strict guarantees use Redlock or a Lua script.)"""
        key, token, end = f"fs:lock:{account}", uuid.uuid4().hex, time.time() + wait
        while not self.r.set(key, token, nx=True, px=3000):
            if time.time() > end:
                raise TimeoutError(f"lock timeout for account {account}")
            time.sleep(0.002)
        try:
            yield
        finally:
            if self.r.get(key) == token:
                self.r.delete(key)

    def features(self, t):
        a, d, ts, amt = t["account_id"], t["device_id"], float(t["ts"]), float(t["amount"])
        ka, kts, kdev, kd = f"fs:a:{a}", f"fs:a:{a}:ts", f"fs:a:{a}:dev", f"fs:d:{d}"
        with self._locked(a):
            p = self.r.pipeline(transaction=False)
            p.hgetall(ka)
            p.zremrangebyscore(kts, "-inf", f"({ts - 86400}")
            p.zcount(kts, ts - 3600, "+inf")
            p.zcard(kts)
            p.sismember(kdev, d)
            p.smembers(kd)
            h, _, c1h, c24h, has_dev, dev_accts = p.execute()
            n = int(h.get("n", 0))
            mean, m2 = float(h.get("mean", 0.0)), float(h.get("m2", 0.0))
            sd = math.sqrt(m2 / (n - 1)) if n > 2 else 0.0
            z = (amt - mean) / sd if sd > 0 else 0.0
            hour = (ts // 3600) % 24
            f = [amt, math.log1p(amt), z, c1h, c24h,
                 min(ts - float(h["last"]), 7 * 86400) if "last" in h else 7 * 86400,
                 int(n > 0 and not has_dev), len(set(dev_accts) | {a}),
                 int("home" in h and t["country"] != h["home"]), int(hour), int(hour < 6),
                 CATS.index(t["merchant_cat"]) if t["merchant_cat"] in CATS else -1,
                 CHANNELS.index(t["channel"]) if t["channel"] in CHANNELS else -1, n]
            # ---- update (one atomic MULTI/EXEC) ----
            n1 = n + 1
            delta = amt - mean
            mean += delta / n1
            m2 += delta * (amt - mean)
            fields = {"n": n1, "mean": repr(mean), "m2": repr(m2), "last": repr(ts)}
            if "home" not in h:
                fields["home"] = t["country"]
            w = self.r.pipeline(transaction=True)
            w.zadd(kts, {f"{ts!r}:{n}": ts})
            w.hset(ka, mapping=fields)
            w.sadd(kdev, d)
            w.sadd(kd, a)
            for k in (ka, kts, kdev, kd):
                w.expire(k, TTL)
            w.execute()
        return np.array(f, dtype=np.float32)
