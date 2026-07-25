# 记忆膨胀恢复记录 — 2026-07-25

## 症状

- MEMORY.md 显示 96%（2,127/2,200），但实际文件大小 252MB
- `wc -c` 报告 252,709,155 字节
- `file` 显示 "Unicode text, UTF-8 text"
- compactor 脚本每次运行超时（>15s）
- 文件开头正常，尾部有 ~840 万行重复

## 诊断步骤

```bash
# 1. 检查实际文件大小
wc -c /opt/data/MEMORY.md
# → 252709155

# 2. 检查重复模式
head -50 /opt/data/MEMORY.md
# 第一轮 IDENTITY + 钩子行

# 3. 统计重复量
grep -c "📦 Archive:" /opt/data/MEMORY.md
# → 1048596

# 4. 定位真实 FACTS 段（首行之后第一个 id:）
grep -n "id:" /opt/data/MEMORY.md | head -5
# → 8388610+ 行处有 9 个 id: 行

# 5. 确认文件结构：header(7行) + 重复IDENTITY块(838万行) + FACTS段(末尾)
```

## 根因

compactor v5 脚本 `memory_compactor_v2.py` 有两个连环 bug：

### Bug A: resolve_section_lines 不锁定 section 状态

```python
# 错误：遇到 ## FACTS 后仍然响应后续 ## IDENTITY
if stripped == '## IDENTITY':
    current = 'identity'
elif stripped == '## FACTS':
    current = 'facts'

# 修复：锁定，一旦进入 facts 不再出来
if current != 'facts':
    if stripped == '## IDENTITY':
        current = 'identity'
    elif stripped == '## FACTS':
        current = 'facts'
```

当文件因任意原因出现重复 `## IDENTITY` 段头（如上一次写中断），parser 每遇到一次就重新进入 identity 模式，保留所有重复行。每次 compactor 输出再追加一行钩子 → 文件越来越大。

### Bug B: compact_memory 保留旧钩子 + 加新钩子

```python
# 错误：facts_styles（旧钩子行）被保留，末尾再加新钩子
all_facts_lines.extend(facts_styles)  # ← 保留旧钩子
...
new_lines.append(f"→ 📦 Archive: {path}\n")  # ← 再加新钩子

# 修复：丢弃 facts_styles，仅在有归档时加新钩子
# 不 extend facts_styles
if to_archive:
    new_lines.append(f"→ 📦 Archive: {path}")
```

每轮 cron（每5分钟）多一行，但一旦重复 IDENTITY 出现 → 那行也会被保留 → 正向反馈循环。

## 恢复步骤

```bash
# 1. 提取真实 header 和 facts 段
head -7 /opt/data/MEMORY.md > /tmp/header.txt
echo "" >> /tmp/header.txt  # 加空行分隔

# 2. 找到 facts 段起始行
grep -n "id:" /opt/data/MEMORY.md | head -3
# 记下第一个 id: 行的行号（本例 8388610）

# 3. 提取 facts 段
tail -n+8388610 /opt/data/MEMORY.md > /tmp/facts.txt

# 4. 检查 facts.txt，删除尾部多余的钩子行
# （保留 ## FACTS 标题行及真实条目，去掉 → 📦 Archive: 行）

# 5. 重建 MEMORY.md
cat /tmp/header.txt /tmp/facts.txt > /tmp/MEMORY_clean.md
# 或手动写入干净版本

# 6. 验证
wc -c /opt/data/MEMORY.md  # 应在1-2KB
file /opt/data/MEMORY.md   # UTF-8 text
```

## 预防措施

1. `resolve_section_lines` 中锁定 section 状态
2. `compact_memory` 中丢弃旧钩子行
3. 仅在有实际归档条目时追加新钩子行
4. 保留 `## FACTS` 段头不过滤
5. **前哨安全检查** — main() 启动时检测文件 > 10KB 立即中止（v6 新增），防止任何场景下的二次膨胀
6. **mtime 守卫** — memory-sync.py v3 不再无条件写入根 MEMORY.md，仅当 compactor 未在 10min 内运行时才写入
7. **id 级去重** — memory-sync.py v3 扫描已有 fact_id 避免重复追加，减少慢膨胀源
8. **容量守卫** — memory-sync.py v3 不超过 80% 容量限制

## 相关链接

- `/opt/data/hooks/references/sync-compactor-conflict.md` — sync↔compactor 冲突全分析
- `/opt/data/MEMORY.md` — 当前干净版本
