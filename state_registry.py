#!/usr/bin/env python3
"""
统一工具状态器 (Unified Tool State Registry) v1
=============================================
覆盖：skills / MCP / tools / 插件 四类扩展点
核心原则：调用前先查状态，状态准确才能调用

与 Hermes Agent 的「我」形成关联：
- agent_state: 我的元状态（在线/忙碌/降级/离线）
- registry_state: 工具注册表状态（更新中/已锁定/正常）
- probe_state: 探测记录（每个工具最后的验证时间）

数据存储：memory_store.db 的 tool_registry 表
状态检查：调用前置拦截（通过 execute_code 或 cron 轮询）
"""

import sqlite3
import json
import time
import os
import sys
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

DB_PATH = "/opt/data/memory_store.db"

# Lazy import: hooks engine is optional
_hook_engine_instance = None
_HOOKS_AVAILABLE = os.path.exists("/opt/data/hooks/hooks_engine.py")


def _get_hook_engine():
    """Lazy singleton hook engine."""
    global _hook_engine_instance
    if _hook_engine_instance is None and _HOOKS_AVAILABLE:
        try:
            sys.path.insert(0, "/opt/data/hooks")
            import hooks_engine
            _hook_engine_instance = hooks_engine.HookEngine()
        except Exception as e:
            print(f"[state_registry] hooks engine unavailable: {e}")
    return _hook_engine_instance


@dataclass
class ToolEntry:
    """一个工具/技能/MCP/插件的完整状态记录"""
    # 标识
    name: str                # 唯一名称 e.g. "github-discover"
    kind: str                # skill | tool | mcp | plugin
    category: str = ""       # 所属分类 e.g. "workflow"

    # 核心状态
    enabled: bool = True     # 是否启用
    healthy: bool = True     # 健康检查是否通过
    version: int = 1         # 版本号
    status: str = "active"   # active | degraded | disabled | deprecated

    # 依赖关系
    dependencies: list = field(default_factory=list)  # 依赖的其他工具名
    conflicts_with: list = field(default_factory=list) # 冲突的工具名

    # 运行时元数据
    last_called: Optional[float] = None  # 上次调用时间戳
    call_count: int = 0                   # 总调用次数
    last_error: str = ""                  # 最后错误信息
    consecutive_failures: int = 0         # 连续失败次数

    # 关联到「我」
    agent_state_required: str = "online"  # online | any (任何状态都可调用)
    agent_state_effect: str = "none"      # none | busy | degrade（调用后对agent的影响）

    # 验证
    verified_at: Optional[float] = None   # 最后验证时间
    verified_by: str = ""                 # 验证方式 e.g. "probe_script" | "manual"

    def to_dict(self):
        return {k: v for k, v in asdict(self).items()}


class ToolStateRegistry:
    """统一工具状态器"""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""CREATE TABLE IF NOT EXISTS tool_registry (
            name                TEXT PRIMARY KEY,
            kind                TEXT NOT NULL,
            category            TEXT DEFAULT '',
            enabled             INTEGER DEFAULT 1,
            healthy             INTEGER DEFAULT 1,
            version             INTEGER DEFAULT 1,
            status              TEXT DEFAULT 'active',
            dependencies        TEXT DEFAULT '[]',
            conflicts_with      TEXT DEFAULT '[]',
            last_called         REAL,
            call_count          INTEGER DEFAULT 0,
            last_error          TEXT DEFAULT '',
            consecutive_failures INTEGER DEFAULT 0,
            agent_state_required TEXT DEFAULT 'online',
            agent_state_effect  TEXT DEFAULT 'none',
            verified_at         REAL,
            verified_by         TEXT DEFAULT '',
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        # 后置钩子表：工具调用后自动触发回调
        conn.execute("""CREATE TABLE IF NOT EXISTS post_hooks (
            hook_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            target_tool     TEXT NOT NULL,
            hook_type       TEXT NOT NULL DEFAULT 'script',
            hook_params     TEXT NOT NULL DEFAULT '{}',
            description     TEXT DEFAULT '',
            enabled         INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS agent_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # 初始化 agent 元状态
        conn.execute("""
            INSERT OR IGNORE INTO agent_meta (key, value) VALUES
                ('state', 'online'),
                ('uptime_start', ?),
                ('registry_lock', 'unlocked'),
                ('last_probe_all', '0')
        """, (time.time(),))
        conn.commit()
        conn.close()

    # ==================== 注册 ====================

    def register(self, entry: ToolEntry):
        """注册或更新一个工具"""
        d = entry.to_dict()
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO tool_registry
                (name, kind, category, enabled, healthy, version, status,
                 dependencies, conflicts_with, last_called, call_count,
                 last_error, consecutive_failures,
                 agent_state_required, agent_state_effect,
                 verified_at, verified_by, updated_at)
            VALUES
                (?,?,?,?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
                kind=excluded.kind,
                category=excluded.category,
                enabled=excluded.enabled,
                healthy=excluded.healthy,
                version=excluded.version,
                status=excluded.status,
                dependencies=excluded.dependencies,
                conflicts_with=excluded.conflicts_with,
                agent_state_required=excluded.agent_state_required,
                agent_state_effect=excluded.agent_state_effect,
                verified_at=excluded.verified_at,
                verified_by=excluded.verified_by,
                updated_at=CURRENT_TIMESTAMP
        """, (
            d['name'], d['kind'], d['category'],
            1 if d['enabled'] else 0,
            1 if d['healthy'] else 0,
            d['version'], d['status'],
            json.dumps(d['dependencies']),
            json.dumps(d['conflicts_with']),
            d['last_called'], d['call_count'],
            d['last_error'], d['consecutive_failures'],
            d['agent_state_required'], d['agent_state_effect'],
            d['verified_at'], d['verified_by']
        ))
        conn.commit()
        conn.close()
        return True

    # ==================== 状态检查（核心拦截器） ====================

    def can_call(self, name: str) -> tuple[bool, str]:
        """
        调用前检查：这个工具现在能被调用吗？
        返回: (允许调用?, 原因/消息)
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM tool_registry WHERE name = ?", (name,)
        ).fetchone()
        conn.close()

        if not row:
            return False, f"UNREGISTERED: '{name}' 未注册到状态器"

        if not row['enabled']:
            return False, f"DISABLED: '{name}' 已被禁用"

        if not row['healthy']:
            reason = row['last_error'] or "健康检查未通过"
            return False, f"UNHEALTHY: '{name}' {reason}"

        if row['status'] == 'disabled':
            return False, f"DISABLED: '{name}' 状态为 disabled"

        if row['status'] == 'deprecated':
            # 允许调用但警告
            return True, f"WARN: '{name}' 已弃用，建议迁移"

        # 检查 agent 状态
        agent_state = self._get_agent_state()
        required = row['agent_state_required']
        if required != 'any' and agent_state != required:
            return False, (
                f"AGENT_STATE_MISMATCH: '{name}' 要求 agent 状态为 '{required}'，"
                f"当前为 '{agent_state}'"
            )

        # 检查依赖
        deps = json.loads(row['dependencies'])
        for dep in deps:
            ok, msg = self.can_call(dep)
            if not ok:
                return False, f"DEP_FAIL: '{name}' 依赖 '{dep}' 不可用: {msg}"

        # 检查冲突
        conflicts = json.loads(row['conflicts_with'])
        for conflict in conflicts:
            c_row = conn = self._get_conn()
            cr = c_row.execute(
                "SELECT status, enabled FROM tool_registry WHERE name = ?",
                (conflict,)
            ).fetchone()
            c_row.close()
            if cr and cr['enabled'] and cr['status'] == 'active':
                return False, f"CONFLICT: '{name}' 与 '{conflict}' 冲突（两者都活跃）"

        return True, "OK"

    # ==================== 调用后记录 ====================

    def record_call(self, name: str, success: bool, error: str = ""):
        """记录一次工具调用结果"""
        conn = self._get_conn()
        now = time.time()

        if success:
            conn.execute("""
                UPDATE tool_registry SET
                    last_called = ?,
                    call_count = call_count + 1,
                    last_error = '',
                    consecutive_failures = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
            """, (now, name))
        else:
            conn.execute("""
                UPDATE tool_registry SET
                    last_called = ?,
                    call_count = call_count + 1,
                    last_error = ?,
                    consecutive_failures = consecutive_failures + 1,
                    healthy = CASE
                        WHEN consecutive_failures >= 2 THEN 0
                        ELSE healthy
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
            """, (now, error[:500], name))

        conn.commit()

        # Auto-fire hooks engine tool_post hooks
        if _HOOKS_AVAILABLE and success:
            try:
                engine = _get_hook_engine()
                if engine:
                    matched = engine.check_post_tool(name)
                    for hook in matched:
                        engine._execute_hook(hook, checkpoint=f"tool_post:{name}",
                                             context={"tool": name, "success": success})
            except Exception:
                pass  # hooks engine errors should not break state_registry

        conn.close()

    # ==================== 后置钩子系统 ====================

    def add_post_hook(self, target_tool: str, hook_type: str = "script",
                       hook_params: dict = None, description: str = ""):
        """注册一个后置钩子：当 target_tool 被调用后，自动执行"""
        params = hook_params or {}
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO post_hooks (target_tool, hook_type, hook_params, description) VALUES (?,?,?,?)",
            (target_tool, hook_type, json.dumps(params), description)
        )
        hook_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
        return hook_id

    def remove_post_hook(self, hook_id: int):
        conn = self._get_conn()
        conn.execute("DELETE FROM post_hooks WHERE hook_id = ?", (hook_id,))
        affected = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        conn.close()
        return affected > 0

    def list_post_hooks(self, target_tool: str = None) -> list:
        conn = self._get_conn()
        if target_tool:
            rows = conn.execute(
                "SELECT * FROM post_hooks WHERE target_tool = ? AND enabled = 1 ORDER BY hook_id",
                (target_tool,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM post_hooks WHERE enabled = 1 ORDER BY target_tool, hook_id"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def trigger_file_write_hook(self, file_path: str):
        """文件写入后的自动触发：对 post_hooks 中所有 write_file 钩子执行回调"""
        hooks = self.list_post_hooks("write_file")
        results = []
        for hook in hooks:
            params = json.loads(hook['hook_params'])
            command = params.get('command', 'python3 /opt/data/scripts/download_gate.py check')
            full_cmd = f"{command} {file_path}"
            try:
                import subprocess
                r = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=30)
                results.append({
                    "hook_id": hook['hook_id'],
                    "exit_code": r.returncode,
                    "stdout": r.stdout.strip(),
                    "stderr": r.stderr.strip()
                })
            except Exception as e:
                results.append({"hook_id": hook['hook_id'], "error": str(e)})
        return results

    # ==================== Hooks Engine Integration ====================

    def check_pre_message_hooks(self, user_message: str) -> list[dict]:
        """Check hooks engine for keyword matches before processing a message."""
        engine = _get_hook_engine()
        if not engine:
            return []
        return engine.check_pre_message(user_message)

    def check_post_tool_hooks(self, tool_name: str, tool_args: dict = None,
                              tool_result: dict = None) -> list[dict]:
        """Check hooks engine for tool_post matches after a tool call."""
        engine = _get_hook_engine()
        if not engine:
            return []
        return engine.check_post_tool(tool_name, tool_args, tool_result)

    def fire_hook_event(self, event_name: str, context: dict = None) -> list[dict]:
        """Fire a system event through the hooks engine."""
        engine = _get_hook_engine()
        if not engine:
            return []
        return engine.fire_event(event_name, context)

    def execute_hook_by_id(self, hook_id: int, checkpoint: str = "manual",
                           context: dict = None) -> dict:
        """Execute a specific hook by its ID."""
        engine = _get_hook_engine()
        if not engine:
            return {"error": "hooks engine unavailable"}
        return engine.execute_hook(hook_id, checkpoint, context or {})

    # ==================== Agent 元状态 ====================

    def _get_agent_state(self) -> str:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM agent_meta WHERE key = 'state'"
        ).fetchone()
        conn.close()
        return row['value'] if row else 'unknown'

    def set_agent_state(self, state: str):
        """设置我的元状态: online | busy | degraded | offline"""
        valid = ['online', 'busy', 'degraded', 'offline']
        if state not in valid:
            raise ValueError(f"无效的 agent 状态: {state}，有效值: {valid}")
        conn = self._get_conn()
        conn.execute(
            "UPDATE agent_meta SET value = ? WHERE key = 'state'",
            (state,)
        )
        conn.commit()
        conn.close()

    # ==================== 批量探测 ====================

    def probe_all(self):
        """
        对所有注册的工具进行状态检查。
        返回摘要报告，包含：总数 / 健康 / 不健康 / 禁用 / 未验证
        """
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM tool_registry").fetchall()
        conn.close()

        now = time.time()
        summary = {
            "total": len(rows),
            "healthy": 0,
            "unhealthy": 0,
            "disabled": 0,
            "unverified": 0,
            "by_kind": {},
        }

        for row in rows:
            kind = row['kind']
            if kind not in summary['by_kind']:
                summary['by_kind'][kind] = {'total': 0, 'healthy': 0, 'unhealthy': 0}

            summary['by_kind'][kind]['total'] += 1

            if not row['enabled']:
                summary['disabled'] += 1
                continue

            if row['healthy']:
                summary['healthy'] += 1
                summary['by_kind'][kind]['healthy'] += 1
            else:
                summary['unhealthy'] += 1
                summary['by_kind'][kind]['unhealthy'] += 1

            if not row['verified_at'] or (now - row['verified_at']) > 86400:
                summary['unverified'] += 1

        # 更新时间戳
        conn = self._get_conn()
        conn.execute(
            "UPDATE agent_meta SET value = ? WHERE key = 'last_probe_all'",
            (str(now),)
        )
        conn.commit()
        conn.close()

        return summary

    # ==================== 查询 ====================

    def get(self, name: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM tool_registry WHERE name = ?", (name,)
        ).fetchone()
        conn.close()

        if not row:
            return None

        d = dict(row)
        d['dependencies'] = json.loads(d['dependencies'])
        d['conflicts_with'] = json.loads(d['conflicts_with'])
        d['enabled'] = bool(d['enabled'])
        d['healthy'] = bool(d['healthy'])
        return d

    def list_by_kind(self, kind: str = None) -> list[dict]:
        conn = self._get_conn()
        if kind:
            rows = conn.execute(
                "SELECT * FROM tool_registry WHERE kind = ? ORDER BY name",
                (kind,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tool_registry ORDER BY kind, name"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def list_unhealthy(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM tool_registry WHERE healthy = 0 AND enabled = 1"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


    # ==================== 类级别统筹 ====================

    def kind_overview(self) -> dict:
        """按 kind 类别输出统筹摘要——skill/tool/mcp/plugin 各有多少"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT kind, COUNT(*) as total, "
            "SUM(CASE WHEN enabled=1 AND healthy=1 THEN 1 ELSE 0 END) as ready, "
            "SUM(CASE WHEN enabled=1 AND healthy=0 THEN 1 ELSE 0 END) as broken, "
            "SUM(CASE WHEN enabled=0 THEN 1 ELSE 0 END) as disabled "
            "FROM tool_registry GROUP BY kind ORDER BY kind"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM tool_registry").fetchone()['c']
        conn.close()
        return {
            "total": total,
            "kinds": {r['kind']: dict(r) for r in rows}
        }

    def dep_chain(self, name: str, depth: int = 0, max_depth: int = 10) -> dict:
        """递归展示一个工具的依赖链（跨 kind）"""
        if depth > max_depth:
            return {"name": name, "kind": "?", "error": "MAX_DEPTH_EXCEEDED"}
        conn = self._get_conn()
        row = conn.execute(
            "SELECT name, kind, enabled, healthy, status, dependencies FROM tool_registry WHERE name = ?",
            (name,)
        ).fetchone()
        conn.close()
        if not row:
            return {"name": name, "kind": "?", "error": "UNREGISTERED"}
        deps = json.loads(row['dependencies'])
        return {
            "name": row['name'],
            "kind": row['kind'],
            "enabled": bool(row['enabled']),
            "healthy": bool(row['healthy']),
            "status": row['status'],
            "dependencies": [self.dep_chain(d, depth + 1, max_depth) for d in deps]
        }

    def kind_health(self, kind: str) -> list[dict]:
        """获取某个 kind 类别下所有工具的健康详情"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name, enabled, healthy, status, version, "
            "last_error, consecutive_failures, verified_at "
            "FROM tool_registry WHERE kind = ? ORDER BY name",
            (kind,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# ==================== CLI 入口 ====================

def cli():
    """完整的命令行接口——支持 state_registry.py 统筹管理所有技能/工具/MCP/插件"""
    import sys
    registry = ToolStateRegistry()

    if len(sys.argv) < 2:
        print("用法: python3 state_registry.py <命令> [参数...]")
        print("")
        print("📋 状态管理:")
        print("  register <name> <kind>    注册一个工具 (kind: skill|tool|mcp|plugin)")
        print("  check <name>              检查工具是否可调用")
        print("  probe                     全量探测")
        print("  report                    查看完整状态报告")
        print("  overview                  按 kind 分类统筹概览（一瞥即知）")
        print("")
        print("🔍 查询:")
        print("  list [kind]               列出已注册的工具")
        print("  unhealthy                 列出不健康工具")
        print("  kind-health <kind>        查看某类 (skill/tool/mcp/plugin) 的健康详情")
        print("  deps <name>               递归展示依赖链")
        print("")
        print("🔄 Agent 控制:")
        print("  set-agent <state>         设置 agent 状态 (online|busy|degraded|offline)")
        print("")
        print("🔗 后置钩子:")
        print("  register-hook <tool> [--cmd <command>]  注册后置钩子 (默认: download_gate.py check)")
        print("  remove-hook <hook_id>                   移除钩子")
        print("  list-hooks [tool]                       列出钩子")
        print("  trigger-hook <path>                     手动触发文件写入钩子")
        return

    cmd = sys.argv[1]

    if cmd == "register" and len(sys.argv) >= 4:
        entry = ToolEntry(name=sys.argv[2], kind=sys.argv[3])
        registry.register(entry)
        print(f"✅ 已注册: {entry.name} ({entry.kind})")

    elif cmd == "check" and len(sys.argv) >= 3:
        ok, msg = registry.can_call(sys.argv[2])
        print(f"{'✅' if ok else '❌'} {msg}")

    elif cmd == "report":
        s = registry.probe_all()
        print(f"📊 工具状态报告")
        print(f"   总数: {s['total']}")
        print(f"   ✅ 健康: {s['healthy']}")
        print(f"   ❌ 不健康: {s['unhealthy']}")
        print(f"   ⏸️  禁用: {s['disabled']}")
        print(f"   ⚠️  未验证: {s['unverified']}")
        print(f"   按类型:")
        for kind, stats in s['by_kind'].items():
            print(f"     {kind}: {stats['total']} 个 ({stats['healthy']} 健康 / {stats['unhealthy']} 不健康)")

    elif cmd == "probe":
        s = registry.probe_all()
        print(f"🔍 探测完成: {s['healthy']}/{s['total']} 健康")

    elif cmd == "set-agent" and len(sys.argv) >= 3:
        registry.set_agent_state(sys.argv[2])
        print(f"🔄 Agent 状态已设为: {sys.argv[2]}")

    elif cmd == "list":
        kind = sys.argv[2] if len(sys.argv) >= 3 else None
        tools = registry.list_by_kind(kind)
        if not tools:
            print("(空)")
        for t in tools:
            status_icon = {
                'active': '✅', 'degraded': '⚠️', 'disabled': '⏸️', 'deprecated': '📦'
            }.get(t['status'], '❓')
            print(f"  {status_icon} {t['name']} ({t['kind']}) v{t['version']} — {t['status']}")
            if not t['healthy'] and t['enabled']:
                print(f"     ❌ 异常: {t['last_error'][:80]}")

    elif cmd == "unhealthy":
        tools = registry.list_unhealthy()
        if not tools:
            print("✅ 所有启用工具都健康")
        else:
            for t in tools:
                print(f"❌ {t['name']} ({t['kind']}): {t['last_error'][:100]}")

    elif cmd == "overview":
        ov = registry.kind_overview()
        print(f"📊 工具统筹概览 (总计 {ov['total']} 个)")
        print(f"{'类别':<12} {'总数':>5} {'就绪':>5} {'故障':>5} {'禁用':>5}")
        print("-" * 40)
        for kind, s in sorted(ov['kinds'].items()):
            print(f"{kind:<12} {s['total']:>5} ✅{s['ready']:>3} ❌{s['broken']:>3} ⏸️{s['disabled']:>3}")

    elif cmd == "deps" and len(sys.argv) >= 3:
        chain = registry.dep_chain(sys.argv[2])
        def _print_dep(d, indent=0):
            icon = "✅" if d.get('enabled') and d.get('healthy') else "❌"
            err = f" — {d.get('error','')}" if 'error' in d else ""
            print(f"{'  ' * indent}{icon} {d['name']} ({d.get('kind','?')}){err}")
            for dep in d.get('dependencies', []):
                _print_dep(dep, indent + 1)
        _print_dep(chain)

    elif cmd == "kind-health" and len(sys.argv) >= 3:
        kind = sys.argv[2]
        tools = registry.kind_health(kind)
        if not tools:
            print(f"(空) — 没有注册类型为 '{kind}' 的工具")
        else:
            print(f"🔍 {kind} 类健康详情 ({len(tools)} 个):")
            for t in tools:
                icon = "✅" if t['healthy'] and t['enabled'] else "❌"
                print(f"  {icon} {t['name']} v{t['version']} — {t['status']}"
                      f"{' 异常: '+t['last_error'][:60] if not t['healthy'] and t['enabled'] else ''}")

    elif cmd == "register-hook" and len(sys.argv) >= 3:
        target_tool = sys.argv[2]
        command = "python3 /opt/data/scripts/download_gate.py check"
        description = f"Download Gate check after {target_tool}"
        if "--cmd" in sys.argv:
            idx = sys.argv.index("--cmd")
            if idx + 1 < len(sys.argv):
                command = sys.argv[idx + 1]
        if "--desc" in sys.argv:
            idx = sys.argv.index("--desc")
            if idx + 1 < len(sys.argv):
                description = sys.argv[idx + 1]
        hook_id = registry.add_post_hook(
            target_tool=target_tool,
            hook_type="script",
            hook_params={"command": command},
            description=description
        )
        print(f"🔗 已注册后置钩子 #{hook_id}: {target_tool} → {command}")

    elif cmd == "remove-hook" and len(sys.argv) >= 3:
        ok = registry.remove_post_hook(int(sys.argv[2]))
        print(f"{'✅' if ok else '❌'} 移除钩子 #{sys.argv[2]}")

    elif cmd == "list-hooks":
        tool = sys.argv[2] if len(sys.argv) >= 3 else None
        hooks = registry.list_post_hooks(tool)
        if not hooks:
            print("(空) 无活跃钩子")
        else:
            print(f"🔗 后置钩子 ({len(hooks)} 个):")
            for h in hooks:
                params = json.loads(h['hook_params'])
                cmd = params.get('command', '?')
                print(f"  #{h['hook_id']} {h['target_tool']}: `{cmd}` [{h['description']}]")

    elif cmd == "trigger-hook" and len(sys.argv) >= 3:
        path = sys.argv[2]
        results = registry.trigger_file_write_hook(path)
        for r in results:
            if 'error' in r:
                print(f"❌ Hook #{r['hook_id']}: {r['error']}")
            else:
                print(f"🔗 Hook #{r['hook_id']}: exit={r['exit_code']} | {r['stdout']}")

    # ==================== Hooks Engine CLI ====================

    elif cmd == "he-fire" and len(sys.argv) >= 3:
        """Fire a hooks engine event. Usage: python3 state_registry.py he-fire <event>"""
        results = registry.fire_hook_event(sys.argv[2])
        print(f"🔥 已触发事件 '{sys.argv[2]}': {len(results)} 个钩子响应")
        for r in results:
            status = "✅" if r.get('success', True) else "❌"
            print(f"  {status} #{r.get('hook_id')} {r.get('name','?')}: {r.get('stdout','')[:80]}")

    elif cmd == "he-check-msg" and len(sys.argv) >= 3:
        """Check user message for keyword hooks. Usage: python3 state_registry.py he-check-msg <message>"""
        matched = registry.check_pre_message_hooks(" ".join(sys.argv[2:]))
        if not matched:
            print("(无匹配)")
        else:
            print(f"🔍 匹配到 {len(matched)} 个钩子:")
            for h in matched:
                print(f"  #{h['id']} {h['name']} (type={h['hook_type']})")

    elif cmd == "he-list":
        """List all hooks engine hooks."""
        engine = _get_hook_engine()
        if not engine:
            print("hooks engine 不可用")
        else:
            hooks = engine.db.list_hooks()
            print(f"📋 hooks engine: {len(hooks)} 个钩子")
            for h in hooks:
                print(f"  #{h['id']} {h['name']:<35} {h['hook_type']:<10} {'✅' if h['enabled'] else '⏸️'}  fires={h['fire_count']}")

    elif cmd == "he-stats":
        """Hooks engine stats."""
        engine = _get_hook_engine()
        if not engine:
            print("hooks engine 不可用")
        else:
            hooks = engine.db.list_hooks()
            by_type = {}
            for h in hooks:
                t = h['hook_type']
                by_type.setdefault(t, 0)
                by_type[t] += 1
            print("📊 hooks engine 统计:")
            print(f"  总钩子: {len(hooks)}")
            for t, c in sorted(by_type.items()):
                print(f"    {t}: {c}")
            print(f"  DB路径: /opt/data/hooks/hooks.db")


if __name__ == "__main__":
    cli()
