---
name: memory-compactor
description: >-2
  Monitor MEMORY.md and USER.md capacity; auto-archive when nearing limits.
  v6: pre-flight safety checks + external archive + hook pattern — pure Python,
  zero LLM dependency. Extracts oldest entries to YYYY-MM-DD.md files,
  leaves → 📦 hook in MEMORY.md.
category: system
platforms: [linux]
related_skills: [hierarchical-memory-sync, hermes-optimization]
triggers:
  keywords:
    - 压缩记忆
    - 记忆压缩
    - 合并记忆
    - 清理记忆
    - 记忆精简
    - compact memory
    - memory compact
    - 记忆合并
    - 减少记忆
    - 去重
    - dedup
---

# Memory Compactor v5 — 归档 + 钩子模式

## 设计原则

```
容量超限时，NOT inline compression → 膨胀回来了
BUT  external archive + hook → 只往外出，永不膨胀
```

| 对比 | v4（旧） | v5（当前） |
|------|---------|-----------|
| 引擎 | VibeThinker-3B caveman + 截断 | 纯 Python，零 LLM |
| 超限策略 | 原地缩短 | **外移旧条目 + 留钩子** |
| 依赖 | Ollama 须在线 | 无 |
| 内存管理 | 全热数据混在一起 | 热=memory / 冷=archive |
| 实现 | `memory_compactor_vibe.py` | `memory_compactor_v2.py` |

## 触发器

| 条件 | 动作 |
|------|------|
| MEMORY > 85% (1700/2000) | 触发归档 |
| USER > 75% (1031/1375) | 触发归档 |
| 双向 > 70% (1400 + 962) | 触发归档 |
| 全部低于阈值 | 静默退出 |

## 工作流

```
每5分钟 cron tick
  ↓
memory_compactor_v2.py 启动
  ├ 读 MEMORY.md + USER.md
  ├ 前哨安全检查（新增 v6）
  │   ├ MEMORY.md > 10KB ? → 🚨 中止，提示手动恢复
  │   ├ MEMORY.md > 2000 行 ? → 🚨 中止，提示手动恢复
  │   └ 安全 → 继续
  ├ check_trigger() — 任何一个阈值超限？
  │   ├ 否 → 静默退出
  │   └ 是 → 进入处理流程
  │       ├ compact(MEMORY.md)
  │       │   ├ Phase 1: 按 id 去重合并（同 id 保留最完整版本）
  │       │   │   ├ 解析 id:N [tag] 行、- 描述 (id:N [tag]) 行
  │       │   │   ├ 相同 id 的条目 → 保留 len(content) 最大的版本
  │       │   │   └ 移除非最佳版本（这是主要的空间释放手段）
  │       │   ├ 再次检查触发阈值（去重可能已降到阈值以下）
  │       │   │   └ 仍超限 → 进入 Phase 2
  │       │   ├ Phase 2: 按语义价值归档
  │       │   │   ├ identity 键永不归档（host/ollama/model/interface）
  │       │   │   ├ 优先级: [preference]=1(最先归档) > [profile]=5 > 其他=10
  │       │   │   └ 每次归档最多 8 条，按优先级+id顺序
  │       │   └ 返回 (精简文本, 归档条目列表)
  │       ├ compact(USER.md) — 同上逻辑
  │       ├ write_archive()
  │       │   ├ 写入 /opt/data/memories/archive/YYYY-MM-DD.md
  │       │   ├ 已有文件则追加上去重
  │       │   └ 返回 (path, hook_line)
  │       ├ insert_hook() — 在 ## IDENTITY 后插入
  │       │   └ → 📦 Archive: /opt/data/memories/archive/2026-07-25.md
  │       ├ 写回 MEMORY.md / USER.md
  │       └ 输出报告（不投递到聊天）
```

## 关键路径

| 元素 | 路径 |
|------|------|
| 热数据 | `/opt/data/MEMORY.md` (≤2000 chars) |
| 用户画像 | `/opt/data/USER.md` (≤1375 chars) |
| 冷归档 | `/opt/data/memories/archive/YYYY-MM-DD.md` |
| 脚本 | `/opt/data/scripts/memory_compactor_v2.py` |
| cron | `memory-compactor-v2` (84030ebfc20b, every 5min) |

## 钩子决议

当 agent 回复时，MEMORY.md 中的 `→ 📦 Archive: <path>` 行总是可见的。

- 用户问起旧事 → agent 可见钩子路径 → 读归档文件
- 用户未问 → 钩子行不产生任何开销（纯标记，不加载文件）

## 两阶段处理策略

### Phase 1 — 按 id 去重合并（优先）

这是最主要的空间释放手段。先合并同 id 的内容不同的条目，往往能把占用率从 89% 降到 60% 以下。

1. 解析所有 `id:N [tag] content` 行和 `- 描述 (id:N [tag])` 行
2. 相同 `id:N` 的条目分为一组
3. 每组保留 `len(content)` 最长的版本（信息最完整）
4. 移除其他版本，非条目行（空行、标题、钩子）不变
5. 分析霍尼钩子行，保留在文件中

### Phase 2 — 按语义价值归档（去重仍超限时才执行）

只有当 Phase 1 去重后仍超出阈值时，才进行归档。归档方向从**低价值 → 高价值**：

1. 遍历所有条目，按语义标签分配优先级：
   - `preference` — 优先级 1（最先归档，通常已固化）
   - `profile` — 优先级 5
   - 其他 — 优先级 10
2. identity 键（host/ollama/model/interface）永不归档
3. 优先级相同则按 id 排序（小 id = 更老的条目优先归档）
4. 每次最多取 8 条，避免单次冲击过大

### ⚠️ 提取方向陷阱

⚠️ ⚠️ 2026-07-25 实证：**从尾部取条目不是"最老的"**！新写入的条目总是追加到文件末尾，所以尾部行实际上是最新的。正确的策略是"先去重合并同 id 内容，如果还不够再按语义价值归档"。之前 v2 脚本的 `extract_oldest()` 从尾部提取导致归档了新数据而留下了旧的重复副本，造成压缩始终不生效。现在已修复为上述两阶段策略。


## 成熟记忆项目压缩策略参考

### Mem0 (重要性+时效性)
- 每条记忆分配重要性分数 (1-10)，重要性+时效性=保留优先级
- 低重要性 + 超期 → 自动归档
- 压缩调度: 可配置（默认每 6 小时）

### MemGPT/Letta (分层归档)
- **工作记忆** (上下文窗口) → **存档记忆** (SQLite/向量库) → **召回记忆** (历史会话)
- 工作记忆超限时 → 自动归档到存档层
- 深度摘要压缩: 合并多条低优先级记忆为一条摘要

### Zep (会话摘要+实体提取)
- 每 N 轮对话触发一次自动摘要
- 实体提取 + 分类管道 → 结构化记忆存储
- 动态阈值: 根据会话频率自动调整压缩强度

---

## 压缩触发条件（v7 新增）

### 条件 1: 会话频次调整

```
检测: 当前会话频率（条/小时）
├── > 10条/小时 → 压缩间隔缩短为 1 小时
├── 5-10条/小时 → 压缩间隔保持 5 分钟（当前默认）
└── < 5条/小时 → 压缩间隔放宽为 3 小时 ← 用户指定
```

**实现方式**: `memory_compactor_v2.py` 读取最近 60 分钟的会话数，动态调整 cron tick 频率。

### 条件 2: L4 记忆容量 > 75%

```
L4 记忆（MEMORY.md / USER.md）总容量 > 75%
├── 立即触发一次压缩
├── 压缩目标: 降到 60% 以下
└── 如果没有释放足够空间 → 进入"紧急归档"模式:
    1. 先做 id 去重（Phase 1）
    2. 再按优先级归档（Phase 2）
    3. 如果仍不够 → 强制归档低信任度条目 (trust < 0.5)
```

### 条件 3: 写保障 (Write Assurance)

L4 在写入新记忆之前，必须确保有足够空间：

```
写入新记忆前检查:
├── 容量 < 70% → 直接写入
├── 容量 70-85% → 先触发一次轻量压缩（仅去重）
└── 容量 > 85% → 先触发归档，再写入

保障目标: 任何新写入操作都不会因为容量不足而失败。
```

### 条件 4: 合并触发

当以下条件同时满足时，跳过常规压缩，直接进入"深度压缩"：

```
条件 A: 容量 > 75%  AND  会话频率 > 5条/小时
条件 B: 距离上次压缩已超过 1 小时
条件 C: MEMORY.md 中存在 5 条以上重复 id

深度压缩:
1. 全量 id 去重（跨两种格式）
2. 合并语义重复条目
3. 归档信任度 < 0.4 且 retrieval_count = 0 的条目
4. 紧急模式下可归档信任度 < 0.6 的任何条目
```

---

## 压缩频率管理

| 场景 | 频率 | 实现方式 |
|------|------|---------|
| 默认 | 每 5 分钟 | cron tick（当前） |
| 高会话频次 (>10/h) | 每 1 小时 | cron tick + 跳过检查 |
| 低会话频次 (<5/h) | **每 3 小时** | cron tick + 通过计数跳过 |
| 紧急 (容量>85%) | 立即触发 | 每次 memory_write 时额外检查 |
| 深度压缩 (合并触发) | 每 6 小时上限 | 防过度压缩 |

## 容量限制
## 与 hierachical-memory-sync 的交互

`memory-sync.py` (cron 每小时) 从 fact_store 同步事实到 `/opt/data/memories/MEMORY.md`。
compactor v6 操作目标是 **根目录** `/opt/data/MEMORY.md`。

### v3 修复后：三把锁防冲突

| 锁 | 组件 | 机制 |
|----|------|------|
| **前哨** | compactor | MEMORY.md > 10KB → 🚨 中止，防二次膨胀 |
| **mtime** | sync | 根 MEMORY.md 在 10min 内被修改过 → 跳过根写入 |
| **id 去重** | sync | 已有 fact_id 不再追加，减少增量膨胀源 |

### 如果两者操作同一文件（未来扩展）

详见 `references/runaway-252mb-recovery.md` 和 `/opt/data/hooks/references/sync-compactor-conflict.md`。
核心规则：优先写入 `memories/` 子目录，根目录通过 mtime 屏障 + 容量守卫 + 前哨检查三重防护。

## 手动执行

```bash
python3 /opt/data/scripts/memory_compactor_v2.py
```

输出格式：
```
━━━ 记忆归档报告 [HH:MM:SS] ━━━
  触发: MEMORY 86% > 85%
  MEMORY: ⚠️ 1730→1374 省356B 归档8行
  USER: ✅ 866/1375 (63%) 正常
  📦 归档: /opt/data/memories/archive/2026-07-25.md
  MEMORY: 1730→1477 (74%)
  USER:   866→866 (63%)
```

## Pitfalls

1. **钩子插入导致文件膨胀** — 在 v5 测试中，第一次 `insert_hook()` 实现有 bug，导致 MEMORY.md 从 1730→2771。修复后确保在第一个 section 标题后插入且不加重复空行。测试验证：insert 后 size 增幅 = hook_line.len + 1。
2. **resolve_section_lines 不锁定 section 状态 → 重复段头使文件无限膨胀** — 2026-07-25 实测：MEMORY.md 被膨胀到 252MB / 840 万行，根因是 `resolve_section_lines()` 遇到重复的 `## IDENTITY` 段头时，不断重置 `current='identity'`，导致所有重复段被保留。每次 compactor 运行还追加一条新钩子行，形成正反馈循环。**修复**：一旦 `current='facts'`，锁定状态，不再响应后续任何 `## IDENTITY` 或 `##` 段头。详见 `references/runaway-252mb-recovery.md`。
3. **compact_memory 保留旧钩子行又追加新钩子行 → 无限增长** — 同次发现。`compact_memory()` 把 `facts_styles`（含所有旧 `→ 📦 Archive:` 行）extend 到 `all_facts_lines` 中，然后在末尾再 append 一条新钩子行。每跑一轮就多一条，cron 每 5 分钟跑 → 2026-07-25 累积 1,048,596 条钩子行。**修复**：`all_facts_lines` 不再 extend `facts_styles`（旧钩子行全部丢弃），且仅在 `to_archive` 非空时才追加新钩子行。
4. **重复 `## FACTS` 头被意外过滤** — 修复 #2 时，`if stripped.startswith('## '): continue` 也匹配到了原始的 `## FACTS` 标题行，导致 FACTS 段头丢失，重建后 identity 和 facts 数据混在一起。**修复**：条件改为 `if stripped.startswith('## ') and stripped != '## FACTS'`，保留原始段头。
5. **双写冲突** — `memory-sync.py` 写 `memories/` 子目录，compactor 写根目录，当前不冲突。如果配置变化（如两者操作同一文件），需在写入前检查文件 mtime（<10min 前被修改过 → 跳过）。
6. **Ollama 不可达** — 这是 v4 的死锁原因。v5 零依赖 Ollama，完全规避此问题。
7. **归档文件膨胀** — `write_archive()` 对已有文件做去重追加，但长期累积可能变大。如果需要，可以加归档裁剪逻辑（保留最近 N 个归档，删除更早的）。
8. **提取方向反了** — 2026-07-25 发现：从尾部取"最老的条目"是错误的。新条目追加在尾部，所以尾部行是最新的。正确做法：Phase 1 先按 id 去重合并 → 再 Phase 2 按语义价值归档。务必不要走"从尾部按行提取"的老路。
9. **正则不匹配连字符标签** — `\w+` 不匹配 `audio-vector-system` 或 `memory-confirmation-feedback`。必须用 `[^\]]+` 来匹配 tag。2026-07-25 修复：`ID_PATTERN = r'^id:(\d+)\s+\[([^\]]+)\]\s*(.*)'`
10. **id:N [tag] 两种格式并存** — MEMORY.md 中事实同时存在 `id:N [tag] content` 和 `- 描述 (id:N [tag])` 两种格式。解析器必须同时支持两种，且去重时需跨格式比较。
11. **记忆同步 cron 持续追加** — `hierarchical-memory-sync` 每小时从 fact_store 追加重复 id 行到文件尾部。压缩器的去重是唯一的清理手段，必须每次运行都执行。
## 适用场景

### 入口条件

- 相关场景触发词被命中
- 用户明确提出了该技能覆盖的问题
- 系统状态满足前置条件

### 出口条件

- 问题已解决或结论已输出
- 所有必要的操作已完成
- 结果已向用户报告


