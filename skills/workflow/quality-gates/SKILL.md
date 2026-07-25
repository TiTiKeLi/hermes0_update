 ---
 name: quality-gates
 description: 质量门禁 — 技能/配置/代码在进入下一阶段前必须通过的检查清单。每次 skill-dev-loop 的 Stage 3 自动加载。
 category: workflow
 platforms: [linux, windows]
 related_skills:
   - skill-creation-rules
   - verification-before-completion
   - skill-dev-loop
 triggers:
   keywords:
     - 质量门
     - 检查清单
     - 验收标准
     - 合规检查
     - 质量检查
     - quality gate
     - checklist
     - acceptance criteria
     - 完成检查
     - 发布检查
   tools:
     - skill_manage
     - patch
 ---
 
 # Quality Gates — 质量门禁系统 v1
 
 ## 核心问题
 
 技能/配置快速创建后缺乏系统验证，容易带着问题进入下一阶段：
 - 触发词不完整（只覆盖了一种表达方式）
 - 边界条件缺失（没定义什么情况下不该用）
 - 依赖不存在（引用了不存在的技能）
 - 命名冲突（与现有技能/文件重名）
 - 安全隐患（包含了不应有的内容）
 
 质量门禁系统在每个关键阶段设置检查点，全部通过才能继续。
 
 ## 门禁类型
 
 ### G1: 创建门（Creation Gate）
 
 在新技能/文件首次创建后执行：
 
 ```
 □ 文件名合法 — 小写中划线，且不与现有技能重名
 □ frontmatter 完整 — name, description, category, triggers, platforms
 □ 结构完整 — 核心问题、边界条件、入口/出口条件齐全
 □ skill-creation-rules 中定义的强制节全部存在
 □ 不包含明文密钥 — api_key/token/password 值不为空
 ```
 
 ### G2: 触发门（Trigger Gate）
 
 在技能发布前执行：
 
 ```
 □ keywords 至少包含 8 个不同的触发词
 □ 覆盖三种表达方式（中文口语/中文书面/英文）
 □ 场景触发词覆盖（新建场景/修改场景/故障场景 — 如果适用）
 □ 无歧义触发词（不会误触发在不相关的场景）
 ```
 
 ### G3: 依赖门（Dependency Gate）
 
 在技能注册前执行：
 
 ```
 □ related_skills 中引用的所有技能都存在（在 SKILL_REGISTRY 中可查到）
 □ required_toolsets 中的工具集在 config.yaml 中已配置
 □ 不循环依赖（A→B→A）
 □ 引用的文件路径存在（references/ 中的文件）
 ```
 
 ### G4: 安全门（Security Gate）
 
 在推送前执行：
 
 ```
 □ 不包含明文密钥 — 由 data-security-audit.ps1 验证
 □ 不包含数据库文件 — 由 .gitignore 验证
 □ 不包含会话数据 — 由 .gitignore 验证
 □ Gitleaks 全量历史扫描通过
 ```
 
 ### G5: 集成门（Integration Gate）
 
 在注册到 ARCHITECTURE.md 前执行：
 
 ```
 □ 新技能与同类别现有技能不冲突（trigger 范围不重叠）
 □ 新技能可以在测试环境中被加载（manual trigger test）
 □ 新技能不破坏现有技能的测试路径
 ```
 
 ## 门禁执行规则
 
 ```
 所有 G1-G5 必须全部通过 → 进入下一阶段
 任意一个失败 → 返回创建阶段，修复后重新检查
 连续 3 次同一门失败 → 触发 error-recovery 的安全机制
 紧急跳过（仅生产故障修复时）：
   git commit --no-verify （跳过所有门禁）
   修复完成后必须补跑所有门禁
 ```
 
 ## 门禁报告格式
 
 ```yaml
 quality_report:
   skill: "data-retention"
   gates:
     G1_creation:  pass ✅
     G2_trigger:   pass ✅
     G3_dependency: pass ✅
     G4_security:  pass ✅
     G5_integration: fail ❌
       reason: "trigger 与 memory-compactor 重叠"
       fix: "调整触发词范围"
   overall: "blocked"
   next_action: "返回 Stage 2，修复后重新提交 G5"
 ```
 
 ## 适用场景
 
 ### 入口条件

- 新技能创建完成准备进入下一阶段
- 现有技能有重大修改
- 配置变更需要安全检查
- 每次 git push 或注册前

### 出口条件

- 所有适用门禁已通过
- 未通过的门禁有明确的修复指引
- 门禁结果已记录



