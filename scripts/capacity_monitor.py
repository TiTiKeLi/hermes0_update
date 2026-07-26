#!/usr/bin/env python3
"""P2: Capacity Monitor - checks L1/L2/L4 usage."""
import sqlite3, os, json

MEMORY_MD = "/opt/data/MEMORY.md"
SESSIONS_DIR = "/opt/data/sessions"
DB = "/opt/data/memory_store.db"
LOG = "/opt/data/logs/capacity_monitor.log"

LIMITS = {
    "l1_sessions_gb": 2.0,
    "l2_facts_soft": 3000,
    "l2_facts_hard": 5000,
    "l2_history_gb": 1.0,
    "l2_history_force_gb": 1.5,
    "l4_chars": 2000,
    "l4_emergency_chars": 1800,
}

def get_l1_size_mb():
    total = 0
    for root, dirs, files in os.walk(SESSIONS_DIR):
        for f in files:
            try: total += os.path.getsize(os.path.join(root, f))
            except: pass
    return total / (1024*1024)

def get_l2_stats():
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM facts WHERE archived=0")
    active = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM facts WHERE archived=1")
    archived = cur.fetchone()[0]
    conn.close()
    return active, archived

def get_l4_chars():
    try: return len(open(MEMORY_MD).read())
    except: return 0

def log_alarm(msg):
    with open(LOG, "a") as f:
        f.write(f"[ALARM] {msg}\n")
    print(f"[ALARM] {msg}")

if __name__ == "__main__":
    alarms = []
    l1 = get_l1_size_mb()
    if l1 > LIMITS["l1_sessions_gb"] * 1024:
        alarms.append(f"L1 > {LIMITS['l1_sessions_gb']}GB ({l1:.0f}MB) - transfer sessions")
    active, archived = get_l2_stats()
    if active > LIMITS["l2_facts_hard"]:
        alarms.append(f"L2 active > {LIMITS['l2_facts_hard']} ({active}) - emergency compress")
    elif active > LIMITS["l2_facts_soft"]:
        alarms.append(f"L2 active > {LIMITS['l2_facts_soft']} ({active}) - compress")
    l4 = get_l4_chars()
    if l4 > LIMITS["l4_chars"]:
        alarms.append(f"L4 > {LIMITS['l4_chars']} chars ({l4}) - emergency evict")
    elif l4 > LIMITS["l4_emergency_chars"]:
        alarms.append(f"L4 > {LIMITS['l4_emergency_chars']} chars ({l4}) - evict soon")
    if alarms:
        for a in alarms: log_alarm(a)
    else:
        print(f"OK - L1:{l1:.0f}MB L2:{active}a/{archived}arc L4:{l4}c")
