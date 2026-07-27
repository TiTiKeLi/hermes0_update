 ---
 name: bridge-monitor
 description: 桥接状态监控 — 检测 Hermes↔Codex 之间的状态机/trigger 积压, 清理残留, 归档已完成任务, 修复断路。每次会话开始时自动检查并处理。
 category: workflow
 platforms: [windows, linux]
 related_skills:
   - codex-collaboration
   - external-brain
   - session-validation
   - git-management
 triggers:
   keywords:
     - 桥接
     - bridge
     - 状态机
     - 积压
     - 残留
     - 未处理
     - 归档
     - trigger
     - 断路
     - 闭环
     - 未闭环
     - 挂起
     - 卡住
     - 停滞
     - 堆积
     - 没人处理
     - 未响应
     - 状态检查
     - 链路检查
     - 心跳
     - watchdog
     - 看门狗
     - 轮询
     - 扫描
     - 检查状态
     - 通讯
     - 交互
     - 两端
     - 同步
     - 遗留
     - backlog
     - pending
     - stuck
     - orphan
     - cleanup
     - sweep
     - stale
 ---
 
# Bridge Monitor — 桥接状态监控 v1
 
 ## 职责
 
 每次会话开始时自动检查 codex-bridge/ 目录的健康状态，处理残留，确保链路畅通。
 
 ## 检查清单
 
 ### 1. state-machine/ 目录
 
 ```
 □ 列出所有 *.json 文件（排除 README/ARCHITECTURE/examples）
 □ 对每个文件读取 state 字段:
   ├── COMPLETED / CONFIRMED / ARCHIVING → 移入 archive/
   ├── PENDING → 执行任务或归档（根据上下文判断是否已过期）
   ├── PROCESSING → 检查 update_at, 超过 1 小时则完成并归档
   ├── AWAITING_REVIEW → 读取 display 字段, 通知用户; 无 display 则直接完成
   └── FAILED / REJECTED → 记录原因, 移入 archive/
 ```
 
 ### 2. triggers/ 目录
 
 ```
 □ 列出所有 *.trg.json 文件
 □ 对每个文件读取 task_id
 ├── 对应状态机存在 → 处理状态机（见 1）
 └── 对应状态机不存在 → 直接删除 trigger（孤儿）
 □ 删除所有已处理 trigger 文件
 ```
 
 ### 3. 桥接进程
 
 ```
 □ 检查 bridge.status.json 是否存在
 ├── 存在 → 读取 status, 确认 running
 └── 不存在 → 桥接未启动, 需要重启
 ```
 
 ### 4. 通知
 
 检查完成后, 汇总结果。如有异常（残留、断路、进程停止）:
 
 ```
 ━━━ 桥接状态 ━━━
 state-machine: N 个残留 (已清理)
 triggers:     N 个积压 (已处理)
 桥接进程:     running / 已停止
 状态:         正常 / 需关注
 ```
 
 ## 泛化原则
 
 本技能不绑定特定业务逻辑。无论 Hermes 写入什么类型的 state-machine,
 只要 state-machine/ 目录和 triggers/ 目录存在, 本技能就能处理。
 
 扩展方式: 新增 state 类型只需在检查清单中添加对应处理分支。
 
 ## 参考
 - [codex-collaboration](../codex-collaboration/SKILL.md) — 状态链定义
 - [external-brain](../../architecture/external-brain/SKILL.md) — 外部大脑定位
 - [session-validation](../session-validation/SKILL.md) — 会话结束前验证
