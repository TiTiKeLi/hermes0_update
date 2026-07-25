---
name: model-router
description: >
  Intelligently route complex tasks to DeepSeek v4 Flash via OpenRouter,
  keep simple tasks on the local VibeThinker-3B model.
category: system
conditions:
  requires_toolsets:
    - terminal
platforms: [linux]
related_skills: [github-discover, skill-creation-rules]
triggers:
  keywords:
    - 模型选择
    - 路由模型
    - 切换模型
    - 用哪个模型
    - model router
    - model select
    - 选择模型
    - 模型切换
    - 模型路由
    - 任务分级
    - 模型分配
---

# Model Router

Automatically detect task complexity and use the optimal model for each task.

## Model Configuration

| Model | Provider | Use Case |
|-------|----------|----------|
| `deepseek-chat` | DeepSeek API | Default model — chat, simple Q&A, daily conversation, multi-step tasks |
| `deepseek-reasoner` | DeepSeek API | Complex reasoning, architecture decisions, deep analysis |
| `VibeThinker-3B:latest` | Custom (Ollama local, fallback) | Local-only mode, offline operation, fallback when DeepSeek unavailable |

## Complex Task Detection

A task is considered **complex** if it involves any of:

1. **Configuration changes** — modifying config.yaml, .env, docker-compose.yml
2. **Verification** — testing whether a previous operation succeeded
3. **Multi-step operations** — 3 or more sequential steps with dependencies
4. **Debugging** — diagnosing errors, reading logs, root cause analysis
5. **Code generation** — writing functions, scripts, or complex logic
6. **Data analysis** — examining data structures, querying databases
7. **Architecture decisions** — choosing between multiple approaches

A task is **simple** (stay on VibeThinker-3B) if:

1. Single-turn Q&A
2. Status checks (`docker ps`, `hermes status`)
3. Confirmation or acknowledgment
4. Casual conversation

## Model Switching Protocol

### Method 1: Config Switch (was the old preferred method; current default is deepseek-chat)

```bash
# The system default is now deepseek-chat (set in config.yaml)
# Only switch from the default when you need a different model
hermes config set model deepseek-reasoner
# ... do complex reasoning ...
hermes config set model deepseek-chat
```

### Method 2: Delegation (for isolated complex sub-tasks)

```bash
# Spawn a sub-agent with the complex model
hermes chat -m deepseek-chat -z "complex task description"
```

### Method 3: One-shot (for quick complex queries)

```bash
hermes -m deepseek-chat -z "complex question"
```

## Memory Recall Protocol

**IMPORTANT: When the user asks about personal information, preferences, projects, codes, or anything that sounds like a recall question, you MUST use memory tools FIRST before answering.**

### Check Built-in Memory (always available)

Use the `memory` tool with `target="user"` to read USER.md, or `target="agent"` for MEMORY.md:

```
memory(action="read", target="user")
```

USER.md contains: user profile, preferences, project context, communication style.
MEMORY.md contains: system notes, operational knowledge, learned patterns.

### Check Holographic Memory (for structured facts)

If the built-in memory doesn't have the answer, use fact_store search:

```
fact_store(action="search", query="<key terms>")
```

### Rules

1. **ALWAYS** check memory first when asked about the user or past information
2. Do NOT guess user-specific information — use the memory tools
3. After finding the answer, confirm with the user before acting on it
4. If memory search returns no results, tell the user it wasn't found

## Rules

1. Document which model was used in the session
2. If OpenRouter / DeepSeek API is unavailable, fall back to VibeThinker-3B via Ollama
3. Never switch models mid-response — complete the current response first
4. **The default model is `deepseek-chat`** (set in config.yaml). Do NOT auto-switch back to VibeThinker-3B after tasks unless the user explicitly asks.

## Verify Model Availability

```bash
curl -s https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  | python3 -c "import sys,json; data=json.load(sys.stdin); print([m['id'] for m in data.get('data',[]) if 'deepseek' in m['id']])"
```

---

## VibeThinker-3B 能力天花板（实证结论）

| 能做什么 | 不能做什么 |
|----------|-----------|
| ✅ 消息分类（chat/task/research） | ❌ **结构化数据压缩** — 4523→43 chars，丢失全部 |
| ✅ 日志分级（fatal/error/warn/info） | ❌ 代码生成 |
| ✅ 单行摘要（10-20 字） | ❌ 多步推理 |
| ✅ 模板填充（变量替换） | ❌ 架构决策 |
| ✅ YES/NO 二元判断 | ❌ 数字计算 |
| ✅ 关键词提取 | ❌ 事实性问答（3B 可能胡编） |

**关键教训 2026-07-24**：试图让 3B 压缩 MEMORY.md（结构化文档，含 ID/实体/关系/标记），
3B 只输出 43 字符就停了。结构化数据压缩必须用确定性算法，不能依赖小模型。

---

## Sub-Agent Architecture: VibeThinker-3B as Routine Worker

### Role Split

```
你 (DeepSeek v4)                       3B Sub-Agent (VibeThinker-3B)
├─ 复杂推理/架构决策                    ├─ 分类/标记/判断
├─ 需求拆解/本质分析                    ├─ 格式化/转换/填充模板
├─ 代码生成/多步操作                    ├─ 摘要/压缩/过滤
├─ 工具编排/技能落地                    ├─ 状态检查/心跳报告
└─ 用户交互/反馈                       └─ 简单提取/去重
```

**核心原则**：3B 不做需要联网、多步推理、架构决策的事。3B 做的事可以每秒调，不心疼 token。

### Calling Protocol

```python
# 通用调用函数 — 存为 /opt/data/scripts/call_vibe.py
import urllib.request, json

def call_vibe(prompt, system="", max_tokens=512, temp=0.1):
    """调用 VibeThinker-3B 并返回响应文本。
    
    Args:
        prompt: 输入提示
        system: 系统指令（默认：简洁中文输出）
        max_tokens: 最大生成token数
        temp: 温度（routine任务用0.1，分类任务用0.0）
    Returns:
        str: 模型响应，去除前后空白
    """
    payload = json.dumps({
        "model": "VibeThinker-3B:latest",
        "prompt": prompt,
        "system": system or "你是Hermes子Agent，中文回复，只输出结果不输出思考过程",
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temp,
            "stop": ["\n\n\n"]
        }
    }).encode()
    req = urllib.request.Request(
        "http://host.docker.internal:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["response"].strip()
```

**端点**：`http://host.docker.internal:11434/api/generate`（Ollama 标准 API）
**温度推荐**：分类/提取 → 0.0 | 摘要/填充 → 0.1 | 创意模板 → 0.3

---

## Sub-Agent Job Catalog

### Job 1: 心跳健康摘要 (Heartbeat Summary)

**触发**：cron 每 15 分钟 | **输入**：healthcheck.log + memory 水位 + cron 状态
**输出**：一行摘要，只有状态变化才通知用户

```
输入:
  MEMORY: 62% (1380/2200)
  crons: memory-compactor ✅, memory-sync ✅
  网络: ❌ api.github.com 超时
输出:
  状态: ✅ 容器存活 | ❌ 网络不通 | MEMORY 62% | cron 2个运行
  建议: 网络仍不通，需人工重启
```

### Job 2: 日志分类器 (Log Classifier)

**触发**：delegate_task 按需 | **输入**：50 行原始日志
**输出**：按严重级别归类的计数 + 异常摘要

```
输入: 50 lines of mixed log
输出:
  致命: 0
  错误: 2 (connection reset by peer ×2)
  警告: 5 (memory approaching limit)
  信息: 43 (routine heartbeat)
```

### Job 3: ~~Memory 压缩助手~~ ❌ 已废弃

**2026-07-24 实证**：VibeThinker-3B 无法做结构化记忆压缩。
4523 字符的 MEMORY.md 交给 3B 压缩到 1800，输出只有 43 字符。

**替代方案**：由 `memory-compactor` skill 使用确定性截断算法
（头部保留 + 尾部优先 + 按行截断不断行），cron 每 5 分钟跑一次。

3B 在此角色中的正确定位：**不做压缩，只做压缩后的简单摘要行**。
即：`memory-compactor` 确定了压缩结果后，3B 可以对其输出一行摘要。

### Job 4: 消息预分类 (Message Pre-classifier)

**触发**：网关消息入口 | **输入**：用户原始消息文本
**输出**：消息类型 + 是否需要主Agent介入

```
输入: "今天心情不错"
输出: chat | 不需主Agent

输入: "研究一下huggingface的audio pipeline"
输出: research_request | topic="huggingface audio pipeline" | 需触发github-discover

输入: "帮我创建一个docker-compose"
输出: task | 需主Agent执行
```

### Job 5: 定时模板报告 (Scheduled Report Filler)

**触发**：cron 每日/每小时 | **输入**：结构化状态数据
**输出**：填入模板的完整报告

```
模板:
━━━ 日报 {date} ━━━
容器状态: {status}
MEMORY: {memory_pct}% ({memory_used}/{memory_total})
cron活动: {cron_count}个
网络: {network_status}

3B填充:
  date → date命令输出
  status → docker compose ps
  memory_pct → stat MEMORY.md
  cron_count → cronjob list | wc -l
```

### Job 6: 命名/分类/标签 (Tagger)

**触发**：按需 | **输入**：文件名或描述
**输出**：文件名 + 标签 + 分类

```
输入: "这个PDF是2024年Q3的财务报告"
输出: filename: "2024-Q3-financial-report.pdf"
      tags: ["finance", "quarterly", "2024"]
      category: "report"
```

### Job 7: 上下文摘要 (Context Summarizer)

**触发**：会话过长时 | **输入**：最近 N 轮对话
**输出**：结构化摘要（已解决、待办、关键决定）

```
输出:
  ━━ 已解决 ━━
  - 网络不通，等重启
  - memory压缩已配置，每5min跑
  ━━ 待办 ━━
  - 网络恢复后审查3个GitHub文件
  ━━ 关键决定 ━━
  - skill必须含5节结构（边界+决策+步骤+联动+反馈）
```

---

## Integration Patterns

### Pattern A: cron + 3B Heartbeat

```yaml
cron:
  schedule: "*/15 * * * *"
  no_agent: true
  script: /opt/data/scripts/call_vibe.py
  # 脚本内部读状态文件 → 调3B → 只有状态变化才输出 → 输出=通知
```

### Pattern B: Delegate → 3B Classification

当需要分类大量数据时，把分类任务 delegate 给子agent，子agent内部调3B API：
```
主agent → delegate_task(goal="分类日志") → 子agent → call_vibe(prompt=...) → 返回结构化结果
```

### Pattern C: 3B Pre-filter (Gateway)

在消息处理管道的入口，先用 3B 判断消息类型：
```
用户消息 → call_vibe(classify_prompt) 
  ├─ "chat" → 3B 直接回复，不进主上下文
  ├─ "task" → 进主agent执行
  └─ "research_request" → 触发 github-discover 流程
```

---

## Reference Files

- `scripts/call_vibe.py` — 通用调用函数，可被 cron 和 delegate_task 直接使用
## 适用场景

### 入口条件

- 相关场景触发词被命中
- 用户明确提出了该技能覆盖的问题
- 系统状态满足前置条件

### 出口条件

- 问题已解决或结论已输出
- 所有必要的操作已完成
- 结果已向用户报告

