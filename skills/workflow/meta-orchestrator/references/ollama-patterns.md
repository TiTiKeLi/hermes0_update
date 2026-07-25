# Ollama 调用模式参考

## 环境
- Ollama 地址: `host.docker.internal:11434`
- 默认模型: `VibeThinker-3B:latest`
- 容器内访问: Docker Desktop DNS 直连

## 已知问题

### 连接不稳定
- 宿主休眠/繁忙时，Ollama API 无响应（curl 超时）
- TCP `/dev/tcp/host.docker.internal 11434` 也会超时
- `--connect-timeout 3 --max-time 5` 是必要的保护参数
- 不要假设 Ollama 总是可用——**必须在 Step 0 检测并缓存结果**

### 检测方法
```bash
# 正确的检测（独立 terminal 调用）
terminal("curl -s --connect-timeout 3 --max-time 5 http://host.docker.internal:11434/api/tags")

# 错误做法：与其它命令 && 拼接
# terminal("echo check && curl ...")  ← 这会超时
```

### Fallback 策略
当 Ollama 不可用时：
- 规划框架：手动构造 JSON（参考 Agent.md 的 capabilities）
- 子任务执行：本地 `read_file` + Python 数据分析 或 `delegate_task`（走 Hermes 模型而非 Ollama）
- 评分：手动评分（`agent_registry.py score` + 人工给出三维评分 JSON）
- 汇总：手动构造 Markdown 报告，拼接所有子任务结果

### 脚本注意事项
- `scripts/eval_aggregate.py` 内置 Ollama 检测（`ollama_available()` 函数），**Ollama 不可用时该脚本会 hang 超时**（curl --connect-timeout 2 仍然无效）
- 此脚本的自动评分模式（fallback branch）逻辑可靠，但入口检测有缺陷
- ✅ 推荐做法：手动评分 `/opt/data/scripts/agent_registry.py score <agent> "<task>" '<{"completeness":X,"accuracy":Y,"relevance":Z}>' ""`

## 调用示例

### generate (非流式)
```bash
curl -s http://host.docker.internal:11434/api/generate \
  -d '{"model":"VibeThinker-3B:latest","prompt":"你好","stream":false}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['response'])"
```

### 强制 JSON 输出
在 prompt 中明确指定 "输出必须是严格的JSON格式" 以提高解析成功率。
