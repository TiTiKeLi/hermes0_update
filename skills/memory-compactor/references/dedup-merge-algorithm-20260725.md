# 去重合并算法修复记录 (2026-07-25)

## 根因

`memory_compactor_v2.py` 的 `extract_oldest()` 从文件**尾部**提取条目，
但新写入的条目总是追加到尾部 → 归档了新数据，留下了老的重复副本。
结果是 `MEMORY.md` 始终 89% 降不下来。

## 修复方案

### 两阶段策略

**Phase 1 — 按 id 去重合并**

1. 用两条正则分别解析两种格式：
   - `id:N [tag] content` → `ID_PATTERN = r'^id:(\d+)\s+\[([^\]]+)\]\s*(.*)'`
   - `- 描述 (id:N [tag])` → `LINE_PATTERN = r'^-\s+(.*)\(id:(\d+)\s+\[([^\]]+)\]\)'`
2. 相同 id:N 的条目分为一组
3. 每组保留 content 最长（最完整）的版本
4. 移除非最佳版本

⚠️ 必须用 `[^\]]+` 而非 `\w+` 匹配 tag，因为 `audio-vector-system`、`memory-confirmation-feedback` 等标签含连字符。

**Phase 2 — 按语义价值归档**（Phase 1 仍超限时）

1. `preference` → 优先级 1（最先归档）
2. `profile` → 优先级 5
3. 其他 → 优先级 10
4. identity 键永不归档（host/ollama/model/interface/lang）

### 关键数字

- 触发阈值：MEMORY > 1700B (85%)
- 去重成功率：14 条重复 → 1779B → 1203B (89% → 60%)
- 脚本运行时间：< 0.1s
- 每次最多归档 8 条

### 验证方法

```bash
cd /opt/data && python3 /opt/data/scripts/memory_compactor_v2.py
# 预期输出: MEMORY: 1779B→1203B (60%) 去重 14 条
```

输出示例：
```
⚠️  触发: MEMORY 89% > 85%
  MEMORY: 1779B→1203B (60%) 去重 14 条
  USER: 870B (63%) 正常，跳过
  ⏱ 0.03s
```
