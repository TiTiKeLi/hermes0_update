# Compactor ↔ Sync 冲突修复

## 问题

- `memory_compactor_vibe.py` (cron, 每5分钟): 压缩 MEMORY.md 到 ≤ 2000 chars
- `memory-sync.py` (cron, 每小时): 从 fact_store 写回 MEMORY.md，导致膨胀
- 结果：压缩后 sync 又写回膨胀数据 → 用户感觉 "压缩没效果"

## 修复位置

修改 `/opt/data/scripts/memory-sync.py`，在写入 MEMORY.md 之前加时间戳检测：

### 具体改动

在 `sync_memory()` 函数中，写入文件前插入：

```python
import os, time

def _was_recently_compressed(path: str, window_seconds: int = 600) -> bool:
    """Check if file was modified within the window (compactor runs every 5min)."""
    if not os.path.exists(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < window_seconds

# 在写入 MEMORY.md 前：
if _was_recently_compressed(MEMORY_PATH):
    print(f"⏭️  跳过 MEMORY.md 写回：{os.path.getmtime(MEMORY_PATH):.0f}s 内被修改过（compactor 刚写）")
    # 跳过当前周期的文件写回
    skip_memory_write = True
```

### 替代方案

Compactor 侧写标记文件 `/tmp/.memory-last-compacted`，sync 检测该文件存在（<10min）则跳过。

## 验证

1. 修改后重启 cron（或等下次 sync 自动触发）
2. 确认 compactor 日志继续产生（`/opt/data/cron/output/84030ebfc20b/`）
3. 观察 sync 日志（`/opt/data/cron/output/a351c7f9e890/`）出现 "⏭️ 跳过" 字样
4. 检查 MEMORY.md 在 1 小时后未被重新膨胀

## 回退

如果出现异常（如事实长期不同步），删除该检测逻辑即可：
```bash
# 在 memory-sync.py 中注释掉 _was_recently_compressed 调用
# 或直接删除这段代码
```
