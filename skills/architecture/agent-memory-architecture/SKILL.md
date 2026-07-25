---
name: agent-memory-architecture
description: >-
  Agent 记忆架构设计模式 — 对比 MemGPT/Mem0/Zep/LangGraph/GraphRAG 五大体系，
  提炼适用于本地模型(3B)的轻量记忆架构。涵盖 Core Memory 结构化、语义检索注入、
  自动萃取、Hook↔Memory 联动、多级摘要五个核心模式。
category: architecture
platforms: [linux, wsl]
related_skills: [hierarchical-memory-sync, memory-compactor, hermes-optimization, tool-governance-v2]
triggers:
  keywords:
      - 记忆架构
      - memory architecture
      - 记忆策略
      - 记忆改进
      - 记忆蠢
      - 记不住
      - 记忆系统
      - 分层记忆
      - 记忆设计
  tool_calls:
      - memory
      - fact_store
      - skill_manage
  events:
      - session_start
      - memory_written
---

# Agent 记忆架构设计模式

## 1. 边界条件

### 入口条件（至少一条满足）
- [ ] 需要设计或重构 agent 的记忆系统
- [ ] 当前记忆策略不够智能（如"记不住""记忆太蠢""上下文不够用"）
- [ ] 需要评估新的记忆方案是否适合本地模型(3B)环境
- [ ] 需要将 hooks 系统与记忆系统打通

### 跳过条件
- [ ] 只是单次手动 memory 写入或 fact_store 操作（不需要架构级改动）
- [ ] 纯临时会话无需持久记忆

### 中止条件
- [ ] 方案需要 embedding 模型（本地只有 3B 无 embedding 能力）
- [ ] 方案依赖外部 API 服务（网络不可达）
- [ ] 方案需要 1GB+ 本地推理模型（环境限 3B）

---

## 2. 五大记忆体系对比

### 2.1 MemGPT / Letta — 参考价值 ★★★★★

| 特性 | 实现 | Hermes 差距 |
|------|------|-------------|
| Core Memory 双块 | Persona(我) + Human(用户) 结构化 JSON | MEMORY.md 是 flat list，无 Persona/Human 分化 |
| 上下文溢出链 | Memory → 自动摘要 → Archival | compactor 硬截断归档，无摘要层 |
| In-context 编辑 | agent 回复中可直接编辑 core memory | 只能通过 memory tool 写入 |

**核心启示**：Core Memory 必须是结构化的（Persona + Human 双块），而非 flat list。

### 2.2 Mem0 — 参考价值 ★★★★★

| 特性 | 实现 | Hermes 差距 |
|------|------|-------------|
| 自动事实提取 | 从对话流自动 parse 事实 | 全靠 agent 手动 memory/fact_store 调用 |
| 语义去重 | embedding 相似度（非精确 id 匹配） | 只有 id:N 精确匹配 |
| 记忆类型分化 | user_memory / assistant_memory / session_memory | 只有一种 FACTS 段 |

**核心启示**：记忆写入应是被动自动触发的，不是 agent 主动调用。

### 2.3 Zep — 参考价值 ★★★★

| 特性 | 实现 | Hermes 差距 |
|------|------|-------------|
| Entity Graph | 从对话提取实体→概念的关系图 | fact_store 是 flat 事实，无关系维度 |
| 多层次摘要 | 按时间粒度保留不同详细度的摘要 | 归档就是原文扔到 archive，不是摘要 |

**核心启示**：需要实体层（entity）连接孤立事实。

### 2.4 LangGraph Persistence — 参考价值 ★★★

| 特性 | 实现 | Hermes 差距 |
|------|------|-------------|
| Checkpoint | 每步 save state snapshot | 无 checkpoint，每次重读 MEMORY.md |
| State mutation 显式 | 记忆变更是显式的 state update | memory tool copy-on-append，无显式 update |

### 2.5 GraphRAG — 参考价值 ★★★

| 特性 | 实现 | Hermes 差距 |
|------|------|-------------|
| 社区检测 | 自动发现概念聚类 | 已有 fact_store reason（近似代数推理），无社区摘要 |
| 分层摘要 | 叶→社区→全局三层 | 无摘要分层 |

---

## 3. 决策矩阵

| # | 场景 | 推荐模式 | 复杂度 | 见效 |
|---|------|---------|--------|------|
| 1 | "记忆不区分你是谁 vs 我是谁" | Core Memory 结构化（Persona + Human 双块） | 中 | 高 |
| 2 | "我老是要手动告诉他记住这个" | 自动记忆萃取（对话被动提取） | 中 | 高 |
| 3 | "记忆不随问题变化，一直是那2000字" | 语义检索注入（每次消息前换入相关记忆） | 高 | 高 |
| 4 | "用户说了啥，钩子检测到但不知道" | Hook↔Memory 联动（hook 检测→触发记忆操作） | 低 | 高 |
| 5 | "归档了就是硬扔，问旧事找不回来" | 多级摘要（归档前先摘要） | 高 | 中 |
| 6 | "事实之间没有关联" | 实体图谱（entity graph） | 极高 | 中 |
| 7 | "252MB 记忆膨胀又来了" | 前哨安全检查（已实现） | ✅ 已有 | ✅ |

---

## 4. 原子模式实现

### 模式 P0: Hook↔Memory 联动（低复杂度，高见效）

**输入**：hooks_engine 运行时 + memory_store.db
**工具**：hooks_engine.fire(), memory(), fact_store
**操作**：
1. 在 hooks_engine.py 中新增 hook 动作类型 `memory_update`
2. 关键词类钩子命中时，自动调用 fact_store 的相关操作
3. 具体实现：在 hooks_engine.py 的 `execute_actions()` 中检测 action.type == 'memory_update'
4. action.config 含 {target: "fact_store", facts: [{content, tags}]}
5. 执行完后写入日志到 hook_log

**验证**：
- hook 触发时检查 fact_store 是否有新条目
- 检查 log 中有 success=True 记录

### 模式 P1: Core Memory 结构化

**输入**：当前 MEMORY.md
**工具**：write_file, patch
**操作**：
1. MEMORY.md 改为三段结构：
   ```
   ## IDENTITY (Persona)
   persona: {host, ollama, model, interface, lang}
   
   ## HUMAN (Human)
   human: {name, preferences, techstack, projects, auth}
   
   ## FACTS (High-activity facts)
   - flat list of tagged facts
   ```
2. agent 解析时能区分"关于我的"vs"关于用户的"
3. 上下文注入时根据消息类型选择性注入

**验证**：agent 收到用户消息后，能在上下文中区分 Persona/Human 块

### 模式 P2: 自动记忆萃取（被动提取）

**输入**：assistant 的回复文本
**工具**：execute_code（parse 回复）, fact_store
**操作**：
1. 每次 agent 回复后（通过 POST_REPLY hook），运行萃取脚本
2. 在回复中搜索以下模式：
   - `memory add` 调用 → 自动写入 fact_store
   - "你之前说过..." → 确认是否更新记忆
   - `fact_store search` → 自动 feed back helpful
3. 萃取脚本 write 新事实到 fact_store，带 trust_score=0.5（初始中等信度）

**验证**：回复后检查 fact_store 是否有新条目，trust 标记正确

---

## 5. 工具/Skill 联动表

| 模式 | 依赖工具 | 依赖 Skill | 读取文件 | 写入文件 |
|------|---------|-----------|---------|---------|
| P0 Hook↔Memory | hooks_engine.py + fact_store | tool-governance-v2 | hooks.db, memory_store.db | hook_log |
| P1 Core Memory 结构化 | write_file + patch | agent-memory-architecture | MEMORY.md | MEMORY.md |
| P2 自动萃取 | execute_code + fact_store | tool-governance-v2 (hooks) | [assistant reply] | fact_store |
| 语义检索 | fact_store.search + session_search | — | memory_store.db | [注入上下文] |

---

## 6. 反馈回路

### 6.1 落地后验证
- 每次架构变更后，运行 compactor 确认文件健康（< 10KB）
- fact_store 条目数记录快照，监控增长率

### 6.2 当前已知 Pitfalls
1. **无 embedding 模型** — 本地只有 3B，无法做语义检索。退化策略：用关键词 + tag + 实体匹配替代
2. **Core Memory 结构化后，compactor 需更新** — 如果 MEMORY.md 格式变了，compactor 的 parse 逻辑必须同步更新
3. **自动萃取噪音** — 3B 模型可能提取错误事实。所有自动提取的事实初始 trust=0.5，需要用户反馈确认
4. **Hook 联动非侵入** — Hook→Memory 联动不能阻塞 agent 主流程。必须是 fire_and_forget（使用 background delegate_task）
5. **多级摘要依赖模型** — 摘要需要 LLM 调用（Ollama 3B），如果 Ollama 不可达，退化到硬截断

---

## 7. 历史踩坑记录

### 2026-07-25: 记忆膨胀 252MB 事件
- **症状**: MEMORY.md 膨胀至 252MB / 840 万行
- **根因**: compactor resolve_section_lines 不锁定 + compact_memory 保留旧钩子
- **修复**: 前哨安全检查（>10KB 中止）+ mtime 守卫 + id 级去重 + 容量守卫
- **教训**: 双组件写同一文件必须用协调机制。所有 cron 脚本必须有前置校验。
- **文件**: `skill memory-compactor → references/runaway-252mb-recovery.md`
