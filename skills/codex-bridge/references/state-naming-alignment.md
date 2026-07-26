# 状态命名同步教训（2026-07-26）

## 发现

`state_machine.py` 的 STATES 和 VALID_TRANSITIONS 中，状态名被人（Codex bridge 同步时）从：
- `AWAITING_CONFIRMATION` → 改成了 `AWAITING_INPUT`
- `CONFIRMED` → 改成了 `INPUT_PROVIDED`
- `REJECTED` 被移除

但所有实际状态文件（`sm-*.json`）和 `codex_state_watcher.py` 仍使用旧名。

## 后果

1. `state_machine.transition()` 读文件后验证 `VALID_TRANSITIONS.get(current_state, [])`
   → 旧状态名（如 `AWAITING_CONFIRMATION`）不在字典 key 中 → 返回 `[]`
   → 任何新状态都不在空列表里 → transition 静默返回 `None`
   → 操作看似成功但实际没做任何事

2. `state_machine.list_active()` 读原始 JSON，不受影响（不做验证，只过滤 COMPLETED/FAILED）

3. watcher 调用 `list_active()` 仍能检测到状态，但调用 `confirm/reject` 时会静默失败

## 修复

将 `state_machine.py` 还原为原始状态名，两者对齐：

```python
STATES = [
    "PENDING",
    "PROCESSING",
    "AWAITING_CONFIRMATION",
    "CONFIRMED",
    "REJECTED",
    "COMPLETED",
    "FAILED",
    "TIMEOUT",
]

VALID_TRANSITIONS = {
    "PENDING": ["PROCESSING"],
    "PROCESSING": ["COMPLETED", "FAILED", "AWAITING_CONFIRMATION"],
    "AWAITING_CONFIRMATION": ["CONFIRMED", "REJECTED", "TIMEOUT"],
    "CONFIRMED": ["PROCESSING", "COMPLETED"],
    "REJECTED": [],
    "COMPLETED": [],
    "FAILED": [],
    "TIMEOUT": ["PENDING"],
}
```

注意：`_archive()` 也需包含 `REJECTED`（旧库只归档 COMPLETED/FAILED）。

## 根因

Codex 在 Windows 侧可以通过 bridge-loop 直接写共享目录下的 `state_machine.py`。
没有校验机制确保 Codex 的修改与现有使用方（watcher、JSON 文件格式）兼容。

## 预防措施

- **不要直接允许 Codex 修改 `state_machine.py`** — 该库是两边共有协议，单方修改即破环
- 如果必须更新状态名，必须同时更新:
  - `state_machine.py` (库)
  - `codex_state_watcher.py` (watcher 的条件判断)
  - 已有 `sm-*.json` 文件（如果存在）
  - `codex-bridge/state-machine/README.md` (文档)
  - `chinese-output` skill (工作流描述)
- 更新后运行 `state_machine.py list` + transition 一个测试状态验证

## 影响范围

此问题导致了本场会话中：
1. `python3 codex_state_watcher.py confirm/reject` 对旧状态文件静默失败
2. 清理 `sm-20260726-191255` 时必须用两步过渡（PENDING→PROCESSING→COMPLETED）
   — 这其实是正确的（PENDING→COMPLETED 是非法路径），但之前以为是 bug
3. 测试状态 `sm-20260726-194551` 和 `sm-20260726-195134` 同理需要两步

## 关联文件

- `/opt/data/scripts/state_machine.py` — 核心库（已修复）
- `/opt/data/scripts/codex_state_watcher.py` — watcher（使用库，需对齐）
- `/opt/data/codex-bridge/state-machine/sm-*.json` — 实际状态文件
