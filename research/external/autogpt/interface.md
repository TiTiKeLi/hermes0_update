# AutoGPT 接口拆解报告
来源: github.com/Significant-Gravitas/AutoGPT (classic/forge/)

## 顶层接口映射

### Heremes Tool 适配 (低难度 — 1:1 映射)

| AutoGPT 接口 | Hermes 类型 | 适配方式 | 难度 |
|-------------|------------|---------|------|
| Command(name, description, args, func) | tool 定义 | 直接映射 — name→name, description→desc, args→parameters, func→callback | 低 |
| ForgeAgent.execute(command_name, **args) | tool 调用 | 直接映射 — command_name→tool_name, args→parameters | 低 |
| AgentComponent 协议 | skill action | 组件注册 → Hermes skill 注册 | 低 |
| DirectiveProvider | prompt 前缀 | 直接注入 system prompt | 低 |
| MessageProvider | 对话消息 | 映射为 message history | 低 |

### 中等难度适配

| AutoGPT 接口 | Hermes 类型 | 适配方式 | 难度 |
|-------------|------------|---------|------|
| AfterParse/AfterExecute | event hook | 映射为 Hermes post-execution hook | 中 |
| SubAgentHandle | delegate_task | 子代理创建 → delegate_task API | 中 |
| ResourceBudget | 调度配置 | 映射为 Hermes max_concurrent_children 等配置 | 中 |

### 高难度 / 不兼容

| 特性 | 问题 | 方案 |
|------|------|------|
| 同步文件 I/O | Hermes 单线程，大型 I/O 阻塞 | 改为异步或委托 terminal |
| LLM 多提供商切换 | Hermes 用 model router 管理 | 整合到 model-router skill |
| 持久化 Agent 状态 | Hermes 无持久化内存 | 使用 fact_store + memory |

## 关键发现
- **Command 类** 与 Hermes tool schema 完全兼容
- **Component 注册机制** 与 Hermes skill 注册方式相同
- **协议管道** (Directive→Command→Message→AfterExecute) 天然适配 Hermes 的 tool + hook 模型
