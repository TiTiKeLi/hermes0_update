 # Codex-Hermes 状态机（State Machine）
 
 > 统一的状态管理机制，用于 Codex ↔ Hermes 之间的异步交互循环。
 > 适用于任何需要"发起→处理→确认→继续"模式的场景。
 
 ---
 
 ## 为什么需要状态机
 
 当前的 bridge 只有"请求→响应"模式，无法处理需要多轮交互的复杂任务：
 
 ```
 当前 bridge（单轮）:
   Codex 写请求 → Hermes 读 → 回复 → 结束
 
 需要状态机（多轮）:
   Codex 发起任务 → Hermes 需要确认 → Codex 等待
   → Hermes 问用户 → 用户确认 → Hermes 写回
   → Codex 继续 → 完成
 ```
 
 ## 核心概念
 
 ### 状态模型
 
 ```
                    ┌──────────┐
                    │ PENDING  │ ← 请求已创建
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │PROCESSING│ ← 正在处理
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │AWAITING  │ │COMPLETED │ │ FAILED   │
        │_CONFIRM  │ │          │ │          │
        └────┬─────┘ └──────────┘ └──────────┘
             │
      ┌──────┼──────┐
      ▼      ▼      ▼
   ┌──────┐┌──────┐┌────────┐
   │CONFIRM││REJECT││TIMEOUT │
   │  ED  ││  ED  ││       │
   └──┬───┘└──────┘└────────┘
      │
      ▼
   ┌──────┐
   │RESUME│ ← 继续执行
   └──────┘
 ```
 
 ### 状态定义
 
 | 状态 | 含义 | 谁写入 | 谁读取 |
 |------|------|--------|--------|
 | PENDING | 请求已创建，等待处理 | 发起方 | 处理方 |
 | PROCESSING | 正在被处理 | 处理方 | 发起方 |
 | AWAITING_CONFIRMATION | 需要用户确认 | 处理方 | 发起方（等待） |
 | CONFIRMED | 用户已确认 | 处理方（通过 WeChat） | 发起方 |
 | REJECTED | 用户拒绝 | 处理方（通过 WeChat） | 发起方 |
 | COMPLETED | 处理完成 | 处理方 | 发起方 |
 | FAILED | 处理失败 | 处理方 | 发起方 |
 | TIMEOUT | 等待超时 | 系统 | 双端 |
 | RESUMED | 确认后继续执行 | 发起方 | 处理方 |
 
 ---
 
 ## 使用场景
 
 ### 1. Hermes Bridge（当前）
 
 Codex 需要 Hermes 在 WeChat 上确认用户的意图。
 
 ```
 Codex → PENDING: "需要确认用户是否要清理磁盘"
   → Hermes 读取 → PROCESSING
   → Hermes 在 WeChat 问用户 → AWAITING_CONFIRMATION
   → 用户确认 → CONFIRMED
   → Codex 读取 → 继续执行 → COMPLETED
 ```
 
 ### 2. Skill 创建（可复用）
 
 Hermes 检测到需要新 skill → 请求 Codex 创建。
 
 ```
 Hermes → PENDING: "用户反复出现同一问题，需要创建 skill"
   → Codex 读取 → PROCESSING
   → Codex 创建 skill → COMPLETED
   → Hermes 验证并注册
 ```
 
 ### 3. MCP 工具调用（可复用）
 
 Hermes 需要调用 MCP 工具，但需要用户先授权。
 
 ```
 Hermes → PENDING: "需要访问 GitHub API，请求授权"
   → Codex 读取 → 需要确认 → AWAITING_CONFIRMATION
   → 用户通过 WeChat 授权 → CONFIRMED
   → Codex 执行 MCP 调用 → COMPLETED
 ```
 
 ### 4. 插件交互（可复用）
 
 插件需要用户提供额外参数才能继续。
 
 ```
 Codex → PENDING: "需要用户提供 API Key"
   → Hermes 在 WeChat 询问 → AWAITING_CONFIRMATION
   → 用户提供 → CONFIRMED (含参数)
   → Codex 继续 → COMPLETED
 ```
 
 ### 5. Agent 自迭代（可复用）
 
 Hermes 发现技能效果不佳 → 请求 Codex 优化 → Codex 优化后通知 Hermes 验证。
 
 ```
 → PENDING → PROCESSING → AWAITING_CONFIRMATION（等用户测试）
 → CONFIRMED → COMPLETED
 ```
 
 ---
 
 ## 文件格式
 
 每个状态机实例是一个 JSON 文件：`codex-bridge/state-machine/{id}.json`
 
 ```json
 {
   "id": "sm-20260726-001",
   "type": "skill_creation | user_confirmation | mcp_call | plugin_action | agent_iteration",
   "state": "PENDING",
   "created_by": "codex | hermes",
   "source_thread": "codex-thread-id（可选）",
   "context": {
     "summary": "请求的简短描述",
     "detail": "请求的详细内容",
     "options": ["选项A", "选项B"],
     "timeout_minutes": 30
   },
   "result": null,
   "error": null,
   "history": [
     {"state": "PENDING", "at": "2026-07-26T18:00:00", "by": "codex"},
     {"state": "PROCESSING", "at": "2026-07-26T18:01:00", "by": "hermes"},
     {"state": "AWAITING_CONFIRMATION", "at": "2026-07-26T18:02:00", "by": "hermes"}
   ],
   "created_at": "2026-07-26T18:00:00",
   "updated_at": "2026-07-26T18:02:00"
 }
 ```
 
 ## 目录结构
 
 ```
 codex-bridge/state-machine/
 ├── README.md          ← 本文档
 ├── {id}.json          ← 活跃的状态机实例
 ├── archive/           ← 已完成/失败的实例（历史记录）
 └── examples/          ← 示例文件
 ```
