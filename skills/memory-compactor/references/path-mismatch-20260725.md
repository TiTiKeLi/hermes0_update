# 记忆压缩路径不匹配 — 诊断记录 (2026-07-25)

## 现象

用户问"记忆压缩为什么没成功"。系统提示显示 MEMORY 1,672/2,200 chars (76%)，但
compactor cron 显示已压缩到 666 chars。

## 诊断

发现系统中有**两个 MEMORY.md 文件**：

| 路径 | 文件大小 | 系统注入？ | 压缩器目标？ |
|------|---------|-----------|------------|
| `/opt/data/MEMORY.md` | 2038 chars | ✅ 系统注入来源 | ❌ 原非目标 |
| `/opt/data/memories/MEMORY.md` | 1489 chars | ❌ 未被系统读 | ✅ 压缩器原目标 |

## 根因

`memory_compactor_vibe.py` 第 10 行写死：
```python
MEMORY_PATH = "/opt/data/memories/MEMORY.md"  # ❌ 错误路径
USER_PATH = "/opt/data/memories/USER.md"      # ❌ 错误路径
```

但 Hermes 系统注入 memory 时读的是 `/opt/data/MEMORY.md` 和 `/opt/data/USER.md`。

## 修复

2026-07-25 将脚本路径改为 `/opt/data/MEMORY.md` 和 `/opt/data/USER.md`。
同时更新 SKILL.md 中的容量限制表、部署配置、pitfalls。

## 防止复发

1. 首次部署 compactor 时，**先确认系统注入 memory 的文件路径**
2. 用 `find /opt/data -name "MEMORY.md"` 检查是否存在多个文件
3. 压缩后查系统提示的 `[N%]` 是否下降，而非只看文件本身
