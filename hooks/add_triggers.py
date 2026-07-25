#!/usr/bin/env python3
"""Bulk-add triggers: to all 21 skills based on their name/description."""
import os
import re

SKILLS_DIR = "/opt/data/skills"

# Trigger definitions per skill
TRIGGERS = {
    # architecture
    "hermes-optimization": {
        "keywords": ["优化", "optimize", "性能", "docker容器", "错误修复", "回复格式"],
    },
    "tool-governance": {
        "keywords": ["工具治理", "tool governance", "拦截器", "toolstate", "state registry"],
        "events": ["session_start"],
    },
    # behavior
    "caveman-compress": {
        "keywords": ["caveman", "小模型压缩", "3B压缩", "受限格式"],
    },
    "caveman-reply": {
        "keywords": ["caveman回复", "小模型回复", "3B格式"],
    },
    "memory-confirmation-feedback": {
        "keywords": ["记忆确认", "memory feedback", "记忆反馈", "feedback protocol", "memory_write_occurred"],
        "events": ["memory_written"],
    },
    # memory
    "hierarchical-memory-sync": {
        "keywords": ["记忆同步", "memory sync", "分层记忆", "hot cache", "fact_store同步"],
        "events": ["session_start", "memory_written"],
    },
    "memory-compactor": {
        "keywords": ["记忆压缩", "压缩", "memory compact", "归档", "archive", "MEMORY.md"],
        "tool_calls": ["memory"],
    },
    # meta
    "skill-creation-rules": {
        "keywords": ["创建技能", "skill_manage", "注册技能", "新技能", "新增skill"],
        "tool_calls": ["skill_manage"],
    },
    # model-router
    "model-router": {
        "keywords": ["模型路由", "model router", "deepseek分发", "任务分发", "路由"],
    },
    # security
    "download-gate": {
        "keywords": ["下载", "download", "curl", "wget", "git clone", "获取文件"],
        "tool_calls": ["terminal"],
    },
    "secure-download": {
        "keywords": ["下载", "download", "secure download", "安全下载"],
        "tool_calls": ["terminal"],
    },
    # thinking
    "deep-need-analysis": {
        "keywords": ["需求分析", "本质需求", "深层需求", "需求洞察", "分析框架"],
        "events": ["session_start"],
    },
    # tool-governance-v2
    "tool-governance-v2": {
        "keywords": ["工具治理v2", "tool governance v2", "前置拦截", "后置钩子", "kind"],
    },
    # workflow
    "arch-decomp": {
        "keywords": ["架构拆解", "arch decom", "模块关系", "控制流", "架构映射"],
    },
    "autogpt-self-improve": {
        "keywords": ["自迭代", "self improve", "技能改进", "autoGPT", "自评估"],
    },
    "dataflow-decomp": {
        "keywords": ["数据流", "data flow", "输入输出路径", "状态管理", "存储策略"],
    },
    "external-adaptor": {
        "keywords": ["外部适配", "external adapt", "下载集成", "拆解重组", "ZIP", "集成管道"],
        "tool_calls": ["terminal", "write_file"],
    },
    "functional-decomp": {
        "keywords": ["功能拆解", "functional decom", "功能清单", "模块职责", "核心流程"],
    },
    "github-discover": {
        "keywords": ["github", "开源", "repo", "项目发现", "发现项目", "提取部署", "arxiv"],
        "tool_calls": ["terminal"],
        "events": ["user_request"],
    },
    "interface-decomp": {
        "keywords": ["接口拆解", "interface decom", "API适配", "类/函数签名", "参数返回值"],
        "tool_calls": ["read_file", "search_files"],
    },
    "meta-orchestrator": {
        "keywords": ["元编排", "orchestrat", "子任务分发", "评分汇总", "生命周期管理"],
    },
}


def patch_frontmatter(filepath, triggers_dict):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        print(f"  ⚠️  {filepath} — 无 frontmatter")
        return False

    # Find closing ---
    end = content.find("---", 3)
    if end == -1:
        print(f"  ⚠️  {filepath} — 无法找到 --- 闭合")
        return False

    front = content[3:end]

    # Check if triggers already exists
    if "triggers:" in front:
        print(f"  ⏭️  {filepath} — 已有 triggers")
        return False

    # Build triggers YAML block
    lines = []
    if triggers_dict.get("keywords"):
        kw_lines = "\n".join(f"      - {k}" for k in triggers_dict["keywords"])
        lines.append(f"  keywords:")
        lines.append(kw_lines)
    if triggers_dict.get("tool_calls"):
        tc_lines = "\n".join(f"      - {t}" for t in triggers_dict["tool_calls"])
        lines.append(f"  tool_calls:")
        lines.append(tc_lines)
    if triggers_dict.get("events"):
        ev_lines = "\n".join(f"      - {e}" for e in triggers_dict["events"])
        lines.append(f"  events:")
        lines.append(ev_lines)

    if not lines:
        print(f"  ⚠️  {filepath} — 无触发器定义")
        return False

    triggers_block = "triggers:\n" + "\n".join(lines) + "\n"

    # Insert before the closing ---
    new_front = front.rstrip() + "\n" + triggers_block
    new_content = "---" + new_front + "---" + content[end + 3:]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def main():
    # Find all SKILL.md
    import glob
    pattern = os.path.join(SKILLS_DIR, "**", "SKILL.md")
    files = sorted(glob.glob(pattern, recursive=True))

    patched = 0
    skipped = 0
    missing = 0

    for filepath in files:
        # Extract skill name from path: .../<category>/<name>/SKILL.md or .../<name>/SKILL.md
        parts = filepath.replace(SKILLS_DIR, "").strip("/").split("/")
        if len(parts) >= 2:
            # Could be <name>/SKILL.md or <category>/<name>/SKILL.md
            skill_name = parts[-2]
        else:
            skill_name = ""

        triggers = TRIGGERS.get(skill_name)
        if not triggers:
            print(f"  ❓ {skill_name:30} — 未定义触发词")
            missing += 1
            continue

        if patch_frontmatter(filepath, triggers):
            print(f"  ✅ {skill_name:30} — triggers 已添加")
            patched += 1
        else:
            skipped += 1

    print(f"\n总计: {patched} 添加 / {skipped} 跳过 / {missing} 未定义")


if __name__ == "__main__":
    main()
