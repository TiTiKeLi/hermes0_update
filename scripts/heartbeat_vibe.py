#!/usr/bin/env python3
"""
heartbeat_vibe.py — VibeThinker-3B 心跳健康摘要
cron 模式: no_agent=True, script=heartbeat_vibe.py
工作流:
  1. 收集关键状态
  2. 调 VibeThinker 生成一行摘要
  3. 与上次报告对比，有变化才输出（静默模式）
  4. 输出 → cron 投递

依赖: call_vibe.py（同目录下）
"""
import json, os, sys, time, hashlib

# ---- 配置 ----
STATE_FILE = "/opt/data/research/heartbeat_last.json"
STATUS_SOURCES = {
    "MEMORY.md": "/opt/data/memories/MEMORY.md",
    "USER.md": "/opt/data/memories/USER.md",
    "SKILL_REGISTRY": "/opt/data/skills/SKILL_REGISTRY.yaml",
}

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from call_vibe import VibeAgent

agent = VibeAgent(system="你是系统状态摘要助手。只输出一行摘要，格式：✅/❌ 组件 | 关键数字。不解释。")


def collect_status() -> dict:
    """采集系统状态"""
    data = {}
    
    # 容器状态
    data["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # 文件状态
    for label, path in STATUS_SOURCES.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            data[label] = {
                "size": size,
                "modified": time.strftime("%m-%d %H:%M", time.localtime(mtime))
            }
        else:
            data[label] = None
    
    # cron 状态
    data["cron_count"] = "?"
    
    return data


def generate_summary(data: dict) -> str:
    """调 3B 摘要"""
    context = json.dumps(data, ensure_ascii=False, indent=2)
    result = agent.ask(
        f"基于以下系统状态，生成一行摘要。格式：✅/❌ 组件 | 关键数字\n\n{context}",
        temperature=0.05,
        max_tokens=100
    )
    return result["response"].strip()


def has_changed(data: dict, summary: str) -> bool:
    """与上次比较，有变化才输出"""
    if not os.path.exists(STATE_FILE):
        return True  # 首次运行
    
    try:
        with open(STATE_FILE) as f:
            last = json.load(f)
        # 比较 hash
        current_hash = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
        last_hash = last.get("hash", "")
        return current_hash != last_hash
    except:
        return True


def main():
    data = collect_status()
    summary = generate_summary(data)
    
    # 计算 hash
    data_hash = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    # 有变化才输出
    if not has_changed(data, summary):
        return  # 静默
    
    # 保存当前状态
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"hash": data_hash, "summary": summary, "time": data["time"]}, f)
    
    # 输出（cron no_agent=True → stdout 投递给用户）
    print("━━━ 心跳摘要 ━━━")
    print(summary)
    print(f"时间: {data['time']}")


if __name__ == "__main__":
    main()
