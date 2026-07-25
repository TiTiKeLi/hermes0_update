# AutoGPT 功能拆解报告
来源: github.com/Significant-Gravitas/AutoGPT
版本: 最新 master (classic/forge 架构)

## 核心架构体系

AutoGPT 分为两代架构 + 平台层：

### 1. Forge 组件化架构 (classic/forge/) ★ 核心焦点
新一代可插拔架构，基于组件 + Agent 协议

### 2. 原始 AutoGPT (classic/original_autogpt/)
成熟稳定版本

### 3. SaaS 平台 (autogpt_platform/)
云平台版本 (backend FastAPI + frontend Next.js)

---

## Forge 核心模块

| 模块 | 文件 | 职责 | 核心程度 |
|------|------|------|---------|
| Agent 基类 | forge/agent/base.py | BaseAgent 抽象类，定义 propose_action/execute/do_not_execute | ⭐⭐⭐ 核心 |
| ForgeAgent | forge/agent/forge_agent.py | 完整实现，预装 10 内置组件 | ⭐⭐⭐ 核心 |
| 组件系统 | forge/agent/components.py | AgentComponent 基类 + ConfigurableComponent | ⭐⭐⭐ 核心 |
| 协议接口 | forge/agent/protocols.py | 6 大协议接口 (Directive/Command/MessageProvider 等) | ⭐⭐⭐ 核心 |
| 执行上下文 | forge/agent/execution_context.py | 子代理管理 (ResourceBudget: max_depth=5, max_children=25) | ⭐⭐ 重要 |
| 命令系统 | forge/command/ | 命令注册 + 执行体系 | ⭐⭐⭐ 核心 |
| LLM 层 | forge/llm/ | 多提供商抽象 (OpenAI, Anthropic 等) | ⭐⭐ 重要 |
| 文件存储 | forge/file_storage/ | 多后端文件存储 | ⭐ 辅助 |
| Agent 协议 | forge/agent_protocol/ | REST API 协议层 | ⭐⭐ 重要 |

## 核心数据流

```
用户输入 → BaseAgent.propose_action()
         → LLM 调用 (选 command)
         → BaseAgent.execute() 
         → CommandProvider 查找命令
         → 执行命令
         → AfterExecute 钩子
         → 结果回 LLM → 下一轮
```

## ForgeAgent 内置组件
10 个预装组件，通过 component registry 热插拔

## Command 系统
Command 类 ≈ Hermes tool 定义，几乎 1:1 映射
- name: str
- description: str  
- arguments: JSON schema
- function: callable
