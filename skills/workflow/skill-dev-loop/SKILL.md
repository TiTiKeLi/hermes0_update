 ---
 name: skill-dev-loop
 description: 技能开发循环 — 从缺口识别→子Agent创建→验证→迭代→集成测试→优化→注册的完整闭环。每个新技能或现有技能的重大更新都经过这个循环。
 category: workflow
 platforms: [linux, windows]
 related_skills:
   - meta-orchestrator
   - skill-creation-rules
   - verification-before-completion
   - dispatching-parallel-agents
   - autogpt-self-improve
   - error-recovery
   - quality-gates
 triggers:
   keywords:
     - 开发循环
     - 技能迭代
     - 完善技能
     - 优化技能
     - 技能生命周期
     - 循环开发
     - dev loop
     - skill lifecycle
     - 子Agent
     - 子智能体
     - parallel agents
     - 多Agent协作
   tools:
     - skill_manage
 ---
 
 # Skill Development Loop — 技能开发循环 v1
 
 ## 核心概念
 
 整个技能开发是一个**闭环**，不是线性流程。每一轮循环都会产出一个更完善的版本。
 
 ```
                    ┌──────────────────┐
                    │  缺口识别 (Gap)   │ ← ARCHITECTURE.md
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ 子Agent 分发      │ ← 每个缺口分配一个子Agent
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
     │ 子Agent A    │ │ 子Agent B    │ │ 子Agent C    │
     │ 创建技能A    │ │ 创建技能B    │ │ 创建技能C    │
     └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
            │               │               │
              └──────────────┼──────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ 质量门 (Gate)     │ ← quality-gates 检查
                    └────────┬─────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
              ┌──────────┐     ┌──────────┐
              │ 通过      │     │ 不通过    │
              └────┬─────┘     └────┬─────┘
                   │               │
                   ▼               ▼
            ┌────────────┐   ┌────────────┐
            │ 集成测试    │   │ 进入 Patch  │
            └─────┬──────┘   │ 子循环     │
                  │          └──────┬─────┘
                  ▼                 │
            ┌────────────┐         │
            │ 通过？      │◄────────┘
            └─────┬──────┘
                  │
          ┌───────┴───────┐
          │               │
          ▼               ▼
    ┌──────────┐     ┌──────────┐
    │ 优化迭代  │     │ 注册发布  │
    │ (autogpt) │     │ (registry│
    └────┬─────┘     │  + push) │
         │           └────┬─────┘
         └───────┬────────┘
                 ▼
          ┌──────────────┐
          │ ARCHITECTURE │
          │ 更新状态      │
          └──────────────┘
                 │
                 ▼
          ┌──────────────┐
          │ 回到缺口识别   │ ← 下一轮
          └──────────────┘
 ```
 
 ## 子Agent 角色定义
 
 每个 P1/P2 缺口分配一个专门的子Agent。
 子Agent 之间**独立工作、不共享状态**（由 dispatching-parallel-agents 保障）。
 
 | 角色 | 职责 | 输入 | 输出 |
 |------|------|------|------|
 | Creator | 创建初始技能 | 缺口描述 + ARCHITECTURE.md | draft SKILL.md |
 | Verifier | 检查质量门 | draft SKILL.md + quality-gates | pass/fail +
 问题列表 |
 | Tester | 集成测试 | 技能 + 实际环境 | test report |
 | Optimizer | 优化触发器/结构 | 技能 + 测试报告 | 优化后的 SKILL.md |
 | Integrator | 注册与架构更新 | 最终技能 | SKILL_REGISTRY + ARCHITECTURE |
 | Loop Coordinator | 循环管理 | 各阶段状态 | 决定下一阶段或重新进入循环 |
 
 ## 子Agent 执行协议
 
 ### Stage 1: 初始化 (Coordinator)
 
 ```
 □ 从 ARCHITECTURE.md 读取缺口列表
 □ 确定本轮要处理的缺口（优先级排序）
 □ 为每个缺口分配一个子Agent
 □ 分发上下文：缺口描述 + 依赖技能 + 边界条件
 ```
 
 ### Stage 2: 并行创建 (Creator × N)
 
 ```
 每个子Agent 独立执行：
 □ 遵循 skill-creation-rules 的 SKILL.md 模板
 □ 检查命名冲突（与现有技能不重复）
 □ 设置完整的 triggers（关键词 + 工具 + 事件）
 □ 定义边界条件（入口/出口/不适用）
 □ 输出 draft SKILL.md 到临时目录
 ```
 
 ### Stage 3: 质量门 (Verifier)
 
 ```
 每个 draft SKILL.md 通过以下检查才能进入下一阶段：
 
 □ 结构完整 — 有 frontmatter、核心问题、边界条件、适用场景
 □ 触发词覆盖 — keywords 覆盖 3 种以上自然语言表达
 □ 依赖正确 — related_skills 引用的技能都存在
 □ 不冲突 — 不覆盖现有技能的 trigger 范围
 □ 可执行 — 步骤可操作，不是纯理论
 ```
 
 ### Stage 4: 集成测试 (Tester)
 
 ```
 □ 在 Hermes 环境中触发技能
 □ 检查是否在预期场景下正确加载
 □ 检查是否与其他技能产生冲突
 □ 输出 test report（pass/fail + 详细日志）
 ```
 
 ### Stage 5: 优化迭代 (Optimizer + autogpt-self-improve)
 
 ```
 □ 根据 test report 优化
 □ triggers 补充新关键词（从测试中发现的表达方式）
 □ references 补充新的参考文档
 □ related_skills 同步更新
 ```
 
 ### Stage 6: 注册 (Integrator)
 
 ```
 □ 更新 SKILL_REGISTRY.yaml（添加新技能）
 □ 更新 ARCHITECTURE.md（标记缺口为 ✅）
 □ 更新 CONTEXT.md（如果有配置变更）
 □ 推送 GitHub
 ```
 
 ### Stage 7: 回到 Stage 1 (循环)
 
 ```
 □ 检查是否还有未处理的缺口
 □ 有 → 进入下一轮循环
 □ 无 → 进入 idle 状态，等待新的缺口被识别
 ```
 
 ## 与现有技能的关系
 
 | 现有技能 | 在循环中的角色 |
 |---------|--------------|
 | meta-orchestrator | 提供子任务分发能力（本循环的运行时引擎） |
 | skill-creation-rules | Stage 2 的创建模板 |
 | verification-before-completion | Stage 3 的验证方法论 |
 | dispatching-parallel-agents | Stage 2 的并行执行机制 |
 | autogpt-self-improve | Stage 5 的优化引擎 |
 | error-recovery | 循环中各阶段出现失败时的兜底 |
 | quality-gates | Stage 3 的具体检查项 |
 
 ## 边界条件
 
 ### 入口条件

- ARCHITECTURE.md 中存在未标记为 ✅ 的缺口
- 现有技能需要版本升级
- 用户要求创建新技能或改进现有技能
- 技能质量门检查未通过需要重新进入循环

### 出口条件

- 本轮循环的缺口已标记为 ✅
- 所有新技能已通过质量门 G1-G5
- 至少产出了一个可推送的版本
- ARCHITECTURE.md 和 SKILL_REGISTRY.yaml 已同步更新



