# Claude Code 工具状态管理 — 参考笔记

## 概述
Claude Code（Anthropic 官方 CLI）的 27 个内置工具经过三次迭代演进的完整状态管理系统。本笔记提取自 Piebald-AI/claude-code-system-prompts 仓库的 100+ 个工具描述文件和 worktree/orchestration 设计。

来源: https://github.com/Piebald-AI/claude-code-system-prompts
提取日期: 2026-07-21

## 关键架构

### 1. Task DAG 状态机
```
状态流转: pending → in_progress → completed / deleted
依赖链:   blocks / blockedBy（构成有向无环图）
所有者:   owner（agent 名称，用于多 agent 场景）
```

核心文件: `tool-description-task-create.md`, `task-update.md`, `task-get.md`, `task-list.md`

### 2. 并行 Agent 编排（Workflow 引擎）

调用条件（**必须满足其一**，不能仅靠 LLM 判断"并行受益"）：
- 用户明确说 "ultracode"
- 用户直接要求 "use a workflow" / "run multi-agent"
- 被 skill 或 slash 命令触发

**核心抽象**：
- `parallel()` — 无依赖的并行执行，带并发上限 min(16, cpu_cores-2)
- `pipeline()` — 流水线执行，每阶段结果**流式传递**（无壁垒等待）
- `agent(prompt, {label, phase, schema})` — 单个子 agent 调用，可附加 JSON schema 约束输出
- `budget.remaining()` — token 预算控制
- `log()` — 日志记录（用于进度显示，非结构化）

**关键模式**：
- 默认用 pipeline() 而非 parallel() — barrier 浪费等待时间
- 只有真正需要全部结果（如 dedup）时才用 parallel()
- 子 agent 数量上限 1000（防跑飞），单次 parallel/pipeline 上限 4096 项

### 3. 会话内状态系统 (TaskList)

- TaskList 列出所有任务摘要（subject, status, owner, blockedBy）
- TaskGet 获取单个任务完整详情（含 dependencies/blockedBy）
- TaskCreate 创建时自动 `pending`
- TaskUpdate 修改状态，支持 `addBlocks/addBlockedBy`

**重要原则**：完成子任务后必须调 TaskList 找下一个可用任务
**owner 机制**：允许多 agent 协作时不冲突地认领任务

### 4. 定时/循环调度 (CronCreate + ScheduleWakeup)

- CronCreate: 标准 5 字段 cron 表达式 + `recurring` 标志
- **避免 :00 和 :30** — 全世界的流量都压在这两个点
- 容差 jitter: 周期性任务最多延迟 10%（最大 15min），一次性任务在 :00/:30 提前 90s
- 周期性任务默认 7 天后过期（防 session 无限增长）

**ScheduleWakeup**：
- delaySeconds 范围 [60, 3600]
- 缓存感知：根据 prompt-cache TTL 选择延迟
  - 1h TTL: 匹配实际等待目标（CI ~480s），闲时 1200-1800s
  - 5min TTL: 270s 内保持缓存热，否则跳 1200s+ 摊薄缓存未命中
- mainta: 绝对不用轮询替代事件驱动的通知

### 5. 事件驱动变更通知

架构：后台变更 → 事件 schema → 推送到 agent
```json
// background-tasks-changed 事件
{ "type": "background_tasks_changed", ... }

// code-change-published 事件（PR 关联）
{ "type": "code_change_published", 
  "url": "https://github.com/.../pull/...",
  "provenance": "scraped_from_command_output" }
```

**关键设计**：
- 事件可能重复发射（idempotent — 幂等处理）
- 事件来源是 CLI 输出 scraping，非可靠来源 → 需要 agent 用自己的 credential 二次验证
- best-effort 交付（如果进程崩溃可能丢事件）

### 6. 子Agent 隔离机制

- **worktree isolation**: 每个子 agent 在独立 git worktree 中操作，改完后合并
- **remote isolation** (CCR): 远程沙箱执行，适合长时间运行任务
- 无变更自动清理 worktree；有变更返回 `{path, branch}`
- 子 agent 的 `agent_state_effect` 控制对父 agent 状态的影响（none/busy/degrade）

### 7. 状态报告与验证

- **Trust but verify**: 子 agent 的"已做完"只是自我报告
- 实际验证手段：读取文件确认变更、运行测试、反向检查
- **「完成但不报告」模式**: 后台子 agent 完成后不自动通知用户，父 agent 需主动发摘要
- 一致性验证：`consecutive_failures >= 2 → healthy=false`（类似方案1的降级策略）

## 与当前方案1 对比

| 维度 | Claude Code 实践 | 方案1 (当前 state_registry) |
|------|-----------------|---------------------------|
| 状态粒度 | Task级 + 工具级 | 只有工具级 |
| 依赖模型 | DAG (blocks/blockedBy) | 扁平依赖列表 |
| 并行编排 | workflow + parallel/pipeline | 无 |
| 子Agent支持 | 完整（fork/worktree/remote） | 无 |
| 超时策略 | 缓存感知 ScheduleWakeup | 无 |
| 事件驱动 | 后端事件推送到 agent | 纯轮询 probe_all |
| 任务owner | 多agent认领机制 | 无 |

## 可复用到方案2的模式

1. **Task DAG + owner 机制** — 在 tool_registry 表上叠加 task 表，支持 pending/in_progress/completed + 依赖链
2. **pipeline 编排** — parallel()/pipeline() API（借鉴而非照搬，Hermes 没有 AST runtime，用 callback 风格）
3. **event-driven probe** — 替代 probe_all 全量轮询，改为变更事件触发 + 懒验证
4. **agent_state_effect 级联** — 子工具/子 agent 执行时自动提升父状态到 busy
5. **缓存感知超时** — 系统进入 degraded/offline 前有智能延迟选择

## 注意事项/坑

- **不要主动替用户决定跑 workflow** — 明确 opt-in 要求（ultracode / 用户主动要求）
- **子 agent 自我报告不可信** — 必须验证实际产出
- **跨 session 的状态持久化** — Claude Code 用 cron 实现，但 cron 到期后状态丢失
- **owner 机制在单 agent 场景不需要** — 只在多 agent 编排时启用
- **Workflow 子 agent 上限 1000** — 防止失控循环
