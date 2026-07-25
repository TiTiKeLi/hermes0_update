---
name: skill-creation-rules
description: 创skills时强制遵守的规则。每次skill_manage(action='create')前必须加载本skill，执行完立即更新SKILL_REGISTRY.yaml
category: meta
conditions:
  requires_toolsets:
    - file
platforms: [linux]
related_skills: [memory-compactor, external-adaptor, secure-download, github-discover]
triggers:
  keywords:
    - 创建技能
    - 新技能
    - 技能规则
    - skill create
    - create skill
    - skill rules
    - 技能模板
    - 技能结构
    - 技能注册
    - SKILL.md
  tools:
      - skill_manage
---

# Skill 创建规则（必遵守）v1

## 0. 触发机制

每次执行 `skill_manage(action='create')` 前：
1. 先 `skill_view(name='skill-creation-rules')` 加载本规则
2. 按规则设计 skill
3. 创建后立即更新 `/opt/data/skills/SKILL_REGISTRY.yaml`

---

## 1. 强制结构

每个 skill 必须包含以下 5 个节，缺一不可：


## 触发器要求（强制）

每个技能的 `triggers.keywords` 必须满足以下标准：

### 数量要求
```
□ 至少 8 个关键词（config-unification 标准: 73个）
□ 少于 8 个 → 质量门 G2 不通过，不允许注册
```

### 场景覆盖要求
```
三大场景都必须覆盖：
□ 新建场景关键词 ≥ 3 个（"新建配置""创建文件""加个"）
□ 修改场景关键词 ≥ 3 个（"修改配置""更新""改一下"）
□ 故障场景关键词 ≥ 3 个（"报错""不通""挂了"）
```

### 语言覆盖要求
```
□ 中文口语关键词 ≥ 3 个（用户日常表达方式）
□ 中文书面关键词 ≥ 3 个（技术描述）
□ 英文关键词 ≥ 2 个（跨语言触发）
```

### 常见缺陷
```
❌ 只有英文没有中文 → 中文用户不会触发
❌ 只有书面语没有口语 → 用户不会用书面描述问题
❌ 只覆盖一个场景 → 其他场景下不会加载
❌ 关键词少于 8 个 → 覆盖面不够
```

### 1.1 边界条件（BOUNDARIES）

```
### 入口条件

- 需要创建新技能
 - 需要更新现有技能
 - 技能结构需要检查

### 跳过条件（一条即跳过）
- [ ] ...
### 中止条件（执行中，一条即停）
- [ ] ...
```

规则：不能只写"在什么场景下触发"——必须同时写**什么场景不触发**和**什么场景中止**。

### 1.2 决策矩阵（DECISION MATRIX）

```
| 场景 | 行动 | 工具链 | 产出 |
|------|------|--------|------|
```
规则：至少覆盖 3 个场景分支（主路径 + 降级 + 异常）。不能只有一条"happy path"。

### 1.3 原子步骤（STEPS）

每步格式：
```
### Step N: 步骤名
**输入**：
**工具**：
**操作**：
**验证**：
**产出**：
```
规则：每步必须有验证手段——光写文件是不够的，必须 read_file 回读确认。

### 1.4 工具/Skill 联动表（TOOL CHAIN MAP）

```
| 步骤 | 调用的工具 | 读取的文件 | 写入的文件 | 依赖的 skill |
|------|-----------|-----------|-----------|-------------|
```
规则：每步必须声明调了什么 Hermes 工具、读了/写了什么文件、依赖什么其他 skill。

### 1.5 反馈回路（FEEDBACK LOOP）

至少包含：
- 文件写后验证（write_file → read_file）
- 回复固化（执行结果写入持久化文件供下次迭代）
- 迭代上下文（state.json 里有 context_for_next 字段）
- 降级/死路标记（连续失败后自动标记跳过）

---

## 2. 技能设计规范

命名规则 + 编写方法 + 目录结构共同构成技能的设计规范。

- 全小写中划线（kebab-case）
- 最大 48 字符
- **同类功能合并，不拆分**（如已有 `tool-governance`，不新建 `tool-registry`——更新已有）
- **强制去重检查**：命名前必须先 `skills_list()` 查看所有已有 skill，确认无功能重叠。如果重叠度 >50% → 绝不可新建，必须 `action=patch` 更新已有 skill
- category 从以下选一：`workflow | memory | behavior | security | thinking | architecture | meta`
- 与已有 skill 重叠的业务功能 → `action=patch` 更新已有，不新创建

### 2.1 技能编写方法（从 superpowers writing-skills 吸收）

编写好 skill 不仅仅是写文档，而是**将 TDD 应用于流程文档**。核心思路：

```
没看到智能体在没有该 skill 时失败，就不知道这个 skill 是否教了正确的东西
```

#### TDD 映射到技能编写

| TDD 概念 | 技能创建中的对应 |
|----------|----------------|
| **测试用例** | 带子智能体的压力场景 |
| **生产代码** | 技能文档（SKILL.md） |
| **测试失败（红）** | 智能体在没有技能时违反规则（基线） |
| **测试通过（绿）** | 智能体在有技能时遵守规则 |
| **重构** | 在保持合规的同时堵住漏洞 |
| **先写测试** | 在编写技能之前先运行基线场景 |
| **观察失败** | 记录智能体使用的确切合理化借口 |
| **最小代码** | 编写针对那些具体违规行为的技能 |
| **观察通过** | 验证智能体现在遵守规则 |

#### 实操步骤（将 TDD 映射落地为可执行流程）

每次创建技能时，按以下顺序执行：

**Step A：跑基线（先写测试 → 先跑基线场景）**
```python
from hermes_tools import delegate_task, read_file

# 1. 在技能创建前，分派子智能体执行目标场景——明确告知它不要使用某技能
result = delegate_task(tasks=[{
    "goal": "运行 <目标场景> 并记录失败行为",
    "context": """你正在被测试——请<b>假装不知道</b>存在 '<技能名>' 技能。
执行 <目标命令/场景>，记录你的原始输出。
重点是：在没有该技能指导的情况下，你会犯什么错误？"""
}])
# 2. 等待子智能体返回完整的原始输出（含错误/遗漏）
```

**Step B：提炼违规模式（观察失败 → 记录合理化借口）**
```python
# 从 Step A 的输出中提取具体违规行为
# 输出格式要求子智能体返回：
baseline_result = "..."   # 子智能体实际输出
violations = []           # 从输出中提取的违规列表
# 示例违规：使用了`sed`代替`patch`、忘记 run verification、对话中出现了"应该"这个词
```

**Step C：编写并验证（最小代码 → 验证通过）**
```python
# 1. 创建技能，仅针对 Step B 发现的违规行为
# 2. 再次分派子智能体
result = delegate_task(tasks=[{
    "goal": "再次运行 <目标场景>——这次使用 '<技能名>' 技能",
    "context": """现在你拥有 '<技能名>' 技能。按技能中的步骤执行。
重点是：这次是否能避免 Step B 中记录的所有违规？"""
}])
# 3. 对比两次结果：新输出不应再出现违规列表中的任何一项
```

> **验证标准**：第二次运行不再出现第一次的错误列表中的任何一项 → 技能有效

#### 技能类型

| 类型 | 描述 | 示例 |
|------|------|------|
| **技术类** | 有具体步骤的方法 | condition-based-waiting、root-cause-tracing |
| **模式类** | 思考问题的方式 | flatten-with-flags、test-invariants |
| **参考类** | API 文档、语法指南、工具文档 | office docs、hermes-tools |

#### 目录结构要求

```
skills/<skill-name>/
├── SKILL.md
├── references/     # 引用文档、API 参考、最佳实践
├── templates/      # 可复用的模板（可选）
└── scripts/        # 辅助脚本（可选）
```

#### 创建决策

**何时创建：**
- 技术对你来说不是直觉上显而易见的
- 会跨项目反复使用
- 模式具有广泛适用性（非项目特定）
- 其他人也会受益

> 何时**不要创建** → 详见 [## 5. 禁止行为](#5-禁止行为)（两处规则一致，以 §5 为权威源）

---

## 3. 关联规则

- 每次创建前先 `skill_view(name='skills_list')` 看有没有重叠
- 如果新 skill 和其他 skill 有交集 → `related_skills` 注明关联，多个用 `;` 分隔
- 执行结果需要固化 → 关联 `memory-compactor`（确保记忆空间足够）
- 需要外部搜索依据 → 关联 `github-discover`（研究管道）

---

## 4. 创建后操作（强制）

```yaml
# 4.1 更新 SKILL_REGISTRY.yaml
# 读取现有 registry，新增或更新条目
# 格式：
- name: <新技能名>
  status: active
  category: <category>
  related: <关联1>;<关联2>
  created: <YYYY-MM-DD>
  last_updated: <YYYY-MM-DD>
  created_by: auto
  description: <一句话>
```

```python
# 4.2 验证 registry 条目已存在
from hermes_tools import read_file
result = read_file(path="/opt/data/skills/SKILL_REGISTRY.yaml")
assert "<新技能名>" in result["content"], "registry 更新失败"
```

### 4.3 创建后检查清单
- [ ] SKILL_REGISTRY.yaml 已更新
- [ ] read_file 回读确认 registry 条目正确
- [ ] 如果依赖其他 skill → 确认那些 skill 是否存在
- [ ] 如果有写文件 → 读回确认内容完整
- [ ] category 正确
- [ ] **编号孤儿陷阱检查**：如果在编号列表（如 `3. ... 4. ...`）中插入了新小节（如 `#### Step 3a`），read_file 回读确认相邻 5 行无悬空编号

### 4.4 创建后闭环验证（User 强制的关闭步骤）

> 光创建了技能还不够——必须让技能"工作一次"，产生可展示的验证证据，才能宣称完成。

**规则**：每个新创建或更新的 skill，在移除 TODO 或回复"完成"之前，必须：

1. **加载确认**：`skill_view(name='<新技能名>')` → 确认可正常读取，无截断
2. **功能验证**：如果 skill 有独立可执行的验证机制（如 `verification-before-completion` 的"运行验证命令"、`dispatching-parallel-agents` 的"分派并行子智能体"），**立即用该 skill 来验证本次创建工作的产出**。示例：
   - 创建了 `dispatching-parallel-agents` → 用它分派 N 个子智能体验证本次更新的每个文件
   - 创建了 `verification-before-completion` → 用它来确认所有文件写入都已 read_file 回读
3. **展示证据**：产出必须包含真正的工具调用输出或子智能体返回结果，不能是"假设已通过"
4. **通过才完成**：只有验证通过后，才能更新 TODO 状态为 completed 或回复"完成"

**违反此规则的惩罚**：如果宣称完成但未执行此步骤，该技能应更新嵌入此惩罚规则作为迭代上下文。

---

## 5. 禁止行为

- ❌ 创建"空的"或"待补充"的 skill
- ❌ 创建只有描述没有步骤的 skill
- ❌ 创建同义 skill（如已有 `tool-governance` 还建 `tool-state`）
- ❌ 为已被吸收的技能创建独立 skill（如之前已合并入 external-adaptor 的 `functional-decomp` 不应重新出现）
- ❌ 创建超过 300 行的 skill（太长 → 拆引用）
- ❌ 创建后不更新 SKILL_REGISTRY
- ❌ 删除 skill 后不清除 registry 条目（标记 status: merged:<target> 或 status: deprecated）

### 出口条件

- 问题已解决或结论已输出
- 所有必要的操作已完成
- 结果已向用户报告

