---
name: tool-governance-v2
description: 工具治理架构 v2 — 前置拦截器 (ToolStateRegistry) + 后置钩子 (hooks) + 类级别统筹 (kind-overview)，覆盖 skill/tool/mcp/plugin 四类扩展点的统一状态管理
category: architecture
conditions:
  requires_toolsets:
    - terminal
    - file
platforms: [linux]
triggers:
  keywords:
      - 工具治理
      - tool governance
      - 工具治理v2
      - tool governance v2
      - 前置拦截
      - 后置钩子
      - 拦截器
      - toolstate
      - state registry
      - kind
      - 六刀审计
      - verifier agent
---

# Tool Governance Architecture v2

## 核心架构（三层）

```
                    Agent
                      │ 请求调用工具 X
                      ▼
┌─────────────────────────────────────┐
│  1. 前置拦截 (can_call)              │
│     ├─ UNREGISTERED?                │
│     ├─ DISABLED?                    │
│     ├─ UNHEALTHY?                   │
│     ├─ status (active/degraded/…)   │
│     ├─ agent_state matches?         │
│     ├─ dependencies OK? (递归)       │
│     └─ conflicts?                   │
│  → OK → 允许调用 / → 拒绝 + 原因      │
└──────────┬──────────────────────────┘
           │ 调用执行
           ▼
┌─────────────────────────────────────┐
### 2. 后置钩子系统：Hooks Engine

hooks engine 是后置钩子的新一代实现，替代旧的 `trigger_file_write_hook` 方案。采用独立 SQLite 存储 + 三种触发器 + cron 混合驱动。

**相关文件**：
- `/opt/data/hooks/hooks_engine.py` — 核心引擎（HookEngine, HookDB, CLI）
- `/opt/data/hooks/hooks.db` — SQLite 数据库
- `/opt/data/hooks/skill_trigger_index.py` — 从 skill frontmatter 自动注册钩子
- `/opt/data/hooks/hooks_watchdog.py` — cron 看门狗（每 5 分钟）
- `/opt/data/hooks/TRIGGERS_REFERENCE.md` — 自动生成的触发参考文档

**三种触发器**：

| 类型 | 触发时机 | 典型用途 |
|------|---------|---------|
| `keyword` | 用户消息含关键词 | 自动加载对应 skill |
| `event` | fire_event() 调用 | session_start, memory_written, cron_tick |
| `tool_post` | tool 调用完成后 | 自动后处理/校验 |

**钩子注册来源**：
- 自动：所有 skill 的 `SKILL.md` frontmatter 中的 `triggers` 字段 → `skill_trigger_index.py scan` 扫描 → 注册到 hooks.db
- 手动：`hooks_engine.py add-hook` / `state_registry.py he-fire`

**state_registry 集成**：
- `record_call()` 成功返回后自动检查 `tool_post` 钩子
- `check_pre_message_hooks(text)` — 检查用户消息的关键词钩子（在主循环前置调用）
- CLI 集成：`state_registry.py he-list`, `he-stats`, `he-fire`, `he-check-msg`

**cron 看门狗**（每 5 分钟 silent 运行）：
- fire `cron_tick` event → 给 event 钩子轮询节拍
- 重新扫描 skill frontmatter → 更新 TRIGGERS_REFERENCE.md
- 无变化时完全静默（`no_agent=True` + `deliver=local`）

**工作流**：
1. 编辑 skill 的 `SKILL.md`，在 frontmatter 中添加 `triggers: {keywords: [...], events: [...], tools: [...]}`
2. 运行 `skill_trigger_index.py scan` → 自动注册/更新钩子
3. 钩子生效：关键词匹配自动加载 skill，事件触发执行 action
4. 检查 `TRIGGERS_REFERENCE.md` 确认注册状态

**设计原则**：
- 后置钩子是安全网 + 自动触发层，不能替代前置拦截
- 钩子执行不应阻塞主流程
- skill 职责自描述：`triggers` 字段声明了 skill 的触发条件
- `trigger_file_write_hook`（旧方案）仍可用作保留兼容

### 3. 类级别统筹 (kind_overview)
           ▼
┌─────────────────────────────────────┐
│  3. 类级别统筹 (kind_overview)       │
│     ├─ skill 类: N 个, N 就绪       │
│     ├─ tool 类: N 个…               │
│     ├─ mcp 类: …                    │
│     └─ plugin 类: …                 │
│  → `python3 state_registry.py overview` │
└─────────────────────────────────────┘
```

## 组件：ToolStateRegistry (v2)

文件: `/opt/data/state_registry.py`

### CLI 命令速查

| 命令 | 作用 | 典型场景 |
|------|------|---------|
| `register <name> <kind>` | 注册/更新 | 新增 skill/tool/mcp/plugin |
| `check <name>` | 是否可调用 | 调用前拦截 |
| `probe` | 全量探测 | cron 定时监控 |
| `report` | 完整报告 | 全局健康审计 |
| **`overview`** | **按类统筹** | **一瞥即知全貌** |
| **`kind-health <skill/tool/mcp/plugin>`** | **某类详情** | **聚焦某一类** |
| **`deps <name>`** | **递归依赖链** | **跨类依赖审计** |
| `list [kind]` | 列出工具 | 浏览 |
| `unhealthy` | 不健康列表 | 排查 |
| `set-agent <state>` | 设置 agent 状态 | online/busy/degraded/offline |
| **`he-list`** | **hooks engine 全量** | **37 个钩子一览** |
| **`he-stats`** | **hooks engine 统计** | **keyword/event/tool_post 分类统计** |
| **`he-fire <event>`** | **触发钩子事件** | **手动 fire cron_tick / session_start** |
| **`he-check-msg <text>`** | **关键词匹配测试** | **调试关键词钩子** |

### kind 四类定义

| kind | 含义 | 例子 |
|------|------|------|
| skill | 技能（工作流/思维框架） | github-discover, deep-need-analysis |
| tool | 工具（可执行脚本/API） | state_registry |
| mcp | MCP 服务器 | (预留) |
| plugin | Hermes 插件 | (预留) |

### v2 新增 API

```python
registry.kind_overview()    # → {"total": 9, "kinds": {"skill": {...}, "tool": {...}}}
registry.kind_health(kind)  # → [{"name": "...", "enabled": True, ...}, ...]
registry.dep_chain(name)    # → {"name": "...", "dependencies": [...]}
```

## 设计原则

1. **工具必须注册才能被治理** — 未注册的工具 can_call 直接返回 UNREGISTERED
2. **前置拦截 > 后置修复** — call 前先查，比 call 后擦屁股好
3. **类级别统筹打破孤岛** — skill/tool/mcp/plugin 不再各自为政，统一到 state_registry
4. **一瞥即知** — overview 命令是所有状态的入口，3 秒看完全局

## 已知限制

### hooks engine: 检测系统 ≠ 行为系统（2026-07-25 诊断）

**核心问题**：agent 循环没有预处理好钩子结果。37 个钩子中 33 个 fire_count=0（诊断脚本: `/opt/data/hooks/fire_count_analysis.py`）。

| 触发类型 | 注册数 | 触发过 | 零触发 | 根因 |
|----------|--------|--------|--------|------|
| keyword | 21 | 0 | 21 | agent 不调 check_pre_message_hooks() |
| tool_post | 10 | 0 | 10 | record_call() 查到但不消费 |
| event | 6 | 4 | 2 | 仅 session_start 初始化触发 |

**关键断裂点**：

> ⚡ **现状态**：这些断裂点的修复目前不在本 skill 中推进。如果以后开始修，更新本节。
1. `check_pre_message_hooks()` 存在 state_registry 中，但 agent 的主循环从未调用它——没有预处理阶段
2. `record_call()` 调了 `check_post_tool()` 但结果不用于加载 skill 或改行为
3. `hooks_log` 表不存在——schema 中有定义但 DB 没创建，没有审计追踪
4. `cron_tick` 事件已注册在 watchdog 中，但 0 个钩子监听它

**修复方向**（尚未实现）：
- 在 agent 主循环入口添加 `check_pre_message_hooks(user_message)` → 自动 `skill_view()` 加载匹配 skill
|- `record_call()` 中匹配到 tool_post 钩子 → 自动执行其 action（脚本/skill）

---

## 组件（v1 吸收）：Verifier Agent（审计模式）

从 `tool-governance` v1 吸收，参考 claude-obsidian `agents/verifier.md` 设计。

### 触发时机

git commit 前 / 发布前 / 重大变更后

### 六刀审计清单

| # | 检查项 | 说明 |
|---|--------|------|
| 1 | **Data egress** | 出站网络/子进程/写外部文件 → 要求用户 opt-in |
| 2 | **Atomic operations** | 多步状态变更 → 要求 temp+rename / 锁 |
| 3 | **Failure-mode rollback** | 部分完成比不做好？→ 要求恢复路径 |
| 4 | **Hermetic test coverage** | 新代码路径 → 要求无网络/LLM 的测试 |
| 5 | **Git hygiene** | 新文件路径 → 要求 .gitignore 覆盖 |
| 6 | **Additive-without-pruning** | +500/-50 LOC → 要求审阅遗留代码 |

⚠️ **已知差距**：泄露版 CLI 实际只实现了第 5 项（git hygiene），第 1 项（Data egress）的 grep 检查被注释掉了。

### 定级体系

| 层级 | 含义 | 动作 |
|------|------|------|
| **BLOCKER** | 影响发版决策 | 必须撤回 commit |
| **HIGH** | 应在提交前修复 | 可跟踪到下个 patch |
| **MEDIUM** | 跟踪为 issue | 推迟到下个 minor |
| **LOW** | 记录备忘 | 未来优化 |

### 输出格式

```
VERDICT: SHIP / HOLD-FIX-FIRST / NEEDS-REWORK

BLOCKER (N findings)
1. <file:line> — <描述>
   Fix: <建议>
HIGH (N findings)
...
```

Verifier agent 必须只读（Read/Grep/Glob/Bash 只读工具），不能有写权限，避免审计 agent 自己引入问题。

---

## 设计对比：Claude Code hooks vs ToolStateRegistry（v1 吸收）

| 维度 | Claude Code hooks | ToolStateRegistry |
|------|------------------|------------------|
| **方向** | 后置型（调用后才反应） | 前置型（调用前拦截） |
| **粒度** | 按工具名正则匹配（matcher） | 6层级联检查 |
| **自动化** | 自动 git commit（运维向） | 自动 unhealthy 标记（治理向） |
| **依赖管理** | ❌ 无 | ✅ 递归检查 |
| **冲突检测** | ❌ 无 | ✅ 活跃冲突检测 |
| **状态联动** | ❌ 独立 | ✅ agent_meta 四态联动 |
| **持久化** | 无（CLAUDE.md 控制） | ✅ SQLite |
| **事件驱动** | ✅ JSON 声明式 | ❌ 需手动调用 API |
| **审计模式** | ✅ verifier agent | ✅ 已吸收 v1 六刀审计 |

---

## Pitfalls
- 未注册的工具绕过检查——必须强制所有入口走 can_call
- 连续失败阈值 2 对不稳定环境太敏感——建议未来做成可配
- 子 agent 自我报告不可信——必须写文件确认后再回传
- 类级别统筹依赖注册时的 kind 字段——录错了 kind 会污染分类统计
- **不要迷信前置拦截** — can_call 只在手动调用时触发，如果绕过 registry 直接调工具，拦截器失效。需要 hooks 层兜底
- **matcher 粒度要精确** — hooks 的 `"Write|Edit"` 是粗粒度匹配，误触发会导致不必要的开销
- **hooks 的 STDOUT 可能不被捕获** — 已知 bug（anthropics/claude-code#10875），inline hooks 比 plugin hooks 更可靠
