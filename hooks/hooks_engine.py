#!/usr/bin/env python3
"""
hooks_engine.py — Hook Engine v1
=================================
Three-layer hook system with SQLite-backed registration, matching, and execution.

Architecture:
  ┌─────────────────────────────────────────────────────────┐
  │                    Agent Checkpoints                      │
  │                                                           │
  │  PRE_MESSAGE ─→ keyword hooks → skill_view() + context    │
  │  POST_TOOL   ─→ tool hooks    → run_script / load_skill   │
  │  POST_REPLY  ─→ reply hooks   → cleanup / emit_event      │
  │  CRON_TICK   ──→ cron hooks   → watchdog fires            │
  │  EVENT_FIRE  ──→ event hooks  → subscribe/broadcast       │
  └─────────────────────────────────────────────────────────┘

Hook Schema (SQLite: /opt/data/hooks/hooks.db):
  hooks:      id, name, hook_type, trigger_json, action_json, enabled,
              priority, cooldown, max_fires, last_fired, fire_count
  hook_log:   id, hook_id, checkpoint, context, result, success, ts
  conditions: id, hook_id, logic (all/any), rules_json (nested)

Hook Types:
  keyword    — user message contains keyword patterns
  tool_pre   — before a tool is called (gating)
  tool_post  — after a tool returns
  event      — system event broadcast (session_start, user_question, ...)
  cron       — scheduled recurring check
  chain      — another hook completed → fire this one

Action Types:
  load_skill(s) — calls skill_view() via agent
  run_script    — executes a script file
  emit_event    — fires another event
  chain         — triggers another hook by name/pattern
  condition_check — runs a condition rule before proceeding

Usage:
  python3 hooks_engine.py init                         # create DB + seed
  python3 hooks_engine.py register <name> <type> ...    # register a hook
  python3 hooks_engine.py list [--type <type>]          # list hooks
  python3 hooks_engine.py match --text "..."            # keyword match
  python3 hooks_engine.py match --tool "write_file" --path "/x"  # tool match
  python3 hooks_engine.py fire <hook_id>                # manual trigger
  python3 hooks_engine.py log [--hook <id>]             # view log
  python3 hooks_engine.py stats                         # summary stats
"""

import sqlite3
import json
import time
import os
import re
import sys
import subprocess
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks.db")
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
os.makedirs(SCRIPTS_DIR, exist_ok=True)


def utcnow() -> float:
    return time.time()


# =====================================================================
# Database Layer
# =====================================================================

class HookDB:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS hooks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,
            description     TEXT DEFAULT '',
            hook_type       TEXT NOT NULL CHECK(hook_type IN (
                'keyword','tool_pre','tool_post','event','cron','chain'
            )),
            trigger_config  TEXT NOT NULL DEFAULT '{}',
            action_type     TEXT NOT NULL CHECK(action_type IN (
                'load_skill','run_script','emit_event','chain','condition_check','tool_call'
            )),
            action_config   TEXT NOT NULL DEFAULT '{}',
            enabled         INTEGER DEFAULT 1,
            priority        INTEGER DEFAULT 0,
            cooldown        INTEGER DEFAULT 0,
            max_fires       INTEGER DEFAULT 0,
            last_fired      REAL,
            fire_count      INTEGER DEFAULT 0,
            last_result     TEXT DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS hook_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            hook_id         INTEGER REFERENCES hooks(id) ON DELETE CASCADE,
            checkpoint      TEXT NOT NULL,
            context         TEXT DEFAULT '{}',
            result          TEXT DEFAULT '{}',
            success         INTEGER DEFAULT 1,
            duration_ms     REAL DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conditions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            hook_id         INTEGER NOT NULL REFERENCES hooks(id) ON DELETE CASCADE,
            logic           TEXT NOT NULL DEFAULT 'all' CHECK(logic IN ('all','any','not')),
            rules_json      TEXT NOT NULL DEFAULT '[]',
            description     TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS events_registry (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name      TEXT NOT NULL UNIQUE,
            description     TEXT DEFAULT '',
            last_broadcast  REAL,
            broadcast_count INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_hook_type ON hooks(hook_type);
        CREATE INDEX IF NOT EXISTS idx_hook_enabled ON hooks(enabled);
        CREATE INDEX IF NOT EXISTS idx_log_hook ON hook_log(hook_id);
        CREATE INDEX IF NOT EXISTS idx_log_ts ON hook_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_cond_hook ON conditions(hook_id);
        """)
        conn.commit()
        conn.close()

    # ----- CRUD -----

    def register_hook(self, name: str, hook_type: str, action_type: str,
                      trigger_config: dict = None, action_config: dict = None,
                      description: str = "", priority: int = 0,
                      cooldown: int = 0, max_fires: int = 0) -> int:
        conn = self._get_conn()
        try:
            cur = conn.execute("""
                INSERT INTO hooks (name, description, hook_type, trigger_config,
                    action_type, action_config, priority, cooldown, max_fires)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                name, description, hook_type,
                json.dumps(trigger_config or {}),
                action_type,
                json.dumps(action_config or {}),
                priority, cooldown, max_fires
            ))
            hook_id = cur.lastrowid
            conn.commit()
            return hook_id
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Hook '{name}' already exists: {e}")
        finally:
            conn.close()

    def update_hook(self, hook_id: int, **kwargs):
        """Update hook fields. Keys: name, description, hook_type, trigger_config,
           action_type, action_config, enabled, priority, cooldown, max_fires."""
        allowed = {'name','description','hook_type','trigger_config','action_type',
                   'action_config','enabled','priority','cooldown','max_fires'}
        sets = {}
        for k, v in kwargs.items():
            if k in allowed:
                if k in ('trigger_config', 'action_config'):
                    sets[k] = json.dumps(v)
                else:
                    sets[k] = v
        if not sets:
            return False
        sets['updated_at'] = 'CURRENT_TIMESTAMP'
        conn = self._get_conn()
        cols = ', '.join(f"{k}=?" if v != 'CURRENT_TIMESTAMP'
                         else f"{k}=CURRENT_TIMESTAMP"
                         for k in sets)
        vals = [v for k, v in sets.items() if v != 'CURRENT_TIMESTAMP']
        vals.append(hook_id)
        conn.execute(f"UPDATE hooks SET {cols} WHERE id=?", vals)
        conn.commit()
        conn.close()
        return True

    def delete_hook(self, hook_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM hooks WHERE id=?", (hook_id,))
        affected = cur.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_hook(self, hook_id: int) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM hooks WHERE id=?", (hook_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_hook_by_name(self, name: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM hooks WHERE name=?", (name,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def list_hooks(self, hook_type: str = None, enabled_only: bool = False) -> list[dict]:
        conn = self._get_conn()
        parts = ["SELECT * FROM hooks"]
        params = []
        wheres = []
        if hook_type:
            wheres.append("hook_type=?")
            params.append(hook_type)
        if enabled_only:
            wheres.append("enabled=1")
        if wheres:
            parts.append("WHERE " + " AND ".join(wheres))
        parts.append("ORDER BY priority DESC, name")
        rows = conn.execute(' '.join(parts), params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ----- Conditions -----

    def set_condition(self, hook_id: int, logic: str = "all",
                      rules: list[dict] = None, description: str = ""):
        conn = self._get_conn()
        conn.execute("DELETE FROM conditions WHERE hook_id=?", (hook_id,))
        conn.execute("""
            INSERT INTO conditions (hook_id, logic, rules_json, description)
            VALUES (?,?,?,?)
        """, (hook_id, logic, json.dumps(rules or []), description))
        conn.commit()
        conn.close()

    def get_conditions(self, hook_id: int) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM conditions WHERE hook_id=?", (hook_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d['rules'] = json.loads(d['rules_json'])
        return d

    # ----- Events -----

    def register_event(self, event_name: str, description: str = ""):
        conn = self._get_conn()
        conn.execute("""
            INSERT OR IGNORE INTO events_registry (event_name, description)
            VALUES (?,?)
        """, (event_name, description))
        conn.commit()
        conn.close()

    def broadcast_event(self, event_name: str):
        conn = self._get_conn()
        now = utcnow()
        conn.execute("""
            UPDATE events_registry SET last_broadcast=?, broadcast_count=broadcast_count+1
            WHERE event_name=?
        """, (now, event_name))
        conn.commit()
        conn.close()

    def list_events(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM events_registry ORDER BY event_name").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ----- Logging -----

    def log(self, hook_id: int, checkpoint: str, context: dict = None,
            result: dict = None, success: bool = True, duration_ms: float = 0):
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO hook_log (hook_id, checkpoint, context, result, success, duration_ms)
            VALUES (?,?,?,?,?,?)
        """, (hook_id, checkpoint, json.dumps(context or {}),
              json.dumps(result or {}), 1 if success else 0, duration_ms))
        conn.commit()
        conn.close()

    def get_log(self, hook_id: int = None, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        if hook_id:
            rows = conn.execute(
                "SELECT * FROM hook_log WHERE hook_id=? ORDER BY id DESC LIMIT ?",
                (hook_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM hook_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ----- Stats -----

    def get_stats(self) -> dict:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) as c FROM hooks").fetchone()['c']
        by_type = conn.execute(
            "SELECT hook_type, COUNT(*) as c FROM hooks GROUP BY hook_type"
        ).fetchall()
        enabled = conn.execute(
            "SELECT COUNT(*) as c FROM hooks WHERE enabled=1"
        ).fetchone()['c']
        total_fires = conn.execute(
            "SELECT COALESCE(SUM(fire_count),0) as c FROM hooks"
        ).fetchone()['c']
        log_24h = conn.execute(
            "SELECT COUNT(*) as c FROM hook_log WHERE created_at > datetime('now','-1 day')"
        ).fetchone()['c']
        conn.close()
        return {
            "total": total,
            "enabled": enabled,
            "total_fires": total_fires,
            "log_24h": log_24h,
            "by_type": {r['hook_type']: r['c'] for r in by_type}
        }


# =====================================================================
# Hook Engine (Matching & Execution)
# =====================================================================

class HookEngine:
    """The agent calls check_* methods at defined checkpoints."""

    def __init__(self, db: HookDB = None):
        self.db = db or HookDB()

    # ---------------------------------------------------------------
    # CHECKPOINT 1: PRE_MESSAGE — user message keyword matching
    # ---------------------------------------------------------------

    def check_pre_message(self, user_message: str, debug: bool = False) -> list[dict]:
        """
        Called BEFORE processing a user message.
        Returns matched hooks (sorted by priority), does NOT execute actions.
        The agent should skill_view() the matched skills.
        """
        matched = []
        hooks = self.db.list_hooks(enabled_only=True)

        for hook in hooks:
            if hook['hook_type'] not in ('keyword', 'event'):
                continue

            # --- Event hooks (session_start, etc.) ---
            if hook['hook_type'] == 'event':
                trigger = json.loads(hook['trigger_config'])
                event_name = trigger.get('event', '')
                # Event hooks are not fired by message content alone
                continue

            # --- Keyword hooks ---
            trigger = json.loads(hook['trigger_config'])
            patterns = trigger.get('patterns', [])
            mode = trigger.get('mode', 'any')  # 'any' | 'all' | 'regex'

            if not patterns:
                continue

            # Check cooldown
            if hook['last_fired'] and hook['cooldown'] > 0:
                if utcnow() - hook['last_fired'] < hook['cooldown']:
                    continue

            # Check conditions (if any)
            cond = self.db.get_conditions(hook['id'])
            if cond:
                if not self._evaluate_condition(cond, {'message': user_message}):
                    continue

            # Pattern matching
            msg_lower = user_message.lower()
            if mode == 'regex':
                if any(re.search(p, user_message) for p in patterns):
                    matched.append(hook)
            else:
                hits = 0
                for p in patterns:
                    if p.lower() in msg_lower:
                        hits += 1
                if mode == 'all' and hits == len(patterns):
                    matched.append(hook)
                elif mode == 'any' and hits > 0:
                    matched.append(hook)

        matched.sort(key=lambda h: h['priority'], reverse=True)
        return matched

    # ---------------------------------------------------------------
    # CHECKPOINT 2: POST_TOOL — after a tool call
    # ---------------------------------------------------------------

    def check_post_tool(self, tool_name: str, tool_args: dict = None,
                        tool_result: dict = None, debug: bool = False) -> list[dict]:
        """Called after a tool returns. Returns hooks that should fire."""
        tool_args = tool_args or {}
        tool_result = tool_result or {}
        matched = []

        # Also check 'any_tool' hooks (trigger on ANY tool call)
        any_tool_hooks = [h for h in self.db.list_hooks(enabled_only=True)
                          if h['hook_type'] == 'tool_post' and
                          json.loads(h['trigger_config']).get('tool') == '*']
        
        hooks = self.db.list_hooks(enabled_only=True)
        for hook in hooks:
            if hook['hook_type'] not in ('tool_post', 'chain'):
                continue

            hook_list = any_tool_hooks + [hook] if hook not in any_tool_hooks else []
            if hook not in any_tool_hooks:
                hook_list.append(hook)

        # Proper loop
        for hook in hooks:
            if hook['hook_type'] not in ('tool_post', 'tool_pre', 'chain'):
                continue

            if hook in any_tool_hooks:
                hook_list = [hook]
                # Will be handled below via hook in hooks + we process it now
            else:
                hook_list = [hook]

        # Redo properly
        matched = []
        hooks_to_check = hooks  # all enabled hooks
        
        for hook in hooks_to_check:
            if hook['hook_type'] not in ('tool_post', 'tool_pre'):
                continue
            
            trigger = json.loads(hook['trigger_config'])
            target_tool = trigger.get('tool', '')
            path_pattern = trigger.get('path_pattern', '')
            
            # Cooldown check
            if hook['last_fired'] and hook['cooldown'] > 0:
                if utcnow() - hook['last_fired'] < hook['cooldown']:
                    continue

            # Tool name match
            if target_tool == '*':
                matches = True
            elif target_tool and target_tool == tool_name:
                matches = True
            elif not target_tool:
                matches = False
            else:
                matches = False

            # Path pattern match
            if matches and path_pattern:
                file_path = tool_args.get('path', '') or tool_result.get('path', '')
                if file_path:
                    import fnmatch
                    if not fnmatch.fnmatch(file_path, path_pattern):
                        matches = False

            if matches:
                matched.append(hook)

        return matched

    # ---------------------------------------------------------------
    # CHECKPOINT 3: EVENT — system event broadcast
    # ---------------------------------------------------------------

    def fire_event(self, event_name: str, context: dict = None) -> list[dict]:
        """Broadcast an event. Returns all hooks that matched + fired."""
        self.db.broadcast_event(event_name)
        context = context or {}
        fired = []

        hooks = self.db.list_hooks(enabled_only=True)
        for hook in hooks:
            if hook['hook_type'] != 'event':
                continue
            trigger = json.loads(hook['trigger_config'])
            target_event = trigger.get('event', '')
            if target_event == event_name or target_event == '*':
                result = self._execute_hook(hook, checkpoint=f"event:{event_name}",
                                            context=context)
                fired.append(result)

        return fired

    # ---------------------------------------------------------------
    # Execute a hook's action
    # ---------------------------------------------------------------

    def execute_hook(self, hook_id: int, checkpoint: str = "manual",
                     context: dict = None) -> dict:
        hook = self.db.get_hook(hook_id)
        if not hook:
            return {"error": f"Hook #{hook_id} not found"}
        return self._execute_hook(hook, checkpoint, context or {})

    def _execute_hook(self, hook: dict, checkpoint: str, context: dict) -> dict:
        hook_id = hook['id']
        hook_name = hook['name']
        action_type = hook['action_type']
        action_config = json.loads(hook['action_config'])
        trigger_config = json.loads(hook['trigger_config'])

        start = utcnow()
        result = {"hook_id": hook_id, "name": hook_name, "action": action_type}

        try:
            if action_type == 'run_script':
                script = action_config.get('script', '')
                params = action_config.get('params', {})
                # Substitute placeholders from context
                for k, v in params.items():
                    if isinstance(v, str) and v.startswith('$'):
                        params[k] = context.get(v[1:], v)

                cmd_parts = [script]
                for k, v in params.items():
                    cmd_parts.extend([f"--{k}", str(v)])

                r = subprocess.run(cmd_parts, shell=False,
                                   capture_output=True, text=True, timeout=30)
                result['stdout'] = r.stdout.strip()
                result['stderr'] = r.stderr.strip()
                result['exit_code'] = r.returncode
                result['success'] = r.returncode == 0

            elif action_type == 'load_skill':
                # NOTE: Agent must execute skill_view() manually.
                # This engine returns instruction values.
                skills = action_config.get('skills', [])
                result['instruction'] = f"CALL skill_view for: {skills}"
                result['skills'] = skills
                result['success'] = True

            elif action_type == 'emit_event':
                event = action_config.get('event', '')
                payload = action_config.get('payload', {})
                self.fire_event(event, {**context, **payload})
                result['event'] = event
                result['success'] = True

            elif action_type == 'chain':
                target = action_config.get('target_hook', '')
                delay = action_config.get('delay', 0)
                if delay > 0:
                    # Schedule via cron (delegated to caller)
                    result['instruction'] = f"DEFER: chain to '{target}' in {delay}s"
                else:
                    target_hook = self.db.get_hook_by_name(target)
                    if target_hook:
                        chained = self._execute_hook(target_hook, checkpoint, context)
                        result['chained'] = chained
                        result['success'] = True
                    else:
                        result['error'] = f"Chain target '{target}' not found"
                        result['success'] = False

            elif action_type == 'condition_check':
                result['success'] = True  # condition already evaluated upstream

            else:
                result['error'] = f"Unknown action_type: {action_type}"
                result['success'] = False

        except Exception as e:
            result['error'] = str(e)
            result['success'] = False

        duration = (utcnow() - start) * 1000
        result['duration_ms'] = round(duration, 1)

        # Update hook stats
        conn = sqlite3.connect(self.db.db_path)
        conn.execute("""
            UPDATE hooks SET last_fired=?, fire_count=fire_count+1,
                last_result=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (utcnow(), json.dumps(result), hook_id))
        conn.commit()
        conn.close()

        # Log
        self.db.log(hook_id, checkpoint, context, result,
                     result.get('success', False), duration)
        return result

    # ---------------------------------------------------------------
    # Condition Evaluation (nested rules with all/any/not logic)
    # ---------------------------------------------------------------

    def _evaluate_condition(self, cond: dict, context: dict) -> bool:
        logic = cond['logic']
        rules = cond.get('rules', [])
        if not rules:
            return True

        results = []
        for rule in rules:
            field = rule.get('field', 'message')
            op = rule.get('op', 'contains')
            value = rule.get('value', '')
            actual = context.get(field, '')

            if op == 'contains':
                results.append(value.lower() in str(actual).lower())
            elif op == 'not_contains':
                results.append(value.lower() not in str(actual).lower())
            elif op == 'matches':
                results.append(bool(re.search(value, str(actual))))
            elif op == 'equals':
                results.append(str(actual) == str(value))
            elif op == 'exists':
                results.append(field in context)
            elif op == 'gt':
                results.append(float(actual) > float(value))
            elif op == 'lt':
                results.append(float(actual) < float(value))
            else:
                results.append(True)

        if logic == 'all':
            return all(results)
        elif logic == 'any':
            return any(results)
        elif logic == 'not':
            return not all(results)
        return True


# =====================================================================
# CLI
# =====================================================================

def cli():
    db = HookDB()
    engine = HookEngine(db)

    if len(sys.argv) < 2:
        print("使用: python3 hooks_engine.py <命令> [参数...]")
        print("")
        print("📦 初始化:")
        print("  init                   初始化数据库 + 注册内置事件")
        print("")
        print("🔗 钩子管理:")
        print("  register <name> <type> <action_type> --trigger <JSON> --action <JSON>")
        print("    type: keyword | tool_pre | tool_post | event | cron | chain")
        print("    action_type: load_skill | run_script | emit_event | chain")
        print("    示例:")
        print("      hooks_engine.py register auto-dl keyword load_skill \\")
        print('        --trigger \'{"patterns":["下载","download"]}\' \\')
        print('        --action \'{"skills":["download-gate"]}\'')
        print("")
        print("  update <id> [--name X] [--enabled 0/1] [--priority N] ...")
        print("  remove <id>")
        print("  list [--type keyword] [--enabled-only]")
        print("  get <id>")
        print("")
        print("🎯 条件管理 (给钩子附加前置条件):")
        print("  condition <hook_id> <all|any|not> <rules_json>")
        print("    示例: condition 5 all '[{\"field\":\"message\",\"op\":\"contains\",\"value\":\"github\"}]'")
        print("")
        print("⚡ 匹配 & 触发:")
        print("  match --text \"用户消息\"          # 关键词匹配 (PRE_MESSAGE)")
        print("  match --tool write_file --path /x  # 工具匹配 (POST_TOOL)")
        print("  fire <id>                         # 手动触发")
        print("  fire-event <event_name> [--ctx JSON]")
        print("")
        print("📊 查询:")
        print("  log [--hook <id>] [--limit 30]")
        print("  stats")
        print("  events")
        return

    cmd = sys.argv[1]

    # ---- init ----
    if cmd == "init":
        # Register default events
        default_events = [
            ("session_start", "New session started"),
            ("session_end", "Session ended"),
            ("tool_fail", "A tool call failed"),
            ("user_question", "User asked a question"),
            ("user_request", "User made a request"),
            ("cron_tick", "Cron watchdog tick"),
        ]
        for evt, desc in default_events:
            db.register_event(evt, desc)
        # Also register event hooks (low priority, safe defaults)
        try:
            db.register_hook(
                name="bootstrap-deep-need",
                hook_type="event",
                action_type="load_skill",
                trigger_config={"event": "session_start"},
                action_config={"skills": ["deep-need-analysis"]},
                description="Session start: auto-load deep-need-analysis",
                priority=100
            )
        except ValueError:
            pass  # already exists
        print("✅ 数据库初始化完成")
        print(f"   位置: {db.db_path}")
        print(f"   内置事件: {len(default_events)} 个")
        return

    # ---- register ----
    if cmd == "register" and len(sys.argv) >= 5:
        name = sys.argv[2]
        hook_type = sys.argv[3]
        action_type = sys.argv[4]
        trigger_config = {}
        action_config = {}
        i = 5
        while i < len(sys.argv):
            if sys.argv[i] == "--trigger" and i + 1 < len(sys.argv):
                trigger_config = json.loads(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--action" and i + 1 < len(sys.argv):
                action_config = json.loads(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--desc" and i + 1 < len(sys.argv):
                description = sys.argv[i + 1]
                # handled below
                i += 2
                continue
            else:
                i += 1

        description = ""
        for i2 in range(5, len(sys.argv)):
            if sys.argv[i2] == "--desc" and i2 + 1 < len(sys.argv):
                description = sys.argv[i2 + 1]

        try:
            hook_id = db.register_hook(
                name=name, hook_type=hook_type,
                action_type=action_type,
                trigger_config=trigger_config,
                action_config=action_config,
                description=description
            )
            print(f"✅ 已注册钩子 #{hook_id}: {name} ({hook_type} → {action_type})")
        except ValueError as e:
            print(f"❌ {e}")
        return

    # ---- update ----
    if cmd == "update" and len(sys.argv) >= 3:
        hook_id = int(sys.argv[2])
        kwargs = {}
        i = 3
        while i < len(sys.argv):
            if sys.argv[i].startswith("--"):
                key = sys.argv[i][2:]
                if i + 1 < len(sys.argv):
                    val = sys.argv[i + 1]
                    if val in ('0', '1'):
                        val = int(val)
                    elif key in ('trigger_config', 'action_config'):
                        val = json.loads(val)
                    kwargs[key] = val
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        db.update_hook(hook_id, **kwargs)
        print(f"✅ 已更新钩子 #{hook_id}")
        return

    # ---- remove ----
    if cmd == "remove" and len(sys.argv) >= 3:
        hook_id = int(sys.argv[2])
        ok = db.delete_hook(hook_id)
        print(f"{'✅' if ok else '❌'} 删除钩子 #{hook_id}")
        return

    # ---- list ----
    if cmd == "list":
        hook_type = None
        enabled_only = False
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
                hook_type = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--enabled-only":
                enabled_only = True
                i += 1
            else:
                i += 1
        hooks = db.list_hooks(hook_type, enabled_only)
        if not hooks:
            print("(空) 无钩子")
            return
        print(f"📌 钩子列表 ({len(hooks)} 个):")
        for h in hooks:
            trig = json.loads(h['trigger_config'])
            act = json.loads(h['action_config'])
            trig_preview = json.dumps(trig)[:60]
            act_preview = json.dumps(act)[:40]
            icon = "✅" if h['enabled'] else "⏸️"
            fires = h['fire_count'] or 0
            last = f" 上次触发: {datetime.fromtimestamp(h['last_fired']).strftime('%H:%M')}" if h['last_fired'] else ""
            print(f"  {icon} #{h['id']:>3} {h['name']:<25} {h['hook_type']:<10} "
                  f"→ {h['action_type']:<12} 🔥{fires}")
            print(f"       ⤷ {trig_preview} → {act_preview} {last}")
        return

    # ---- get ----
    if cmd == "get" and len(sys.argv) >= 3:
        hook = db.get_hook(int(sys.argv[2]))
        if not hook:
            print("❌ 未找到")
            return
        for k, v in hook.items():
            if k in ('trigger_config', 'action_config'):
                print(f"  {k}: {json.dumps(json.loads(v), ensure_ascii=False, indent=2)}")
            elif k == 'last_fired' and v:
                print(f"  {k}: {datetime.fromtimestamp(v).isoformat()}")
            else:
                print(f"  {k}: {v}")
        cond = db.get_conditions(hook['id'])
        if cond:
            print(f"  conditions: {json.dumps(cond, ensure_ascii=False, indent=2)}")
        return

    # ---- condition ----
    if cmd == "condition" and len(sys.argv) >= 5:
        hook_id = int(sys.argv[2])
        logic = sys.argv[3]
        rules = json.loads(sys.argv[4])
        desc = " ".join(sys.argv[5:]) if len(sys.argv) > 5 else ""
        db.set_condition(hook_id, logic, rules, desc)
        print(f"✅ 已设置条件 #{hook_id}: {logic} / {len(rules)} 条规则")
        return

    # ---- match (PRE_MESSAGE) ----
    if cmd == "match" and "--text" in sys.argv:
        idx = sys.argv.index("--text")
        text = sys.argv[idx + 1]
        matched = engine.check_pre_message(text)
        if not matched:
            print("❌ 无匹配钩子")
            return
        print(f"✅ 匹配到 {len(matched)} 个钩子 (按优先级):")
        for h in matched:
            act = json.loads(h['action_config'])
            trig = json.loads(h['trigger_config'])
            print(f"  🔗 #{h['id']} {h['name']:<25} pri={h['priority']}")
            print(f"     触发: {json.dumps(trig, ensure_ascii=False)[:80]}")
            print(f"     动作: {json.dumps(act, ensure_ascii=False)[:80]}")
        return

    # ---- match (POST_TOOL) ----
    if cmd == "match" and "--tool" in sys.argv:
        idx = sys.argv.index("--tool")
        tool_name = sys.argv[idx + 1]
        tool_path = ""
        if "--path" in sys.argv:
            pidx = sys.argv.index("--path")
            tool_path = sys.argv[pidx + 1]
        matched = engine.check_post_tool(tool_name, {"path": tool_path})
        if not matched:
            print("❌ 无匹配后置钩子")
            return
        print(f"✅ 匹配到 {len(matched)} 个后置钩子:")
        for h in matched:
            print(f"  🔗 #{h['id']} {h['name']}")
        return

    # ---- fire ----
    if cmd == "fire" and len(sys.argv) >= 3:
        hook_id = int(sys.argv[2])
        # Check for --ctx
        ctx = {}
        if "--ctx" in sys.argv:
            cidx = sys.argv.index("--ctx")
            if cidx + 1 < len(sys.argv):
                ctx = json.loads(sys.argv[cidx + 1])
        result = engine.execute_hook(hook_id, "manual", ctx)
        icon = "✅" if result.get('success') else "❌"
        print(f"{icon} 触发 #{hook_id}:")
        print(f"   {json.dumps(result, ensure_ascii=False, indent=2)}")
        return

    # ---- fire-event ----
    if cmd == "fire-event" and len(sys.argv) >= 3:
        event = sys.argv[2]
        ctx = {}
        if "--ctx" in sys.argv:
            cidx = sys.argv.index("--ctx")
            if cidx + 1 < len(sys.argv):
                ctx = json.loads(sys.argv[cidx + 1])
        fired = engine.fire_event(event, ctx)
        print(f"📢 广播事件 '{event}': {len(fired)} 个钩子响应")
        for f in fired:
            print(f"  🔗 #{f['hook_id']} {f['name']} → {'✅' if f.get('success') else '❌'}")
        return

    # ---- log ----
    if cmd == "log":
        hook_id = None
        limit = 30
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--hook" and i + 1 < len(sys.argv):
                hook_id = int(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
                limit = int(sys.argv[i + 1])
                i += 2
            else:
                i += 1
        entries = db.get_log(hook_id, limit)
        if not entries:
            print("(空) 无日志")
            return
        print(f"📋 钩子日志 ({len(entries)} 条):")
        for e in entries:
            icon = "✅" if e['success'] else "❌"
            ctx = json.loads(e['context'])
            res = json.loads(e['result'])
            skills = res.get('skills', [])
            skill_info = f" → skill_view: {skills}" if skills else ""
            print(f"  {icon} #{e['hook_id']:>3} | {e['checkpoint']:<24} | "
                  f"{e['duration_ms']:.0f}ms | {e['created_at'][:19]}{skill_info}")
        return

    # ---- stats ----
    if cmd == "stats":
        s = db.get_stats()
        print("📊 钩子系统统计:")
        print(f"  总数: {s['total']}")
        print(f"  启用: {s['enabled']}")
        print(f"  总触发: {s['total_fires']}")
        print(f"  24h日志: {s['log_24h']}")
        print(f"  按类型:")
        for t, c in sorted(s['by_type'].items()):
            print(f"    {t:<12}: {c}")
        return

    # ---- events ----
    if cmd == "events":
        evts = db.list_events()
        if not evts:
            print("(空) 无事件")
            return
        print("📢 已注册事件:")
        for e in evts:
            bc = e['broadcast_count'] or 0
            last = f" 上次: {datetime.fromtimestamp(e['last_broadcast']).strftime('%H:%M')}" if e['last_broadcast'] else "未广播"
            print(f"  {e['event_name']:<25} 📡{bc}次 {last}")
        return

    print(f"❌ 未知命令: {cmd}")


if __name__ == "__main__":
    cli()
