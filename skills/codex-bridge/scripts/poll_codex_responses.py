#!/usr/bin/env python3
"""
Codex Bridge 响应轮询脚本 — 触发式生命周期

用法：
  python3 poll_codex_responses.py add <req-id> [<req-id>...]   # 注册待监听的请求
  python3 poll_codex_responses.py remove <req-id>              # 取消监听
  python3 poll_codex_responses.py list                          # 当前待监听列表
  python3 poll_codex_responses.py run                           # 执行一次轮询

行为（run模式）：
- 扫描 responses/ 目录，只检查已注册的请求ID
- 新 completed → 输出摘要。所有已注册请求都完成 → 最后一行输出 ALL_DONE
- 无新结果 → 静默退出（cron 无输出 = 不投递）

生命周期：
  1. 提交请求到 Codex
  2. 立即注册监听：poll_codex_responses.py add req-xxx-001
  3. 创建临时 cron：每15分钟，调用 poll_codex_responses.py run
  4. 轮询检测到完成 → 输出结果 + ALL_DONE
  5. 我作为 agent 收到 ALL_DONE → 移除 cron + 清理注册列表
"""

import json
import os
import glob
import sys
import argparse

BRIDGE_DIR = "/opt/data/codex-bridge"
STATE_FILE = os.path.join(BRIDGE_DIR, ".poll_state.json")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"watching": [], "seen_ids": [], "done_ids": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def cmd_add(ids):
    state = load_state()
    for rid in ids:
        if rid not in state["watching"]:
            state["watching"].append(rid)
    save_state(state)
    print(f"✅ 已注册监听: {', '.join(ids)}")
    print(f"   当前待监听: {', '.join(state['watching'])}")


def cmd_remove(rid):
    state = load_state()
    if rid in state["watching"]:
        state["watching"].remove(rid)
    if rid in state["seen_ids"]:
        state["seen_ids"].remove(rid)
    save_state(state)
    print(f"✅ 已移除监听: {rid}")


def cmd_list():
    state = load_state()
    print(f"📋 待监听: {state['watching']}")
    print(f"📋 已处理: {state['seen_ids']}")
    print(f"📋 已完成: {state['done_ids']}")


def cmd_run():
    state = load_state()
    watching = state["watching"]
    if not watching:
        sys.exit(0)  # 没有待监听请求，静默退出

    new_results = []
    all_done = True

    for rid in watching:
        if rid in state["done_ids"]:
            continue  # 已经处理完毕

        rfile = os.path.join(BRIDGE_DIR, "responses", f"{rid}.json")
        if not os.path.exists(rfile):
            all_done = False  # 响应文件还没出现
            continue

        # Windows端写入的响应文件可能带 UTF-8 BOM + \r\n
        with open(rfile, encoding="utf-8-sig") as f:
            raw = f.read().replace("\r\n", "\n")
            try:
                resp = json.loads(raw)
            except json.JSONDecodeError:
                all_done = False
                continue

        status = resp.get("status", "unknown")

        if status == "completed":
            # 收集结果
            result = {
                "id": rid,
                "status": "completed",
                "response": resp.get("response", ""),
                "files_changed": resp.get("files_changed", []),
                "bugs_fixed": [],
                "optimizations": [],
            }
            details = resp.get("details", {})
            if isinstance(details, dict):
                result["bugs_fixed"] = details.get("bugs_fixed", [])
                result["optimizations"] = details.get("optimizations", [])
            new_results.append(result)

            # 标记为已处理
            if rid not in state["seen_ids"]:
                state["seen_ids"].append(rid)
            if rid not in state["done_ids"]:
                state["done_ids"].append(rid)

        elif status == "pending":
            all_done = False  # Codex 还在处理
        else:
            all_done = False

    save_state(state)

    if not new_results:
        # 无新完成结果 → 静默退出（cron 不投递）
        if not all_done:
            sys.exit(0)
        else:
            # 所有已完成但无新结果 → 说明已处理过了，不发重复消息
            sys.exit(0)

    # 输出格式化结果
    for r in new_results:
        print(f"📦 **{r['id']}** — {r['status']}")
        print(f"   {r['response']}")
        if r["bugs_fixed"]:
            for b in r["bugs_fixed"]:
                print(f"   🐛 修复: {b['file']} — {b.get('fix', '')}")
        if r["optimizations"]:
            for o in r["optimizations"]:
                print(f"   ⚡ 优化: {o}")
        if r["files_changed"]:
            print(f"   📁 修改文件: {', '.join(r['files_changed'])}")
        print("")

    # 所有请求都完成 → 输出 ALL_DONE 信号
    if all_done:
        print("ALL_DONE")


def main():
    parser = argparse.ArgumentParser(description="Codex Bridge 响应轮询")
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="注册待监听请求")
    p_add.add_argument("ids", nargs="+", help="请求ID (req-xxx)")

    p_rm = sub.add_parser("remove", help="取消监听")
    p_rm.add_argument("rid", help="请求ID")

    p_ls = sub.add_parser("list", help="查看当前监听列表")

    p_run = sub.add_parser("run", help="执行一次轮询")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.ids)
    elif args.command == "remove":
        cmd_remove(args.rid)
    elif args.command == "list":
        cmd_list()
    elif args.command == "run":
        cmd_run()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
