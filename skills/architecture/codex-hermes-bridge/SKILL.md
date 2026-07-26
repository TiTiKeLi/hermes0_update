 ---
 name: codex-hermes-bridge
 description: Codex ↔ Hermes 协作流程 — bridge 请求/响应、状态机、WeChat 确认、精简格式。双方协作的完整协议和工作流。
 category: architecture
 platforms: [linux, windows]
 related_skills:
   - wechat-format
   - chinese-format
   - project-lifecycle
   - memory-implementer
 triggers:
   keywords:
     - bridge
     - 协作
     - Codex
     - Hermes
     - 桥接
     - 状态机
     - 确认
     - 交互循环
     - 跨端
     - 异步
     - 请求响应
     - codex hermes
     - 两端协作
     - 桥接协议
 ---
 
 # Codex ↔ Hermes Bridge 协作协议
 
 ## 架构概览
 
 ```
 ┌─────────────────────────────────────────────────────┐
 │                    Windows 宿主机                   │
 │                                                     │
 │  Codex（桌面应用）    共享文件系统           Hermes（容器）│
 │    │                                              │
 │    │  codex-bridge/requests/  ────────────►  读取  │
 │    │  codex-bridge/responses/  ◄────────────  写入  │
 │    │  codex-bridge/state-machine/  ◄───────►  读写  │
 │    │                                              │
 │    │  skills/ (bind mount) ───────────────►  加载  │
 │    └──────────────────────────────────────────────┘
 ```
 
 ## 协作通道
 
 ### 通道 1: Bridge 请求/响应（一次性）
 
 适用于一次性任务，不需要多轮交互。
 
 ```
 Codex 写 → codex-bridge/requests/{id}.json
   └── type: skill_update | config_change | info_notify
   └── 响应上限: 50 行 / 5KB
 
 Hermes 读 → 处理 → 写回 → codex-bridge/responses/{id}.json
   └── status: completed | failed
   └── 微信转发前必须经 wechat-format 精简
 ```
 
 ### 通道 2: 状态机（多轮交互）
 
 适用于需要用户确认或多次往返的复杂任务。
 
 ```
 state 流转:
   PENDING → PROCESSING → AWAITING_CONFIRMATION
                           → COMPLETED
   AWAITING_CONFIRMATION → CONFIRMED → COMPLETED
                         → REJECTED
 
 WeChat 确认格式:
   ━━━ 需要确认 ━━━
   {一句话描述}
 
   【1】确认
   【2】拒绝
   【3】稍后
 ```
 
 ### 通道 3: 技能同步（长期）
 
 Codex 创建的技能通过 bind mount 实时同步到容器。
 Hermes 加载后即可使用，无需额外操作。
 
 ```
 Codex 写 skills/{category}/{name}/SKILL.md
   → bind mount 实时同步 → Hermes 下次会话加载
   → hermes skills list 确认已加载
 ```
 
 ## 回复精简规则（WeChat 转发前强制）
 
 ```
 □ 单条消息 ≤ 200 字
 □ 工具类 ≤ 5 行
 □ 3 秒内可读完
 □ 禁止发送原始 JSON
 □ 中文回复，禁止英文状态词
 □ 超过 200 字截断并加 "...(详情见文件)"
 ```
 
 ## 适用场景
 
 ### 入口条件
 - Codex 需要通知 Hermes 更新
 - Hermes 需要 Codex 协助处理复杂任务
 - 需要用户通过 WeChat 确认
 - 技能创建/更新需要同步
 
 ### 出口条件
 - 请求已处理（桥接或状态机）
 - 回复已按精简格式发送到 WeChat
 - 技能已同步并加载
 - 状态机已归档完成
 
 ## 参考
 - [Bridge 协议](../../../codex-bridge/BRIDGE_PROTOCOL.md)
 - [状态机协议](../../../codex-bridge/state-machine/README.md)
 - [WeChat 格式](../../behavior/wechat-format/SKILL.md)
 - [中文格式](../../behavior/chinese-format/SKILL.md)
