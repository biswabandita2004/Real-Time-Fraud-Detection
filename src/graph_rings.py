"""Link suspicious accounts into fraud rings: bipartite graph account<->device (and merchant) built ONLY from
flagged transactions; connected components with >= MIN_ACCOUNTS accounts are candidate rings."""
import json
import sys
import networkx as nx
import db

MIN_ACCOUNTS = 3


def detect(conn, min_accounts=MIN_ACCOUNTS):
    rows = conn.execute("SELECT * FROM txns WHERE decision != 'approve'").fetchall()
    g = nx.Graph()
    for r in rows:
        a, d = f"acct:{r['account_id']}", f"dev:{r['device_id']}"
        g.add_edge(a, d)
    rings = []
    for comp in nx.connected_components(g):
        accts = sorted(n[5:] for n in comp if n.startswith("acct:"))
        if len(accts) < min_accounts:
            continue
        devs = sorted(n[4:] for n in comp if n.startswith("dev:"))
        tx = [r for r in rows if r["account_id"] in accts]
        rings.append({"accounts": accts, "devices": devs, "n_flagged_txns": len(tx), "total_amount": round(sum(r["amount"] for r in tx), 2),
                      "max_score": round(max(r["score"] for r in tx), 3)})
    rings.sort(key=lambda r: -r["total_amount"])
    for i, r in enumerate(rings):
        r["ring_id"] = i
    return rings, g


def evaluate(conn, rings):
    """Compare with planted rings (only possible because the simulator sends ground-truth labels)."""
    truth = {}
    for r in conn.execute("SELECT DISTINCT account_id, label_ring FROM txns WHERE label_ring >= 0"):
        truth.setdefault(r["label_ring"], set()).add(r["account_id"])
    if not truth:
        return None
    found = [set(r["accounts"]) for r in rings]
    caught = sum(any(len(t & f) / len(t) >= 0.5 for f in found) for t in truth.values())
    true_members = set().union(*truth.values())
    pure = sum(len(f & true_members) for f in found) / max(sum(len(f) for f in found), 1)
    return {"planted_rings": len(truth), "rings_recovered(>=50% members in one component)": caught,
            "ring_recall": caught / len(truth), "member_precision": pure, "detected_components": len(found)}


if __name__ == "__main__":
    conn = db.connect()
    rings, _ = detect(conn)
    out = {"rings": rings, "eval": evaluate(conn, rings)}
    json.dump(out, open(db.DB_PATH.parent / "rings.json", "w"), indent=2)
    print(f"{len(rings)} candidate rings"); print(json.dumps(out["eval"], indent=2))
