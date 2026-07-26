 ---
 name: codex-collaboration
 description: Codex ↔ Hermes 协同机制 — 状态机协议 + 事件驱动 + 用户确认流程。管理双方之间的任务创建、流转、确认、完成的完整生命周期。
 category: workflow
 platforms: [windows, linux]
 related_skills:
   - project-lifecycle
   - git-management
   - quality-gates
   - config-unification
 triggers:
   keywords:
     - 协同
     - 协作
     - 状态机
     - 握手
     - 桥接
     - 全链路
     - 交互
     - 确认
     - 授权
     - 任务流转
     - codex hermes
     - 两端协作
     - 协同机制
     - 全链路测试
     - handshake
 ---
 
 # Codex ↔ Hermes 协同机制
 
 ## 架构总览
 
 ```
 Hermes (容器)              Windows 宿主机               Codex (桌面)
    │                            │                          │
    │  写 PENDING ──────────► state-machine/ ◄────── 处理结果 │
    │                            │                          │
    │                     bridge-loop (FSW)                  │
    │                            │                          │
    │                     READING → WRITING                  │
    │                     → PROCESSING                       │
    │                            │                          │
    │                     ┌──────┴──────┐                    │
    │                     │  triggers/  │ ──── FSW ───► Codex│
    │                     └─────────────┘                    │
    │                            │                          │
    │                     AWAITING_CONFIRMATION               │
    │                            │                          │
    │  CONFIRMED ◄── Hermes 检测 ──── 用户确认               │
    │                            │                          │
    │                     Codex 继续 → COMPLETED             │
    │                            │                          │
    │                     bridge-loop 归档 → archive/        │
 ```
 
 ## 状态链
 
 ```
 PENDING → READING → WRITING → PROCESSING
   → AWAITING_CONFIRMATION → CONFIRMED → COMPLETED → ARCHIVING
                          → REJECTED
   → FAILED
 ```
 
 | 状态 | 含义 | 谁写入 |
 |------|------|--------|
 | PENDING | 任务已创建 | Hermes 或 Codex |
 | READING | bridge-loop 已拾取 | bridge-loop |
 | WRITING | bridge-loop 正在写 trigger | bridge-loop |
 | PROCESSING | trigger 已写入, 等待 Codex | bridge-loop |
 | AWAITING_CONFIRMATION | Codex 需要用户确认 | Codex |
 | CONFIRMED | 用户已确认 | Hermes |
 | REJECTED | 用户拒绝 | Hermes |
 | COMPLETED | Codex 执行完成 | Codex |
 | FAILED | Codex 执行失败 | Codex |
 
 ## 三方职责
 
 ### bridge-loop (Windows PowerShell)
 
 ```
 启动:  restart-bridge.cmd 或直接运行 bridge-loop.ps1
 监听:  FileSystemWatcher(state-machine/, requests/)
 职责:
   - PENDING → READING → WRITING → PROCESSING（自动流转）
   - 写 triggers/{id}.trg.json（事件触发 Codex）
   - 识别 CONFIRMED/REJECTED 但不处理（留给相应方）
   - COMPLETED/FAILED/REJECTED → ARCHIVING → 移入 archive/
 ```
 
 ### Codex (桌面应用)
 
 ```
 监听:  FileSystemWatcher(triggers/)
 职责:
   - 检测到 trigger → 读取状态机 → 执行任务
   - 需要用户确认 → AWAITING_CONFIRMATION + 暂停
   - 检测到 CONFIRMED → 继续执行
   - 完成 → COMPLETED + result 字段
 ```
 
 ### Hermes (容器 Agent)
 
 ```
 触发:  用户发消息（对话本身就是事件）
 职责:
   - 发起新任务 → 创建 PENDING 状态机
   - 检测到 AWAITING_CONFIRMATION → 询问用户
   - 用户确认 → CONFIRMED；用户拒绝 → REJECTED
   - 检查 COMPLETED 结果 → 汇报用户
 ```
 
 ## 目录结构
 
 ```
 codex-bridge/
 ├── state-machine/          状态机文件（活跃任务）
 │   ├── sm-{id}.json       任务实例
 │   └── archive/           已完成/失败任务归档
 ├── triggers/               事件触发（bridge-loop 写入, Codex 读取）
 │   └── {id}.trg.json      触发文件
 ├── cooperation-plan.json   共享规划文档
 ├── bridge-loop.ps1         bridge-loop 脚本
 ├── bridge.status.json      bridge-loop 心跳状态
 └── codex-handshake.md      握手协议
 ```
 
 ## 完整任务生命周期
 
 ```
 1. 发起: Hermes 或 Codex 写 sm-{id}.json, state=PENDING
 2. 流转: bridge-loop FSW 检测到新文件
    → READING → WRITING → PROCESSING
    → 写 triggers/{id}.trg.json
 3. 执行: Codex FSW 检测到 trigger
    → 读取状态机 → 执行任务
    → 需要确认? → AWAITING_CONFIRMATION（等待 Hermes）
    → 不需要? → COMPLETED
 4. 确认:（可选）Hermes 检测 AWAITING_CONFIRMATION
    → 问用户 → CONFIRMED / REJECTED
    → Codex FSW 检测到 → 继续 / 中止
 5. 归档: bridge-loop 检测终态 → ARCHIVING → archive/
 6. 汇报: Hermes 下次对话检查结果 → 汇报用户
 ```
 
 ## 状态机文件格式
 
 ```json
 {
   "id": "sm-20260727-001",
   "type": "skill_audit",
   "state": "PENDING",
   "created_by": "hermes",
   "context": {"summary": "审计技能重叠/缺口"},
   "result": {"summary": "完成, 合并2个技能"},
   "error": null,
   "history": [
     {"state":"PENDING", "at":"...", "by":"hermes"},
     {"state":"READING", "at":"...", "by":"bridge"},
     {"state":"COMPLETED", "at":"...", "by":"codex"}
   ],
   "created_at": "...",
   "updated_at": "..."
 }
 ```
 
 ## 边界条件
 
 ### 入口条件
 - Codex 或 Hermes 需要发起一个跨端任务
 - 任务需要经过用户确认
 - 任务涉及文件操作、技能修改、配置变更
 
 ### 出口条件
 - 任务已完成（COMPLETED）并归档
 - 用户已确认或拒绝
 - 状态机实例已移入 archive/
 
 ### 错误处理
 - bridge-loop 崩溃: 重启 restart-bridge.cmd
 - 状态机卡住: 检查 history 最后一步, 手动推进
 - trigger 丢失: 重新创建状态机
 
 ## 参考
 - [握手协议](../../../codex-bridge/codex-handshake.md)
 - [协同计划](../../../codex-bridge/cooperation-plan.json)
 - [状态机示例](../../../codex-bridge/state-machine/archive/)


