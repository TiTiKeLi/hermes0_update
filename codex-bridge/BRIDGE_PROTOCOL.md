# Codex-Hermes Bridge 协议 v1

## 请求格式
请求文件放在 codex-bridge/requests/<id>.json

```json
{
  "id": "req-20260726-001",
  "created_at": "2026-07-26T00:00:00",
  "source": "hermes-wechat",
  "type": "skill_optimize | project_design | ui_component | bug_fix | general",
  "context": "请求的背景信息",
  "request": "具体的请求内容"
}
```

## 响应格式
响应文件放在 codex-bridge/responses/<id>.json

```json
{
  "id": "req-20260726-001",
  "responded_at": "2026-07-26T00:05:00",
  "status": "completed | failed | needs_more_info",
  "response": "处理结果描述",
  "details": "详细的处理内容",
  "files_changed": ["path/to/file1", "path/to/file2"]
}
```

## 时序

1. Hermes 写请求 → requests/ 目录 (即时)
2. git-sync.ps1 每 1h 推送到 GitHub (或手动触发)
3. Codex 下次会话时检测 → 处理 → 写响应 (用户打开 Codex 时)
4. Codex commit + push (即时)
5. Hermes 下轮同步 → 读取响应 → 回复用户 (1h 内)
