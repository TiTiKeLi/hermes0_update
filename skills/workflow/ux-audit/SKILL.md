---
name: ux-audit
description: UX 审计 — 定义用户体验预期、逐项审计功能覆盖、打分追踪、差距分级。每个项目的 P0/P1/P5 阶段自动加载。
category: workflow
platforms: [linux, windows]
related_skills:
  - project-lifecycle
  - verification-before-completion
  - quality-gates
triggers:
  keywords:
    - 用户体验
    - UX
    - 用户预期
    - 体验评估
    - UX审计
    - 功能审计
    - 界面评估
    - 交互评估
    - user experience
    - UX audit
    - experience review
    - 用户反馈
    - 体验打分
    - UX评分
    - 可用性
    - usability
    - 体验差距
    - UX gap
    - 用户测试
    - 体验测试
    - 对照参考
    - 标杆对比
---

# UX Audit — 用户体验审计 v1

## 核心问题

功能实现了但用户说"不好用"。因为没有 UX 预期基准，实现者和用户对"好用"的定义不一致。
UX 预期必须量化、文档化、可审计。

## UX Scorecard 模板

### 评分维度（每个 1-5 分）

| 维度 | 5分定义 | 权重 |
|------|--------|------|
| 响应速度 | 操作 200ms 内反馈 | 20% |
| 视觉一致性 | 配色/字体/间距全系统统一 | 15% |
| 错误处理 | 错误信息清晰、有恢复路径 | 15% |
| 空状态 | 无数据时有引导 | 10% |
| 加载状态 | 等待时有进度指示 | 10% |
| 操作路径 | 核心任务 ≤3 步完成 | 15% |
| 无障碍 | 键盘导航完整 | 5% |
| 移动适配 | 手机/平板正常使用 | 10% |

### 审计流程

```
Step 1: 加载 UX Scorecard（从项目文档或技能默认）
Step 2: 逐功能对照 Scorecard 的每个维度
Step 3: 记录每个功能在每个维度的得分
Step 4: 计算加权总分
Step 5: 生成 UX 差距报告
```

### 审计报告格式

```yaml
ux_audit_report:
  project: "Hermes GUI"
  date: "2026-07-26"
  
  total_score: 68/100
  target_score: 85/100 (从 UX 预期设定)
  
  gaps:
    - feature: "会话列表"
      severity: "P0"
      dimension: "响应速度"
      current: "2/5 — 需要手动刷新"
      target: "5/5 — 实时更新"
      
    - feature: "设置面板"
      severity: "P1"
      dimension: "视觉一致性"
      current: "3/5 — 字体大小不统一"
      target: "5/5 — 全系统统一"
  
  top_3_priorities:
    - "修复会话列表实时更新 (P0, 影响最大)"
    - "统一设置面板字体 (P1, 视觉最明显)"
    - "添加空状态引导 (P1, 新用户第一印象)"
```

## 适用场景

### 入口条件
- 项目启动时需要设定 UX 基准
- 功能开发完成后需要验证
- 用户反馈"不好用"时需要定位问题
- 版本迭代时需要追踪 UX 改进

### 出口条件
- UX Scorecard 已创建并打分
- 差距报告已生成
- 差距已按 P0-P3 分级
- 改进优先级已确定
