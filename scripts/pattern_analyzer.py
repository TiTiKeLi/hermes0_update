#!/usr/bin/env python3
"""L3-C: Pattern Analyzer - runs every 12h."""
import sqlite3, json, os, time
from collections import Counter

DB = "/opt/data/memory_store.db"
SESS = "/opt/data/sessions"

def extract_entities():
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cur.execute("SELECT entity, COUNT(*) as c FROM facts WHERE archived=0 AND entity IS NOT NULL AND entity != '' GROUP BY entity HAVING c > 10")
    res = [{"entity": r[0], "count": r[1]} for r in cur.fetchall()]
    conn.close(); return res

def write_result(items):
    conn = sqlite3.connect(DB); cur = conn.cursor()
    for item in items:
        entity = item["entity"] or "unnamed"
        cur.execute("INSERT INTO facts (content,entity,tags,trust_score) VALUES (?,?,?,?)",
            ("[auto] entity "+entity+" appears "+str(item["count"])+" times, review recommended",
             "pattern:"+entity, "auto,pattern,review", 0.3))
    conn.commit(); conn.close()

if __name__ == "__main__":
    hf = extract_entities()
    if hf:
        write_result(hf)
        print(f"wrote {len(hf)} patterns to L2")
    else:
        print("no high-frequency entities")
