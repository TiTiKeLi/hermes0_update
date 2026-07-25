# Sync vs Compactor 冲突压制策略（2026-07-24）

## 冲突描述

两个 cron 同时操作 MEMORY.md：

| cron | 文件 | 频率 | 行为 |
|------|------|------|------|
| hierarchical-memory-sync | memory-sync.py | 每小时 | 从 fact_store 写回 MEMORY.md（膨胀） |
| memory-compactor | memory_compactor_vibe.py | 每5分钟 | VibeThinker 清洗 + 截断（压制） |

sync 写入后，MEMORY.md 膨胀到 2000+ chars。5 分钟后 compactor 将其压回 1600-1800 chars。

## 当前策略

**频率压制**——compactor 频率（5min）远高于 sync 频率（1h），压缩可以压住膨胀。

代价：sync 的细粒度条目（fact_store 中的低优先级事实）会在 compactor 截断中被丢弃。

## 数据点

```
10:00  sync 跑 → MEMORY 1884 chars (94%)
10:05  compactor 跑 → 1062 chars (53%) [3B] ✅
10:10  compactor 跑 → 不动（已在阈值下）
10:15  compactor 跑 → 不动
```

## 可选改造方向

1. **单路径写入**：让 memory-sync.py 只写一个路径（memories/），避免双路径覆盖
2. **时间戳协作**：compactor 压缩后写时间戳标记，sync 检测后跳过同一轮
3. **同步触发压制**：sync 写完后立即触发一次 compactor 而非等 5 分钟
4. **合入同一脚本**：sync 脚本末尾调用 compress 函数，减少冲突窗口
