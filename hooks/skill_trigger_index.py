#!/usr/bin/env python3
"""
skill_trigger_index.py — Skill Trigger Scanner v1
==================================================
Scans ALL /opt/data/skills/**/SKILL.md for `triggers:` frontmatter fields,
then auto-registers hooks in hooks_engine.py.

Two outputs:
1. hooks_engine.py registration — auto-register hooks for each skill
2. TRIGGERS_REFERENCE.md — human-readable trigger map (gen by cron)

Usage:
  python3 skill_trigger_index.py scan              # scan + auto-register hooks
  python3 skill_trigger_index.py list               # list all detected triggers
  python3 skill_trigger_index.py validate            # check all SKILL.md for completeness
"""

import os
import re
import json
import sys
import glob
import time
import subprocess

SKILLS_DIR = "/opt/data/skills"
HOOKS_ENGINE = "/opt/data/hooks/hooks_engine.py"
TRIGGERS_FILE = "/opt/data/hooks/TRIGGERS_REFERENCE.md"
HOOKS_DB = "/opt/data/hooks/hooks.db"

# Priority by category
CATEGORY_PRIORITY = {
    "workflow": 80,
    "security": 70,
    "behavior": 60,
    "thinking": 50,
    "architecture": 40,
    "system": 30,
    "memory": 30,
    "meta": 20,
}


def extract_yaml_frontmatter(filepath: str) -> dict:
    """Extract YAML frontmatter using proper YAML parser."""
    import yaml
    with open(filepath, "r") as f:
        content = f.read()

    if not content.startswith("---"):
        return {}

    # Find closing ---
    end = content.find("---", 3)
    if end == -1:
        return {}

    frontmatter = content[3:end].strip()
    try:
        return yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as e:
        print(f"  ⚠️  YAML parse error in {filepath}: {e}", file=sys.stderr)
        return {}


def scan_all_skills() -> list[dict]:
    """Scan all SKILL.md files and extract triggers."""
    results = []

    # Find all SKILL.md files (up to 3 levels deep)
    pattern = os.path.join(SKILLS_DIR, "**", "SKILL.md")
    files = glob.glob(pattern, recursive=True)

    for filepath in sorted(files):
        frontmatter = extract_yaml_frontmatter(filepath)
        if not frontmatter:
            continue

        name = frontmatter.get("name", "")
        if not name:
            continue

        # Relative path for display
        rel_path = os.path.relpath(filepath, SKILLS_DIR)

        triggers = frontmatter.get("triggers", {})
        if isinstance(triggers, str):
            triggers = {}

        description = frontmatter.get("description", "")
        category = frontmatter.get("category", "")
        priority = CATEGORY_PRIORITY.get(category, 0)

        entry = {
            "name": name,
            "path": rel_path,
            "category": category,
            "priority": priority,
            "description": description,
            "triggers": triggers,
            "triggers_detected": bool(triggers and (
                triggers.get("keywords") or
                triggers.get("tool_calls") or
                triggers.get("events")
            )),
        }
        results.append(entry)

    return results


def find_existing_hooks(entries: list[dict]) -> dict:
    """Query hooks.db to find which skills already have hooks registered."""
    # Use hooks_engine CLI to list
    try:
        result = subprocess.run(
            [sys.executable, HOOKS_ENGINE, "list", "--enabled-only"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
    except Exception:
        output = ""

    existing = {}
    for line in output.split("\n"):
        m = re.match(r'.*#(\d+)\s+(\S+)\s+', line)
        if m:
            existing[m.group(2)] = int(m.group(1))

    return existing


def register_triggers(entries: list[dict], dry_run: bool = False) -> list[dict]:
    """Auto-register hooks for each skill's triggers."""
    registered = []

    for entry in entries:
        name = entry["name"]
        triggers = entry.get("triggers", {})
        if not triggers:
            continue

        # 1) Keyword triggers
        keywords = triggers.get("keywords", [])
        if keywords:
            hook_name = f"skill-{name}"
            trig_json = json.dumps({"patterns": keywords, "mode": "any"}, ensure_ascii=False)
            act_json = json.dumps({"skills": [name]}, ensure_ascii=False)

            if dry_run:
                registered.append({
                    "name": hook_name,
                    "type": "keyword",
                    "patterns": keywords,
                    "skills": [name],
                    "dry_run": True,
                })
                continue

            cmd = [
                sys.executable, HOOKS_ENGINE, "register",
                hook_name, "keyword", "load_skill",
                "--trigger", trig_json,
                "--action", act_json,
                "--desc", f"Auto: {name} keyword trigger",
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                hook_id = None
                id_match = re.search(r'#(\d+)', r.stdout)
                if id_match:
                    hook_id = int(id_match.group(1))
                registered.append({
                    "name": hook_name,
                    "type": "keyword",
                    "hook_id": hook_id,
                    "patterns": keywords,
                    "success": r.returncode == 0,
                    "output": r.stdout.strip(),
                })
            except Exception as e:
                registered.append({
                    "name": hook_name,
                    "type": "keyword",
                    "error": str(e),
                    "success": False,
                })

        # 2) Tool call triggers
        tool_calls = triggers.get("tool_calls", [])
        if tool_calls:
            for tool_name in tool_calls:
                hook_name = f"skill-{name}-{tool_name}"
                trig_json = json.dumps({"tool": tool_name}, ensure_ascii=False)
                act_json = json.dumps({"skills": [name]}, ensure_ascii=False)

                if dry_run:
                    registered.append({
                        "name": hook_name,
                        "type": "tool_post",
                        "tool": tool_name,
                        "dry_run": True,
                    })
                    continue

                cmd = [
                    sys.executable, HOOKS_ENGINE, "register",
                    hook_name, "tool_post", "load_skill",
                    "--trigger", trig_json,
                    "--action", act_json,
                    "--desc", f"Auto: {name} after {tool_name}",
                ]
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    registered.append({
                        "name": hook_name,
                        "type": "tool_post",
                        "tool": tool_name,
                        "success": r.returncode == 0,
                        "output": r.stdout.strip(),
                    })
                except Exception as e:
                    registered.append({
                        "name": hook_name,
                        "type": "tool_post",
                        "error": str(e),
                        "success": False,
                    })

        # 3) Event triggers
        events = triggers.get("events", [])
        if events:
            for event_name in events:
                hook_name = f"skill-{name}-evt"
                trig_json = json.dumps({"event": event_name}, ensure_ascii=False)
                act_json = json.dumps({"skills": [name]}, ensure_ascii=False)

                if dry_run:
                    registered.append({
                        "name": hook_name,
                        "type": "event",
                        "event": event_name,
                        "dry_run": True,
                    })
                    continue

                cmd = [
                    sys.executable, HOOKS_ENGINE, "register",
                    hook_name, "event", "load_skill",
                    "--trigger", trig_json,
                    "--action", act_json,
                    "--desc", f"Auto: {name} on {event_name}",
                ]
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    registered.append({
                        "name": hook_name,
                        "type": "event",
                        "event": event_name,
                        "success": r.returncode == 0,
                        "output": r.stdout.strip(),
                    })
                except Exception as e:
                    registered.append({
                        "name": hook_name,
                        "type": "event",
                        "error": str(e),
                        "success": False,
                    })

    return registered


def generate_triggers_reference(entries: list[dict]) -> str:
    """Generate TRIGGERS_REFERENCE.md — human-readable trigger map."""
    lines = [
        "---",
        "autogenerated: true",
        f"generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "---",
        "",
        "# 📌 Skill Trigger Reference (Auto-Generated)",
        "",
        "本文件自动生成。每次运行 `skill_trigger_index.py scan` 后刷新。",
        "",
        "## 用法",
        "",
        "当用户消息包含以下关键词时，**必须** `skill_view()` 加载对应技能：",
        "",
    ]

    # Group by category
    by_category = {}
    for entry in entries:
        if not entry.get("triggers"):
            continue
        cat = entry.get("category", "uncategorized")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(entry)

    for cat, cat_entries in sorted(by_category.items()):
        lines.append(f"### {cat.title()}")
        lines.append("")
        for entry in sorted(cat_entries, key=lambda e: e['name']):
            t = entry['triggers']
            keywords = t.get('keywords', [])
            tool_calls = t.get('tool_calls', [])
            events = t.get('events', [])

            parts = []
            if keywords:
                parts.append(f"keywords: `{'`, `'.join(keywords)}`")
            if tool_calls:
                parts.append(f"tools: `{'`, `'.join(tool_calls)}`")
            if events:
                parts.append(f"events: `{'`, `'.join(events)}`")

            trigger_str = " · ".join(parts)
            lines.append(f"- **{entry['name']}** — {trigger_str}")
            if entry.get('description'):
                lines.append(f"  _({entry['description'][:80]})_")
            lines.append("")

    # Add skills without triggers
    untriggered = [e for e in entries if not e.get('triggers')]
    if untriggered:
        lines.append("### ⚠️ 未设置触发器的技能")
        lines.append("")
        for entry in sorted(untriggered, key=lambda e: e['name']):
            lines.append(f"- {entry['name']} ({entry.get('category', '?')})")
        lines.append("")

    # Stats footer
    total = len(entries)
    triggered = total - len(untriggered)
    lines.append(f"---")
    lines.append(f"共 {total} 技能 | {triggered} 有触发器 | {len(untriggered)} 无触发器")

    return "\n".join(lines)


def validate_skills(entries: list[dict]) -> list[dict]:
    """Validate all SKILL.md for completeness."""
    issues = []
    for entry in entries:
        checks = []
        if not entry['name']:
            checks.append("missing name")
        if not entry.get('description'):
            checks.append("missing description")
        if not entry.get('category'):
            checks.append("missing category")
        if not entry.get('triggers'):
            checks.append("no triggers (recommended)")
        if checks:
            issues.append({
                "name": entry['name'] or entry['path'],
                "path": entry['path'],
                "issues": checks,
            })
    return issues


# =====================================================================
# CLI
# =====================================================================

def cli():
    if len(sys.argv) < 2:
        print("使用: python3 skill_trigger_index.py <命令>")
        print("")
        print("  scan         扫描所有 skill + 自动注册 hooks")
        print("  scan --dry   只扫描不注册 (预览)")
        print("  list         列出所有已检测的触发器")
        print("  validate     检查所有 SKILL.md 完整性")
        print("  ref          生成 TRIGGERS_REFERENCE.md")
        print("  help         显示帮助")
        return

    cmd = sys.argv[1]

    # ---- scan ----
    if cmd == "scan":
        dry_run = "--dry" in sys.argv or "-n" in sys.argv
        print(f"{'🔍 DRY-RUN' if dry_run else '🔍'} 扫描 skill 触发器...")

        entries = scan_all_skills()
        print(f"   找到 {len(entries)} 个 skill")

        triggered = [e for e in entries if e.get('triggers')]
        print(f"   有触发器声明: {len(triggered)}")

        if triggered:
            print("\n   已检测触发器:")
            for e in triggered:
                t = e['triggers']
                kw = t.get('keywords', [])
                tc = t.get('tool_calls', [])
                ev = t.get('events', [])
                parts = []
                if kw: parts.append(f"{len(kw)}关键词")
                if tc: parts.append(f"{len(tc)}工具")
                if ev: parts.append(f"{len(ev)}事件")
                print(f"     ✅ {e['name']:<28} ({', '.join(parts)})")

        if dry_run:
            print("\n(Dry run — 未实际注册)")
            return

        print("\n   注册 hooks...")
        results = register_triggers(entries)
        ok = sum(1 for r in results if r.get('success'))
        fail = sum(1 for r in results if not r.get('success'))
        skip = sum(1 for r in results if r.get('dry_run'))
        if results:
            print(f"   已注册: ✅{ok} / ❌{fail} / ⏭️{skip}")
            for r in results:
                icon = "✅" if r.get('success') else "❌"
                print(f"     {icon} {r['name']:<35} {r.get('output','')}")
        else:
            print("   无新触发器可注册 (已存在则跳过)")

        # Generate reference
        generate_triggers_reference(entries)
        with open(TRIGGERS_FILE, "w") as f:
            f.write(generate_triggers_reference(entries))
        print(f"\n   已生成: {TRIGGERS_FILE}")

        # Validate
        issues = validate_skills(entries)
        no_triggers = [i for i in issues if 'no triggers (recommended)' in i['issues']]
        other = [i for i in issues if i not in no_triggers]
        if other:
            print(f"\n   ⚠️ 完整性检查 ({len(other)} 个问题):")
            for i in other:
                print(f"     ❌ {i['name']}: {', '.join(i['issues'])}")
        if no_triggers:
            print(f"\n   ℹ️  无触发器: {len(no_triggers)} 个 skill (可手动添加 `triggers:` 字段)")
        print("\n✅ 扫描完成")

    # ---- list ----
    elif cmd == "list":
        entries = scan_all_skills()
        triggered = [e for e in entries if e.get('triggers')]
        untriggered = [e for e in entries if not e.get('triggers')]

        print(f"📋 技能触发器索引 ({len(entries)} 个)")
        print(f"")
        for e in triggered:
            t = e['triggers']
            kw = t.get('keywords', [])
            tc = t.get('tool_calls', [])
            ev = t.get('events', [])
            parts = []
            if kw: parts.append(f"🔑 {', '.join(kw[:3])}{'...' if len(kw)>3 else ''}")
            if tc: parts.append(f"🛠 {', '.join(tc)}")
            if ev: parts.append(f"📢 {', '.join(ev)}")
            print(f"  ✅ {e['name']:<28} {' · '.join(parts)}")

        if untriggered:
            print(f"\n  ⚠️ 无触发器的 skill:")
            for e in untriggered:
                print(f"     {e['name']:<28} ({e.get('category','?')})")

    # ---- validate ----
    elif cmd == "validate":
        entries = scan_all_skills()
        issues = validate_skills(entries)
        if not issues:
            print("✅ 全部 skill 通过完整性检查")
            return
        print(f"📋 技能完整性检查 ({len(issues)} 个问题):")
        for i in issues:
            print(f"  ❌ {i['name']:<28} ({i['path']})")
            for chk in i['issues']:
                print(f"      - {chk}")

    # ---- ref ----
    elif cmd == "ref":
        entries = scan_all_skills()
        ref = generate_triggers_reference(entries)
        with open(TRIGGERS_FILE, "w") as f:
            f.write(ref)
        print(f"✅ 已生成触发器参考: {TRIGGERS_FILE}")
        print(f"   共 {len(entries)} 技能, "
              f"{sum(1 for e in entries if e.get('triggers'))} 有触发器")

    else:
        print(f"❌ 未知命令: {cmd}")
        print("可用命令: scan, list, validate, ref")


if __name__ == "__main__":
    cli()
