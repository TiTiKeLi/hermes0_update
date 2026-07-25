# Sync ↔ Compactor 冲突分析 (2026-07-25 已修复)

## 死锁因果链

### 涉及组件

| 组件 | 角色 | 频率 | 操作文件 |
|------|------|------|----------|
| `memory-sync.py` | fact_store → memory 同步 | 每小时 | 根 `/opt/data/MEMORY.md` + `/opt/data/memories/MEMORY.md` |
| `memory_compactor_v2.py` | 去重+归档+压缩 | 每5分钟 | 根 `/opt/data/MEMORY.md` + `/opt/data/USER.md` |
| Hermes Agent | 读取 MEMORY.md 做上下文 | 每会话 | 根 `/opt/data/MEMORY.md`（仅前 2200 字符） |

### 连锁反应链

```
Stage 1: 初始触发
  memory-sync.py (v2) 写入一条新事实到根 MEMORY.md
  → 文件轻微膨胀

Stage 2: 去重失效
  memory_compactor_v2.py (v5) 运行
  → resolve_section_lines() 遇到重复 ## IDENTITY → 不锁定 → 保留所有重复
  → compact_memory() 保留旧 → 📦 Archive: 行 + 追加新一行
  → 文件 2倍增长 (Bug A + Bug B 正反馈)

Stage 3: 死亡螺旋
  下一轮 → compactor 读 2倍大文件 → 又保留全部重复 → 又是 2倍
  每小时 sync 追加新事实 → 更多燃料
  每5分钟 compactor 加倍一次 → 5.6 小时达 1TB
  实际 2.25 小时达 252MB（文件系统限速）

Stage 4: 隐形危机
  Hermes 只读前 2200 字符 → MEMORY.md 前 2KB 永远正常
  cpu 2 持续 100% → 用户无感知（docker stats 看不到）
  容器磁盘 252MB 垃圾 → 9p 协议传输缓慢
  所有 ls/wc 命令卡顿

Stage 5: 外显症状
  用户发现"记忆占 96%"（仅看前 2200 → 实际文件 252MB）
  compactor 运行 >15s 超时
  cat 命令显示 840 万行 > 2MB 终端输出
```

## 三个 Bug 的根因

### Bug A: resolve_section_lines 不锁定 section 状态

```python
# ❌ 旧代码
if stripped == '## IDENTITY': 
    current = 'identity'
# → 文件中有 N 个 ## IDENTITY? 处理 N 次，每次都保留所有内容

# ✅ 新代码
if current != 'facts' and stripped == '## IDENTITY':
    current = 'identity'
# → 一旦进入 facts 段就锁死，不再响应任何段头
```

**为什么会有重复段头**：`memory-sync.py` 的 `append` 不检查文件结构。如果它在文件末尾追加一行 `- 描述 (id:N [tag])`，而文件末尾正好在 `## FACTS` 段中，就没事。但如果 compactor 上次写入时钩子行被追加到了文件末尾（段头结构外），sync 追加时无段感知，引入悬空行。compactor 再次读取时，悬空行 → 落在 'header' 段 → 保留 → 每次 compactor 跑都可能产生新的结构错乱，最终 `## IDENTITY` 被复制。

### Bug B: compact_memory 保留旧钩子 + 追加新钩子

```python
# ❌ 旧代码
all_facts_lines.extend(facts_styles)  # facts_styles 包含所有旧 → 📦 Archive: 行
...
new_lines.append(f"→ 📦 Archive: ...")  # 再加一条新的
# → 每跑一轮就多一条钩子

# ✅ 新代码
# 完全丢弃 facts_styles，仅在有实际归档条目时才追加新钩子行
```

**演化**：compactor 每 5 分钟跑一次，每次保留之前所有 `→ 📦 Archive:` 行再加 1 条。
- 1 小时: 12 条
- 12 小时: 144 条
- 但有 Bug A 的 2x 增长，钩子行也被 2x 复制 → 指数级 + 线性级叠加

### Bug C: 前哨安全检查缺失

**根本不存在**大小/行数校验。compactor 对 252MB 文件的反应和 2KB 文件完全相同——读入内存、逐行处理、写回。没有"文件异常大"的感知。

## 修复总览

### memory_compactor_v2.py
1. ✅ resolve_section_lines: 进入 facts 段后锁定 current
2. ✅ compact_memory: 丢弃旧钩子行，仅按需追加新钩子
3. ✅ FACTS 标题过滤: `if stripped.startswith('## ') and stripped != '## FACTS'`
4. ✅ 前哨安全检查: `if mem_size > 10KB → 🚨` 中止，提示手动恢复

### memory-sync.py
1. ✅ 停止无条件写根 MEMORY.md — 优先写 memories/
2. ✅ id 级去重 — 精确检测已存在的 fact_id
3. ✅ mtime 守卫 — compactor 运行后 10min 内跳过根写入
4. ✅ 容量守卫 — 不超过 80% 容量限制

### cron 架构
1. ✅ compactor cron 加入前哨安全检查路径
2. ✅ sync cron 加入 mtime 守卫路径
3. ✅ 两者不再无脑写入同一文件

## 恢复流程（当再次触发前哨时）

```bash
# 1. 检查文件大小
ls -lh /opt/data/MEMORY.md

# 2. 如果 > 10KB，手动恢复
python3 -c "
import re
p = '/opt/data/MEMORY.md'
with open(p) as f: content = f.read()
# 只取第一段 ## IDENTITY + 第一段 ## FACTS
lines = content.split('\n')
header = []
identity = []
facts = []
section = 'header'
for line in lines:
    s = line.strip()
    if s == '## IDENTITY': section='identity'; header.append(line); continue
    if s == '## FACTS': section='facts'; header.append(line); continue
    if s.startswith('#'): header.append(line); continue
    if s.startswith('→ 📦'): continue
    if section == 'identity': identity.append(line)
    elif section == 'facts': facts.append(line)

# 去重
seen_ids = set()
unique_facts = []
for line in facts:
    m = re.search(r'id:(\d+)', line)
    if m and int(m.group(1)) in seen_ids: continue
    if m: seen_ids.add(int(m.group(1)))
    unique_facts.append(line)

result = '\n'.join(header + identity + [''] + unique_facts) + '\n'
with open(p, 'w') as f: f.write(result)
print(f'恢复完成: {len(result)} chars')
"
```
