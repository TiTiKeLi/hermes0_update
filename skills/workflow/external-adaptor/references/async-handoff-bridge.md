# 异步代理桥接模式 v1
## 2026-07-26 实测 — Codex-Hermes Bridge

## 概述

当外部 AI 代理无法直接在 Hermes 容器内运行时（如 Windows 端桌面 IDE 工具），
可以通过 **文件系统 + Git 同步** 实现异步桥接。

## 管道架构

```
Hermes (Linux 容器)
    │ 写入 JSON 请求
    ↓
codex-bridge/requests/<id>.json
    │
    ↓  [git sync / 共享目录]
    │
Windows 端脚本 (bridge-loop.ps1)
    │ 检测到新请求 → 触发外部代理
    ↓
外部代理 (Codex/Claude Code/Cursor)
    │ 处理 → 写 JSON 响应
    ↓
codex-bridge/responses/<id>.json
    │
    ↓  [git sync / 共享目录]
    │
Hermes 读取响应 → 验证 → 回应用户
```

## 请求格式

```json
{
  "id": "req-<topic>-<seq>",
  "created_at": "2026-07-26T12:00:00",
  "source": "hermes-wechat",
  "type": "skill_optimize | bug_fix | project_design | ui_component",
  "context": {},
  "request": "具体的请求描述",
  "fixes_needed": [{"id": "BUG-1", "file": "...", "severity": "medium", "description": "...", "fix": "..."}],
  "optimizations_requested": [{"area": "...", "description": "..."}],
  "constraints": {"runtime": "...", "python_only": true}
}
```

## 响应格式

```json
{
  "id": "req-finance-opt-001",
  "responded_at": "2026-07-26T12:05:00",
  "status": "completed | failed | needs_more_info",
  "response": "处理结果描述",
  "details": {},
  "files_changed": ["path/to/file1"]
}
```

## 最佳实践

| 角色 | 职责 |
|------|------|
| **Hermes** | 写完整请求（含bug详情、约束条件、辅助参考） |
| **桥接脚本** | 轮询 → 请求文件移入archive → 分发到代理 |
| **外部代理** | 实际处理 → 写响应 + 修改的文件 |
| **Hermes（回读）** | cron 轮询响应 → 验证 → 合并改动 → 回传用户 |

## 关键约束

1. **异步性** — 请求发出后不能即时等待，Hermes 需要通过 cron 轮询响应
2. **请求必须自包含** — 外部代理没有 Hermes 的上下文、记忆、技能
3. **状态文件是唯一通道** — 所有信息必须编码进 JSON 请求
4. **验证责任在 Hermes** — 外部代理的 claims 不可信，必须回读验证

## 推荐场景

| 场景 | 适合 | 不适合 |
|------|------|--------|
| 代码重构/优化 | ✅ 外部 IDE 有完整工具链 | ❌ 需要 Hermes 内部数据的任务 |
| UI 组件设计 | ✅ 外部有前端工具 | ❌ 需要即时反馈 |
| 多文件批量修改 | ✅ 外部代理处理大文件好 | ❌ 少量文字修改 |
| 复杂调试 | ✅ 外部有完整 debug 能力 | ❌ 纯推理/分析任务 |
