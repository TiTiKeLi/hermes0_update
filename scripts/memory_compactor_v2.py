#!/usr/bin/env python3
"""
memory_compactor_v2.py — 记忆压缩 v2（去重优先 + 归档 + 钩子）
cron 模式: no_agent=True

策略（解决"尾部提取是反的"问题）：
  Phase 1 — 按 id 去重合并：同 id 保留最完整版本，移除其他
  Phase 2 — 按语义价值归档：优先归档 preference / project 类条目
  Phase 3 — 留钩子到外部归档

零依赖，纯 Python。
"""

import os, re, time, datetime

# ── 配置 ──
MEMORY_PATH = "/opt/data/MEMORY.md"
USER_PATH = "/opt/data/USER.md"
ARCHIVE_DIR = "/opt/data/memories/archive/"

MEMORY_LIMIT = 2000
USER_LIMIT = 1375
MEMORY_ALERT_PCT = 85
USER_ALERT_PCT = 75
BIDIR_THRESHOLD = 70
EXTRACT_COUNT = 8          # 每轮最多归档条目数

# 永不归档的身份键
IDENTITY_KEYS = {"host", "ollama", "model", "interface", "lang"}
# 优先归档的类别（preference > project > 其他）
ARCHIVE_PRIORITY = {"preference": 0, "profile": 0, "test": 1}

# ── 文件工具 ──

def load(path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return f.read()
    return ''

def save(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

def fmt_ts():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# ── 解析器 ──

ID_PATTERN = re.compile(r'^id:(\d+)\s+\[([^\]]+)\]\s*(.*)')
LINE_PATTERN = re.compile(r'^-\s+(.*)\(id:(\d+)\s+\[([^\]]+)\]\)')

def parse_lines(text):
    """解析 MEMORY.md 为结构化数据。
    返回 (header_lines, identity_entries, fact_entries, style_lines)
    
    header_lines: # MEMORY 和 ## IDENTITY/## FACTS 之类的行
    identity_entries: [{tag, content, raw}]
    fact_entries: [{id, tag, content, raw, type}]  # type='id:' or '-'
    style_lines: 其他无法解析的行（空行、分隔线等）
    """
    lines = text.split('\n')
    header_lines = []
    identity_entries = []
    fact_entries = []
    style_lines = []
    
    section = 'header'
    for line in lines:
        stripped = line.strip()
        
        # 忽略钩子行
        if '→ 📦' in stripped or 'Archive:' in stripped:
            style_lines.append(line)
            continue
        
        # 段标题
        if stripped.startswith('#') or stripped.startswith('##'):
            if 'FACTS' in stripped or 'MEMORY' in stripped:
                section = 'facts'
            if 'IDENTITY' in stripped:
                section = 'identity'
            header_lines.append(line)
            continue
        
        if section == 'header':
            header_lines.append(line)
            continue
        
        # IDENTITY 段（- key:value 格式）
        if section == 'identity':
            m = re.match(r'^-\s+(\w+):(.*)', stripped)
            if m:
                identity_entries.append({
                    'tag': m.group(1),
                    'content': m.group(2).strip(),
                    'raw': line
                })
                continue
            else:
                style_lines.append(line)
                continue
        
        # FACTS 段（id:N [tag] content 或 - content (id:N [tag])）
        if section == 'facts':
            m_id = ID_PATTERN.match(stripped)
            if m_id:
                fact_entries.append({
                    'id': int(m_id.group(1)),
                    'tag': m_id.group(2),
                    'content': m_id.group(3),
                    'raw': line,
                    'type': 'id:'
                })
                continue
            
            m_line = LINE_PATTERN.match(stripped)
            if m_line:
                fact_entries.append({
                    'id': int(m_line.group(2)),
                    'tag': m_line.group(3),
                    'content': m_line.group(1),
                    'raw': line,
                    'type': '-'
                })
                continue
            
            style_lines.append(line)
            continue
    
    return header_lines, identity_entries, fact_entries, style_lines


def resolve_section_lines(text):
    """轻量解析：按段 (IDENTITY / FACTS / 其他) 分割行列表"""
    lines = text.split('\n')
    sections = {'header': [], 'identity': [], 'facts': [], 'other': []}
    current = 'header'
    
    # 用于重建的关键标记
    identity_start = -1
    facts_start = -1
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # 一旦进入 facts 段，锁定不再退出（防止重复 IDENTITY 头）
        if current != 'facts':
            if stripped == '## IDENTITY':
                current = 'identity'
                identity_start = i
            elif stripped == '## FACTS':
                current = 'facts'
                facts_start = i
        
        if current == 'header':
            sections['header'].append((i, line))
        elif current == 'identity':
            sections['identity'].append((i, line))
        elif current == 'facts':
            # 过滤掉 facts 段内的重复 section 标题行（但保留原始 ## FACTS）
            if stripped.startswith('## ') and stripped != '## FACTS':
                continue  # 忽略嵌入的重复标题
            # 跳过旧钩子行
            if is_hook_line(stripped):
                continue
            sections['facts'].append((i, line))
        else:
            sections['other'].append((i, line))
    
    return sections, identity_start, facts_start


def should_trigger(mem_len, usr_len):
    mem_pct = round(mem_len / MEMORY_LIMIT * 100)
    usr_pct = round(usr_len / USER_LIMIT * 100)
    
    if mem_len > MEMORY_LIMIT * MEMORY_ALERT_PCT / 100:
        return True, f"MEMORY {mem_pct}% > {MEMORY_ALERT_PCT}%"
    if usr_len > USER_LIMIT * USER_ALERT_PCT / 100:
        return True, f"USER {usr_pct}% > {USER_ALERT_PCT}%"
    if (mem_len > MEMORY_LIMIT * BIDIR_THRESHOLD / 100 and
        usr_len > USER_LIMIT * BIDIR_THRESHOLD / 100):
        return True, f"双向 {mem_pct}% & {usr_pct}% > {BIDIR_THRESHOLD}%"
    
    return False, f"MEMORY {mem_pct}% | USER {usr_pct}%"


def is_hook_line(stripped):
    return '→ 📦' in stripped or 'Archive:' in stripped


def compact_memory(text):
    """
    核心压缩逻辑：
    Phase 1 — 按 id 去重合并（保留最完整版本）
    Phase 2 — 如果还超限，按语义优先级归档
    """
    sections, id_start, facts_start = resolve_section_lines(text)
    
    # ── Phase 1: 按 id 去重 ──
    # 从 FACTS 段提取所有条目行
    fact_lines = []          # (index, raw_line)
    id_map = {}              # id -> [(index, raw_line)]
    
    # 也收集 FACTS 段内的非条目行（如空行、注释）
    facts_styles = []
    
    for i, line in sections.get('facts', []):
        stripped = line.strip()
        if is_hook_line(stripped):
            facts_styles.append((i, line))
            continue
        
        m_id = ID_PATTERN.match(stripped)
        m_line = LINE_PATTERN.match(stripped) if not m_id else None
        
        if m_id:
            eid = int(m_id.group(1))
            tag = m_id.group(2)
            if eid not in id_map:
                id_map[eid] = []
            id_map[eid].append((i, line))
        elif m_line:
            eid = int(m_line.group(2))
            tag = m_line.group(3)
            if eid not in id_map:
                id_map[eid] = []
            id_map[eid].append((i, line))
        else:
            facts_styles.append((i, line))
    
    # 去重：同 id 保留内容最长的版本
    removed_count = 0
    deduped_lines = []  # (index, raw_line)
    
    for eid, entries in id_map.items():
        if len(entries) == 1:
            deduped_lines.append(entries[0])
        else:
            # 保留内容最长的
            best = max(entries, key=lambda x: len(x[1].strip()))
            deduped_lines.append(best)
            removed_count += len(entries) - 1
    
    # 按原行顺序重排 FACTS 段（排除旧钩子行）
    identity_entries = sections.get('identity', [])
    header_entries = sections.get('header', [])
    all_facts_lines = [(i, line) for i, line in deduped_lines]
    # 故意不 extend facts_styles —— 旧钩子行全部丢弃
    all_facts_lines.sort(key=lambda x: x[0])
    
    # ── 重建全文 ──
    new_lines = []
    # Header
    for i, line in header_entries:
        new_lines.append(line)
    
    # Identity（保持不变）
    for i, line in identity_entries:
        new_lines.append(line)
    
    # 旧的钩子行去掉，末尾再重新加
    # Facts（去重后）
    for i, line in all_facts_lines:
        new_lines.append(line)
    
    deduped_text = '\n'.join(new_lines) + '\n'
    deduped_size = len(deduped_text.encode('utf-8'))
    
    # ── Phase 2: 如果还超限，归档条目 ──
    archive_entries = []
    
    if deduped_size > MEMORY_LIMIT * MEMORY_ALERT_PCT / 100:
        # 重新解析去重后的事实条目，按优先级排序
        entries_for_archive = []  # (priority, id, tag, raw_line)
        
        for i, line in all_facts_lines:
            stripped = line.strip()
            if is_hook_line(stripped):
                continue
            
            m_id = ID_PATTERN.match(stripped)
            m_line = LINE_PATTERN.match(stripped) if not m_id else None
            
            if m_id:
                tag = m_id.group(2)
                eid = int(m_id.group(1))
            elif m_line:
                tag = m_line.group(3)
                eid = int(m_line.group(2))
            else:
                continue
            
            priority = ARCHIVE_PRIORITY.get(tag, 10)
            # identity 键永不归档
            if tag in IDENTITY_KEYS:
                continue
            entries_for_archive.append((priority, eid, tag, i, line))
        
        # 按优先级排序（低 priority 值优先归档 = preference 优先）
        entries_for_archive.sort(key=lambda x: (x[0], x[1]))  # 同优先级按 id
        
        # 每次归档 EXTRACT_COUNT 条
        to_archive = entries_for_archive[:EXTRACT_COUNT]
        keep_set = {e[3] for e in entries_for_archive[EXTRACT_COUNT:]}
        
        # 重建 facts 行（剔除要归档的）
        final_facts = []
        for i, line in sorted(all_facts_lines + identity_entries, key=lambda x: x[0]):
            if i in {e[3] for e in to_archive}:
                archive_entries.append(line)
            else:
                final_facts.append((i, line))
        
        final_facts.sort(key=lambda x: x[0])
        
        # 重建全文
        new_lines = []
        for i, line in header_entries:
            new_lines.append(line)
        for i, line in identity_entries:
            new_lines.append(line)
        for i, line in final_facts:
            new_lines.append(line)
        
        # 加钩子（仅当有实际归档条目时）
        if to_archive:
            today = datetime.date.today()
            archive_path = os.path.join(ARCHIVE_DIR, f"{today}.md")
            new_lines.append(f"→ 📦 Archive: {archive_path}")

        result_text = '\n'.join(new_lines) + '\n'
    else:
        result_text = deduped_text
    
    # 清理尾部空行
    result_text = result_text.rstrip('\n') + '\n'
    
    # 如果有多余空行，压缩
    while '\n\n\n' in result_text:
        result_text = result_text.replace('\n\n\n', '\n\n')
    
    return result_text, archive_entries, removed_count


def write_archive(entries):
    """写入归档文件"""
    today = datetime.date.today()
    path = os.path.join(ARCHIVE_DIR, f"{today}.md")
    
    # 如果今天已有归档，追加
    existing = load(path)
    
    lines = []
    if not existing:
        lines.append(f"# 记忆归档 — {today}")
        lines.append(f"*归档时间: {fmt_ts()}*\n")
    else:
        lines = existing.rstrip('\n').split('\n')
        lines.append(f"\n## 追加归档 {fmt_ts()}")
    
    for entry in entries:
        lines.append(f"- {entry.strip()}")
    
    save(path, '\n'.join(lines) + '\n')
    return path


def compact_file(path, limit, source_name):
    """通用压缩入口"""
    text = load(path)
    if not text.strip():
        return f"{source_name}: 空文件，跳过"
    
    raw_size = len(text.encode('utf-8'))
    if raw_size <= limit * MEMORY_ALERT_PCT / 100:
        raw_pct = round(raw_size / limit * 100)
        return f"{source_name}: {raw_size}B ({raw_pct}%) 正常，跳过"
    
    # 只有 MEMORY.md 做去重归档，USER.md 只检查
    if source_name == 'MEMORY':
        result, archived, removed = compact_memory(text)
        save(path, result)
        
        new_size = len(result.encode('utf-8'))
        new_pct = round(new_size / limit * 100)
        msgs = []
        if removed > 0:
            msgs.append(f"去重 {removed} 条")
        if archived:
            apath = write_archive(archived)
            msgs.append(f"归档 {len(archived)} 条到 {apath}")
        if not msgs:
            msgs.append("无需压缩")
        
        return f"{source_name}: {raw_size}B→{new_size}B ({new_pct}%) {' | '.join(msgs)}"
    else:
        # USER.md：仅报告
        raw_pct = round(raw_size / limit * 100)
        return f"{source_name}: {raw_size}B ({raw_pct}%) 超限但 USER 不归档"


# ── 主入口 ──

def main():
    mem_raw = load(MEMORY_PATH)
    mem_size = len(mem_raw.encode('utf-8'))
    usr_size = len(load(USER_PATH).encode('utf-8'))
    
    # ── 前哨安全检查：文件异常膨胀检测 ──
    # 正常 MEMORY.md 应 < 10KB（约 200 行），超过即视为损坏
    SANITY_MAX_SIZE = 10 * 1024  # 10KB
    SANITY_MAX_LINES = 2000      # 正常约 30-50 行
    if mem_size > SANITY_MAX_SIZE:
        line_count = len(mem_raw.split('\n'))
        print(f"🚨 安全门: MEMORY.md 异常 ({mem_size/1024:.0f}KB, {line_count}行)")
        print(f"  预期 < {SANITY_MAX_SIZE//1024}KB, 实际 {mem_size//1024}KB")
        print(f"  跳过压缩。文件可能已损坏。请手动检查 /opt/data/MEMORY.md")
        print(f"  恢复参考: skill_view('memory-compactor', 'references/runaway-252mb-recovery.md')")
        # 仍报告 USER 状态
        usr_pct = round(usr_size / USER_LIMIT * 100)
        print(f"  USER: {usr_size}B ({usr_pct}%)")
        return
    
    trigger, reason = should_trigger(mem_size, usr_size)
    if not trigger:
        print(f"✅ {reason}")
        return
    
    print(f"⚠️  触发: {reason}")
    
    result = compact_file(MEMORY_PATH, MEMORY_LIMIT, 'MEMORY')
    print(f"  {result}")
    
    result2 = compact_file(USER_PATH, USER_LIMIT, 'USER')
    print(f"  {result2}")


if __name__ == '__main__':
    start = time.time()
    main()
    elapsed = round(time.time() - start, 2)
    print(f"  ⏱ {elapsed}s")
