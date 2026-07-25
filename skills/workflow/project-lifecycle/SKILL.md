 ---
 name: project-lifecycle
 description: 项目全生命周期管理 — 从 UX 预期设定→功能审计→差距分析→实施→验证→UX验证→部署→复盘沉淀，完整八阶段闭环。适用于任何复杂软件开发项目。
 category: workflow
 platforms: [linux, windows]
 related_skills:
   - ux-audit
   - dependency-tracker
   - quality-gates
   - error-recovery
   - task-prioritization
   - verification-before-completion
   - dispatching-parallel-agents
   - meta-orchestrator
 triggers:
   keywords:
     - 项目生命周期
     - 开发流程
     - 完整项目
     - 项目开发
     - project lifecycle
     - full project
     - 软件开发
     - 大项目
     - 复杂项目
     - 从头开发
     - 项目实施
     - 项目规划
     - 项目执行
     - 项目交付
     - 功能实现
     - 用户预期
     - UX
     - 用户体验
     - 全流程
     - end to end
   tools:
     - skill_manage
     - patch
     - terminal
     - browser
     - web_extract
 ---
 
 # Project Lifecycle — 项目全生命周期管理 v1
 
 ## 核心问题
 
 项目开发缺乏系统化流程：功能实现凭感觉、UX 没有预期基准、改了 A 导致 B 出问题、经验无法沉淀。需要一个覆盖"从 UX 预期到复盘沉淀"的完整闭环。
 
 ## 八阶段闭环架构
 
 ```
 ┌─────────────────────────────────────────────────────────────────┐
 │                   项目全生命周期闭环                              │
 │                                                                 │
 │  P0 ─→ P1 ─→ P2 ─→ P3 ─→ P4 ─→ P5 ─→ P6 ─→ P7 ─→ (回到 P0)  │
 │  UX     功能    差距    实施    验证    UX     部署    复盘      │
 │  预期    审计    分析            测试    验证           沉淀     │
 │                                                                 │
 │  ↑                       失败←Gate←通过                        │
 │  │                         │                                    │
 │  └─────────────────────────┘                                    │
 └─────────────────────────────────────────────────────────────────┘
 ```
 
 ---
 
 ## P0: UX 预期设定
 
 目标：定义"什么样的体验才算好"，作为后续所有阶段的评判标准。
 
 ### 执行步骤
 
 1. **参考收集**
    - 找到官方/标杆产品的 UX 设计方案（截图、文档、产品页）
    - 提取关键交互模式、视觉风格、操作流程
    - 参考项目: 官方 Hermes Dashboard, Open Interpreter UI, AutoGPT Frontend
 
 2. **UX 维度定义**
    ```
    □ 响应速度:  操作后多久看到反馈？（目标: <500ms）
    □ 视觉一致性: 配色方案、字体、间距是否统一？
    □ 错误处理:   出错时用户看到什么？
    □ 空状态:     无数据时页面显示什么？
    □ 加载状态:   等待时用户看到什么？
    □ 操作路径:   完成一个核心任务需要几步？
    □ 无障碍:     键盘导航、屏幕阅读器支持
    ```
 
 3. **UX 预期文档化**
    - 写入项目文档（如 `docs/GUI-UX.md`）
    - 包含: 截图参考、交互描述、量化目标
    - 输出: UX Baseline + Scorecard
 
 ### 质量门
 ```
 G0: UX 预期已文档化 — 所有维度有量化目标
 G0: 参考来源已记录 — 至少 2 个参考项目
 G0: UX Scorecard 已创建 — 可打分、可追踪
 ```
 
 ---
 
 ## P1: 功能审计
 
 目标：逐一检查现有功能是否达到 UX 预期，标记差距。
 
 ### 执行步骤
 
 1. **功能清单编制**
    - 列出项目所有功能点（模块化、颗粒化）
    - 例: GUI 的功能点 → 登录、会话列表、消息展示、设置面板...
 
 2. **逐项审计**
    ```
    功能: 会话列表显示
    UX 预期: 显示最近 20 条会话、每条显示概要、点击进入
    现状: 只显示 10 条、无概要、需要刷新
    差距: ❌ 显示数量不足、❌ 无概要、⚠️ 需点击无预览
    ```
 
 3. **差距分级**
    ```
    P0: 完全不符合 UX 预期（严重）
    P1: 部分符合但缺关键功能（中等）
    P2: 功能有但体验需要打磨（轻微）
    P3: 无此功能但属于增强（可选）
    ```
 
 ### 输出
 ```
 □ 功能清单 (Feature Inventory) — 所有功能点及其状态
 □ 差距报告 (Gap Report) — 每个功能与 UX 预期的差距、分级
 □ UX 覆盖率评分 — 当前功能覆盖 UX 预期的百分比
 ```
 
 ---
 
 ## P2: 差距分析
 
 目标：对差距排优先级，规划实施路径（考虑依赖关系、风险、工作量）。
 
 ### 执行步骤
 
 1. **依赖分析**（调用 dependency-tracker）
    ```
    功能 A 依赖功能 B → B 必须先完成
    功能 A 修改可能影响功能 C → C 需要回归测试
    数据库结构变更 → 需要迁移脚本
    ```
 
 2. **影响范围评估**
    ```
    修改 X 会影响到: [模块 A, 模块 B, ...]
    影响类型: [界面/逻辑/数据/API]
    影响级别: [同一文件/同一模块/跨模块/全系统]
    ```
 
 3. **实施路径规划**
    ```
    第一轮 (P0差距):   功能A, 功能B (最影响用户体验的)
    第二轮 (P1差距):   功能C, 功能D (中等影响)
    第三轮 (P2差距):   功能E, 功能F (体验打磨)
    第四轮 (P3增强):   功能G (锦上添花)
    ```
 
 ### 边界管理
 
 ```
 执行边界: 每一轮只修改规划内的功能，不越界
 修改边界: 修改已知影响范围外的功能需要重新评估
 优化边界: 不影响功能行为的前提下可自由优化代码结构
 废弃时机: 功能被替代后立即标记 deprecated、移出 UI（不移除代码，留作回退）
 ```
 
 ---
 
 ## P3: 实施
 
 目标：按差距分析的优先级，每个差距独立实现。
 
 ### 实施单元
 
 每个差距作为一个独立"实施单元"（Feature Unit），遵循：
 
 ```
 Feature Unit: 修复会话列表显示数量不足
   ├── 修改文件: gui.py, gui.html
   ├── UX 目标: 显示 20 条, 显示概要
   ├── 依赖: 无
   ├── 影响: 会话列表模块
   ├── 实施
   ├── 自测
   └── 通过 ✓ / 回滚
 ```
 
 ### 实施时的安全网
 
 ```
 □ 修改前: dependency-tracker 检查影响范围
 □ 修改中: git commit 触发 data-security-audit
 □ 修改后: quality-gates 检查完整性
 □ 回滚: git revert 恢复到已知正常状态
 ```
 
 ---
 
 ## P4: 验证测试
 
 目标：每个实施单元通过三级测试。
 
 ```
 T1 — 单元测试: 功能本身是否正确？
   例: 设置面板能不能保存设置？读回来是否一致？
  
 T2 — 集成测试: 功能与其他模块是否正常协作？
   例: 修改设置后，会话列表的行为是否受影响？
  
 T3 — 回归测试: 修改是否破坏了已有功能？
   例: 修改会话列表后，消息发送是否正常？
 ```
 
 ---
 
 ## P5: UX 验证
 
 目标：回到 UX 预期，验证实现是否达到标准。
 
 ### 执行步骤
 
 1. **对照 UX Scorecard** 逐项打分
 2. **差距复检**: 原来的差距是 P0，现在解决了吗？
 3. **新差距发现**: 实现过程中是否有产生新的 UX 问题？
 4. **UX 覆盖率重算**: 从 P1 的 X% → 现在 Y%
 
 ---
 
 ## P6: 部署
 
 目标：将已验证的版本部署到生产环境。
 
 ```
 □ 代码冻结 (Code Freeze): 不再接受新功能修改
 □ 版本标记: git tag v2.6.0
 □ 部署: docker compose down + up
 □ 健康检查: health-monitor + Gitleaks
 □ 回滚就绪: 已知正常版本的 docker-compose.yml
 ```
 
 ---
 
 ## P7: 复盘沉淀
 
 目标：将项目过程中的经验固化为技能、更新到知识库。
 
 ### 沉淀内容
 
 ```
 □ 新增技能: 过程中发现需要但没有的技能
 □ 更新技能: 现有技能的使用反馈、改进点
 □ 更新 ARCHITECTURE.md: 新模块/新依赖
 □ 更新 CONTEXT.md: 新增配置/变量
 □ 记录 Pitfalls: 踩过的坑、修复方式
 ```
 
 ### 复盘报告格式
 
 ```yaml
 retrospective:
   project: "Hermes GUI v2.6"
   duration: "14 天"
   
   planned_gaps: 12
   completed_gaps: 10
   deferred_gaps: 2 (原因: 依赖未就绪)
   
   new_issues_found: 3
   regressions: 0
   
   skills_created: 2
   skills_updated: 5
   
   key_lessons:
     - "UX 预期越具体，审计越准确"
     - "小步提交比大 PR 更容易回滚"
     - "dependency-tracker 在 P2 阶段省了大量返工"
 ```
 
 ### 进入下一轮循环
 
 P7 完成后，检查是否还有未完成的差距：
 - 有 → 回到 P2 (差距分析)
 - 无 → 回到 P0 (设定下一版本的 UX 预期)
 
 ---
 
 ## 状态管理
 
 每个实施单元（Feature Unit）在生命周期中经历以下状态：
 
 ```
 IDENTIFIED → PLANNED → IN_PROGRESS → REVIEW → TESTING → DEPLOYED
     ↑           │                                                │
     └───────────┘ (放弃)                  (失败回滚) ←────────────┘
 ```
 
 状态存储: `projects/<project_name>/state.json`
 
 ## 参数管理
 
 所有跨文件参数在修改前必须执行:
 
 ```
 □ 查 CONTEXT.md → 这个参数在哪些文件/层出现？
 □ 查 dependency-tracker → 修改会影响哪些功能？
 □ 兼容性检查 → 旧版本是否兼容新参数？
 □ 废弃计划 → 旧参数何时移除？
 ```
 
 ---
 
 ## 相关参考
 
 - [ux-audit](../ux-audit/SKILL.md) — UX 审计方法论
 - [dependency-tracker](../dependency-tracker/SKILL.md) — 依赖追踪
 - [quality-gates](../quality-gates/SKILL.md) — 质量门禁
 - [error-recovery](../error-recovery/SKILL.md) — 错误恢复
 - [config-unification](../../architecture/config-unification/SKILL.md) — 配置统筹
 - [Hermes Official Dashboard](https://github.com/nousresearch/hermes) — 参考实现
 - [GUI 项目模板](references/gui-project-template.md)
