---
name: codex-bridge
description: Codex ↔ Hermes 桥接协议 — 状态机驱动的往返循环 + 兼容旧版请求/响应
category: workflow
platforms: [linux, windows]
triggers:
  keywords:
    - CodeX
    - codex
    - 桥接
    - bridge
    - 管道
    - 发给codex
    - codex优化
    - codex请求
    - 往返循环
    - 状态机
    - codex确认
    - 回传
    - 桥
related_skills:
  - external-adaptor
  - skill-creation-rules
  - verification-before-completion
  - chinese-output
  - preference-learning
---

# Codex ↔ Hermes Bridge 协议

## 架构总览

```
┌──────────────────┐   state-machine/   ┌───────────────────┐
│    Hermes        │ ◄─ ─ ─ ─ ─ ─ ─ ─ ► │    Codex          │
│   (Linux容器)    │  共享 JSON 状态文件  │   (Windows端)     │
│                  │                     │                   │
│  cron 15min 检测 │                     │ bridge-loop 5min  │
│  AWAITING_CONFIRM│   state_machine.py  │ 检测状态变化       │
│  → 推送给你      │   (核心库)          │ → 继续执行        │
└────────┬─────────┘                     └───────────────────┘
         │        用户确认通道（全中文 + 选项式）
         └──────────── 你(WeChat) ───────────────┘
```

## 状态机协议（主协议）

### 核心库

Codex 在 `scripts/state_machine.py` 实现了状态机库。**所有状态操作通过此库**，不直接读写 JSON。

| 函数 | 用途 |
|------|------|
| `create(type, context, created_by)` | 创建状态（默认 PENDING） |
| `transition(id, new_state, by, result, error)` | 过渡（校验合法路径） |
| `read(id)` | 读取（含已归档） |
| `list_active()` | 列出活跃未归档的 |

### 状态文件

`codex-bridge/state-machine/{id}.json` — 全程一个文件，状态驱动。

```json
{
  "id": "sm-20260726-xxxxxx",
  "type": "memory_compression | user_confirmation | ...",
  "state": "AWAITING_CONFIRMATION",
  "created_by": "codex | hermes",
  "context": {
    "summary": "简短描述（给用户看时转中文）",
    "detail": "详细内容",
    "options": ["选项A", "选项B"]
  },
  "result": {"files_changed": [...], "summary": "..."},
  "error": null,
  "history": [
    {"state": "PENDING", "at": "...", "by": "codex"},
    {"state": "PROCESSING", "at": "...", "by": "hermes"}
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

### 状态与合法过渡

```
                   PENDING
                      │
                      ▼
                 PROCESSING
                ┌────┼────┐
                ▼    ▼    ▼
       AWAITING_   COMPLETED   FAILED
        CONFIRM
          │
      ┌───┼───┐
      ▼   ▼   ▼
   CONFIRMED REJECTED TIMEOUT
      │
      ▼
   PROCESSING → … → COMPLETED
```

| 当前状态 | 可过渡到 |
|----------|---------|
| PENDING | PROCESSING |
| PROCESSING | COMPLETED, FAILED, AWAITING_CONFIRMATION |
| AWAITING_CONFIRMATION | CONFIRMED, REJECTED, TIMEOUT |
| CONFIRMED | PROCESSING, COMPLETED |

终止态（自动归档）：COMPLETED, FAILED, REJECTED

### Hermes 侧脚本

| 脚本 | 用途 |
|------|------|
| `codex_state_watcher.py` | 主轮询。检测 AWAITING_CONFIRMATION / COMPLETED / FAILED |
| `state_machine.py` | 核心库 — ⚠️ 两边共享协议，Codex 可能通过 bridge 单方修改（见 references/state-naming-alignment.md） |
| `wechat_state_bridge.py` | 微信确认/拒绝辅助（依赖 state_machine.py） |
| `poll_codex_responses.py` | 旧版轮询（兼容旧请求/响应） |

### 完整工作流

#### Step 1: 构造请求（高层）
- 只写「做什么」，不写「怎么做」
- Codex 遇选择会返回 `AWAITING_CONFIRMATION`
- 引用文件用 context.detail

#### Step 2: 发前确认（中文 + 选项式）
```
━━━ 请求 Codex ━━━
任务: <<高层描述>>
目标:
  · 要点1
  · 要点2

请回复：
【1】确认发送
【2】补充细节后发
【3】取消
────────────────
```

#### Step 3: 创建初始状态
```python
import state_machine as sm
st = sm.create("memory_compression", {"summary": "...", "detail": "..."}, created_by="hermes")
```

#### Step 4: 往返循环
- cron `codex-state-watcher` 每 15min 运行 `codex_state_watcher.py run`
- 检测到 `AWAITING_CONFIRMATION` → 自动推送中文确认界面
- 你回复后，用 `codex_state_watcher.py confirm <sm_id>` 确认（状态 → CONFIRMED）
- Codex 侧 bridge-loop 每 5min 同步 → 检测到 CONFIRMED → 继续执行（→ PROCESSING）
- 循环直到 COMPLETED 或 FAILED

#### Step 5: 收后验证
- 读 result.files_changed → 确认文件存在 → 语法检查 → 运行一次
- 生成中文审核摘要给你

### 确认界面格式（强制规范）

**所有推送给用户的确认消息，必须全中文、使用以下格式：**

```
━━━ 需要确认 ━━━
<<简短描述>>

请回复：
【1】<<选项1>>
【2】<<选项2>>
【3】<<选项3>>（如有）
────────────────
回复数字即可
```

规则：
- 使用 `━━━` 分隔线（全角 U+2501 × 3）
- 选项用 `【N】` （全角方括号 + 数字）
- 末尾 `────────────────` 全角水平线
- 不用 markdown 标题、代码块、列表符号
- 3–5 行，一眼看完

### Codex 侧钩子

Windows `bridge-loop.ps1`：
- 每 5 分钟同步 `state-machine/` 目录
- 向 Codex 注入状态上下文（state_machine.py 作为库）
- Codex 检测状态变化 → 执行 → 用 `sm.transition()` 更新

## 旧版请求/响应协议（v1/v2 — 兼容）

```
requests/<id>.json  →  bridge-loop 拾取 → 移入 archive/
responses/<id>.json ←  Codex 写回（pending → completed）
```

仅当 bridge 未升级到 state-machine 或旧任务需兼容时回退。

## 常见错误

**错误1: 替 Codex 做决策** — 写死规格不给 Codex 留空间
→ 只写高层，Codex 遇选择返回 AWAITING_CONFIRMATION

**错误2: 手动写 JSON 而非用 state_machine.py**
→ 必须通过 `import state_machine as sm` 操作，直接写 JSON 丢历史

**错误3: 确认界面用英文/markdown** ← 用户纠正
→ 必须用 `━━━` + `【N】` 全中文格式

**错误4: JSON 字段混入 markdown** — string 字段不能含 `**`、`[xxx]`

**错误5: 发前未确认** — 文件写前需你批准

**错误6: 回后不验证** — 必须实际运行脚本

**错误7: Windows UTF-8 BOM** — 读状态文件用 `encoding='utf-8-sig'`

## 参考文件

| 文件 | 内容 |
|------|------|
| `references/state-vs-reqres-lesson.md` | 状态机 vs 请求/响应两次教训 |
| `references/round-trip-protocol-lesson.md` | 往返循环教训记录 |
| `references/pitfalls-learned.md` | 通用实战教训汇编 |
| `references/codex-indent-bug-pattern.md` | Codex 缩进 bug 模式 |
| `references/tencent-api-fieldmap.md` | 外部 API 字段映射 |
| `references/state-naming-alignment.md` | 状态命名同步教训 — 库被 Codex 单方修改导致不一致 |
| `scripts/codex_state_watcher.py` | 状态机轮询（Hermes 侧主脚本） |
| `scripts/state_machine.py` | 核心库（Codex 实现） |
| `scripts/wechat_state_bridge.py` | 微信确认桥接（Codex 实现） |
| `scripts/poll_codex_responses.py` | 旧版响应轮询（兼容） |

Codex 侧原始文档位于 `codex-bridge/state-machine/`：
- `README.md` — 状态机完整文档 + 流转图
- `ARCHITECTURE.md` — 架构复用分析
- `wechat-confirm-format.md` — 确认界面设计
- `examples/` — 示例文件
