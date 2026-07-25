# Hermes Memory System Internals

Discovered during the 2026-07-21 memory hierarchy design session.

## MemoryProvider Architecture (`/usr/local/lib/python3.11/site-packages/agent/`)

### Event Hook Model
MemoryProvider (abstract class in `memory_provider.py`) exposes these hooks:

| Method | When Called | Return |
|--------|-------------|--------|
| `initialize(session_id, **kwargs)` | Agent startup | None |
| `system_prompt_block()` | Before prompt assembly | str |
| `prefetch(query)` | Before each turn | Context block |
| `sync_turn(user_msg, assistant_response)` | After each turn | None |
| `get_tool_schemas()` | Tool registration | List[dict] |
| `handle_tool_call(name, args)` | Tool dispatch | Response |
| `shutdown()` | Agent shutdown | None |
| `on_turn_start(turn, message, **kwargs)` | Per-turn tick | None |
| `on_session_end(messages)` | Session ends | None |
| `on_session_switch(new_session_id)` | Session ID rotation | None |
| `on_pre_compress(messages)` | Before context compression | str |
| `on_memory_write(action, target, content, metadata)` | Built-in memory tool writes | None |
| `on_delegation(task, result, **kwargs)` | Subagent completes | None |

### MemoryManager (`memory_manager.py`)
- Orchestrates providers, enforces ONE external provider limit
- Wired into `run_agent.py` lifecycle
- `prefetch_all()` → called before each turn to retrieve memory context
- `sync_all()` → called after each turn to persist session data
- `on_session_end()` → delegates to all providers
- `on_pre_compress()` → collects text from providers for compression summary

## Memory Store Database (`/opt/data/memory_store.db`)

### Tables
- `facts` — core fact storage (content, category, tags, trust_score, retrieval_count, helpful_count, created_at, updated_at, hrr_vector)
- `entities` — named entities (name, entity_type, aliases)
- `fact_entities` — linking table
- `facts_fts` — FTS5 full-text search index
- `memory_banks` — grouped fact collections with HRR vectors

### Key Queries
```sql
-- All facts sorted by trust
SELECT fact_id, content, trust_score FROM facts ORDER BY trust_score DESC;

-- High-trust facts for memory sync
SELECT fact_id, content, trust_score, retrieval_count, helpful_count, tags
FROM facts WHERE trust_score >= ? ORDER BY trust_score DESC LIMIT ?;

-- Update trust score directly
UPDATE facts SET trust_score = ? WHERE fact_id = ?;
```

### fact_feedback Behavior
- `fact_feedback(action='helpful')` → `trust_score += 0.05` (very slow)
- To accelerate: direct SQL UPDATE (must be done carefully)
- The 0.05 increment means trust_score climbs from 0.5 to 0.7 in 4 votes

## Holographic HRR Implementation (`plugins/memory/holographic/holographic.py`)
- Phase-encoded Holographic Reduced Representations
- 1024-dimensional vectors by default
- Operations: encode_atom, bind (convolve), unbind (correlate), bundle (superpose), similarity
- Deterministic via SHA-256 — cross-platform reproducible
- `encode_text(text)` → bag-of-words bundle of atom vectors
- Stored as BLOB in `facts.hrr_vector` column

## Known Constraints
- `memory` char limit: 2200 (config: `memory.memory_char_limit`)
- `memory` user profile limit: 1375 (config: `memory.user_char_limit`)
- `hooks: {}` in config — no hooks configured by default
- `approvals.cron_mode: deny` by default — cron may need approval override
- `ai_service` → GPT-4o mini (default) for session_search; can be overridden per auxiliary
