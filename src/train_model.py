"""Replay history through FeatureState, split BY TIME, train LightGBM, pick a cost-based threshold on validation."""
import json
import argparse
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score
from features import FeatureState, FEATURES

REVIEW_COST = 5.0     # cost of an analyst reviewing one flagged txn (assumption - tune with your team)

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="../data/transactions.parquet")
ap.add_argument("--art", default="../artifacts")
a = ap.parse_args()

df = pd.read_parquet(a.data).sort_values("ts").reset_index(drop=True)
st = FeatureState()
X = np.stack([st.features(r) for r in df.to_dict("records")])
y = df.is_fraud.to_numpy()
n = len(df)
i1, i2 = int(n * .6), int(n * .8)
Xtr, ytr, Xva, yva, Xte, yte = X[:i1], y[:i1], X[i1:i2], y[i1:i2], X[i2:], y[i2:]
amt_va, amt_te = df.amount.to_numpy()[i1:i2], df.amount.to_numpy()[i2:]

params = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_child_samples=20, feature_fraction=0.9,
              scale_pos_weight=max(1.0, (ytr == 0).sum() / max(ytr.sum(), 1)) ** 0.5, verbose=-1, seed=0)
model = lgb.train(params, lgb.Dataset(Xtr, ytr, feature_name=FEATURES), num_boost_round=400,
                  valid_sets=[lgb.Dataset(Xva, yva)], callbacks=[lgb.early_stopping(30, verbose=False)])


def cost(p, yy, amt, t):
    flag = p >= t
    return float(((~flag) & (yy == 1)).dot(amt) + REVIEW_COST * flag.sum())      # missed fraud costs the amount


pva = model.predict(Xva)
grid = np.linspace(0.02, 0.98, 49)
t_review = float(grid[np.argmin([cost(pva, yva, amt_va, t) for t in grid])])
t_block = float(max(0.9, t_review))

pte = model.predict(Xte)
flag = pte >= t_review
res = {"n_train": int(i1), "n_val": int(i2 - i1), "n_test": int(n - i2), "test_fraud_rate": float(yte.mean()),
       "roc_auc": float(roc_auc_score(yte, pte)), "pr_auc": float(average_precision_score(yte, pte)),
       "baseline_pr_auc(random)": float(yte.mean()),
       "threshold_review": t_review, "threshold_block": t_block,
       "precision@review": float(precision_score(yte, flag)), "recall@review": float(recall_score(yte, flag)),
       "flag_rate": float(flag.mean()), "cost_with_model": cost(pte, yte, amt_te, t_review),
       "cost_no_model": float(amt_te[yte == 1].sum()),
       "feature_importance(gain)": dict(sorted(zip(FEATURES, map(float, model.feature_importance("gain"))), key=lambda x: -x[1]))}
model.save_model(f"{a.art}/model.txt")
json.dump({"review": t_review, "block": t_block}, open(f"{a.art}/thresholds.json", "w"))
json.dump(res, open(f"{a.art}/metrics.json", "w"), indent=2)
print(json.dumps({k: v for k, v in res.items() if k != "feature_importance(gain)"}, indent=2))
print("top features:", list(res["feature_importance(gain)"])[:5])
