# Codex Bridge 实战教训

## 事故1：JSON 内嵌 markdown（2026-07-26）

**背景**：第一次发 finance-expert 优化请求给 Codex。

**错误**：
1. `request` 字段写了自然语言 "见 below" — 这是跨字段引用，不是 JSON 结构
2. `fixes_needed` 字段的描述中混入了 `**`、`` ` ``、`→` 等非 JSON 符号
3. requests/ 目录附带了一个 .md 辅助文件

**后果**：
- 被用户指出 → 重写整个请求为纯 JSON
- 被要求将规则固化到 skill 中

**修复方式**：
- `request` 字段改为纯描述性短句："Fix 3 bugs and optimize 4 Python scripts..."
- 所有信息和约束用 `fixes`/`optimizations`/`constraints` 等结构化字段传递
- 辅助文件移入 `skills/codex-bridge/references/`

**验证方法**：
```python
import json
with open('request.json') as f:
    d = json.load(f)
# 检查所有 string 字段是否含 markdown 符号
import re
markdown_chars = r'[*_#`\[\]()>|-]'
for key, val in d.items():
    if isinstance(val, str) and re.search(markdown_chars, val):
        print(f"WARNING: field '{key}' contains markdown chars: {val}")
```

## 事故2：架构方案未等评审就实施（2026-07-26）

**背景**：用户提出三层记忆架构后，我直接写了详细实施计划。

**错误**：没有先发给 Codex 评审就制定了实现方案。

**教训**：涉及架构变更的请求，必须先经 Codex 评审（type=architectural_review），收到 completed 响应后才能开始实现。

## 事故3：UTF-8 BOM 编码不兼容（2026-07-26）

**背景**：Codex 的 bridge-loop.ps1 在 Windows 上运行，写入 JSON 响应文件时带 UTF-8 BOM 头（`\xef\xbb\xbf`）+ Windows 换行（`\r\n`）。

**错误**：Hermes 侧的 `poll_codex_responses.py` 轮询脚本直接用 `json.load(f)` 读取，Python 默认 UTF-8 编码不跳过 BOM，导致 `JSONDecodeError: Unexpected UTF-8 BOM`。

**现象**：
- 轮询脚本输出不完整或无输出
- cron 日志中 silent fail
- 用户说"信息已经同步了"但 Hermes 检测不到

**修复方式**：
```python
# 在打开文件时指定 encoding='utf-8-sig' 自动剥离 BOM
with open(rfile, encoding='utf-8-sig') as f:
    raw = f.read().replace('\r\n', '\n')  # 统一换行
    resp = json.loads(raw)
```

**验证方法**：
```bash
# 确认 BOM 存在
head -1 response.json | cat -A | grep -q 'M-oM-;M-?'
# 确认脚本能正常解析
python3 -c "import json; json.loads(open('response.json', encoding='utf-8-sig').read().replace('\r\n','\n')); print('OK')"
```

## 事故4：永久全局轮询而非触发式生命周期（2026-07-26）

**背景**：第一次实现 Codex Bridge 自动轮询时，创建了全局常驻 cron（`every 5m`）。

**错误**：
- 不管有没有待处理的 Codex 请求都在跑
- 结果返回后还在继续扫，浪费资源
- 5分钟间隔过于密集（用户纠正为15分钟）

**用户纠正**：
- "应该是触发bridge后才轮询"
- "结果返回即停"
- "10分钟或15分钟"

**修复方式**：
1. 移除全局永久 cron
2. 提交请求后才创建 temp cron（every 15m）
3. 监听状态记录在 `.poll_state.json`（watching/seen_ids/done_ids）
4. 检测到 ALL_DONE → 移除 cron + 清理监听
5. 无待处理时：零轮询
