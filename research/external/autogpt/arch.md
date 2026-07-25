# AutoGPT 架构拆解报告

## 架构模式
**Component-Pipeline (组件管道) + FastAPI REST 混合架构**
本质上是由协议端点驱动的 Agent 框架。

## 模块调用链（自上而下）

```
app.py
  → ForgeAgent (多重继承: ProtocolAgent + BaseAgent)
    → BaseAgent.run_pipeline() 遍历组件, 按协议分派
      → AgentComponent 子类 (SystemComponent, TodoComponent 等 14+ 组件)
        → @command 装饰的命令 (finish, archive, clipboard 等)
          → Command 对象 + 实际函数调用
    → ProtocolAgent CRUD → AgentDB (SQLAlchemy) + FileStorage
```

## 控制流核心 — run_pipeline()
- 接收一个"协议方法"(如 DirectiveProvider.get_resources)
- 遍历已拓扑排序的 self.components[]
- 只调用实现了该协议的组件
- 组件级重试 (ComponentEndpointError) + 管道级重试 (EndpointPipelineError)
- 参数快照回滚机制

## 扩展机制
- **命令**: `@command` 装饰器注册新命令
- **组件**: `AgentComponent` 子类注册新组件，`_run_after` 声明排序依赖
- **配置**: `UserConfigurable` 自动从环境变量加载
- **子代理**: `ExecutionContext` + `ResourceBudget` + `AgentFactory` 协议

## Hermes 适配方案
| 方式 | 源组件 | Hermes 映射 | 难度 |
|------|--------|-------------|------|
| A | `@command` 方法 | 独立 Hermes tool，用 tool-governance-v2 registry 注册 | 低 |
| B | `run_pipeline` 管道 | Hermes skill 内的步骤编排 | 中 |
| C | `ExecutionContext` 子代理管理 | tool-governance post_execute hook | 中 |

## 无循环依赖 ✅
整个架构依赖关系清晰单向。
