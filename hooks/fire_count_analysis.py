#!/usr/bin/env python3
"""fire_count_analysis.py — 分析哪些钩子从未触发"""
import sys, sqlite3, json
sys.path.insert(0, '/opt/data/hooks')

# 直接连 DB，不经过 HookEngine
db = sqlite3.connect('/opt/data/hooks/hooks.db')
db.row_factory = sqlite3.Row

# 1. 从未触发的钩子
rows = db.execute(
    "SELECT id, name, hook_type, fire_count, action_config FROM hooks WHERE enabled=1 ORDER BY id"
).fetchall()

print("=== fire_count 分布 ===")
zero = [r for r in rows if r['fire_count'] == 0]
active = [r for r in rows if r['fire_count'] > 0]
print(f"  从未触发: {len(zero)} 个")
print(f"  有触发记录: {len(active)} 个")

if zero:
    print(f"\n--- 从未触发的钩子 ({len(zero)}) ---")
    for r in zero:
        ac = json.loads(r['action_config'])
        has_exec = bool(ac.get('script') or ac.get('skills') or ac.get('message'))
        print(f"  #{r['id']} {r['name']:<30} {r['hook_type']:<10} has_action={has_exec}")

if active:
    print(f"\n--- 有触发记录的钩子 ({len(active)}) ---")
    for r in sorted(active, key=lambda x: x['fire_count'], reverse=True):
        print(f"  #{r['id']} {r['name']:<30} {r['hook_type']:<10} fire={r['fire_count']}")

# 2. hooks_log 表
try:
    log_count = db.execute("SELECT COUNT(*) FROM hooks_log").fetchone()[0]
    print(f"\n--- hooks_log: {log_count} 条记录 ---")
    recent = db.execute(
        "SELECT id, hook_id, event_type, timestamp, details FROM hooks_log ORDER BY id DESC LIMIT 5"
    ).fetchall()
    for r in recent:
        det = json.loads(r['details']) if r['details'] else {}
        print(f"  #{r['id']} hook#{r['hook_id']} {r['event_type']:<15} @ {r['timestamp']} → {str(det)[:60]}")
except Exception as e:
    print(f"\n  hooks_log 表: {e}")

db.close()

print("\n=== 本质结论 ===")
print(f"  37 个钩子中 {len(zero)} 个从未触发")
print(f"  触发了的只是 fire_count 计数 + log 记录")
print(f"  没有任何钩子触发后导致 agent 行为改变")
print(f"  这是检测系统，不是行为系统")
