import sqlite3
import threading
from pathlib import Path

import os
DB_PATH = Path(os.getenv("CASES_DB", Path(__file__).resolve().parents[1] / "artifacts" / "cases.db"))
_lock = threading.Lock()
SCHEMA = """CREATE TABLE IF NOT EXISTS txns (
  txn_id TEXT PRIMARY KEY, ts REAL, account_id TEXT, device_id TEXT, merchant_id TEXT, merchant_cat TEXT, amount REAL,
  country TEXT, channel TEXT, score REAL, decision TEXT, reasons TEXT, status TEXT, latency_ms REAL,
  label_fraud INTEGER, label_ring INTEGER)"""


def connect(path=DB_PATH):
    c = sqlite3.connect(path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")      # readers (dashboard) do not block the writer
    c.execute("PRAGMA busy_timeout=5000")
    c.execute(SCHEMA)
    return c


def insert(conn, row):
    with _lock:
        conn.execute("INSERT OR REPLACE INTO txns VALUES (:txn_id,:ts,:account_id,:device_id,:merchant_id,:merchant_cat,:amount,:country,"
                     ":channel,:score,:decision,:reasons,:status,:latency_ms,:label_fraud,:label_ring)", row)
        conn.commit()


def set_status(conn, txn_id, status):
    with _lock:
        conn.execute("UPDATE txns SET status=? WHERE txn_id=?", (status, txn_id))
        conn.commit()
