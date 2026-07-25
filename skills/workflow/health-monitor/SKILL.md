---
name: health-monitor
description: 系统健康监控 — 组件级健康检查、趋势追踪、自动恢复触发。周期性检查或故障时自动加载。
category: workflow
platforms: [linux, windows]
related_skills: [error-recovery, network-repair, hermes-optimization]
triggers:
  keywords:
    - 健康检查
    - 系统状态
    - 运行状态
    - 检查一下
    - 还活着吗
    - 心跳
    - 状态检测
    - 系统健康
    - health check
    - system status
    - heartbeat
    - status check
    - component health
    - 一切正常吗
    - 有没有问题
---

# Health Monitor — 系统健康监控 v1

## 核心问题

当前只有 Docker 的容器级健康检查（healthcheck.sh），没有组件级健康视图。
当某个组件（WeChat、Ollama、磁盘）出问题时，无法及时发现。

## 健康检查层级

### L1: 容器级（Docker healthcheck）
```
当前: healthcheck.sh — Gateway 是否运行 + WeChat 是否连接
频率: 每 60s
```

### L2: 组件级（新增）
```
Hermes Gateway:      hermes gateway status  → is running?
Ollama:              curl host.docker.internal:11434/api/tags → 可达?
WeChat iLink:        gateway_state.json → state=connected?
磁盘空间:            df -h /opt/data → 使用率 < 90%?
内存:                free -m → 可用 > 500MB?
进程数:              ps aux | wc -l → 正常范围?
Docker daemon:       docker ps → 可达?
GitHub sync:         git status → 无冲突?
```

### L3: 趋势级（跨时间）
```
磁盘增长趋势:  每小时记录大小，预测满盘时间
内存泄漏:     持续内存增长超过 24h
错误率:       error-recovery 触发的频率趋势
响应延迟:     命令执行时间的趋势变化
```

## 检查命令速查

```powershell
# 一键健康检查
Write-Host "Gateway:"
docker exec hermes sh -c 'hermes gateway status 2>/dev/null || echo "DOWN"'

Write-Host "Ollama:"
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://host.docker.internal:11434/api/tags

Write-Host "WeChat:"
docker exec hermes sh -c 'python3 -c "import json;f=open(\"/opt/data/gateway_state.json\");d=json.load(f);print(d[\"platforms\"].get(\"weixin\",{}).get(\"state\",\"unknown\"))"'

Write-Host "Disk:"
docker exec hermes sh -c 'df -h /opt/data | tail -1'

Write-Host "DB size:"
docker exec hermes sh -c 'ls -lh /opt/data/state.db'
```

## 自动恢复触发

当健康状况低于阈值时，触发对应恢复流程：

| 检测到 | 触发 | 严重级别 |
|-------|------|---------|
| Gateway 不可用 | 重启容器 | 🔴 严重 |
| WeChat 断连 | healthcheck.sh 自动重连 | 🟡 警告 |
| 磁盘 > 90% | 触发 data-retention 清理 | 🟡 警告 |
| Ollama 不可达 | 切换模型（model-router） | 🟠 次要 |
| 内存 < 500MB | 触发 memory-compactor | 🟠 次要 |

## 适用场景

### 入口条件

- 用户询问系统状态
 - 检测到组件可能异常
 - 周期性健康检查触发点
 - 故障恢复后需要验证

### 出口条件

- 所有组件健康 → 报告正常
 - 异常组件已标识并触发恢复
 - 严重异常已升级通知



