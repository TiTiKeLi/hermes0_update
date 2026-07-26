#!/usr/bin/env python3
"""
Codex Bridge 状态机轮询 — 往返循环确认协议

监视 codex-bridge/states/ 目录，检测 Codex 状态变更。
当 direction=codex→hermes 时 → 报告给用户。

用法：
  python3 codex_state_watcher.py run              # 执行一次状态检查
  python3 codex_state_watcher.py status <task>     # 查看指定任务状态
  python3 codex_state_watcher.py answer <task> <decision>  # 写入用户决策
  python3 codex_state_watcher.py list              # 列出所有活跃任务

状态机协议：
  Task: user 发高层需求 → Codex 遇到选择返回问题 → 用户确认 → 循环 → 完成

  状态流转:
    planning (hermes→codex)  —  Codex 规划/实现
      ↓
    awaiting_user (codex→hermes) — Codex 有问题，等用户决策
      ↓ 用户回答
    executing (hermes→codex)  —  用户已回答，Codex 继续
      ↓
    awaiting_user (codex→hermes) — 又遇到选择点...
      ↓ ...循环...
    completed (codex→hermes)  —  Codex 完成全部工作
    failed (codex→hermes)     —  Codex 执行出错
"""

import json
import os
import sys
import glob
from datetime import datetime

BRIDGE_DIR = "/opt/data/codex-bridge"
STATES_DIR = os.path.join(BRIDGE_DIR, "states")
SEEN_FILE = os.path.join(BRIDGE_DIR, ".state_seen.json")


# ── 辅助 ──────────────────────────────────────────────────

def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return json.load(f)
    return {"reported_ids": [], "done_ids": []}


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f)


def load_state(task_id):
    path = os.path.join(STATES_DIR, f"{task_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def write_state(state):
    task_id = state["task_id"]
    state["updated_at"] = now_iso()
    path = os.path.join(STATES_DIR, f"{task_id}.json")
    with open(path, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return path


# ── 命令实现 ──────────────────────────────────────────────

def cmd_run():
    """执行一次状态检查。发现 codex→hermes 状态则输出摘要（供 cron 投递）"""
    if not os.path.isdir(STATES_DIR):
        sys.exit(0)

    seen = load_seen()
    new_states = []

    for fpath in sorted(glob.glob(os.path.join(STATES_DIR, "*.json"))):
        task_id = os.path.splitext(os.path.basename(fpath))[0]

        state = load_state(task_id)
        if not state:
            continue

        direction = state.get("direction", "")
        status = state.get("status", "")
        # 只关心 Codex 写过来的状态（需要我转发给用户）
        if direction != "codex→hermes":
            continue
        # 只关心需要用户介入的状态
        if status not in ("awaiting_user", "completed", "failed"):
            continue
        # 已报告过且状态没变 → 跳过
        if task_id in seen["done_ids"]:
            continue

        new_states.append(state)

    if not new_states:
        sys.exit(0)  # 无新状态 → 静默退出

    # 输出格式化结果给用户
    for s in new_states:
        task_id = s["task_id"]
        status = s.get("status", "?")
        payload = s.get("payload", {})
        ptype = payload.get("type", "")
        pmsg = payload.get("message", "")
        options = payload.get("options", [])

        print(f"🔁 **{task_id}** — 状态: {status} (第 {s.get('round',1)} 轮)")
        print()

        if status == "awaiting_user":
            print(f"📝 **Codex 需要你确认：**")
            print(f"   {pmsg}")
            if options:
                print()
                print("选项：")
                for i, opt in enumerate(options, 1):
                    print(f"   {i}. {opt}")
            print()
            print("回复你的选择，我传回 Codex。")
        elif status == "completed":
            output = s.get("output", {})
            files = output.get("files_changed", [])
            summary = output.get("summary", "")
            print(f"✅ **Codex 已完成工作！**")
            if summary:
                print(f"   {summary}")
            if files:
                print(f"   📁 修改文件: {', '.join(files)}")
            print()
            print("我需要先验证，验证结果再给你最终确认。")
        elif status == "failed":
            error = s.get("error", "未知错误")
            print(f"❌ **Codex 执行出错：** {error}")
        print("───")

    # 标记已报告
    for s in new_states:
        tid = s["task_id"]
        if tid not in seen["reported_ids"]:
            seen["reported_ids"].append(tid)
        # completed/failed 标记为 done
        if s.get("status") in ("completed", "failed"):
            if tid not in seen["done_ids"]:
                seen["done_ids"].append(tid)

    save_seen(seen)


def cmd_status(task_id):
    """查看指定任务的当前状态"""
    state = load_state(task_id)
    if not state:
        print(f"❌ 任务 {task_id} 不存在")
        return
    print(json.dumps(state, ensure_ascii=False, indent=2))


def cmd_answer(task_id, decision_text):
    """写入用户决策 → 修改状态为 executing，方向 hermes→codex"""
    state = load_state(task_id)
    if not state:
        print(f"❌ 任务 {task_id} 不存在")
        return

    state["status"] = "executing"
    state["direction"] = "hermes→codex"
    state["round"] = state.get("round", 1) + 1
    state["decision"] = decision_text
    state["payload"]["decision"] = decision_text
    state["payload"]["type"] = "answer"

    # 清掉 old options/message（用户已决策）
    state["payload"].pop("options", None)
    state["payload"]["message"] = f"User decision: {decision_text}"

    path = write_state(state)
    print(f"✅ 已写入决策，状态 {task_id} → executing")
    print(f"   文件: {path}")
    print(f"   通知: bridge 下次同步会拾取，Codex 将收到你的决策继续执行")


def cmd_list():
    """列出所有活跃任务状态"""
    if not os.path.isdir(STATES_DIR):
        print("(无活跃任务)")
        return
    for fpath in sorted(glob.glob(os.path.join(STATES_DIR, "*.json"))):
        task_id = os.path.splitext(os.path.basename(fpath))[0]
        state = load_state(task_id)
        if state:
            status = state.get("status", "?")
            direction = state.get("direction", "?")
            rnd = state.get("round", 1)
            print(f"  {task_id}: [{status}] dir={direction}  round={rnd}")


# ── 主入口 ────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  codex_state_watcher.py run")
        print("  codex_state_watcher.py status <task_id>")
        print("  codex_state_watcher.py answer <task_id> '<decision>'")
        print("  codex_state_watcher.py list")
        return

    cmd = sys.argv[1]

    if cmd == "run":
        cmd_run()
    elif cmd == "status":
        if len(sys.argv) < 3:
            print("需要 task_id")
            return
        cmd_status(sys.argv[2])
    elif cmd == "answer":
        if len(sys.argv) < 4:
            print("用法: codex_state_watcher.py answer <task_id> '<decision>'")
            return
        cmd_answer(sys.argv[2], sys.argv[3])
    elif cmd == "list":
        cmd_list()
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
