#!/usr/bin/env python3
import sqlite3, json, sys
sys.path.insert(0, "/opt/data/hooks")
from hooks_engine import HookEngine

DB = "/opt/data/hooks/hooks.db"

def run():
    conn = sqlite3.connect(DB)
    events = [
        ("state_machine_input_needed", "状态机需要用户输入"),
        ("bridge_request_received", "bridge 收到新请求"),
        ("skill_updated", "技能文件已更新"),
        ("config_changed", "配置已变更"),
        ("reliability_check", "可靠性补偿检查"),
    ]
    for name, desc in events:
        conn.execute("INSERT OR IGNORE INTO events_registry (event_name, description) VALUES (?,?)", (name, desc))
    conn.commit()
    print("events registered")
    conn.close()

    db = HookEngine(DB)
    db.register_hook(
        name="bridge-reliability", hook_type="cron", action_type="run_script",
        trigger_config=json.dumps({"interval_seconds": 1800}),
        action_config=json.dumps({"script": "/opt/data/scripts/wechat_state_bridge.py", "args": ["pending"]}),
        priority=1)
    print("reliability hook registered")

if __name__ == "__main__":
    run()
