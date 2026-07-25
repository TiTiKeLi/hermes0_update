---
name: data-retention
description: 数据保留策略 — 日志/会话/缓存/数据库的自动清理规则、保留期限、归档策略。当磁盘空间不足或定期维护时自动加载。
category: workflow
platforms: [linux, windows]
related_skills:
  - health-monitor
  - memory-compactor
  - git-version-control
  - error-recovery
triggers:
  keywords:
    - 磁盘满
    - 磁盘空间
    - 空间不足
    - 清理
    - 没空间了
    - 数据清理
    - 存储清理
    - 日志清理
    - 清理一下
    - disk full
    - cleanup
    - storage
    - purge
    - retention
    - 清理旧数据
    - 释放空间
    - 太满了
  tools:
    - terminal
---

# Data Retention — 数据保留策略 v1

## 核心问题

Hermes 运行时产生大量数据，且无限增长：
- state.db: 58MB → 持续增长（对话状态）
- memory_store.db: 600KB → 持续增长（记忆）
- agent.log: 3.8MB → 无上限（应用日志）
- sessions/: 164 个文件 → 每次会话新增
- cron/output/: 每分钟生成运行记录
- incoming/: 4392 个文件 → 请求转储无限堆积

没有自动清理机制 → 最终磁盘耗尽 → 系统崩溃。

## 保留策略矩阵

| 数据类型 | 保留期限 | 清理后操作 | 优先级 |
|---------|---------|-----------|-------|
| agent.log, errors.log | 保留最近 7 天 | 删除超期日志 | P0 |
| cron/output/ | 保留最近 3 天 | 删除超期输出 | P0 |
| sessions/*.json | 保留最近 30 天 | 归档为 summaries（可选），删除原文件 | P1 |
| request_dump_* | 保留最近 7 天 | 直接删除 | P1 |
| .jsonl （旧版） | 保留最近 14 天 | 直接删除 | P1 |
| state.db | 保留最近 90 天的状态 | VACUUM 缩小文件 | P2 |
| memory_store.db | 由 memory-compactor 管理 | 不在此处理 | - |
| incoming/ | 保留最近 7 天 | 删除超期文件 | P1 |
| backups/ | 保留最近 3 个版本 | 删除最旧备份 | P2 |

## 执行策略

### 自动触发条件
- `health-monitor` 报告磁盘使用率 > 80% → 触发 P0 清理
- `health-monitor` 报告磁盘使用率 > 90% → 触发 P0+P1 清理
- 每周日凌晨 3:00 → 全量清理
- 用户说"清理一下" → 全量清理

### 清理命令模板

```bash
# P0: 清理超期日志（保留 7 天）
find /opt/data/logs -name "*.log*" -mtime +7 -delete 2>/dev/null
find /opt/data -maxdepth 1 -name "*.log" -mtime +7 -delete 2>/dev/null

# P0: 清理 cron 输出（保留 3 天）
find /opt/data/cron/output -type f -mtime +3 -delete 2>/dev/null

# P1: 清理 request_dump（保留 7 天）
find /opt/data -maxdepth 1 -name "request_dump_*" -type f -mtime +7 -delete 2>/dev/null

# P1: 清理旧 sessions（保留 30 天）
find /opt/data/sessions -name "*.json" -mtime +30 -delete 2>/dev/null

# P2: 数据库 VACUUM（缩小文件）
sqlite3 /opt/data/state.db "VACUUM;"
sqlite3 /opt/data/memory_store.db "VACUUM;"
```

### 安全保护

```
□ 不删除最后 3 天的 logs/（保留最近的运行记录用于排查）
□ 不删除 backups/ 的最后 3 个版本
□ 不操作 memory_store.db（由 memory-compactor 管理）
□ 每次清理前检查磁盘使用率，避免清理本身产生大量 I/O
```

## 适用场景

### 入口条件

- 磁盘使用率超过 80%
 - 每周定时维护触发
 - 用户要求清理
 - 日志文件大小超过阈值

### 出口条件

- 磁盘使用率低于 70%
 - 超期数据已清理
 - 清理日志已记录
 - 保留期限内的数据不受影响



