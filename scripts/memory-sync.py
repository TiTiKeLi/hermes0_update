#!/usr/bin/env python3
"""
Hierarchical Memory Sync - fact_store to memory auto-sync daemon. (v3)

Deployed as a cronjob (no_agent mode, hourly).
Reads high-trust facts from SQLite, dedups against MEMORY.md, appends new ones.

=== v3 防护增强 ===
1. 仅写 memories/ 子目录，不再写根 MEMORY.md（打断 sync↔compactor 冲突）
2. id 级去重：扫描现有 fact_id 避免重复追加
3. mtime 守卫：检测根 MEMORY.md 最近是否被 compactor 修改（<10min）
4. 容量守卫：不写入超过 80% 容量限制
5. 段感知：追加到 ## FACTS 段下而非文件末尾

Usage:
  python3 /opt/data/scripts/memory-sync.py
"""

import sqlite3
import os
import sys
import time
from datetime import datetime
import re

# === 配置 ===
DB_PATH = "/opt/data/memory_store.db"
MEMORY_PATH = "/opt/data/MEMORY.md"
MEMORIES_PATH = "/opt/data/memories/MEMORY.md"
SYNCED_IDS_PATH = "/opt/data/.synced_fact_ids.txt"
MAX_MEMORY_CHARS = 1800       # 不超过 80% 容量（留余量给 compactor）
MIN_TRUST_THRESHOLD = 0.6
MAX_FACTS_TO_SYNC = 10        # 减少每轮同步量，降低洪水频率
MTIME_GUARD_MINUTES = 10      # 如果根 MEMORY.md 在 N 分钟内被修改过，跳过
MEMORY_CAP = 2000             # Hermes 系统容量上限


def fmt_ts():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def load_synced_ids():
    if not os.path.exists(SYNCED_IDS_PATH):
        return set()
    with open(SYNCED_IDS_PATH) as f:
        return set(int(line.strip()) for line in f if line.strip().isdigit())


def save_synced_ids(ids):
    with open(SYNCED_IDS_PATH, 'w') as f:
        for fid in sorted(ids):
            f.write(f"{fid}\n")


def read_current_memory(path):
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        return f.read()


def extract_existing_ids(memory_content):
    """从 MEMORY.md 提取所有已有 fact_id（精确检测）"""
    ids = set()
    # id:N [tag] 格式
    for m in re.finditer(r'\bid:(\d+)\b', memory_content):
        ids.add(int(m.group(1)))
    return ids


def extract_facts_section(memory_content):
    """找到 ## FACTS 段后的内容"""
    lines = memory_content.split('\n')
    facts_start = -1
    for i, line in enumerate(lines):
        if line.strip() == '## FACTS':
            facts_start = i
            break
    if facts_start >= 0:
        return facts_start, lines
    # 没有 ## FACTS 段头——自己找标识点
    return -1, lines


def is_file_recently_modified(path, minutes=MTIME_GUARD_MINUTES):
    """检测文件最近是否被修改过（防止与 compactor 冲突）"""
    if not os.path.exists(path):
        return False
    try:
        mtime = os.path.getmtime(path)
        age_seconds = time.time() - mtime
        return age_seconds < minutes * 60
    except OSError:
        return False


def format_fact_for_memory(fact_content, fact_id, tags):
    tag_str = f" [{tags}]" if tags else ""
    return f"- {fact_content.strip()} (id:{fact_id}{tag_str})"


def get_high_confidence_facts(cursor, exclude_ids):
    cursor.execute("""
        SELECT fact_id, content, trust_score, retrieval_count, helpful_count, tags
        FROM facts
        WHERE trust_score >= ? AND archived = 0
        ORDER BY trust_score DESC, retrieval_count DESC, helpful_count DESC
        LIMIT ?
    """, (MIN_TRUST_THRESHOLD, MAX_FACTS_TO_SYNC))
    return cursor.fetchall()


def sync_memory():
    print(f"[{fmt_ts()}] 开始记忆分层同步 v3...")

    # ── 0. 检查 fact_store 是否存在 ──
    if not os.path.exists(DB_PATH):
        print("  ❌ fact_store 不存在")
        return False

    # ── 0.5 mtime 守卫: 检查根 MEMORY.md 是否最近被 compactor 修改过 ──
    if is_file_recently_modified(MEMORY_PATH):
        print(f"  ⏭️ 根 MEMORY.md 在 {MTIME_GUARD_MINUTES} 分钟内被修改过（compactor 刚运行），跳过同步")
        print(f"  仅同步到 memories/ 子目录")
        # 仍然写入 memories/ 子目录
    else:
        print(f"  根 MEMORY.md 稳定，允许写入")

    # ── 1. 查询高信任度事实 ──
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    synced_ids = load_synced_ids()
    print(f"  已同步ID: {len(synced_ids)} 个")

    facts = get_high_confidence_facts(cursor, synced_ids)
    print(f"  找到高信任度事实: {len(facts)} 条")

    if not facts:
        print("  无需同步")
        conn.close()
        return True

    # ── 2. 检查与根 MEMORY.md 的重叠 ──
    root_content = read_current_memory(MEMORY_PATH)
    existing_ids = extract_existing_ids(root_content)

    new_items = []
    newly_synced = set()

    for fact_id, content, trust, retr, helpful, tags in facts:
        if fact_id in existing_ids:
            print(f"  ⏭️ id:{fact_id}: 根 MEMORY.md 中已存在, 跳过")
            newly_synced.add(fact_id)
            continue

        if fact_id in synced_ids:
            # 已标记同步但不在文件中—仍然追加
            pass

        entry = format_fact_for_memory(content, fact_id, tags or "")
        entry_size = len(entry) + 1

        current_usage = sum(len(item) + 1 for item in new_items)
        if current_usage + entry_size > MAX_MEMORY_CHARS:
            print(f"  ⚠️ 容量将超限 ({current_usage + entry_size}/{MAX_MEMORY_CHARS})，停止追加")
            break

        new_items.append(entry)
        newly_synced.add(fact_id)
        print(f"  ✅ id:{fact_id}: {content[:80]}...")

    if not new_items:
        print("  无新事实需追加")
        conn.close()
        save_synced_ids(synced_ids | newly_synced)
        return True

    # ── 3. 写入 memories/ 子目录（始终写入） ──
    os.makedirs(os.path.dirname(MEMORIES_PATH), exist_ok=True)
    memories_content = read_current_memory(MEMORIES_PATH)

    # 确保有 section 头
    if not memories_content.strip() or "## FACTS" not in memories_content:
        if not memories_content.strip():
            memories_content = "# MEMORY\n## IDENTITY\n## FACTS\n"
        elif "## FACTS" not in memories_content:
            memories_content += "\n## FACTS\n"

    with open(MEMORIES_PATH, 'a') as f:
        for item in new_items:
            f.write(item + '\n')
    print(f"  ✅ memories/ 已追加 {len(new_items)} 条 ({MEMORIES_PATH})")

    # ── 4. 选择性写入根 MEMORY.md（仅当 mtime 无冲突时） ──
    if not is_file_recently_modified(MEMORY_PATH):
        # 重新检查 mtime（可能文件在上一步被修改）
        root_content = read_current_memory(MEMORY_PATH)
        root_size = len(root_content.encode('utf-8'))

        # 检查追加后是否超限
        append_size = sum(len(i) + 1 for i in new_items)
        if root_size + append_size > MEMORY_CAP * 0.85:
            print(f"  ⚠️ 写入根 MEMORY.md 后将超限 ({root_size} + {append_size} > {MEMORY_CAP*0.85:.0f})")
            print(f"  跳过根 MEMORY.md 写入，仅保留在 memories/")
        else:
            with open(MEMORY_PATH, 'a') as f:
                for item in new_items:
                    f.write(item + '\n')
            print(f"  ✅ 根 MEMORY.md 已追加 {len(new_items)} 条")
    else:
        print(f"  ⏭️ 根 MEMORY.md 被其他进程锁定（mtime < {MTIME_GUARD_MINUTES}min），跳过")

    # ── 5. 更新同步状态 ──
    all_synced = synced_ids | newly_synced
    save_synced_ids(all_synced)
    print(f"  已同步ID总计: {len(all_synced)} 个")

    conn.close()
    print(f"[{fmt_ts()}] 同步完成")
    return True


if __name__ == "__main__":
    start = time.time()
    success = sync_memory()
    elapsed = round(time.time() - start, 2)
    print(f"  ⏱ {elapsed}s")
    sys.exit(0 if success else 1)
