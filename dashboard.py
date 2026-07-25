#!/usr/bin/env python3
"""Hermes Dashboard Server - lightweight, runs on Windows."""
import os, subprocess, json, sys, glob, html as htmlmod, yaml
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = 8643
HERMES = r"C:\Users\Lsc\.hermes"
HTML = os.path.join(HERMES, "dashboard.html")

def wsl(cmd, timeout=15):
    try:
        r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd],
            capture_output=True, timeout=timeout)
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        return out.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return ""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/" or p == "/dashboard.html":
            return self.serve(HTML, "text/html")
        elif p == "/api/status":
            return self.json(self.status())
        elif p == "/api/config":
            return self.serve(os.path.join(HERMES, "config.yaml"), "text/plain")
        elif p == "/api/logs":
            return self.text(wsl("docker logs hermes --tail 30 2>&1") or "(empty)")
        elif p == "/api/history":
            return self.json(self.get_history())
        elif p == "/api/memory":
            return self.json(self.get_memory())
        elif p == "/api/skills":
            return self.json(self.get_skills())
        elif p == "/api/mcp":
            return self.json(self.get_mcp())
        elif p == "/api/capabilities":
            return self.json(self.get_capabilities())
        elif p == "/api/cron/list":
            return self.text(wsl("docker exec hermes hermes cron list 2>&1", 10))
        elif p == "/api/ollama/models":
            return self.json(self.get_ollama_models())
        self.json({"error":"not found"}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/query":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
            prompt = body.get("prompt","")
            model = body.get("model","qwen3:8b")
            # Write prompt to file in mounted volume, then read from container
            with open(os.path.join(HERMES, "_prompt.txt"), "w", encoding="utf-8") as f:
                f.write(prompt)
            out = wsl(f"docker exec hermes hermes -z \"$(cat /opt/data/_prompt.txt)\" -m {model} 2>&1", 120)
            return self.json({"response": out})
        elif p == "/api/skill/create":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
            name = body.get("name","unnamed")
            desc = body.get("description","")
            import datetime
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Write a minimal skill file
            sdir = os.path.join(HERMES, "skills")
            os.makedirs(sdir, exist_ok=True)
            spath = os.path.join(sdir, f"{name}.md")
            with open(spath, "w", encoding="utf-8") as f:
                f.write(f"# {name}\n\n{desc}\n\nCreated: {ts}\n")
            return self.json({"ok":True, "path":spath, "created":ts})
        elif p == "/api/cron/create":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
            prompt = body.get("prompt", "")
            schedule = body.get("schedule", "")
            name = body.get("name", "")
            deliver = body.get("deliver", "origin")
            if not prompt or not schedule:
                return self.json({"error": "prompt and schedule required"}, 400)
            cmd = f'docker exec hermes hermes cron create'
            if name: cmd += f' --name "{name}"'
            if deliver: cmd += f' --deliver {deliver}'
            import shlex
            cmd += f' "{schedule}" "{prompt}" 2>&1'
            out = wsl(cmd, 15)
            return self.json({"result": out})
        elif p == "/api/cron/list":
            out = wsl("docker exec hermes hermes cron list 2>&1", 10)
            return self.text(out)
        elif p == "/api/cron/tick":
            out = wsl("docker exec hermes hermes cron tick 2>&1", 30)
            return self.json({"result": out or "tick complete"})
        elif p == "/api/cron/remove":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
            jid = body.get("job_id", "")
            if not jid: return self.json({"error":"job_id required"}, 400)
            out = wsl(f'docker exec hermes hermes cron remove "{jid}" 2>&1', 10)
            return self.json({"result": out})
        elif p == "/api/action":
            act = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0)))).get("action","")
            cmds = {"restart":"docker restart hermes","doctor":"docker exec hermes hermes doctor 2>&1"}
            if act in cmds:
                return self.json({"message": wsl(cmds[act], 30)})
            return self.json({"error":"unknown"}, 400)
        elif p == "/api/ollama/set-model":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
            model = body.get("model","")
            if not model:
                return self.json({"ok":False, "error":"model required"})
            try:
                self.set_default_model(model)
                config_msg = f"config.yaml model.default → {model}"
                restart_out = wsl("docker restart hermes", 30)
                if "hermes" in restart_out:
                    restart_msg = f"容器已重启 ({restart_out.strip()})"
                else:
                    restart_msg = f"容器重启结果: {restart_out or '无返回'}"
                return self.json({"ok":True, "model":model, "config": config_msg, "restart": restart_msg})
            except Exception as e:
                return self.json({"ok":False, "error": str(e), "model":model})
        elif p == "/api/dashboard/chat":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
            msg = body.get("message","")
            result = self.process_dashboard_chat(msg)
            return self.json(result)
        self.json({"error":"not found"}, 404)

    def status(self):
        c = wsl("docker ps -a --filter name=hermes --format '{{.Status}}'")
        cont = "running" if "Up" in c else "stopped"
        up = c.replace("Up ","") if "Up" in c else "—"
        o = wsl("docker exec hermes python3 -c \"import urllib.request,json; print(json.dumps(json.loads(urllib.request.urlopen('http://host.docker.internal:11434/api/tags',timeout=5).read())))\" 2>&1 || echo FAIL", 10)
        ollama = "reachable" if o and "models" in o else "unreachable"
        try: models = ", ".join(m["name"] for m in json.loads(o).get("models",[])[:3]) if ollama=="reachable" else "—"
        except: models = "—"
        e_path = os.path.join(HERMES, ".env")
        wx = "disconnected"
        acct = "—"
        try:
            with open(e_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("WEIXIN_ACCOUNT_ID="):
                        acct = line.strip().split("=", 1)[1]
                        wx = "connected" if acct else "disconnected"
                        break
        except: pass
        mem = self.get_memory()
        mem_count = mem["session_count"]
        mem_size = mem["total_bytes"]
        return {
            "container": cont, "uptime": up,
            "ollama": ollama, "ollamaModel": models,
            "wechat": wx, "wechatAccount": acct,
            "memory": mem_count,
            "memoryDetail": f"{mem_count} 对话 · {mem_size//1024}KB",
            "env": {"gateway":":8642","auth":"hermes-dev","dm":"开放","provider":"custom -> Ollama","base":"http://host.docker.internal:11434/v1","group":"已关闭"}
        }

    def get_history(self):
        """Read latest conversation from JSONL session files."""
        sdir = os.path.join(HERMES, "sessions")
        jsons = sorted(glob.glob(os.path.join(sdir, "*.jsonl")), key=os.path.getmtime, reverse=True)
        msgs = []
        for jp in jsons[:3]:
            sid = os.path.splitext(os.path.basename(jp))[0]
            with open(jp, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        msg = entry.get("message", entry)
                        role = msg.get("role", "?")
                        content = (msg.get("content", "") or "")[:500]
                        ts = (msg.get("timestamp", "") or "")[:19]
                        if role in ("user", "assistant") and content:
                            msgs.append({"role": role, "content": content, "time": ts, "session": sid})
                    except: pass
        return msgs

    def get_memory(self):
        """Read Hermes memory store."""
        mdir = os.path.join(HERMES, "memories")
        items = []
        total_bytes = 0
        if os.path.isdir(mdir):
            for fn in os.listdir(mdir):
                fp = os.path.join(mdir, fn)
                if os.path.isfile(fp):
                    sz = os.path.getsize(fp)
                    total_bytes += sz
                    items.append({"name": fn, "size": sz})
        # Also count sessions
        sdir = os.path.join(HERMES, "sessions")
        slist = []
        smeta = os.path.join(sdir, "sessions.json")
        if os.path.exists(smeta):
            try:
                with open(smeta, encoding="utf-8") as f:
                    sd = json.load(f)
                    for k, v in sd.items():
                        slist.append({
                            "key": k, "session_id": v.get("session_id",""),
                            "platform": v.get("platform","?"),
                            "updated": (v.get("updated_at","") or "")[:19],
                        })
            except: pass
        return {
            "memories": sorted(items, key=lambda x: x["size"], reverse=True)[:20],
            "total_bytes": total_bytes,
            "sessions": sorted(slist, key=lambda x: x["updated"], reverse=True)[:20],
            "session_count": len(slist),
        }

    def get_skills(self):
        skills = []
        sdir = os.path.join(HERMES, "skills")
        if os.path.isdir(sdir):
            for fn in os.listdir(sdir):
                fp = os.path.join(sdir, fn)
                if not os.path.isfile(fp) or fn.startswith("."): continue
                content = open(fp, encoding="utf-8", errors="replace").read()
                name = fn
                desc = "—"
                ts = "—"
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if line.startswith("# ") and i == 0:
                        name = line[2:].strip()
                    if line.startswith("Created:"):
                        ts = line.replace("Created:","").strip()
                # Use second line as description fallback
                if len(lines) > 1 and lines[1].strip():
                    desc = lines[1].strip()
                skills.append({"name": name, "file": fn, "description": desc, "created": ts, "content": content[:2000]})
        return skills

    def get_mcp(self):
        out = wsl("docker exec hermes hermes mcp list 2>&1")
        servers = []
        for line in out.split("\n"):
            line = line.strip()
            if not line or "┏" in line or "┃" in line or "┣" in line or "┗" in line:
                continue
            # MCP uses space columns too
            parts = [p.strip() for p in line.split() if p.strip()]
            if len(parts) >= 3 and not any(x in line for x in ["Configured","Name","──"]):
                servers.append({"name": parts[0], "url": parts[1], "status": parts[2]})
        if not servers:
            servers = []
        return servers

    def get_capabilities(self):
        # Run helper script inside container via mounted volume
        raw = wsl("docker exec hermes python3 /opt/data/_tools_to_json.py 2>&1", 15)
        cap = {}
        try:
            cap = json.loads(raw)
        except: pass
        tools = cap.get("tools", [])
        if not isinstance(tools, list): tools = []
        enabled = sum(1 for t in tools if "enabled" in (t.get("status","")))
        disabled = sum(1 for t in tools if "disabled" in (t.get("status","")))
        # Count tool usage from session logs
        usage = {}
        sdir = os.path.join(HERMES, "sessions")
        if os.path.isdir(sdir):
            for jp in glob.glob(os.path.join(sdir, "*.jsonl")):
                try:
                    with open(jp, encoding="utf-8", errors="replace") as f:
                        for line in f:
                            try:
                                entry = json.loads(line)
                                msg = entry.get("message", entry)
                                calls = msg.get("tool_calls", [])
                                if not calls and "tool_calls" in entry:
                                    calls = entry["tool_calls"]
                                for tc in calls:
                                    fn = tc.get("function",{}).get("name","") or tc.get("name","")
                                    if fn:
                                        usage[fn] = usage.get(fn, 0) + 1
                            except: pass
                except: pass
        for t in tools:
            t["uses"] = usage.get(t["name"], 0)
        mem_plugins = cap.get("plugins", [])
        if not isinstance(mem_plugins, list): mem_plugins = []
        # Sessions
        sdir = os.path.join(HERMES, "sessions")
        jsons = glob.glob(os.path.join(sdir, "*.jsonl")) if os.path.isdir(sdir) else []
        total_msgs = 0
        for jp in jsons:
            try:
                with open(jp, encoding="utf-8", errors="replace") as f:
                    total_msgs += sum(1 for _ in f)
            except: pass
        skills = self.get_skills()
        mcp = self.get_mcp()
        ver = wsl("docker exec hermes hermes --version 2>&1 | head -2").split("\n")[0]
        return {
            "version": ver,
            "tools": {"total": len(tools), "enabled": enabled, "disabled": disabled, "list": tools},
            "skills": {"count": len(skills), "list": skills[:50]},
            "mcp": {"count": len(mcp), "list": mcp},
            "memory_plugins": {"count": len(mem_plugins), "list": mem_plugins},
            "sessions": {"count": len(jsons), "messages": total_msgs},
        }

    def serve(self, path, mime):
        try:
            with open(path, encoding="utf-8") as f: c = f.read()
            b = c.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", mime+"; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control","no-cache")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            self.wfile.write(b)
        except Exception as e:
            self.json({"error":str(e)}, 404)

    def json(self, d, code=200):
        body = json.dumps(d, ensure_ascii=False)
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control","no-cache")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers()
        self.wfile.write(b)

    def text(self, d, code=200):
        b = d.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type","text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control","no-cache")
        self.end_headers()
        self.wfile.write(b)

    def get_ollama_models(self):
        try:
            import urllib.request
            r = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
            data = json.loads(r.read().decode())
            models = []
            for m in data.get("models", []):
                models.append({
                    "name": m.get("name", "?"),
                    "size": m.get("size", 0),
                    "modified": (m.get("modified_at", "") or "")[:19],
                })
            return {"models": models}
        except Exception as e:
            return {"error": str(e), "models": []}

    def set_default_model(self, model):
        path = os.path.join(HERMES, "config.yaml")
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        cfg["model"]["default"] = model
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

    def process_dashboard_chat(self, message):
        skill_path = os.path.join(HERMES, "skills", "dashboard-modifier.md")
        skill_content = ""
        if os.path.exists(skill_path):
            with open(skill_path, "r", encoding="utf-8") as f:
                skill_content = f.read()
        sys_prompt = f"You are a dashboard modification assistant. The dashboard files are in {HERMES}. User wants: {message}. Respond with a step-by-step plan, then make the changes. Skill:\n{skill_content}"
        try:
            import subprocess
            result = subprocess.run(
                ["opencode", "run", sys_prompt],
                capture_output=True, text=True, timeout=120, cwd=HERMES
            )
            if result.returncode == 0 and result.stdout:
                return {"response": result.stdout.strip()[:2000]}
        except: pass
        # Fallback: use Ollama directly
        try:
            import urllib.request
            body = json.dumps({
                "model": "qwen2.5:0.5b", "messages": [
                    {"role": "system", "content": "你是仪表盘修改助手。修改 Hermes 仪表盘文件。"},
                    {"role": "user", "content": f"技能:\n{skill_content[:1500]}\n\n需求: {message}\n\n请分两步回复：1)分析需要改什么 2)给出具体代码变更。文件在 {HERMES}"}
                ], "stream": False
            }).encode()
            r = urllib.request.urlopen("http://localhost:11434/api/chat", body, timeout=30)
            resp = json.loads(r.read().decode())
            content = resp.get("message", {}).get("content", "")[:2000]
            return {"response": content, "note": "via Ollama (opencode CLI unavailable)"}
        except Exception as e:
            return {"response": f"无法执行: {str(e)[:200]}"}

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[DASH] {args[0]} {args[1]}\n")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except: pass
print(f"\n  == Hermes Dashboard ==\n  URL: http://localhost:{PORT}\n")
HTTPServer(("localhost", PORT), H).serve_forever()
