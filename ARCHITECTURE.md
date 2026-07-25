# Hermes 架构总览 (Architecture)

> Hermes 技能/工具/插件的完整架构蓝图。
> 每个模块的职责、边界、依赖、缺口都在这里记录。

---

## 一、架构层次

```
┌─────────────────────────────────────────────────────┐
│  L8: Meta     系统维护、技能治理、自我升级           │
├─────────────────────────────────────────────────────┤
│  L7: Behavior  沟通风格、反馈协议、模型适配          │
├─────────────────────────────────────────────────────┤
│  L6: Security  下载安全、数据审计、网络防御          │
├─────────────────────────────────────────────────────┤
│  L5: Workflow  任务执行、外部集成、验证闭环          │
├─────────────────────────────────────────────────────┤
│  L4: Memory    记忆分层、压缩、同步、检索            │
├─────────────────────────────────────────────────────┤
│  L3: Thinking  需求分析、模型路由、深度推理          │
├─────────────────────────────────────────────────────┤
│  L2: Governance 权限规则、审批流、工具治理            │
├─────────────────────────────────────────────────────┤
│  L1: Identity  身份/SOUL、记忆/MEMORY、用户/USER    │
├─────────────────────────────────────────────────────┤
│  L0: Infra     Docker 容器、网络、持久化、密钥管理    │
└─────────────────────────────────────────────────────┘
```

---

## 二、各层现状与缺口

### L0: 基础设施层 — 完成度 80%

| 组件 | 状态 | 文档 |
|------|------|------|
| Docker 容器编排 | ✅ | docker-compose.yml |
| 网络配置 | ✅ | CONTEXT.md, network-repair.ps1 |
| DNS 兜底 | ✅ | daemon.json |
| 数据持久化 | ✅ | bind mount |
| 密钥管理 | ⚠️ 仅 .env | 无密钥轮换机制 |
| 备份策略 | ⚠️ 手动 | 无自动备份 |

### L1: 身份与记忆层 — 完成度 90%

| 组件 | 状态 | 文档 |
|------|------|------|
| AI 人格定义 | ✅ | SOUL.md |
| 事实记忆 | ✅ | MEMORY.md |
| 用户画像 | ✅ | USER.md |
| 项目上下文 | ✅ | CONTEXT.md |
| 架构总览 | ✅ | **ARCHITECTURE.md ← 本文件** |

### L2: 治理层 — 完成度 70%

| 组件 | 状态 | 文档 |
|------|------|------|
| 授权协议 | ✅ | Authorization skill |
| 工具治理 v1 | ✅ | tool-governance |
| 工具治理 v2 | ✅ | tool-governance-v2 |
| 审批流 | ⚠️ 基础 | config.yaml approvals |
| 策略冲突检测 | ❌ 缺口 | **需创建: policy-audit** |

### L3: 思维层 — 完成度 65%

| 组件 | 状态 | 文档 |
|------|------|------|
| 深度需求分析 | ✅ | deep-need-analysis |
| 模型路由 | ✅ | model-router |
| 第一性原理 | ✅ | FirstPrinciples |
| 增强思考 | 外部 skill | EnhancedThinking |
| 结构化推理管道 | ❌ 缺口 | **需创建: reasoning-pipeline** |

### L4: 记忆层 — 完成度 70%

| 组件 | 状态 | 文档 |
|------|------|------|
| 记忆分层同步 | ✅ | hierarchical-memory-sync |
| 记忆压缩 | ✅ | memory-compactor |
| 记忆写入反馈 | ✅ | memory-confirmation-feedback |
| 记忆架构 | ✅ | agent-memory-architecture |
| 记忆检索策略 | ❌ 缺口 | **需创建: memory-retrieval** |
| 遗忘策略 | ❌ 缺口 | **需创建: memory-forgetting** |

### L5: 工作流层 — 完成度 75%

| 组件 | 状态 | 文档 |
|------|------|------|
| 元编排 | ✅ | meta-orchestrator |
| 自迭代 | ✅ | autogpt-self-improve |
| 外部适配 | ✅ | external-adaptor |
| 功能拆解 | ✅ | functional-decomp |
| 架构拆解 | ✅ | arch-decomp |
| 接口拆解 | ✅ | interface-decomp |
| 数据流拆解 | ✅ | dataflow-decomp |
| GitHub 发现 | ✅ | github-discover |
| 验证前置 | ✅ | verification-before-completion |
| 并行代理 | ✅ | dispatching-parallel-agents |
| 版本管理 | ✅ | git-version-control |
| 配置统筹 | ✅ | config-unification |
| 错误恢复 | ✅ | error-recovery** |
| 任务优先级 | ✅ | task-prioritization** |
| 健康监控 | ✅ | health-monitor** |

### L6: 安全层 — 完成度 60%

| 组件 | 状态 | 文档 |
|------|------|------|
| 安全下载 | ✅ | secure-download |
| 下载门卫 | ✅ | download-gate |
| 数据审计 | ✅ | data-security-audit |
| 网络安全 | ✅ | network-repair.ps1 |
| Gitleaks 集成 | ✅ | git-version-control |
| 数据保留策略 | ❌ 缺口 | **需创建: data-retention** |
| 隐私合规 | ❌ 缺口 | **需创建: privacy-policy** |

### L7: 行为层 — 完成度 60%

| 组件 | 状态 | 文档 |
|------|------|------|
| 小模型模式 | ✅ | caveman, caveman-compress |
| 记忆反馈 | ✅ | memory-confirmation-feedback |
| 用户偏好学习 | ❌ 缺口 | **需创建: preference-learning** |
| 跨会话连续性 | ❌ 缺口 | **需创建: session-continuity** |

### L8: 元层 — 完成度 50%

| 组件 | 状态 | 文档 |
|------|------|------|
| 技能创建规则 | ✅ | skill-creation-rules |
| 系统完整性 | 外部 skill | System |
| PAI 升级 | 外部 skill | PAIUpgrade |
| 性能度量 | ❌ 缺口 | **需创建: performance-metrics** |
| 依赖管理 | ❌ 缺口 | **需创建: dependency-graph** |

---

## 三、缺口优先级

### P0: 必须立即创建

| 缺口 | 原因 | 估计工作量 |
|------|------|-----------|
| error-recovery | 所有技能执行都可能失败，没有兜底 | 中 (1 skill) |
| task-prioritization | 多任务无排序依据 | 中 (1 skill) |
| health-monitor | 系统无整体健康视图 | 大 (1 skill + 1 script) |

### P1: 本周内创建

| 缺口 | 原因 | 估计工作量 |
|------|------|-----------|
| data-retention | 日志/会话无限增长 | 小 (1 skill) |
| reasoning-pipeline | 复杂问题缺乏结构化路径 | 中 (1 skill) |
| preference-learning | 用户画像不进化 | 中 (1 skill) |

### P2: 本月内创建

| 缺口 | 原因 | 估计工作量 |
|------|------|-----------|
| memory-retrieval | 记忆检索无策略 | 中 (1 skill) |
| memory-forgetting | 无遗忘机制 | 小 (1 skill) |
| session-continuity | 每次会话从零开始 | 大 (1 skill) |
| dependency-graph | 技能依赖混乱 | 中 (1 skill) |
| policy-audit | 策略冲突不可检测 | 中 (1 skill) |

---

## 四、当前子 Agent 规划

为了验证本架构规划的完整性，我需要多个子 Agent 分别审核不同层面：

| 子 Agent | 审核层 | 验证内容 |
|---------|--------|---------|
| infra-agent | L0 | Docker/网络/备份完整性 |
| identity-agent | L1-L2 | 身份/治理覆盖度 |
| cognitive-agent | L3-L4 | 思维/记忆完整性 |
| execution-agent | L5 | 工作流闭环 |
| security-agent | L6 | 安全覆盖度 |
| meta-agent | L7-L8 | 行为/元层完整性 |

每个子 Agent 检查: 当前层是否有未标识的缺口？依赖是否正确？

