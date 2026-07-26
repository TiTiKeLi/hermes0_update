---
name: performance-metrics
description: 性能度量 — 跟踪系统响应时间、技能执行效率、记忆压缩率、错误率趋势。提供数据驱动的性能评估视图。
category: workflow
platforms: [linux, windows]
related_skills:
  - health-monitor
  - data-retention
  - capacity_monitor
triggers:
  keywords:
    - 性能
    - 指标
    - 度量
    - 效率
    - 延迟
    - 响应时间
    - 吞吐
    - 瓶颈
    - 性能分析
    - 监控
    - 趋势
---

# Performance Metrics — 性能度量 v1

## 指标

| 指标 | 数据来源 | 采集频率 |
|------|---------|---------|
| 技能触发频次 | skill_trigger_index.py | 每次触发 |
| 记忆压缩率 | capacity_monitor.py | 每次压缩 |
| 磁盘增长趋势 | capacity_monitor.py | 每小时 |
| 错误频率 | hooks/hook_log | 每次错误 |
