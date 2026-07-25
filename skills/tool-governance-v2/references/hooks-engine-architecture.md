# Hooks Engine Architecture

## Overview

The hooks engine is a self-contained reactive trigger subsystem for Hermes Agent. It provides three trigger types (keyword, event, tool_post), SQLite-based persistence, automated registration from skill frontmatter, and cron-driven maintenance.

## Component Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Agent Loop                         │
│  ┌─────────────┐   ┌──────────┐   ┌──────────────┐  │
│  │ pre_message  │   │ tool_call│   │ record_call   │  │
│  │ check_keyword│──▶│ execute  │──▶│ check_tool_post│  │
│  └──────┬──────┘   └──────────┘   └──────┬───────┘  │
└─────────┼────────────────────────────────┼──────────┘
          │                                 │
          ▼                                 ▼
┌─────────────────────────────────────────────────────┐
│                  HookEngine API                       │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │match_keyword│  │match_event/  │  │ execute_hook│  │
│  │ (regex)     │  │fire_event    │  │ (action)    │  │
│  └──────┬──────┘  └──────┬───────┘  └──────┬─────┘  │
└─────────┼────────────────┼────────────────┼─────────┘
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────┐
│                    HookDB (SQLite)                    │
│  hooks | execution_log | events (三张表)             │
│  /opt/data/hooks/hooks.db                            │
└─────────────────────────────────────────────────────┘
          ▲
┌─────────┴──────────────────────┐
│      skill_trigger_index       │
│  scan_all_skills() → hooks.db  │
│  (从 21 个 skill frontmatter)  │
└────────────────────────────────┘
          ▲
┌─────────┴──────────────────────┐
│    hooks_watchdog (cron)       │
│  fire cron_tick + rebuild ref  │
│  every 5 minutes (no_agent)    │
└────────────────────────────────┘
```

## Database Schema (hooks.db)

### hooks 表
```sql
CREATE TABLE hooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    hook_type TEXT NOT NULL CHECK(hook_type IN ('keyword','event','tool_post')),
    trigger_config TEXT NOT NULL,   -- JSON: {patterns:[], event:'', tool:''}
    action_config TEXT NOT NULL,    -- JSON: {skills:[], command:'', condition:''}
    enabled INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 0,
    fire_count INTEGER DEFAULT 0,
    last_fired_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

### execution_log 表
```sql
CREATE TABLE execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hook_id INTEGER,
    hook_name TEXT,
    event_type TEXT,
    context_snapshot TEXT,
    success INTEGER,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (hook_id) REFERENCES hooks(id)
);
```

## Trigger Types in Detail

### keyword
- Matching: case-insensitive substring match via `any(kw in msg.lower() for kw in patterns)`
- Use case: user says "下载项目" → auto-load `download-gate`, `github-discover` skills
- Agent integration: call `engine.match_keyword(text)` in pre-message handler

### event
- Matching: exact event name match
- Built-in events: `session_start`, `memory_written`, `cron_tick`
- Custom events: any string via `engine.fire_event(name, context={...})`
- Use: scheduled maintenance, startup init, inter-skill communication

### tool_post
- Matching: tool name match (exact or glob pattern)
- Execution trigger: `state_registry.record_call()` auto-fires after successful call
- Context provided: tool_name, args (truncated), result (truncated), timestamp

## Skill Frontmatter → Hook Registration

Each skill's `SKILL.md` has a `triggers` YAML section:

```yaml
triggers:
  keywords:
    - 下载
    - download
    - github项目
  events:
    - session_start
  tools:
    - terminal
```

The `skill_trigger_index.py` scanner:
1. Walks all skill directories
2. Parses frontmatter with PyYAML
3. Extracts `triggers` → generates one hook per keyword/event/tool
4. Upserts into hooks.db (checks for existing by name)

## Integration Points

| Component | Integration Method | File |
|-----------|-------------------|------|
| state_registry | Lazy import HookEngine in `_get_hook_engine()` | state_registry.py |
| record_call | Auto-fire tool_post after conn.commit() | state_registry.py |
| CLI (state_registry) | `he-list`, `he-stats`, `he-fire`, `he-check-msg` | state_registry.py |
| CLI (hooks_engine) | `add-hook`, `delete-hook`, `list-hooks`, `match`, `fire` | hooks_engine.py |
| Cron watchdog | `no_agent=True`, script: `hooks_watchdog.sh` | cronjob |

## Real Diagnostics (2026-07-25)

### Fire Count Analysis
Script: `/opt/data/hooks/fire_count_analysis.py` — directly queries SQLite DB.

**37 hooks total: 33 zero-fire, 4 ever-fired.**

The 4 that fired are all `event` type, triggered by session bootstrap — not from agent-loop integration. They're echoes, not signals.

| Hook | Type | Fire Count | Trigger |
|------|------|-----------|---------|
| bootstrap-deep-need | event | 2 | session_start |
| skill-tool-governance-evt | event | 1 | session_start |
| skill-hierarchical-memory-sync-evt | event | 1 | session_start |
| skill-deep-need-analysis-evt | event | 1 | session_start |

**Missing table**: `hooks_log` table does not exist despite being in the schema. No audit trail is written.

### Known Gaps
1. **Agent never calls check_pre_message_hooks()** — 21 keyword hooks silently sit
2. **record_call() tool_post results discarded** — 10 tool_post hooks fire, but nothing happens
3. **hooks_log missing** — no execution audit trail
4. **cron_tick: 0 listeners** — watchdog runs every 5 minutes, nobody listens

## Current Stats (2026-07-25)

- Total hooks: 37 (6 event + 21 keyword + 10 tool_post)
- Skill coverage: 21/21 skills have trigger frontmatter
- Watchdog interval: 5 minutes
- Reference doc: /opt/data/hooks/TRIGGERS_REFERENCE.md
