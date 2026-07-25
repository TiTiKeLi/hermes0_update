# memory_compactor_vibe.py — 架构说明

## 文件
- `/opt/data/scripts/memory_compactor_vibe.py` — cron no_agent 脚本
- `/opt/data/scripts/call_vibe.py` — VibeThinker 调用库（被 import）

## VibeAgent.compress_memory() 接口

```python
agent = VibeAgent()
result = agent.compress_memory(content="...原始内容...", target_chars=1800)
# → {"response": "压缩后内容", "elapsed_s": 4.2, "tokens": 199}
```

## Prompt 模板
```
压缩以下内容到 {target} 字符以内。
保留所有实体名、数字、关系、ID。
去掉自然语言水词（"是...的"、"可以..."、"用于..."，"需要"可省略）。
只输出压缩结果，不解释。
```

## 失败回退链
```
try VibeThinker → 成功则用 → 失败则 truncate()
truncate(): 分离 header + body → body 尾部向前保留最新条目
```

## 已知冲突
`memory-sync.py` 每小时覆盖写 MEMORY.md → compactor 每5分钟压制
