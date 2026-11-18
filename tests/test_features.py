import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from features import FeatureState, FEATURES


def txn(ts, acct="A1", dev="D1", amt=50.0, country="IN"):
    return dict(account_id=acct, device_id=dev, ts=ts, amount=amt, country=country, merchant_cat="grocery", channel="pos")


def test_feature_length():
    assert len(FeatureState().features(txn(0))) == len(FEATURES)


def test_no_future_leakage_and_velocity():
    s = FeatureState()
    f1 = s.features(txn(0))
    f2 = s.features(txn(60))
    assert f1[FEATURES.index("txn_1h")] == 0       # first txn sees no history
    assert f2[FEATURES.index("txn_1h")] == 1


def test_shared_device_counts_accounts():
    s = FeatureState()
    s.features(txn(0, acct="A1", dev="SHARED"))
    f = s.features(txn(10, acct="A2", dev="SHARED"))
    assert f[FEATURES.index("device_n_accounts")] == 2


def test_new_device_and_country_flags():
    s = FeatureState()
    s.features(txn(0))
    f = s.features(txn(10, dev="D2", country="US"))
    assert f[FEATURES.index("new_device")] == 1 and f[FEATURES.index("country_mismatch")] == 1
