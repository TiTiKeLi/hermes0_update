---
name: reasoning-pipeline
description: 结构化推理管道 — 复杂问题按阶段拆解：问题定义→事实收集→假设生成→验证→结论。当问题需要多步深度推理时自动加载。
category: thinking
platforms: [linux, windows]
related_skills:
  - deep-need-analysis
  - model-router
  - verification-before-completion
  - meta-orchestrator
triggers:
  keywords:
    - 推理
    - 推导
    - 逻辑
    - 分析
    - 论证
    - 归因
    - 因果
    - 为什么
    - 怎么做到的
    - 根本原因
    - 深层原因
    - 影响分析
    - 推演
    - 如果...会怎样
    - 假设
    - 前提
    - reasoning
    - inference
    - logic
    - root cause
    - impact analysis
    - what if
---

# Reasoning Pipeline — 结构化推理管道 v1

## 核心问题

复杂问题（故障排查、影响分析、决策推演）需要多步结构化推理。
直接给出结论会遗漏中间步骤，无法追溯推理过程。

## 推理阶段

### Stage 1: 问题定义
```
□ 问题是什么？（一句话）
□ 发生在哪里？（系统/组件/模块）
□ 什么时候开始的？（时间点/版本）
□ 影响到谁？（功能/用户/数据）
□ 输入: 原始问题描述
□ 输出: 清晰的问题陈述
```

### Stage 2: 事实收集
```
□ 相关的系统状态（health-monitor 输出）
□ 最近的变更（git log 最近 5 条）
□ 错误日志（相关时间段的日志）
□ 现有知识（MEMORY.md / skills / CONTEXT.md）
□ 输入: 问题陈述
□ 输出: 事实清单
```

### Stage 3: 假设生成
```
□ 列出所有可能的根因（至少 3 个）
□ 每个假设标注: 可能性(高/中/低) + 依据 + 可验证的预测
□ 输入: 事实清单
□ 输出: 假设列表
```

### Stage 4: 验证
```
□ 对每个假设设计验证步骤
□ 按可能性从高到低执行验证
□ 每一步记录: 验证方法 + 结果 + 是否支持假设
□ 输入: 假设列表
□ 输出: 验证结果（哪些假设被证实/证伪）
```

### Stage 5: 结论
```
□ 被证实的根因（如果没有，输出"未确定"）
□ 修复建议（具体可执行）
□ 预防措施（避免再次发生）
□ 未解决的问题（需要进一步调查）
□ 输入: 验证结果
□ 输出: 完整推理报告
```

## 推理报告格式

```yaml
reasoning_report:
  problem: "Hermes 容器无法访问 OpenAI API"
  defined_at: "2026-07-25T23:00:00"
  
  facts:
    - "百度可访问，DeepSeek 可访问"
    - "NO_PROXY=* 在基础镜像中设置"
    - "Docker Desktop 引擎代理已启用"
  
  hypotheses:
    - h1: "NO_PROXY=* 阻塞代理"
      likelihood: "high"
      evidence: "docker exec 测试: unset NO_PROXY → OpenAI 421"
      status: "confirmed ✅"
    
    - h2: "Docker Desktop 代理挂了"
      likelihood: "low"
      evidence: "http.docker.internal:3128 REFUSED"
      status: "partially confirmed"
  
  conclusion: "NO_PROXY=* 是元凶，已在 entrypoint 中 unset"
  fix: "entrypoint sh -c 中添加 unset NO_PROXY no_proxy"
```

## 适用场景

### 入口条件
- 问题需要多步推理才能解决
- 存在多个可能的根因需要排除
- 决策需要完整的推理链条
- 故障/异常需要根因分析

### 出口条件
- 推理报告已完成（含结论或"未确定"）
- 如果根因确定 → 同时输出修复建议
- 如果未确定 → 输出需要补充的信息
