#!/usr/bin/env python3
"""L3-A: Dead Loop Detector - runs every 6h."""
import sqlite3, json, os, time
from collections import Counter

DB = "/opt/data/memory_store.db"
SESS = "/opt/data/sessions"


def get_kws(hours=48):
    kws = []
    cut = time.time() - hours * 3600
    for f in os.listdir(SESS):
        fp = os.path.join(SESS, f)
        if not f.endswith(".json") or os.path.getmtime(fp) < cut:
            continue
        try:
            d = json.load(open(fp))
            c = d.get("content", "") or json.dumps(d)
            kws.extend(c.split())
        except:
            pass
    return [k for k, c in Counter(kws).most_common(20) if c >= 3]


def check_fix(kws):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    found = []
    for kw in kws:
        for r in cur.execute(
            "SELECT fact_id FROM facts WHERE content LIKE ? AND archived=0",
            ("%" + kw + "%fix%",),
        ):
            found.append({"fact_id": r[0], "keyword": kw})
    conn.close()
    return found


def archive(recs):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    for r in recs:
        cur.execute("UPDATE facts SET archived=1 WHERE fact_id=?", (r["fact_id"],))
        cur.execute(
            "INSERT INTO facts (content,entity,tags,trust_score) VALUES (?,?,?,?)",
            (
                "[auto] " + r["keyword"] + " old fix archived",
                "deadloop:" + r["keyword"],
                "deadloop,reframed",
                0.6,
            ),
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    kws = get_kws()
    if not kws:
        print("no dead loops")
        exit(0)
    recs = check_fix(kws)
    if recs:
        archive(recs)
        print(f"archived {len(recs)} loops, reframed")
    else:
        print(f"found {len(kws)} repeats, no fix records")
