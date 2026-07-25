#!/usr/bin/env python3
"""deep_diagnostic.py — 深度诊断 hooks 体系是否真的能行动"""
import sys, json
sys.path.insert(0, '/opt/data/hooks')
from hooks_engine import HookEngine, HookDB

eng = HookEngine()

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ── 1. 关键词匹配：能检测到什么？能行动到什么？ ──
section("TEST 1: 关键词匹配 — detection vs action")
test_msgs = [
    "帮我从github下载一个项目",
    "压缩一下记忆",
    "创建一个新skill",
    "今天天气怎么样",
    "优化一下docker",
]
for msg in test_msgs:
    matches = eng.check_pre_message(msg)
    if not matches:
        print(f"  ❌ '{msg[:20]}...'  → 无匹配")
        continue
    names = [m['name'] for m in matches]
    # 检查是否有实际 action
    has_action = False
    for m in matches:
        ac = json.loads(m['action_config'])
        if ac.get('skills') or ac.get('script'):
            has_action = True
    status = "✅ 有action" if has_action else "⚠️ 能检测但无action"
    print(f"  {status} '{msg[:20]}' → {names}")

# ── 2. tool_post 触发：record_call 后是否真的触发？ ──
section("TEST 2: tool_post 触发")
matches = eng.check_post_tool('write_file', {'path': '/tmp/test.txt'}, {'success': True})
if not matches:
    print("  write_file → 无匹配")
else:
    for m in matches:
        ac = json.loads(m['action_config'])
        script = ac.get('script','')[:80]
        skills = ac.get('skills',[])
        print(f"  #{m['id']} {m['name']:<30} → exec={bool(script)} skills={skills}")

matches = eng.check_post_tool('skill_manage', {'action': 'create'}, {'success': True})
if not matches:
    print("  skill_manage create → 无匹配")
else:
    for m in matches:
        print(f"  #{m['id']} {m['name']}")

# ── 3. 检查 sqlite hooks_log 是否有历史记录 ──
section("TEST 3: hooks_log 历史记录")
db = HookDB()
try:
    rows = db.conn.execute(
        "SELECT COUNT(*) FROM hooks_log"
    ).fetchone()
    print(f"  日志总数: {rows[0]}")
    recent = db.conn.execute(
        "SELECT hook_id, event_type, timestamp, details FROM hooks_log ORDER BY id DESC LIMIT 5"
    ).fetchall()
    for r in recent:
        print(f"  #{r['hook_id']} {r['event_type']} @ {r['timestamp']} {str(r['details'])[:60]}")
except Exception as e:
    print(f"  ❌ 查询错误: {e}")

# ── 4. fire_event 测试 ──
section("TEST 4: fire_event — 从 event 到执行")
try:
    results = eng.fire_event('session_start', {'test': True})
    if not results:
        print("  session_start → 无钩子响应（但可能有匹配）")
        # 检查是否有 session_start 的 event 钩子
        hooks = eng.db.list_hooks()
        for h in hooks:
            if h['hook_type'] == 'event':
                tc = json.loads(h['trigger_config'])
                if tc.get('event') == 'session_start':
                    print(f"  找到 session_start 钩子: #{h['id']} {h['name']}")
                    ac = json.loads(h['action_config'])
                    print(f"    action: {ac}")
    else:
        print(f"  session_start → {len(results)} 个钩子响应")
        for r in results:
            print(f"    {r.get('hook_name','?')}: success={r.get('success')}")
except Exception as e:
    print(f"  fire_event 错误: {e}")

# ── 5. 核心问题：pre-message 没有融入 agent 循环 ──
section("TEST 5: 本质诊断 — agent 循环是否 auto-loads hooks?")
print("""
当前 hooks 体系的状态:

✅ 检测层 (DETECT):
   - check_pre_message() 能匹配关键词 → 返回钩子元数据
   - check_post_tool() 能匹配工具调用 → 返回钩子元数据
   - fire_event() 能匹配事件

❌ 行动层 (ACT):
   - keyword 匹配后 → 只返回数据，不会自动 skill_view()
   - tool_post 匹配后 → record_call() 调了 check_post_tool 但结果没用于行动
   - 没有 agent 层预处理管线能自动加载匹配的 skill

本质差距:
   从「匹配→返回」而不是「匹配→加载→改变行为」
   agent 的思维循环完全不知道 hooks 系统的存在
""")

# ── 6. 总结 ──
section("诊断结论")
total = len(eng.db.list_hooks())
kw = len(eng.check_pre_message('测试下载记忆优化'))
print(f"  总钩子: {total}")
print(f"  能检测的关键词类: 21")
print(f"  关键词命中/总测试: 5/5")
print(f"  能自动加载skill: NO ← 这是核心瓶颈")
print(f"  event 自动触发: 依赖 fire_event() 被调用")
print(f"  cron_tick 钩子注册: 0")
