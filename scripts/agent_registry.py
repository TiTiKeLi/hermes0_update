#!/usr/bin/env python3
"""
Agent Registry — 智能体注册表管理系统
管理 Agent.md 读取、状态变更、评分记录、规划生命周期
"""
import json
import os
import sys
import yaml
from datetime import datetime
from pathlib import Path

AGENTS_DIR = Path("/opt/data/agents")
AGENTS_REGISTRY = AGENTS_DIR / "registry.json"
AGENTS_AGENTS_DIR = AGENTS_DIR / "agents"
PLANS_DIR = AGENTS_DIR / "plans"
TEMPLATES_DIR = AGENTS_DIR / "templates"

for d in [AGENTS_AGENTS_DIR, PLANS_DIR, TEMPLATES_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def load_registry() -> dict:
    """加载注册表索引"""
    if AGENTS_REGISTRY.exists():
        return json.loads(AGENTS_REGISTRY.read_text())
    return {"agents": {}, "updated": None}


def save_registry(registry: dict):
    """保存注册表索引"""
    registry["updated"] = datetime.now().isoformat()
    AGENTS_REGISTRY.write_text(json.dumps(registry, indent=2, ensure_ascii=False))


def list_agents(status=None) -> list:
    """列出所有 agents，可按状态筛选"""
    registry = load_registry()
    agents = []
    for name, info in registry["agents"].items():
        if status and info.get("state") != status:
            continue
        agent_dir = AGENTS_AGENTS_DIR / name
        md_path = agent_dir / "Agent.md"
        if md_path.exists():
            with open(md_path) as f:
                content = f.read()
            agents.append({
                "name": name,
                "state": info.get("state", "unknown"),
                "role": info.get("role", ""),
                "model": info.get("model", ""),
                "score_avg": info.get("score_avg", 0),
                "score_count": info.get("score_count", 0),
                "last_used": info.get("last_used", ""),
                "created": info.get("created", ""),
                "agent_md_preview": content[:200]
            })
    return agents


def register_agent(name: str, md_content: str) -> dict:
    """注册新 agent（写入 Agent.md + 更新注册表）"""
    agent_dir = AGENTS_AGENTS_DIR / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    md_path = agent_dir / "Agent.md"

    # 写入 Agent.md
    md_path.write_text(md_content)

    # 解析 frontmatter
    frontmatter = _parse_yaml_frontmatter(md_content)

    # 更新注册表
    registry = load_registry()
    now = datetime.now().isoformat()
    registry["agents"][name] = {
        "name": name,
        "role": frontmatter.get("role", ""),
        "model": frontmatter.get("model", "VibeThinker-3B:latest"),
        "capabilities": frontmatter.get("capabilities", []),
        "state": "available",
        "score_avg": 0,
        "score_count": 0,
        "score_history": [],
        "created": now,
        "last_used": None,
        "agent_md": str(md_path)
    }
    save_registry(registry)
    return {"status": "registered", "name": name, "state": "available"}


def update_state(name: str, new_state: str) -> dict:
    """更新 agent 生命周期状态"""
    valid_states = ["available", "assigned", "working", "done", "failed", "cancelled", "timeout", "archived"]
    if new_state not in valid_states:
        return {"error": f"无效状态: {new_state}。有效值: {valid_states}"}

    registry = load_registry()
    if name not in registry["agents"]:
        return {"error": f"Agent '{name}' 未注册"}

    old_state = registry["agents"][name]["state"]
    registry["agents"][name]["state"] = new_state
    if new_state in ["done", "failed"]:
        registry["agents"][name]["last_used"] = datetime.now().isoformat()
    save_registry(registry)
    return {"status": "updated", "name": name, "old_state": old_state, "new_state": new_state}


def record_score(name: str, task: str, scores: dict, comment: str = "") -> dict:
    """记录 agent 执行评分"""
    registry = load_registry()
    if name not in registry["agents"]:
        return {"error": f"Agent '{name}' 未注册"}

    avg_score = sum(scores.values()) / len(scores) if scores else 0
    entry = {
        "round": len(registry["agents"][name].get("score_history", [])) + 1,
        "task": task,
        "score": round(avg_score, 1),
        "scores": scores,
        "comment": comment,
        "timestamp": datetime.now().isoformat()
    }

    agent = registry["agents"][name]
    agent.setdefault("score_history", []).append(entry)
    # 更新平均分
    all_scores = [s["score"] for s in agent["score_history"]]
    agent["score_avg"] = round(sum(all_scores) / len(all_scores), 1)
    agent["score_count"] = len(all_scores)
    agent["state"] = "available"  # 评分后回到可用
    save_registry(registry)
    return {"status": "scored", "name": name, "score": avg_score, "round": entry["round"]}


def create_plan(requirement: str, framework_json: str) -> dict:
    """创建新的规划"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_dir = PLANS_DIR / f"plan-{timestamp}"
    plan_dir.mkdir(parents=True)

    framework = json.loads(framework_json) if isinstance(framework_json, str) else framework_json

    plan_info = {
        "id": f"plan-{timestamp}",
        "requirement": requirement,
        "framework": framework,
        "status": "created",
        "tasks": [],
        "results": [],
        "created": datetime.now().isoformat(),
        "completed": None
    }

    # 写 plan.md
    plan_md = f"""# 规划: plan-{timestamp}

## 需求
{requirement}

## 规划框架
```json
{json.dumps(framework, indent=2, ensure_ascii=False)}
```

## 状态
- 总任务数: 0
- 已完成: 0
- 失败: 0
- 状态: created
"""
    (plan_dir / "plan.md").write_text(plan_md)
    (plan_dir / "tasks").mkdir(exist_ok=True)
    (plan_dir / "results").mkdir(exist_ok=True)

    # 写入 state.json
    (plan_dir / "state.json").write_text(json.dumps(plan_info, indent=2, ensure_ascii=False))

    return {"status": "created", "plan_id": plan_info["id"], "plan_dir": str(plan_dir)}


def add_task_to_plan(plan_id: str, task: dict) -> dict:
    """添加子任务到规划"""
    plan_dir = PLANS_DIR / plan_id
    if not plan_dir.exists():
        return {"error": f"规划 '{plan_id}' 不存在"}

    # 生成 task_id
    task_id = f"task-{len(list((plan_dir / 'tasks').glob('*.json'))):03d}"
    task["task_id"] = task_id
    task["status"] = "pending"
    task["created"] = datetime.now().isoformat()
    task["assigned_agent"] = task.get("assigned_agent", None)
    task["result"] = None
    task["score"] = None

    (plan_dir / "tasks" / f"{task_id}.json").write_text(
        json.dumps(task, indent=2, ensure_ascii=False))

    # 更新 state.json
    state_path = plan_dir / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        state["tasks"].append(task_id)
        state["status"] = "in_progress"
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))

    return {"status": "added", "task_id": task_id}


def complete_task(plan_id: str, task_id: str, result: dict, score: float = None) -> dict:
    """完成一个子任务"""
    task_path = PLANS_DIR / plan_id / "tasks" / f"{task_id}.json"
    if not task_path.exists():
        return {"error": f"任务 '{task_id}' 不存在"}

    task = json.loads(task_path.read_text())
    task["status"] = "completed"
    task["result"] = result
    task["score"] = score
    task["completed"] = datetime.now().isoformat()
    task_path.write_text(json.dumps(task, indent=2, ensure_ascii=False))

    # 写入 results/
    result_path = PLANS_DIR / plan_id / "results" / f"{task_id}.json"
    result_path.write_text(json.dumps({
        "task_id": task_id,
        "result": result,
        "score": score,
        "completed": task["completed"]
    }, indent=2, ensure_ascii=False))

    return {"status": "completed", "task_id": task_id, "score": score}


def get_plan(plan_id: str) -> dict:
    """获取规划详情"""
    plan_dir = PLANS_DIR / plan_id
    if not plan_dir.exists():
        return {"error": f"规划 '{plan_id}' 不存在"}

    state_path = plan_dir / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    tasks = []
    for tf in sorted((plan_dir / "tasks").glob("*.json")):
        tasks.append(json.loads(tf.read_text()))

    results = {}
    for rf in (plan_dir / "results").glob("*.json"):
        results[rf.stem] = json.loads(rf.read_text())

    return {
        "plan_id": plan_id,
        "state": state,
        "tasks": tasks,
        "results": results,
        "plan_md": (plan_dir / "plan.md").read_text() if (plan_dir / "plan.md").exists() else ""
    }


def _parse_yaml_frontmatter(content: str) -> dict:
    """从 Agent.md 提取 YAML frontmatter"""
    lines = content.split("\n")
    if lines and lines[0].strip() == "---":
        try:
            end = next(i for i, l in enumerate(lines[1:], 1) if l.strip() == "---")
            yaml_block = "\n".join(lines[1:end])
            return yaml.safe_load(yaml_block) or {}
        except (StopIteration, yaml.YAMLError):
            pass
    return {}


def main():
    """CLI 入口"""
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <command> [args...]")
        print("命令: list, register, state, score, plan, task, get")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        status = sys.argv[2] if len(sys.argv) > 2 else None
        agents = list_agents(status)
        print(json.dumps(agents, indent=2, ensure_ascii=False))

    elif cmd == "register":
        name = sys.argv[2]
        md_file = sys.argv[3]
        md_content = Path(md_file).read_text()
        result = register_agent(name, md_content)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "state":
        name = sys.argv[2]
        new_state = sys.argv[3]
        result = update_state(name, new_state)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "score":
        name = sys.argv[2]
        task = sys.argv[3]
        scores = json.loads(sys.argv[4])
        comment = sys.argv[5] if len(sys.argv) > 5 else ""
        result = record_score(name, task, scores, comment)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "plan":
        requirement = sys.argv[2]
        framework = sys.argv[3]
        result = create_plan(requirement, framework)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "task":
        plan_id = sys.argv[2]
        action = sys.argv[3]
        if action == "add":
            task = json.loads(sys.argv[4])
            result = add_task_to_plan(plan_id, task)
        elif action == "complete":
            task_id = sys.argv[4]
            result_data = json.loads(sys.argv[5])
            score = float(sys.argv[6]) if len(sys.argv) > 6 else None
            result = complete_task(plan_id, task_id, result_data, score)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "get":
        plan_id = sys.argv[2]
        result = get_plan(plan_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
