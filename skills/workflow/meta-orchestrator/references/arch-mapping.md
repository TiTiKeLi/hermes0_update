# AutoGPT Forge → Hermes Meta-Orchestrator 架构映射

用户要求构建元编排系统时指定"可以参考"AutoGPT 架构。以下是核心映射关系。

## 架构借用的关键模式

| AutoGPT Forge 概念 | Meta-Orchestrator 实现 | 说明 |
|---|---|---|
| `Component` (可注册的模块) | 每个 agent 的 Agent.md | 身份定义 + 能力声明（YAML frontmatter） |
| `@command()` 装饰器 | agent_registry.py 的 CLI 子命令 | 注册表 CRUD、状态变更、评分记录 |
| `run_pipeline()` (遍历所有 component) | SKILL.md 的 Step 0→6 线性管道 | 每个 step 是独立的阶段 |
| `Protocol` (协议端点) | agent 间的约定接口 | planner→dispatcher→evaluator→aggregator 的固定输入/输出 schema |
| `ExecutionContext` (执行上下文) | plan state.json + task*.json | 持久化规划/任务/结果的全生命周期 |
| `ResourceBudget` (资源预算) | max_concurrent_children = 3 + 分批 | 防 Ollama 过载 |
| `AgentState` (生命周期) | available→assigned→working→done/failed | 精确的状态机，score_record 后回归 available |
| `post_execute` hook | evaluator 评分 → registry.json | 执行后自动评估，非侵入式反馈 |

## 组件调用链对比

```
AutoGPT Forge:
  app.py → ForgeAgent.run_pipeline()
    → AgentCommand.register()
    → StepExecutor.execute()
    → ResultCollector.collect()
    → Pipeline complete

Meta-Orchestrator (Hermes):
  用户需求 → load meta-orchestrator skill
    → Step 0: agent_registry list + Ollama ping
    → Step 1: Ollama planner (规划框架)
    → Step 2: capability matching (agent 分配)
    → Step 3: delegate_task / Ollama curl (子任务执行)
    → Step 4: Ollama evaluator (多维评分)
    → Step 5: Ollama aggregator (结果汇总)
    → Step 6: state reset (生命周期闭环)
```

## 命令调度模式

AutoGPT 用 `@command` 装饰器注册，Hermes 用 `agent_registry.py` 的 `register` 命令。

```
# AutoGPT
@command(
    command_id="analyze_code",
    label="分析代码质量",
    input_template="请提供代码路径"
)
def analyze_code(self, code_path: str) -> str:
    ...

# Hermes
# agent_registry.py register <name> <Agent.md>
# → 自动从 YAML frontmatter 解析 role/capabilities/trigger
```

## 状态机对比

```
AutoGPT Agent 生命周期:
  LOADING → CONFIGURING → IDLE → RUNNING → STOPPED / ERROR

Meta-Orchestrator Agent 状态:
  available → assigned → working → done / failed / cancelled / timeout
                                        ↓
                                  evaluator 评分
                                        ↓
                                  available (自动回归)
```

## 核心设计原则（从 Forge 继承）

1. **可注册性**: 所有 agent 通过 Agent.md + `register` 命令注册，无需改代码
2. **协议驱动**: agent 间的输入/输出由固定的 template 约束（input_template / output_template）
3. **管道串联**: 每个 phase 的输出是下一个 phase 的输入，无中间人
4. **反馈闭环**: 评分数据持久化到 registry.json，影响后续 agent 匹配优先
5. **降级路径**: Ollama 不可用时报告退出，不硬撑
