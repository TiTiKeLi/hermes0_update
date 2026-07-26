---
name: meta-orchestrator
description: 元编排系统 — 接收需求→规划框架→拆分子任务→分发Ollama智能体→评分→汇总，全程生命周期管理
category: workflow
conditions:
  requires_toolsets:
    - terminal
    - file
platforms: [linux]
related_skills:
  - autogpt-self-improve
  - external-adaptor
  - tool-governance-v2
triggers:
  keywords:
    - 编排
    - 子任务
    - 分发任务
    - 拆分任务
    - 分配
    - 协调
    - orchestrate
    - subtask
    - task dispatch
    - 任务拆分
    - 任务分发
    - 协调多个
    - 编排任务
---

# Meta-Orchestrator v1 — 元编排系统

借鉴 AutoGPT Forge 的 Component-Pipeline 架构（run_pipeline 遍历组件 / 协议分派 / @command 注册），
适配为 Hermes 的元编排：**规划→拆解→分发→执行→评分→汇总**全链路。

核心思想：**Agent.md 作为智能体身份定义**，agent_registry.py 管理全生命周期，Ollama 驱动每个子智能体。

> 架构映射详见 `references/arch-mapping.md` — AutoGPT Forge → Hermes 对照表
> Ollama 调用模式详见 `references/ollama-patterns.md` — 超时处理、检测方法、fallback 策略
> 评分+汇总引擎见 `scripts/eval_aggregate.py` — 自动评分（Ollama 可用/不可用双模式）

---

## 1. 边界条件

### 入口条件

- 复杂任务需要拆分为子任务
 - 需要多个子智能体协作
 - 任务需要全生命周期管理

### Ollama 可用性标志
⛔ **Ollama 可能不可用**。`host.docker.internal:11434` 在宿主休眠或繁忙时超时。
**所有步骤都必须同时支持"Ollama 可用"和"Ollama 不可用"两条路径。**
在 Step 0 检查并缓存结果到变量 `ollama_ok`，后续步骤据此走分支。

### 跳过条件（一条即跳过）
- [ ] 用户需求简单到不需要拆解（单个 tool 能搞定）
- [ ] 用户明确说"不用规划，直接做"

### 中止条件（执行中，一条即停）
- [ ] agent_registry.py 报语法/运行时错误
- [ ] 连续 2 次 Ollama 调用超时
- [ ] 规划框架生成后无有效子任务
- [ ] 用户中途切换话题

---

## 2. 决策矩阵

| 场景 | 行动 | 产出 |
|------|------|------|
| 新需求 | 全链路：规划→拆解→分发→评分→汇总 | 完整规划 + 执行报告 |
| 已有规划需继续 | 读取 plan state.json → 找出未完成任务 → 只分发这些 | 增量执行报告 |
| 某个 agent 执行失败 | 记录失败→重新分配（最多 2 次）→仍失败标记为 FAILED | 失败报告 |
| 评分 < 5/10 | 触发重试：让另一个 agent 重做同一任务 | 重做结果 + 对比 |
| 所有任务完成 | 汇总所有结果 → 加权评分 → 最终报告 | 最终汇总报告 |

---

## 3. 原子步骤

### Step 0: 需求接收 + Agent 盘点 + Ollama 连通性检测

**输入**：用户需求

**操作**：
1. 记录需求原文到临时变量
2. `terminal("python3 /opt/data/scripts/agent_registry.py list")` → 获取当前可用 agents
3. 检查 agent 数量 ≥ 2，否则报告 "需要至少注册 2 个 agent"
4. ⚠️ **Ollama 连通性检测（必须分开执行，不可链式拼接）**：
   ```bash
   # 独立 terminal() 调用，不要与其它命令 && 拼接
   terminal("curl -s --connect-timeout 3 --max-time 5 http://host.docker.internal:11434/api/tags")
   ```
   - 成功 → 设置 `ollama_ok = True`
   - 失败/超时 → 设置 `ollama_ok = False`，记录 fallback 模式
5. 后续所有步骤根据 `ollama_ok` 分支：
   - `ollama_ok=True` → 用 Ollama 生成/评分/汇总
   - `ollama_ok=False` → 手动提供规划框架 / 本地评分 / 简单拼接汇总
6. 记录 `ollama_ok` 状态到规划 state.json 的 `ollama_available` 字段

**Terminal 工具的重要约束**：
- ⚡ **每次 terminal() 只执行一条命令**。多命令通过 `&&`、`;`、或内联 `python3 -c` 链式拼接在同一个 terminal() 调用中会导致超时（>5s 即 timeout）。
- ✅ 正确的做法：分多次 terminal() 调用，每次一句简单命令。
- 例外：轻量的 `echo "text" && python3 -c "print(1)"` 可以，但不要有 `find`、`grep`、`curl` 等 I/O 操作在同一命令内。

**验证**：
```python
# 用单独的 terminal() 调用，不要与 echo 链式拼接
terminal("python3 /opt/data/scripts/agent_registry.py list | python3 -c \"import sys,json;d=json.load(sys.stdin);print(f'{len(d)} agents ready')\"")
```

**产出**：需求记录 + agent 列表

---

### Step 1: 规划框架生成（Planner Phase）

**输入**：用户需求 + agent 列表

**操作**：
1. 读取所有 Agent.md 了解每个 agent 的能力边界：
   ```
   for agent in agents:
       read agent/Agent.md → 提取 role + capabilities + trigger
   ```
2. 根据 `ollama_ok` 分两条路：

   **路径 A — Ollama 可用（推荐）**：
   调用 Ollama 生成规划框架（使用 agent-planner 的 base_prompt）：
   ```bash
   # 独立 terminal() 调用，勿与其它命令拼接
   terminal("curl -s http://host.docker.internal:11434/api/generate -d '{\"model\":\"VibeThinker-3B:latest\",\"prompt\":\"...\",\"stream\":false}'")
   ```
   解析返回的 JSON → 提取任务列表

   **路径 B — Ollama 不可用（fallback）**：
   手动根据 Agent.md 的 capabilities 构造规划框架。
   参考 agent-planner 的 role 定义，人工拆解 2-4 个子任务。
   框架格式：
   ```json
   {"framework":"<name>","version":"1.0","steps":["<step1>","<step2>",...],"dependencies":[...]}
   ```

3. `terminal("python3 /opt/data/scripts/agent_registry.py plan '<需求>' '<framework_json>'")` → 创建规划记录

**验证**：`python3 agent_registry.py get <plan_id>` → 确认 tasks 非空

**产出**：plan_id + 任务列表

---

### Step 2: 任务拆解 + Agent 匹配（Decomposition Phase）

**输入**：规划框架

**操作**：
1. 对 Step 1 生成的每个子任务，执行：
   - 读取各 Agent.md 的 capabilities + trigger 字段
   - 匹配最佳 agent（按 capability 匹配度打分）
   - 写入任务 JSON（含 agent 分配）
2. `terminal("python3 agent_registry.py state <agent_name> assigned")` → 更新 agent 状态
3. `terminal("python3 agent_registry.py task <plan_id> add '<task_json>'")` → 注册任务

**验证**：所有 task 都有 assigned_agent，agent 状态已更新为 assigned

**产出**：agent→任务映射表

---

### Step 3: 子任务分发执行（Dispatch Phase）

**输入**：agent→任务映射表

**操作**：
1. 根据 `ollama_ok` 和执行方式选择：

   **路径 A — delegate_task 分发（推荐，支持并行）**：
   使用 `delegate_task` 并行分发（最多 3 个并发）：
   ```
   delegate_task(
     goal="<任务目标>",
     context="<Agent.md base_prompt>\n\n<任务上下文>\n响应使用简体中文。输出JSON格式结果。确保结果包含完成任务所需的所有数据字段。"
   )
   ```
   ⚠️ **结果回收的关键约束**：
   - `delegate_task` 的每个子代理结果以 **独立消息** 形式回到当前对话，不可直接写文件到 plan 目录
   - **context 中必须包含 "输出JSON格式结果"** 以保证子代理的 stdout 可解析
   - **context 中必须包含 "响应使用简体中文"** 以防止默认英文输出污染最终汇总
   - 子代理不知道 plan/task 目录路径 — 它们只能通过 stdout 返回结果文本
   - **正确回收模式**：等待每个子代理的结果消息到达后，手动用 `write_file()` 将结果写入 `plan/results/` 目录
   - 不可靠模式：期望子代理自己写文件到 plan 目录（子代理没有 /opt/data 写入路径的知识）

   **路径 B — Ollama 直接调用（适合子任务少，<3个）**：
   用 terminal 直接 curl Ollama API：
   ```bash
   # 独立 terminal() 调用
   terminal("curl -s http://host.docker.internal:11434/api/generate -d '{\"model\":\"VibeThinker-3B:latest\",\"prompt\":\"...\",\"stream\":false}' | python3 -c \"import sys,json;d=json.load(sys.stdin);print(d['response'])\"")
   ```

   **路径 C — 本地执行（Ollama 不可用时的 fallback）**：
   用 `read_file()` + 本地分析代替 AI 生成。
   每个子任务的目标通过 read_file + 本地数据处理来完成。

2. 每种路径之后，立即更新 agent 状态：
   ```
   terminal("python3 agent_registry.py state <agent_name> working")
   ```

3. **结果写入**（关键模式）：
   收到子代理结果或本地分析结果后，执行：
   ```
   terminal("python3 /opt/data/scripts/agent_registry.py task <plan_id> complete <task_id> '<result_json>'")
   ```
   或直接写入 task JSON 文件。**

**验证**：每个任务 result 非空，agent 状态 = working

---

### Step 4: 结果评分（Evaluation Phase）

**输入**：各 agent 的执行结果

**操作**：
1. 对每个结果，调用 Ollama 评分（用评估视角）：
   ```
   prompt = f"""
   评估以下 Agent 执行结果：
   Agent: {agent_name}
   任务: {task_goal}
   结果: {result}
   
   按三个维度评分（0-10）：
   - completeness（完整性）：是否覆盖所有要求？
   - accuracy（准确性）：结果是否正确无错误？
   - relevance（相关性）：结果是否切题？
   
   输出 JSON: {{"completeness": X, "accuracy": Y, "relevance": Z, "comment": "..."}}
   """
   ```
2. 解析评分结果
3. `python3 agent_registry.py score <agent_name> "<task>" '<scores_json>' "<comment>"`
4. 如果均分 < 5 → 标记"需要重试" → 回到 Step 3 重新分发

**验证**：每个任务有评分记录，agent score_history 已更新

**产出**：评分表

---

### Step 5: 结果汇总（Aggregation Phase）

**输入**：所有执行结果 + 评分

**操作**：
1. 按评分加权汇总各 agent 的结果
2. 调用 Ollama 生成最终汇总报告：
   ```bash
   curl -s http://host.docker.internal:11434/api/generate \
     -d '{"model":"VibeThinker-3B:latest","prompt":"汇总以下N个子任务结果...","stream":false}'
   ```
3. 写入 `plan-<id>/summary.md`
4. 将最终结果交付用户

**验证**：`read_file(plan/summary.md)` 非空

**产出**：最终汇总报告 + summary.md

---

### Step 6: 生命周期闭环

**输入**：所有步骤完成

**操作**：
1. `python3 agent_registry.py state <agent_name> available` → 所有 agent 回到可用
2. 更新 plan state.json：`plan["status"] = "completed"` + `completed = now`
3. 可选：将本次规划的关键信息存入 fact_store
4. 输出最终报告给用户

**验证**：所有 agent 状态 = available，plan state = completed

**产出**：完整闭环的规划记录

---

## 3.5 验证构建（Verification Phase）

**⚠️ 这条是用户的硬性偏好：构建完成后必须实际验证，不能只描述理论结果。**

每次元编排执行完毕后（或任何 Skill 构建完成后），必须做：
1. **展示实际输出**：运行验证命令，让用户看到真实的终端输出
2. **展示目录结构**：`search_files(target='files', pattern='*', path='<产出路径>')`
3. **展示关键文件内容摘要**：读取关键文件的前几行
4. **阻塞问题必须报告**：Ollama 不可达、terminal 超时等真实限制不能跳过或假装正常
5. **结论判断**：基于实际输出给出 ✅/⚠️/❌ 评级

---

## 4. 工具/Skill 联动表

| 步骤 | 调用的工具 | 读取的文件 | 写入的文件 | 依赖的脚本/参考 |
|------|-----------|-----------|-----------|-------------|
| Step 0 | `terminal` + `skill_view` | Agent.md 列表 | 需求记录 | references/ollama-patterns.md |
| Step 1 | `terminal`(curl Ollama 或手动) | Agent.md | plan.md + state.json | references/ollama-patterns.md |
| Step 2 | `read_file` + `terminal` | Agent.md | tasks/*.json | — |
| Step 3 | `delegate_task` 或 `terminal`(Ollama) 或本地分析 | tasks/*.json | results/*.json | references/ollama-patterns.md |
| Step 4 | `terminal`(评分) 或 `scripts/eval_aggregate.py` | results/*.json | 评分记录 → registry | scripts/eval_aggregate.py |
| Step 5 | `terminal`(汇总) 或 `scripts/eval_aggregate.py` | 所有结果 | summary.md | scripts/eval_aggregate.py |
| Step 6 | `terminal`(registry) | state.json | registry.json | — |

---

## 5. 反馈回路

### 5.1 失败重试
Step 4 评分 < 5 → 自动重试（换 agent 或相同 agent 重做），最多 2 次。连续失败标记为 FAILED。

### 5.2 Agent 能力进化
如果某个 agent 连续 3 次评分 > 8 → 增加其权重/优先分配。
如果连续 3 次评分 < 5 → 标记 `score_warning`，提示检查 Agent.md 定义。

### 5.3 规划复用
已完成规划的 plan.md + state.json 保留在 `agents/plans/` 下。
同类需求出现时，先搜索已有规划作为参考（`search_files(pattern="<关键词>", path="/opt/data/agents/plans/")`）。

### 5.4 并发控制
delegate_task 默认最多 3 个子 agent 并发（max_concurrent_children）。
如果子任务 > 3，分批执行。每批完成后启动下一批。

### 5.5 回滚路径
任何步骤失败：

**Ollama 相关失败**（高概率）：
- Step 0 检测到 Ollama 不可用 → 设置 `ollama_ok=False`，后续所有步骤走 fallback 路径
- Step 1 Ollama 生成规划 → 手动构造规划框架 JSON（参考 Agent.md 的 capabilities）
- Step 3 Ollama 子代理执行 → 用 `read_file` + 本地 Python 分析替代
- Step 4 Ollama 评分不可用 → `scripts/eval_aggregate.py` 的自动评分模式（基于内容长度/关键词）
- Step 5 Ollama 汇总不可用 → 同上脚本模式，或手动拼接 Markdown 报告

**其他失败**：
- Step 1 失败 → 告知用户"无法生成规划框架"，退出
- Step 2 失败 → 告知用户"无法匹配 agent"，手动指定或退出
- Step 3 失败（某 agent 超时/出错）→ 重试 2 次 → 仍失败则标记 FAILED 继续
- Step 4 评分 < 5 → 重试（回到 Step 3）

### 5.6 持久化记录
所有规划、任务、结果、评分都持久化到 `/opt/data/agents/plans/` 下，可被后续查询和复用。

### 出口条件

- 问题已解决或结论已输出
- 所有必要的操作已完成
- 结果已向用户报告

