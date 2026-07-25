#!/usr/bin/env python3
"""
评分 + 汇总引擎 — 用于 Step 4 和 Step 5
- Ollama 可用时：调用 VibeThinker-3B 评分
- Ollama 不可用时：基于结果内容长度/关键字自动评分
- 汇总：生成结构化 Markdown 报告

用法: python3 eval_aggregate.py <plan_id>

输出: 写入 plan_dir/summary.md，更新所有 task 的 score 字段
"""
import json
import sys
import subprocess
from pathlib import Path

AGENTS_DIR = Path("/opt/data/agents")
PLANS_DIR = AGENTS_DIR / "plans"
OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
OLLAMA_MODEL = "VibeThinker-3B:latest"


def ollama_available() -> bool:
    try:
        r = subprocess.run(
            ["curl", "-s", "--connect-timeout", "2", "--max-time", "3",
             OLLAMA_URL.replace("/api/generate", "/api/tags")],
            capture_output=True, text=True, timeout=5
        )
        return r.returncode == 0
    except:
        return False


def call_ollama(prompt: str) -> str | None:
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False})
    try:
        r = subprocess.run(
            ["curl", "-s", "--connect-timeout", "5", "--max-time", "15",
             OLLAMA_URL, "-d", payload],
            capture_output=True, text=True, timeout=20
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout).get("response", "")
    except:
        return None
    return None


def evaluate_result(task: dict, result: dict) -> dict:
    """评分一条结果。Ollama 可用时走 AI，否则自动评估"""
    use_ollama = ollama_available()
    result_str = json.dumps(result, ensure_ascii=False)

    if use_ollama:
        prompt = f"""评估以下 Agent 执行结果：
Agent: {task.get('assigned_agent', 'unknown')}
任务: {task.get('goal', '')}
结果: {result_str[:500]}

按三维度评分 (0-10)：completeness, accuracy, relevance
输出 JSON: {{"completeness": X, "accuracy": Y, "relevance": Z, "comment": "..."}}
"""
        response = call_ollama(prompt)
        if response:
            try:
                return json.loads(response.strip())
            except:
                pass

    # Fallback 自动评分
    has_content = len(result_str) > 100
    no_errors = "error" not in str(result).lower()
    result_shape = result.get("result") or result.get("findings") or result.get("missing_fields")
    
    return {
        "completeness": 8 if has_content else 5,
        "accuracy": 8 if no_errors else 4,
        "relevance": 9 if result_shape else 5,
        "comment": "自动评分（Ollama 不可用）"
    }


def aggregate(plan_id: str, tasks: list, scores: dict, results: dict) -> str:
    lines = [f"# 规划汇总报告: {plan_id}\n"]
    lines.append(f"## 概览\n- 总任务数: {len(tasks)}\n")
    
    for task in tasks:
        tid = task["task_id"]
        result = results.get(tid, {"error": "no result"})
        score = scores.get(tid, {})
        lines.append(f"## {tid}: {task['goal']}")
        lines.append(f"- Agent: {task.get('assigned_agent','?')}")
        lines.append(f"- 评分: {json.dumps(score, ensure_ascii=False)}")
        lines.append(f"- 结果: {json.dumps(result, ensure_ascii=False)[:200]}\n")

    avg = sum(s["completeness"] + s["accuracy"] + s["relevance"] for s in scores.values()) / (len(scores) * 3) if scores else 0
    health = "🟢 健康" if avg >= 8 else ("🟡 基本正常" if avg >= 5 else "🔴 需关注")
    lines.append(f"## 综合\n- 均分: {avg:.1f} — {health}")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <plan_id>"); sys.exit(1)
    plan_id = sys.argv[1]
    plan_dir = PLANS_DIR / plan_id
    if not plan_dir.exists():
        print(f"❌ 规划不存在: {plan_id}"); sys.exit(1)
    
    state = json.loads((plan_dir / "state.json").read_text()) if (plan_dir / "state.json").exists() else {}
    tasks = sorted([json.loads(tf.read_text()) for tf in (plan_dir / "tasks").glob("*.json")], key=lambda t: t["task_id"])
    
    results_dir = plan_dir / "results"
    results = {}
    if results_dir.exists():
        for rf in results_dir.glob("*.json"):
            results[rf.stem] = json.loads(rf.read_text())
    
    scores = {}
    for task in tasks:
        tid = task["task_id"]
        result = results.get(tid, {"error": "no result"})
        score = evaluate_result(task, result)
        scores[tid] = score
        task["result"] = result
        task["score"] = score
        task["status"] = "completed"
        (plan_dir / "tasks" / f"{tid}.json").write_text(json.dumps(task, indent=2, ensure_ascii=False))
    
    report = aggregate(plan_id, tasks, scores, results)
    (plan_dir / "summary.md").write_text(report)
    state["status"] = "completed"
    (plan_dir / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(report)

if __name__ == "__main__":
    main()
