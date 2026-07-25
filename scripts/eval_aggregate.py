#!/usr/bin/env python3
"""
评分 + 汇总 引擎 — 用于步骤4和步骤5
从 plan 的 results 目录读取执行结果，调用 Ollama 评分，
然后生成汇总报告。
当 Ollama 不可用时，使用预设评分。
"""
import json
import sys
import os
import subprocess
from pathlib import Path

AGENTS_DIR = Path("/opt/data/agents")
PLANS_DIR = AGENTS_DIR / "plans"
REGISTRY_PATH = AGENTS_DIR / "registry.json"

OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
OLLAMA_MODEL = "VibeThinker-3B:latest"


def ollama_available() -> bool:
    try:
        r = subprocess.run(
            ["curl", "-s", "--connect-timeout", "2", "--max-time", "3", OLLAMA_URL.replace("/api/generate", "/api/tags")],
            capture_output=True, text=True, timeout=5
        )
        return r.returncode == 0
    except:
        return False


def call_ollama(prompt: str) -> str | None:
    """调用 Ollama 生成"""
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False})
    try:
        r = subprocess.run(
            ["curl", "-s", "--connect-timeout", "5", "--max-time", "15", OLLAMA_URL,
             "-d", payload],
            capture_output=True, text=True, timeout=20
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            return data.get("response", "")
    except:
        return None
    return None


def evaluate_result(task_id: str, task: dict, result: dict) -> dict:
    """对单个任务结果评分"""
    use_ollama = ollama_available()
    
    if use_ollama:
        prompt = f"""评估以下 Agent 执行结果：
Agent: {task.get('assigned_agent', 'unknown')}
任务: {task.get('goal', '')}
结果: {json.dumps(result, ensure_ascii=False)[:500]}

按三个维度评分 (0-10)：
- completeness（完整性）：是否覆盖要求？
- accuracy（准确性）：结果是否正确？
- relevance（相关性）：结果是否切题？

输出严格 JSON: {{"completeness": X, "accuracy": Y, "relevance": Z, "comment": "..."}}
"""
        response = call_ollama(prompt)
        if response:
            try:
                scores = json.loads(response.strip())
                return scores
            except:
                pass
    
    # Fallback: 根据 result 内容自动评分
    completeness = 8 if len(json.dumps(result, ensure_ascii=False)) > 100 else 5
    accuracy = 8 if "error" not in str(result).lower() else 4
    relevance = 9 if result.get("result") or result.get("findings") or result.get("missing_fields") else 5
    
    return {
        "completeness": completeness,
        "accuracy": accuracy,
        "relevance": relevance,
        "comment": "自动评估（Ollama不可用）"
    }


def aggregate_results(plan_id: str, tasks: list, scores: dict) -> str:
    """汇总所有结果生成报告"""
    lines = []
    lines.append(f"# 规划汇总报告: {plan_id}")
    lines.append(f"## 概览")
    lines.append(f"- 总任务数: {len(tasks)}")
    lines.append(f"- 总评分: {sum(scores.values()) / len(scores) if scores else 0:.1f}")
    lines.append("")
    
    all_results = []
    for task in tasks:
        tid = task.get("task_id", "?")
        agent = task.get("assigned_agent", "?")
        goal = task.get("goal", "?")
        result = task.get("result", {})
        score = task.get("score", {})
        
        lines.append(f"## {tid}: {goal}")
        lines.append(f"- Agent: {agent}")
        lines.append(f"- 评分: {json.dumps(score, ensure_ascii=False)}")
        lines.append(f"- 结果预览: {json.dumps(result, ensure_ascii=False)[:200]}")
        lines.append("")
        all_results.append(result)
    
    lines.append("---")
    lines.append("## 综合结论")
    
    avg_score = sum(scores.values()) / len(scores) if scores else 0
    if avg_score >= 8:
        lines.append("🟢 系统状态健康，所有检查点通过")
    elif avg_score >= 5:
        lines.append("🟡 系统基本正常，存在少量可改进项")
    else:
        lines.append("🔴 系统需关注，部分检查点未通过")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: eval_aggregate.py <plan_id>")
        sys.exit(1)
    
    plan_id = sys.argv[1]
    plan_dir = PLANS_DIR / plan_id
    
    if not plan_dir.exists():
        print(f"❌ 规划 {plan_id} 不存在")
        sys.exit(1)
    
    # 读取 state
    state = json.loads((plan_dir / "state.json").read_text()) if (plan_dir / "state.json").exists() else {}
    
    # 读取所有 task
    tasks = []
    for tf in sorted((plan_dir / "tasks").glob("*.json")):
        tasks.append(json.loads(tf.read_text()))
    
    # 读取 results
    results_dir = plan_dir / "results"
    results = {}
    if results_dir.exists():
        for rf in results_dir.glob("*.json"):
            results[rf.stem] = json.loads(rf.read_text())
    
    # 评分
    scores = {}
    for task in tasks:
        tid = task["task_id"]
        result = results.get(tid, {"error": "no result"})
        score = evaluate_result(tid, task, result)
        scores[tid] = score
        # 写入 task
        task["result"] = result
        task["score"] = score
        task["status"] = "completed"
        (plan_dir / "tasks" / f"{tid}.json").write_text(json.dumps(task, indent=2, ensure_ascii=False))
    
    # 汇总
    report = aggregate_results(plan_id, tasks, scores)
    
    # 写 summary.md
    (plan_dir / "summary.md").write_text(report)
    
    # 更新 state
    state["status"] = "completed"
    state["results"] = {tid: s.get("score", 0) for tid, s in scores.items()}
    (plan_dir / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False))
    
    print(report)


if __name__ == "__main__":
    main()
