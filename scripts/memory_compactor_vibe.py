#!/usr/bin/env python3
"""
memory_compactor_vibe.py — 记忆压缩（两阶段：VibeThinker caveman 清洗 + 确定性截断）
cron 模式: no_agent=True
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from call_vibe import VibeAgent

MEMORY_PATH = "/opt/data/MEMORY.md"
USER_PATH = "/opt/data/USER.md"
MEMORY_LIMIT = 2000
USER_LIMIT = 1375
TRIGGER_RATIO = 0.80  # 降触发点，让格式清洗也跑

CAVEMAN_SYSTEM = """只做逐行格式转换，把"- 描述文字 (id:N [tag])" 变为 "id:N [tag] 提取的信息"

规则：
- 行以 "id:" 开头 → 保留原样
- 行以 "- " 开头，包含 (id:N [tag]) → 提取为 id:N [tag] + 精简描述（从括号前的描述中提取关键内容，不用"精简值"三字）
  例1: "- 用户偏好中文回复简洁 (id:6 [pref])" → "id:6 [pref] 中文·简洁"
  例2: "- LLM通过host.docker.internal访问 (id:3 [ollama])" → "id:3 [ollama] host.docker.internal:11434"
- 行以 "##" 开头或 "# MEMORY" → 保留原样
- 空行或 "§" → 保留
- 其他行 → 保留原样

禁止：不要输出"精简值"这三个字。
输出：只输出行。不解释，不思考。
"""


def vibe_clean_body(body_text: str) -> str:
    """VibeThinker 清洗正文：prose→id 格式"""
    try:
        lines = body_text.split("\n")
        # 分批：每批15行，避免模型超载
        batch_size = 15
        cleaned = []
        for i in range(0, len(lines), batch_size):
            batch = "\n".join(lines[i:i+batch_size])
            agent = VibeAgent(system=CAVEMAN_SYSTEM)
            result = agent.ask(
                f"逐行转换格式。输入:\n{batch}\n\n输出:",
                temperature=0.05,
                max_tokens=1024
            )
            output = result["response"].strip()
            if output:
                cleaned.append(output)
            else:
                # VibeThinker 失败时保留原文
                cleaned.append(batch)
        return "\n".join(cleaned)
    except Exception as e:
        return body_text  # 出错回退


def deterministic_compress(content: str, limit: int) -> str:
    """确定性截断：保留头部 + 尾部最新条目"""
    if len(content) <= limit:
        return content

    lines = content.split("\n")
    # 找头部（# MEMORY / ## IDENTITY 等）
    header_end = 0
    for i, line in enumerate(lines):
        if i > 0 and line.strip() == "" and header_end == 0:
            header_end = i
        if i > 0 and (line.startswith("## ") or line.startswith("---")):
            header_end = i + 1
        if i > 5 and line.strip() == "" and i - header_end > 1:
            header_end = i
            break

    header_lines = lines[:max(3, header_end)]
    body_lines = lines[max(3, header_end):]
    header_text = "\n".join(header_lines) + "\n"
    available = limit - len(header_text) - 10
    if available < 50:
        return truncate_force(content, limit)

    kept = []
    buffer = []
    for line in reversed(body_lines):
        is_entry_start = (
            line.startswith("id:") or
            line.strip().startswith("- ") or
            line.strip() in ("§", "") or
            line.strip().startswith("# ")
        )
        if is_entry_start and buffer:
            candidate = "\n".join(reversed(buffer)) + "\n"
            if len(candidate) > available:
                break
            kept.append(line)
            kept.extend(reversed(buffer))
            buffer = []
        elif is_entry_start and not buffer:
            line_len = len(line) + 1
            if line_len < available:
                kept.append(line)
                available -= line_len
            else:
                break
        else:
            buffer.append(line)

    if buffer:
        candidate = "\n".join(reversed(buffer)) + "\n"
        if len(candidate) <= available:
            kept.extend(reversed(buffer))

    body_kept = list(reversed(kept))
    result = header_text + "\n".join(body_kept)

    if len(result) > limit:
        cut = result.rfind("\n", 0, limit)
        if cut < len(header_text):
            cut = limit
        result = result[:cut] + "\n... [截断]"
    elif len(result) < len(content):
        result += "\n... [截断]"

    return result


def truncate_force(content: str, limit: int) -> str:
    lines = content.split("\n")
    head = "\n".join(lines[:3])
    tail = ""
    tail_len = 0
    for line in reversed(lines[3:]):
        if tail_len + len(line) + 1 > limit - len(head) - 20:
            break
        tail = line + "\n" + tail
        tail_len += len(line) + 1
    return head + "\n" + tail + "... [截断]"


def split_header_body(content: str):
    """拆成头部（标题+section标签）和正文（数据行）"""
    lines = content.split("\n")
    # 找第一个 ## section 或第一个 id: 行
    mid = 0
    for i, line in enumerate(lines):
        # 找到数据行的起始点
        if line.startswith("## ") or line.strip().startswith("id:"):
            mid = i
            break
    if mid == 0:
        # 回到简单的：第一行是标题
        mid = 1 if lines[0].startswith("# ") else 0
    # 标题 + 空行属于 header
    header_lines = lines[:mid]
    body_lines = lines[mid:]
    # 去除 header 尾部多余空行
    while header_lines and header_lines[-1].strip() == "":
        header_lines = header_lines[:-1]
    return "\n".join(header_lines), "\n".join(body_lines)


def compress(content: str, limit: int) -> tuple:
    """主入口：(压缩后内容, 主体标签) 主体: 3B/暴力/3B+暴力/"" """
    header, body = split_header_body(content)

    need_clean = len(content) > limit * TRIGGER_RATIO
    need_truncate = len(content) > limit

    if not need_clean:
        return content, ""  # 无动作

    cleaned_body = vibe_clean_body(body)
    merged = header + "\n" + cleaned_body
    vibe_did_work = (cleaned_body != body)

    if not need_truncate:
        return merged, ("3B" if vibe_did_work else "")

    # 阶段2：确定性截断
    result = deterministic_compress(merged, limit)
    actor = "暴力" if not vibe_did_work else "3B+暴力"
    return result, actor


def main():
    changed = []
    for path, limit, label in [
        (MEMORY_PATH, MEMORY_LIMIT, "MEMORY"),
        (USER_PATH, USER_LIMIT, "USER")
    ]:
        if not os.path.exists(path):
            continue
        with open(path, "r") as f:
            content = f.read()

        before = len(content)
        pct_before = round(before / limit * 100)

        if before <= limit * TRIGGER_RATIO:
            changed.append(f"{label}: ✅ {before}/{limit} ({pct_before}%) 不动")
            continue

        compressed, actor = compress(content, limit)
        with open(path, "w") as f:
            f.write(compressed)

        after = len(compressed)
        pct_after = round(after / limit * 100)
        saved = before - after
        actor_tag = f" [{actor}]" if actor else ""
        changed.append(f"{label}: ⚠️ {before}({pct_before}%)→{after}({pct_after}%){actor_tag} 省{saved}")

    if not changed:
        return
    print("━━━ 记忆压缩报告 ━━━")
    for line in changed:
        print(line)
    print(f"时间: {time.strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
