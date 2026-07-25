#!/usr/bin/env python3
"""
Hierarchical Memory Sync — fact_store → memory auto-sync daemon.

Deployed as a cronjob (no_agent mode, hourly).
Reads high-trust facts from SQLite, dedups against MEMORY.md, appends new ones.

Usage:
  python3 /opt/data/scripts/memory-sync.py
  # or from ~/.hermes/scripts/: memory-sync.py (cronjob path)
"""

import sqlite3
import os
import sys
from datetime import datetime

DB_PATH = "/opt/data/memory_store.db"
MEMORY_PATH = "/opt/data/MEMORY.md"
MEMORIES_PATH = "/opt/data/memories/MEMORY.md"
SYNCED_IDS_PATH = "/opt/data/.synced_fact_ids.txt"
MAX_MEMORY_CHARS = 2100
MIN_TRUST_THRESHOLD = 0.6
MAX_FACTS_TO_SYNC = 15


def load_synced_ids():
    if not os.path.exists(SYNCED_IDS_PATH):
        return set()
    with open(SYNCED_IDS_PATH) as f:
        return set(int(line.strip()) for line in f if line.strip().isdigit())


def save_synced_ids(ids):
    with open(SYNCED_IDS_PATH, 'w') as f:
        for fid in sorted(ids):
            f.write(f"{fid}\n")


def get_high_confidence_facts(cursor, exclude_ids):
    cursor.execute("""
        SELECT fact_id, content, trust_score, retrieval_count, helpful_count, tags
        FROM facts
        WHERE trust_score >= ?
        ORDER BY trust_score DESC, retrieval_count DESC, helpful_count DESC
        LIMIT ?
    """, (MIN_TRUST_THRESHOLD, MAX_FACTS_TO_SYNC))
    return cursor.fetchall()


def read_current_memory(path):
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        return f.read()


def extract_existing_facts(memory_content):
    facts = set()
    for line in memory_content.split('\n'):
        line = line.strip()
        if line.startswith('- ') or line.startswith('* '):
            clean = line[2:].strip()
            if clean and len(clean) > 10:
                facts.add(clean.lower())
        if '**' in line and '-' in line:
            parts = line.split('**')
            for p in parts:
                p = p.strip().strip(':').strip()
                if len(p) > 15:
                    facts.add(p.lower())
    return facts


def is_duplicate(content, existing_facts, threshold=0.7):
    content_lower = content.lower()
    if content_lower in existing_facts:
        return True
    words = set(content_lower.split())
    if len(words) < 3:
        return content_lower in existing_facts
    for existing in existing_facts:
        existing_words = set(existing.split())
        if len(existing_words) < 3:
            continue
        overlap = len(words & existing_words) / min(len(words), len(existing_words))
        if overlap > threshold:
            return True
    return False


def format_fact_for_memory(fact_content, fact_id, tags):
    tag_str = f" [{tags}]" if tags else ""
    return f"- {fact_content.strip()} (id:{fact_id}{tag_str})"


def sync_memory():
    print(f"[{datetime.now().isoformat()}] 开始记忆分层同步...")
    
    if not os.path.exists(DB_PATH):
        print("  ❌ fact_store 不存在")
        return False
    
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
    
    memory_content = read_current_memory(MEMORY_PATH)
    existing_facts = extract_existing_facts(memory_content)
    
    new_items = []
    newly_synced = set()
    
    for fact_id, content, trust, retr, helpful, tags in facts:
        if is_duplicate(content, existing_facts):
            print(f"  ⏭️ {fact_id}: 已存在, 跳过")
            newly_synced.add(fact_id)
            continue
        
        entry = format_fact_for_memory(content, fact_id, tags or "")
        entry_size = len(entry) + 1
        
        current_size = len(memory_content) + sum(len(item) + 1 for item in new_items)
        
        if current_size + entry_size > MAX_MEMORY_CHARS:
            print(f"  ⚠️ memory 容量将超限，停止追加")
            break
        
        new_items.append(entry)
        newly_synced.add(fact_id)
        print(f"  ✅ {fact_id}: {content[:80]}...")
    
    if new_items:
        with open(MEMORY_PATH, 'a') as f:
            f.write('\n')
            for item in new_items:
                f.write(item + '\n')
        
        if os.path.exists(MEMORIES_PATH):
            with open(MEMORIES_PATH, 'a') as f:
                f.write('\n')
                for item in new_items:
                    f.write(item + '\n')
        
        print(f"  ✅ 已追加 {len(new_items)} 条新事实")
    else:
        print("  无新事实需追加")
    
    all_synced = synced_ids | newly_synced
    save_synced_ids(all_synced)
    print(f"  已同步ID总计: {len(all_synced)} 个")
    
    conn.close()
    print(f"[{datetime.now().isoformat()}] 同步完成")
    return True


if __name__ == "__main__":
    success = sync_memory()
    sys.exit(0 if success else 1)
