#!/usr/bin/env python3
"""Hermes Container Web GUI - 在容器内运行，宿主机浏览器访问"""
import json, os, subprocess, sys, glob, sqlite3, time, re, yaml, struct
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
from pathlib import Path
from datetime import datetime
from typing import Optional, List

import numpy as np
import urllib.request as urlreq

PORT = 8644
DATA = Path("/opt/data")
HTML_FILE = DATA / "gui.html"

def run(cmd: str, timeout: int = 15) -> str:
    try:
        r = subprocess.run(["sh", "-c", cmd], capture_output=True, timeout=timeout)
        return r.stdout.decode("utf-8", errors="replace").strip()
    except: return ""

def read_file(path: Path) -> str:
    try: return path.read_text(encoding="utf-8", errors="replace")
    except: return ""

def json_bytes(data) -> bytes:
    return json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")

def parse_yaml_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from SKILL.md files."""
    if not content.startswith("---"):
        return {}
    try:
        end = content.index("---", 3)
        fm = yaml.safe_load(content[3:end])
        return fm if isinstance(fm, dict) else {}
    except:
        return {}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/" or p == "/gui.html":
            return self.serve_html()
        elif p == "/api/status":
            return self.json(self.get_status())
        elif p == "/api/memory":
            return self.json(self.get_memory())
        elif p == "/api/config":
            return self.text(read_file(DATA / "config.yaml"))
        elif p == "/api/logs":
            return self.text(run("hermes doctor --tail 50 2>&1 || echo 'no logs'", 10))
        elif p == "/api/sessions":
            return self.json(self.get_sessions())
        elif p == "/api/skills":
            return self.json(self.get_skills())
        elif p.startswith("/api/session/"):
            sid = unquote(p[len("/api/session/"):])
            return self.json(self.get_session_detail(sid))
        elif p == "/api/facts":
            return self.json(self.get_facts())
        elif p == "/api/health":
            return self.json(self.get_health())
        elif p == "/api/version":
            return self.text(run("hermes --version 2>&1", 5))
        elif p == "/api/search":
            query = unquote(p[len("/api/search?q="):]) if "?q=" in p else ""
            if not query:
                qs = urlparse(self.path).query
                for param in qs.split("&"):
                    if param.startswith("q="):
                        query = unquote(param[2:])
            if not query:
                return self.json({"error": "q parameter required"}, 400)
            top_k = 10
            session_id = None
            for param in urlparse(self.path).query.split("&"):
                if param.startswith("k="):
                    try: top_k = int(param[2:])
                    except: pass
                if param.startswith("session="):
                    session_id = param[8:]
            return self.json(self.semantic_search(query, top_k, session_id))
        elif p == "/api/embed/sync":
            return self.json(self.sync_embeddings())
        else:
            self.json({"error": "not found"}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode()) if length else {}
        if p == "/api/chat":
            prompt = body.get("prompt", "")
            model = body.get("model", "")
            if not prompt:
                return self.json({"error": "prompt required"}, 400)
            cmd = f'hermes -z {shlex_quote(prompt)}'
            if model: cmd += f" -m {shlex_quote(model)}"
            out = run(cmd, 120)
            return self.json({"response": out})
        elif p == "/api/action":
            action = body.get("action", "")
            cmds = {
                "restart": "hermes gateway restart 2>&1",
                "doctor": "hermes doctor --fix 2>&1",
                "reload-config": "hermes config reload 2>&1",
                "restart-container": "kill 1 2>&1 || echo 'cannot restart container'",
            }
            if action in cmds:
                return self.json({"result": run(cmds[action], 30)})
            return self.json({"error": "unknown action"}, 400)
        else:
            return self.json({"error": "not found"}, 404)

    def get_status(self):
        gw = run("hermes gateway status 2>&1", 5)
        gw_ok = "is running" in gw or "running" in gw
        state_file = DATA / "gateway_state.json"
        wechat_state = "unknown"
        wechat_acct = ""
        if state_file.exists():
            try:
                sd = json.loads(state_file.read_text())
                wx = sd.get("platforms", {}).get("weixin", {})
                wechat_state = wx.get("state", "unknown")
                wechat_acct = wx.get("account", wx.get("wxid", ""))
            except: pass
        ollama = "unreachable"
        ollama_models = []
        try:
            import urllib.request
            r = urllib.request.urlopen("http://host.docker.internal:11434/api/tags", timeout=5)
            od = json.loads(r.read())
            ollama = "reachable"
            ollama_models = [m["name"] for m in od.get("models", [])[:5]]
        except: pass
        cfg = read_file(DATA / "config.yaml")
        default_model = "unknown"
        provider = "unknown"
        for line in cfg.split("\n"):
            if "default:" in line: default_model = line.split(":", 1)[1].strip()
            if "provider:" in line and "deepseek" in line: provider = "deepseek"
        uptime = run("cat /proc/uptime 2>/dev/null | awk '{print int($1/60) \"m\"}'", 3) or "—"
        return {
            "gateway": "running" if gw_ok else "stopped",
            "wechat": wechat_state,
            "wechat_account": wechat_acct,
            "ollama": ollama,
            "ollama_models": ollama_models,
            "model": default_model,
            "provider": provider,
            "uptime": uptime,
            "container": "running",
        }

    def get_memory(self):
        um = read_file(DATA / "memories/USER.md")
        mm = read_file(DATA / "memories/MEMORY.md")
        facts = []
        db_path = DATA / "memory_store.db"
        if db_path.exists():
            try:
                db = sqlite3.connect(str(db_path))
                cur = db.execute("SELECT content FROM facts ORDER BY fact_id DESC LIMIT 50")
                facts = [r[0] for r in cur.fetchall()]
                db.close()
            except: pass
        soul = read_file(DATA / "SOUL.md") if (DATA / "SOUL.md").exists() else ""
        return {
            "user_md": um,
            "agent_md": mm,
            "soul": soul,
            "facts": facts,
            "fact_count": len(facts),
            "user_size": len(um),
            "agent_size": len(mm),
        }

    def get_sessions(self):
        db_path = DATA / "state.db"
        if not db_path.exists():
            return self._get_sessions_legacy()
        try:
            db = sqlite3.connect(str(db_path))
            cur = db.cursor()
            cur.execute("""
                SELECT s.id, s.source, s.model, s.started_at, s.ended_at,
                       COUNT(m.id) as msg_count,
                       MAX(m.timestamp) as last_msg_ts
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                GROUP BY s.id
                ORDER BY COALESCE(last_msg_ts, s.started_at) DESC
                LIMIT 30
            """)
            sessions = []
            for row in cur.fetchall():
                sid, source, model, started, ended, msg_count, last_ts = row
                # Get first user message as preview
                preview = ""
                try:
                    cur2 = db.execute(
                        "SELECT content FROM messages WHERE session_id=? AND role='user' ORDER BY timestamp ASC LIMIT 1",
                        (sid,)
                    )
                    r = cur2.fetchone()
                    if r: preview = (r[0] or "")[:120]
                except: pass
                sessions.append({
                    "id": sid,
                    "preview": preview,
                    "platform": source or "unknown",
                    "model": model or "",
                    "msg_count": msg_count or 0,
                    "updated": datetime.fromtimestamp(last_ts).isoformat()[:19] if last_ts else (datetime.fromtimestamp(started).isoformat()[:19] if started else ""),
                    "started": datetime.fromtimestamp(started).isoformat()[:19] if started else "",
                })
            db.close()
            return sessions
        except Exception as e:
            return self._get_sessions_legacy()

    def _get_sessions_legacy(self):
        sdir = DATA / "sessions"
        sessions = []
        if sdir.is_dir():
            files = sorted(sdir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)[:30]
            for f in files:
                sid = f.stem
                lines = f.read_text(encoding="utf-8", errors="replace").split("\n")
                preview = ""
                platform = ""
                msg_count = 0
                for line in lines:
                    if not line.strip(): continue
                    try:
                        entry = json.loads(line)
                        role = entry.get("role", "")
                        content = entry.get("content", "")
                        if role == "session_meta":
                            platform = entry.get("platform", "")
                        elif role in ("user", "assistant") and content:
                            msg_count += 1
                            if role == "user" and not preview:
                                preview = content[:120]
                    except: pass
                sessions.append({
                    "id": sid, "preview": preview,
                    "platform": platform,
                    "msg_count": msg_count,
                    "updated": datetime.fromtimestamp(f.stat().st_mtime).isoformat()[:19],
                    "size": f.stat().st_size,
                })
        return sessions

    def get_session_detail(self, sid: str):
        db_path = DATA / "state.db"
        if db_path.exists():
            try:
                db = sqlite3.connect(str(db_path))
                # Get session meta
                cur = db.execute("SELECT source, model, started_at FROM sessions WHERE id=?", (sid,))
                row = cur.fetchone()
                if not row:
                    db.close()
                    return {"error": "session not found"}
                meta = {
                    "platform": row[0] or "unknown",
                    "model": row[1] or "",
                    "timestamp": datetime.fromtimestamp(row[2]).isoformat() if row[2] else "",
                }
                # Get messages (limit to 200 most recent)
                cur = db.execute("""
                    SELECT role, content, timestamp
                    FROM messages
                    WHERE session_id=? AND role IN ('user', 'assistant')
                    ORDER BY timestamp DESC
                    LIMIT 200
                """, (sid,))
                messages = []
                for r in cur.fetchall():
                    if r[1]:
                        messages.append({
                            "role": r[0],
                            "content": r[1][:3000],
                            "timestamp": datetime.fromtimestamp(r[2]).isoformat() if r[2] else "",
                        })
                messages.reverse()  # Chronological order
                db.close()
                return {"id": sid, "meta": meta, "messages": messages, "msg_count": len(messages)}
            except:
                pass
        # Fallback to legacy JSONL
        return self._get_session_detail_legacy(sid)

    def _get_session_detail_legacy(self, sid: str):
        sdir = DATA / "sessions"
        fpath = sdir / f"{sid}.jsonl"
        if not fpath.exists():
            return {"error": "session not found"}
        messages = []
        meta = {}
        for line in fpath.read_text(encoding="utf-8", errors="replace").split("\n"):
            if not line.strip(): continue
            try:
                entry = json.loads(line)
                role = entry.get("role", "")
                if role == "session_meta":
                    meta = {
                        "model": entry.get("model", ""),
                        "platform": entry.get("platform", ""),
                        "timestamp": entry.get("timestamp", ""),
                    }
                elif role in ("user", "assistant"):
                    content = entry.get("content", "")
                    if content:
                        messages.append({
                            "role": role,
                            "content": content[:3000],
                            "timestamp": entry.get("timestamp", ""),
                        })
            except: pass
        return {"id": sid, "meta": meta, "messages": messages, "msg_count": len(messages)}

    def get_skills(self):
        skills = []
        registry_path = DATA / "skills" / "SKILL_REGISTRY.yaml"
        registry = {}
        if registry_path.exists():
            try:
                reg_content = registry_path.read_text(encoding="utf-8", errors="replace")
                reg_data = yaml.safe_load(reg_content)
                if isinstance(reg_data, list):
                    for item in reg_data:
                        if isinstance(item, dict) and "name" in item:
                            registry[item["name"]] = item
            except: pass

        sdir = DATA / "skills"
        if sdir.is_dir():
            for skill_dir in sorted(sdir.rglob("SKILL.md")):
                content = skill_dir.read_text(encoding="utf-8", errors="replace")
                fm = parse_yaml_frontmatter(content)
                name = fm.get("name", skill_dir.parent.name)
                desc = fm.get("description", "")
                category = fm.get("category", "")
                platforms = fm.get("platforms", [])
                related = fm.get("related_skills", [])
                reg_info = registry.get(name, {})

                body = content
                if "---" in content:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        body = parts[2].strip()

                lines = body.split("\n")
                summary = ""
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("---"):
                        summary = line[:200]
                        break

                skills.append({
                    "name": name,
                    "description": desc,
                    "category": category or reg_info.get("category", ""),
                    "platforms": platforms,
                    "related_skills": related or reg_info.get("related", "").split(";") if reg_info.get("related") else [],
                    "status": reg_info.get("status", "active"),
                    "created": reg_info.get("created", ""),
                    "last_updated": reg_info.get("last_updated", ""),
                    "summary": summary,
                    "content": content[:3000],
                    "path": str(skill_dir.relative_to(DATA)),
                })
        return skills

    def get_facts(self, query: str = ""):
        db_path = DATA / "memory_store.db"
        if not db_path.exists(): return []
        try:
            db = sqlite3.connect(str(db_path))
            if query:
                cur = db.execute("SELECT content FROM facts WHERE content LIKE ? LIMIT 20", (f"%{query}%",))
            else:
                cur = db.execute("SELECT fact_id, content, trust_score, created_at FROM facts ORDER BY fact_id DESC LIMIT 50")
            rows = cur.fetchall()
            db.close()
            return [{"id": r[0], "content": r[1], "trust": r[2] if len(r) > 2 else 0.5, "created": r[3] if len(r) > 3 else ""} for r in rows]
        except:
            return []

    def get_health(self):
        gw = run("hermes gateway status 2>&1", 5)
        wechat_state = "unknown"
        sf = DATA / "gateway_state.json"
        if sf.exists():
            try:
                sd = json.loads(sf.read_text())
                wechat_state = sd.get("platforms", {}).get("weixin", {}).get("state", "unknown")
            except: pass
        return {
            "gateway": "ok" if "running" in gw else "fail",
            "wechat": wechat_state,
            "memory_store": (DATA / "memory_store.db").exists(),
            "memories_dir": (DATA / "memories").is_dir(),
            "skills_dir": (DATA / "skills").is_dir(),
            "config_exists": (DATA / "config.yaml").exists(),
            "timestamp": datetime.now().isoformat()[:19],
        }

    def serve_html(self):
        try:
            content = read_file(HTML_FILE)
            b = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b)
        except Exception as e:
            self.send_error(500, str(e))

    def json(self, data, code=200):
        b = json_bytes(data)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)

    def text(self, data, code=200):
        b = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[GUI] {args[0]} {args[1]}\n")

    # ===== 语义搜索 =====
    def get_embedding(self, text: str):
        """调用 Ollama 生成嵌入"""
        try:
            data = json.dumps({"model": "nomic-embed-text", "prompt": text[:500]}).encode()
            req = urlreq.Request(
                "http://host.docker.internal:11434/api/embeddings",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urlreq.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                return np.array(result["embedding"], dtype=np.float32)
        except Exception as e:
            sys.stderr.write(f"Embedding error: {e}\n")
            return None

    def emb_to_blob(self, emb) -> bytes:
        return struct.pack(f'{len(emb)}f', *emb.tolist())

    def blob_to_emb(self, blob: bytes):
        n = len(blob) // 4
        return np.array(struct.unpack(f'{n}f', blob), dtype=np.float32)

    def init_vector_table(self, db):
        db.execute("""
            CREATE TABLE IF NOT EXISTS message_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                message_id INTEGER,
                role TEXT,
                content TEXT,
                timestamp REAL,
                embedding BLOB,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                UNIQUE(session_id, message_id)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_emb_session ON message_embeddings(session_id)")
        db.commit()

    def sync_embeddings(self):
        """同步消息嵌入到向量表"""
        db_path = DATA / "state.db"
        if not db_path.exists():
            return {"error": "state.db not found"}
        try:
            db = sqlite3.connect(str(db_path))
            self.init_vector_table(db)
            # 获取未同步的消息
            cur = db.execute("""
                SELECT m.session_id, m.id, m.role, m.content, m.timestamp
                FROM messages m
                WHERE m.role IN ('user', 'assistant')
                  AND m.content IS NOT NULL
                  AND LENGTH(m.content) > 10
                  AND NOT EXISTS (
                      SELECT 1 FROM message_embeddings e 
                      WHERE e.session_id = m.session_id AND e.message_id = m.id
                  )
                ORDER BY m.timestamp DESC
                LIMIT 200
            """)
            messages = cur.fetchall()
            if not messages:
                db.close()
                return {"synced": 0, "message": "No new messages"}
            synced = 0
            for msg in messages:
                emb = self.get_embedding(msg[3])
                if emb is not None:
                    db.execute("""
                        INSERT OR REPLACE INTO message_embeddings 
                        (session_id, message_id, role, content, timestamp, embedding)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (msg[0], msg[1], msg[2], msg[3], msg[4], self.emb_to_blob(emb)))
                    synced += 1
                    if synced % 10 == 0:
                        db.commit()
            db.commit()
            db.close()
            return {"synced": synced, "total": len(messages)}
        except Exception as e:
            return {"error": str(e)}

    def semantic_search(self, query: str, top_k: int = 10, session_id: str = None):
        """语义相似度搜索"""
        db_path = DATA / "state.db"
        if not db_path.exists():
            return {"error": "state.db not found"}
        try:
            # 获取查询嵌入
            query_emb = self.get_embedding(query)
            if query_emb is None:
                return {"error": "Failed to generate embedding"}
            db = sqlite3.connect(str(db_path))
            self.init_vector_table(db)
            # 查询嵌入
            if session_id:
                cur = db.execute(
                    "SELECT session_id, message_id, role, content, timestamp, embedding "
                    "FROM message_embeddings WHERE session_id=?",
                    (session_id,)
                )
            else:
                cur = db.execute(
                    "SELECT session_id, message_id, role, content, timestamp, embedding "
                    "FROM message_embeddings"
                )
            results = []
            for row in cur.fetchall():
                emb = self.blob_to_emb(row[5])
                norm_q = np.linalg.norm(query_emb)
                norm_e = np.linalg.norm(emb)
                sim = float(np.dot(query_emb, emb) / (norm_q * norm_e)) if norm_q > 0 and norm_e > 0 else 0
                results.append({
                    "session_id": row[0],
                    "message_id": row[1],
                    "role": row[2],
                    "content": row[3][:300],
                    "timestamp": datetime.fromtimestamp(row[4]).strftime('%Y-%m-%d %H:%M') if row[4] else "",
                    "similarity": round(sim, 4)
                })
            db.close()
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return {"query": query, "results": results[:top_k]}
        except Exception as e:
            return {"error": str(e)}

def shlex_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"Hermes Web GUI: http://0.0.0.0:{port}")
    print(f"Serving from: {DATA}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
