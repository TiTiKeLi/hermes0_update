---
name: autogpt-self-improve
description: 基于 AutoGPT Forge 架构提炼的自迭代代理技能 — 能分析自身技能、评估效果、生成改进方案
category: workflow
conditions:
  requires_toolsets:
    - file
    - terminal
    - web
platforms: [linux]
related_skills:
  - functional-decomp
  - interface-decomp
  - arch-decomp
  - dataflow-decomp
  - download-gate
  - tool-governance-v2
  - meta-orchestrator
triggers:
  keywords:
      - 自迭代
      - self improve
      - 技能改进
      - autoGPT
      - 自评估
---

# AutoGPT Self-Improve v1 — 自迭代代理

从 AutoGPT 经典 Forge 架构提炼，核心机制：**Command 注册 → 执行 → 结果评估 → 自改进**。

---

## 1. 边界条件

### 入口条件（必须全部满足）
- [ ] 有可分析的自有技能列表（`skill_list` 或 `skills_list`）
- [ ] 有技能执行记录（cron 日志 或 session 记录）
- [ ] 容器能调用 LLM（`host.docker.internal:11434`）

### 跳过条件（一条即跳过）
- [ ] 系统无有效技能（< 2 个）
- [ ] 技能无执行历史
- [ ] 上次自迭代在 24 小时内（防循环）

### 中止条件（执行中，一条即停）
- [ ] LLM 不可用（Ollama 超时）
- [ ] 技能注册表损坏（SKILL_REGISTRY.yaml 语法错误）
- [ ] 磁盘空间 < 100MB

---

## 2. 决策矩阵

| 场景 | 行动 | 产出 |
|------|------|------|
| 技能有执行错误（cron 日志含 error） | 读取错误日志 → 分析根因 → patch skill | 修复后的 skill |
| 技能无最优轮次记录 | 读取 skill 内容 → LLM 评估完整性/质量 → 评分 | 评估报告 + 改进建议 |
| 技能功能重叠（2+ skill 做同一件事） | 合并 + 去重 → 删除旧 skill | 合并后的 skill |
| 新增外部项目（incoming/ 有未处理内容） | 走 external-adaptor 管道 → 拆解 → 评估 → 集成 | 新 skill |

---

## 3. 原子步骤

### Step 1: 技能盘点

**操作**：
1. `skills_list()` → 获取全部技能
2. 对每个 skill: `skill_view(name)` → 获取 SKILL.md
3. 记录：name, description, category, 最后修改时间, 执行统计

### Step 2: 执行记录分析

**操作**：
1. `cronjob(action="list")` → 获取所有 cron
2. 关联 cron 到对应 skill
3. 分析每条 cron 的 `output/` 日志 — 找 error/失败模式

### Step 3: LLM 评估

**操作**：
1. 构建评估 prompt，包含：技能名、描述、步骤结构、cron 日志
2. 调用 Ollama 评估：
   - 完整性（0-10）：是否覆盖所有关键步骤
   - 准确性（0-10）：命令/参数是否正确
   - 时效性（0-10）：是否过时
   - 重叠度（0-10）：与其他技能的重复程度

#### Step 3a: 高级 GEPA 式多维度评估（可选模式，需要外部 API）

当容器可访问外部 LLM API（OpenRouter/Anthropic）且需要高精度评估时，启用此模式。

**评估维度表：**

| 维度 | 权重 | 评分标准（0-10） | 测量方法 |
|------|------|-----------------|---------|
| **准确性** | 0.35 | 命令/路径/参数是否精确正确 | 执行验证 |
| **完整性** | 0.25 | 是否漏掉关键步骤或边界 |
| **简洁性** | 0.15 | 是否啰嗦重复 |
| **可执行性** | 0.25 | 步骤是否可被直接执行无需补充 |

**评估数据集：**
- 从 cron 日志提取 3-5 个真实执行案例作为评估样本
- 如果不足 3 个，使用人工构造的代表性场景

**统计显著性检查：**
- 连续两次评估的改进幅度 < 0.3/10 → 提前终止迭代（已达局部最优）
- 使用滑动窗口平均值（窗口=3）

**执行轨迹分析（ vs 结果分析）：**
- 除了看输出结果，还要分析执行路径：
  1. 技能步骤是否按预期顺序执行？
  2. 有没有步骤被"合理化"跳过了？（如 tool 调用失败但 agent 宣称成功）
  3. 实际调用的工具是否和技能声明的工具一致？
- 通过对比 `cron 日志中的实际工具调用序列` vs `技能 Step Map（工具/Skill 联动表）` 发现偏差

**如果是 `meta-orchestrator` 技能**，额外评估其 agent 注册表数据：
- 评分数据反映 orchestrator 的实际运行质量
- 低分 agent（score_avg < 5）→ 建议检查该 Agent.md 的 base_prompt 或 capability 定义
- 长期未用 agent（score_count = 0）→ 建议调整触发条件或合并到其他 agent

4. 输出评估报告

### Step 4: 改进执行

**操作**：
1. 按评估结果排序改进优先级
2. **多层级改进（从 NousResearch GEPA 框架吸收）：**

   | 层级 | 范围 | 风险 | 适用条件 |
   |------|------|------|---------|
   | **Tier 1** | SKILL.md 内容/步骤 | 低 | 任何改进 |
   | **Tier 2** | Tool 描述/触发条件 | 中 | 步骤调优不够时 |
   | **Tier 3** | System prompt | 高 | 仅当路径/日志分析确认了 prompt 级别 bug |
   | **Tier 4** | 底层代码（hooks/scripts） | 最高 | 仅当有 100% 通过的测试套件 |

   改进**不能跨级跳跃**：必须先尝试 Tier 1，再逐步升级。除非评估明确指向更高层级的问题。

   **GEPA 式 guardrails（改进前启动）：**
   - [ ] 当前改进版本 vs 上一个版本是否语义一致？（核心目标未改变）
   - [ ] 改进导致的大小变化 < 30%（防止膨胀）
   - [ ] 如果改进 Tier 3/4：是否有可运行的测试套件？
   - [ ] 如果改进涉及 cron 脚本：是否有前置校验（大小/行数/exit code 守卫）？

3. 对低分 skill（< 5/10）：
   - `skill_view(name)` → 读取当前内容
   - LLM 生成改进版
   - `skill_manage(action="edit")` 或 `patch` → 更新
4. 对重叠 skill：
   - LLM 生成合并方案
   - 创建合并后 skill
   - 删除旧 skill（`skill_manage(action="delete", absorbed_into="合并后名称")`）

### Step 5: 自迭代闭环

**操作**：
1. 将本次自迭代的评估报告写入 `/opt/data/research/self_improve/latest_eval.md`
2. `cronjob(action="create", schedule="every 24h", prompt="运行 autogpt-self-improve 技能的自迭代闭环", skills=["autogpt-self-improve"])` — 已存在则跳过

---

## 4. 工具/Skill 联动表

| 步骤 | 调用的工具 | 读取的文件 | 写入的文件 | 依赖的 skill |
|------|-----------|-----------|-----------|-------------|
| Step 1 | `skills_list` + `skill_view` | 所有 SKILL.md | 技能清单 | — |
| Step 2 | `cronjob` + `read_file` | cron 输出日志 | 执行分析 | — |
| Step 3 | terminal(Ollama API) | 技能清单 + 日志 | 评估报告 | — |
| Step 4 | `skill_manage` + `patch` | 需要改进的 skill | 改进后的 skill | — |
| Step 5 | `write_file` + `cronjob` | — | 评估报告 | — |

---

## 5. 反馈回路

- **写后验证**：Step 4 修改 skill 后必须 `skill_view` 回读确认
- **回复固化**：评估报告写入 `research/self_improve/latest_eval.md`
- **迭代上下文**：跟踪"最后改进时间戳"，24h 内不重复
- **降级标记**：如果连续 3 次评估无建议改进 → 写 `STABLE` 标记到评估报告，将 cron 频率降为 7 天
