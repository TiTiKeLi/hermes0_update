#!/usr/bin/env python3
"""
Download Gate — 下载门卫脚本
==============================
- 检查文件是否在 trusted.json 白名单中
- 扫描文件危险模式
- 添加/更新 trusted.json 条目
- 供 cron 扫描器和后置钩子调用

用法:
  python3 download_gate.py check <path>         # 检查文件是否已信任
  python3 download_gate.py scan <path>          # 扫描文件危险模式
  python3 download_gate.py trust <path> --source <url>  # 标记文件为信任
  python3 download_gate.py list-trusted         # 列出所有信任文件
  python3 download_gate.py scan-new             # 扫描 /opt/data/ 下所有新文件
  python3 download_gate.py list-blocked         # 列出所有拒绝记录
  python3 download_gate.py report               # 完整状态报告
"""

import json
import hashlib
import os
import re
import sys
import time
import glob
from datetime import datetime, timezone

GATE_DIR = "/opt/data/download_gate"
TRUSTED_FILE = os.path.join(GATE_DIR, "trusted.json")
BLOCKED_DIR = os.path.join(GATE_DIR, "blocked")
STATE_FILE = os.path.join(GATE_DIR, "state.json")
ISOLATION_DIR = os.path.join(GATE_DIR, "isolation")
INCLUDED_EXTENSIONS = {'.py', '.sh', '.js', '.ts', '.yaml', '.yml', '.toml', '.json', '.md', '.txt', '.env', '.conf', '.cfg'}
EXCLUDED_DIRS = {'__pycache__', 'node_modules', '.git', '.venv', 'venv', 'env', 'isolation', 'blocked'}

# ==================== 底层 ====================

def _ensure_dirs():
    os.makedirs(GATE_DIR, exist_ok=True)
    os.makedirs(BLOCKED_DIR, exist_ok=True)
    os.makedirs(ISOLATION_DIR, exist_ok=True)

def _load_trusted():
    _ensure_dirs()
    if not os.path.exists(TRUSTED_FILE):
        return []
    try:
        with open(TRUSTED_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def _save_trusted(entries):
    _ensure_dirs()
    with open(TRUSTED_FILE, 'w') as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

def _file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def _timestamp():
    return datetime.now(timezone.utc).isoformat()

# ==================== 检查 ====================

def is_trusted(path):
    """检查文件是否在 trusted.json 中（按路径和哈希匹配）"""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return False, "文件不存在"
    
    current_hash = _file_hash(abs_path)
    entries = _load_trusted()
    
    for entry in entries:
        if entry.get("file_path") == abs_path and entry.get("file_hash") == current_hash:
            return True, "路径+哈希匹配"
        if entry.get("file_hash") == current_hash:
            return True, "哈希匹配（文件可能已移动）"
    
    return False, "未在白名单中"

def scan_file(path):
    """扫描文件的危险模式，返回扫描报告"""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return {"error": f"文件不存在: {abs_path}"}
    
    report = {
        "file": abs_path,
        "size": os.path.getsize(abs_path),
        "scanned_at": _timestamp(),
        "dangers": [],
        "warnings": [],
        "safe_ext": False,
        "summary": ""
    }
    
    ext = os.path.splitext(abs_path)[1].lower()
    if ext in {'.exe', '.dll', '.bin', '.msi', '.dmg', '.apk', '.jar'}:
        return {**report, "danger": True, "summary": "二进制可执行文件，不能信任"}
    
    if ext not in INCLUDED_EXTENSIONS and ext != '':
        report["warnings"].append(f"非常见扩展名: {ext}，需人工确认")
    
    report["safe_ext"] = ext in INCLUDED_EXTENSIONS or ext in {''}
    
    try:
        with open(abs_path, 'r', errors='replace') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception as e:
        return {**report, "danger": True, "summary": f"无法读取: {e}"}
    
    # 凭据泄露模式
    credential_patterns = [
        (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?(?:sk-|ak-|pk-)?[A-Za-z0-9_\-]{10,}', "硬编码 API Key"),
        (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,}', "硬编码密码"),
        (r'(?i)(secret|token)\s*[=:]\s*["\'][A-Za-z0-9_\-\.]{8,}', "硬编码 Secret/Token"),
        (r'(?i)private_key\s*[=:]\s*["\']?-{3,}BEGIN', "硬编码私钥"),
        (r'(?i)-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', "PEM 私钥泄露"),
        (r'(?i)(host|server)\s*[=:]\s*["\']?\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', "硬编码 IP 地址"),
    ]
    
    for pattern, desc in credential_patterns:
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                report["dangers"].append({
                    "type": "credential",
                    "description": desc,
                    "line": i,
                    "preview": line.strip()[:120]
                })
                break  # 每类只报第一次
    
    # 恶意代码模式
    malicious_patterns = [
        (r'\beval\s*\(', "eval() 动态执行"),
        (r'\bexec\s*\(', "exec() 动态执行"),
        (r'base64\s*\.\s*(b64decode|decode)\s*\(', "base64 解码"),
        (r'__import__\s*\(', "动态 import"),
        (r'\bcompile\s*\(', "compile() 动态编译"),
        (r'socket\.\w+\s*\(', "socket 网络连接"),
        (r'(?i)(subprocess|os\.system|os\.popen|pty\.spawn)', "子进程执行"),
        (r'(?i)(requests|urllib)\.(get|post)\s*\(\s*["\']https?://', "外发 HTTP 请求"),
        (r'(?i)reverse_shell|backconnect|bindshell', "反向shell"),
        (r'(?i)chmod\s+\d{3}\s+/', "文件权限修改"),
        (r'(?i)(wget|curl)\s+-[a-z]*O\s+https?://', "远程下载执行"),
    ]
    
    for pattern, desc in malicious_patterns:
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                report["dangers"].append({
                    "type": "malicious",
                    "description": desc,
                    "line": i,
                    "preview": line.strip()[:120]
                })
                break
    
    # 判断总结
    if report["dangers"]:
        has_cred = any(d["type"] == "credential" for d in report["dangers"])
        has_mal = any(d["type"] == "malicious" for d in report["dangers"])
        if has_mal:
            report["summary"] = f"❌ 拒绝：发现 {len(report['dangers'])} 个危险模式（含恶意代码）"
        elif has_cred:
            report["summary"] = f"⚠️ 警告：发现 {len(report['dangers'])} 个凭据泄露"
        else:
            report["summary"] = f"⚠️ 警告：发现 {len(report['dangers'])} 个疑点"
    else:
        report["summary"] = "✅ 安全：未发现危险模式"
    
    return report

# ==================== 写门 ====================

def trust_file(path, source=""):
    """标记一个文件为信任"""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return {"error": f"文件不存在: {abs_path}"}
    
    entry = {
        "file_path": abs_path,
        "file_hash": _file_hash(abs_path),
        "source": source,
        "trusted_at": _timestamp(),
        "verified_by": "download-gate"
    }
    
    entries = _load_trusted()
    # 去重（按路径去重）
    entries = [e for e in entries if e.get("file_path") != abs_path]
    entries.append(entry)
    _save_trusted(entries)
    
    return {"status": "trusted", "entry": entry}

def untrust_file(path):
    """从白名单移除"""
    abs_path = os.path.abspath(path)
    entries = _load_trusted()
    entries = [e for e in entries if e.get("file_path") != abs_path]
    _save_trusted(entries)
    return {"status": "untrusted", "file": abs_path}

def block_file(path, source="", scan_report=None):
    """记录一个被拒绝的文件"""
    abs_path = os.path.abspath(path)
    _ensure_dirs()
    block_entry = {
        "file_path": abs_path,
        "file_hash": _file_hash(abs_path) if os.path.exists(abs_path) else "N/A",
        "source": source,
        "blocked_at": _timestamp(),
        "scan_report": scan_report or {}
    }
    ts = int(time.time())
    with open(os.path.join(BLOCKED_DIR, f"blocked_{ts}.json"), 'w') as f:
        json.dump(block_entry, f, indent=2, ensure_ascii=False)
    return {"status": "blocked", "entry": block_entry}

def isolate_file(path, source=""):
    """将危险文件隔离到 isolation 目录"""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return {"error": f"文件不存在: {abs_path}"}
    
    _ensure_dirs()
    basename = os.path.basename(abs_path)
    ts = int(time.time())
    dest = os.path.join(ISOLATION_DIR, f"{ts}_{basename}")
    
    import shutil
    shutil.move(abs_path, dest)
    
    report = scan_file(abs_path) if os.path.exists(abs_path) else {"summary": "已移动，无法扫描"}
    
    record = {
        "original_path": abs_path,
        "isolated_to": dest,
        "source": source,
        "isolated_at": _timestamp(),
        "scan": report
    }
    with open(os.path.join(BLOCKED_DIR, f"isolated_{ts}.json"), 'w') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    
    return {"status": "isolated", "dest": dest}

# ==================== 扫描新文件 ====================

def scan_new_files():
    """扫描 /opt/data/ 下所有不在 trusted.json 中的文件"""
    trusted = _load_trusted()
    trusted_paths = {e.get("file_path") for e in trusted}
    trusted_hashes = {e.get("file_hash") for e in trusted}
    
    results = {
        "scanned_at": _timestamp(),
        "total": 0,
        "trusted_skip": 0,
        "safe": [],
        "suspicious": [],
        "dangerous": [],
        "errors": []
    }
    
    for root, dirs, files in os.walk("/opt/data/"):
        # 跳过排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.')]
        
        for fname in files:
            fpath = os.path.join(root, fname)
            
            # 只扫描文本扩展名
            ext = os.path.splitext(fname)[1].lower()
            if ext not in INCLUDED_EXTENSIONS and ext not in {'.md', '.txt'}:
                continue
            
            # 跳过 download_gate 自己的文件
            if fpath.startswith(GATE_DIR):
                continue
            
            # 跳过已信任的文件
            if fpath in trusted_paths:
                current_hash = _file_hash(fpath)
                if current_hash in trusted_hashes:
                    results["trusted_skip"] += 1
                    continue
            
            results["total"] += 1
            
            # 扫描
            report = scan_file(fpath)
            
            if "danger" in report:
                results["dangerous"].append({"file": fpath, "summary": report.get("summary", "")})
                # 自动隔离危险文件
                try:
                    iso = isolate_file(fpath, source="cron-scanner")
                    results["dangerous"][-1]["isolated_to"] = iso.get("dest")
                except Exception as e:
                    results["errors"].append(f"隔离失败 {fpath}: {e}")
            elif report.get("dangers"):
                results["suspicious"].append({"file": fpath, "summary": report.get("summary", ""), "count": len(report["dangers"])})
            else:
                results["safe"].append(fpath)
                # 自动信任安全文件
                try:
                    trust_file(fpath, source="cron-auto-scan")
                except Exception as e:
                    results["errors"].append(f"自动信任失败 {fpath}: {e}")
    
    # 更新 state.json
    _update_state(results)
    
    return results

# ==================== 状态 ====================

def _update_state(scan_results=None):
    state = {
        "last_check": _timestamp(),
        "total_passed": len(_load_trusted()),
        "total_blocked": len(glob.glob(os.path.join(BLOCKED_DIR, "*.json"))),
        "status": "active",
        "trusted_json_valid": os.path.exists(TRUSTED_FILE)
    }
    if scan_results:
        state["last_scan"] = {
            "total_scanned": scan_results.get("total", 0),
            "safe": len(scan_results.get("safe", [])),
            "suspicious": len(scan_results.get("suspicious", [])),
            "dangerous": len(scan_results.get("dangerous", [])),
            "trusted_skip": scan_results.get("trusted_skip", 0)
        }
    _ensure_dirs()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def report():
    _ensure_dirs()
    trusted = _load_trusted()
    blocked_files = glob.glob(os.path.join(BLOCKED_DIR, "*.json"))
    state = {"last_check": "N/A", "status": "unknown"}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
    
    print(f"🔒 Download Gate 状态报告")
    print(f"{'='*40}")
    print(f"状态: {state.get('status', 'unknown')}")
    print(f"白名单: {len(trusted)} 个文件")
    print(f"拒绝记录: {len(blocked_files)} 条")
    print(f"最后检查: {state.get('last_check', 'N/A')}")
    if state.get("last_scan"):
        s = state["last_scan"]
        print(f"\n📋 上次扫描:")
        print(f"  扫描: {s['total_scanned']} 个文件")
        print(f"  ✅ 安全: {s['safe']}")
        print(f"  ⚠️ 可疑: {s['suspicious']}")
        print(f"  ❌ 危险(已隔离): {s['dangerous']}")
        print(f"  ⏭️  跳过的信任文件: {s['trusted_skip']}")
    print(f"\n📂 目录: {GATE_DIR}")

# ==================== CLI ====================

if __name__ == "__main__":
    _ensure_dirs()
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 download_gate.py check <path>")
        print("  python3 download_gate.py scan <path>")
        print("  python3 download_gate.py trust <path> [--source <url>]")
        print("  python3 download_gate.py untrust <path>")
        print("  python3 download_gate.py scan-new")
        print("  python3 download_gate.py isolate <path> [--source <url>]")
        print("  python3 download_gate.py list-trusted")
        print("  python3 download_gate.py list-blocked")
        print("  python3 download_gate.py report")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "check" and len(sys.argv) >= 3:
        trusted, reason = is_trusted(sys.argv[2])
        print(f"{'✅' if trusted else '❌'} {os.path.abspath(sys.argv[2])}: {reason}")
    
    elif cmd == "scan" and len(sys.argv) >= 3:
        r = scan_file(sys.argv[2])
        print(f"📄 扫描报告: {r['file']}")
        print(f"大小: {r['size']} bytes | 安全扩展名: {r.get('safe_ext','?')}")
        if r.get("dangers"):
            print(f"\n⚠️ 发现 {len(r['dangers'])} 个危险模式:")
            for d in r["dangers"]:
                print(f"  [{d['type']}] {d['description']} (行 {d['line']}): {d['preview'][:80]}")
        else:
            print(f"\n✅ {r['summary']}")
        print(f"\n{'-'*40}\n{r['summary']}")
    
    elif cmd == "trust" and len(sys.argv) >= 3:
        source = ""
        if "--source" in sys.argv:
            idx = sys.argv.index("--source")
            if idx + 1 < len(sys.argv):
                source = sys.argv[idx + 1]
        r = trust_file(sys.argv[2], source)
        if "error" in r:
            print(f"❌ {r['error']}")
        else:
            print(f"✅ 已信任: {r['entry']['file_path']}")
    
    elif cmd == "untrust" and len(sys.argv) >= 3:
        r = untrust_file(sys.argv[2])
        print(f"📝 已取消信任: {r['file']}")
    
    elif cmd == "check-path":
        print(f"{'✅ 可信任' if _load_trusted() else '❌ 无白名单'}")
    
    elif cmd == "scan-new":
        r = scan_new_files()
        print(f"🔍 新文件扫描完成:")
        print(f"  扫描: {r['total']} 个文件")
        print(f"  ✅ 安全: {len(r['safe'])}")
        print(f"  ⚠️ 可疑: {len(r['suspicious'])}")
        print(f"  ❌ 危险(已隔离): {len(r['dangerous'])}")
        print(f"  ⏭️  信任跳过: {r['trusted_skip']}")
        for d in r["dangerous"]:
            print(f"    ❌ {d['file']} -> 隔离至 {d.get('isolated_to', '?')}")
        for s in r["suspicious"]:
            print(f"    ⚠️ {s['file']}: {s['summary']}")
    
    elif cmd == "isolate" and len(sys.argv) >= 3:
        source = ""
        if "--source" in sys.argv:
            idx = sys.argv.index("--source")
            if idx + 1 < len(sys.argv):
                source = sys.argv[idx + 1]
        r = isolate_file(sys.argv[2], source)
        if "error" in r:
            print(f"❌ {r['error']}")
        else:
            print(f"⛔ 已隔离: {r['original_path']} → {r['dest']}" if 'original_path' in r else f"⛔ 已隔离: {r['dest']}")
    
    elif cmd == "list-trusted":
        entries = _load_trusted()
        if not entries:
            print("(空) 白名单未设置")
        else:
            print(f"📋 白名单 ({len(entries)} 项):")
            for e in entries:
                print(f"  ✅ {e.get('file_path','?')}  [{e.get('source','?')}]")
    
    elif cmd == "list-blocked":
        files = sorted(glob.glob(os.path.join(BLOCKED_DIR, "*.json")))
        if not files:
            print("(空) 无拒绝记录")
        else:
            print(f"📋 拒绝记录 ({len(files)} 条):")
            for fpath in files[-10:]:
                try:
                    with open(fpath) as f:
                        data = json.load(f)
                    print(f"  ⛔ {data.get('file_path','?')}  [{data.get('source','?')}] ({data.get('blocked_at','?')})")
                except:
                    print(f"  ? {fpath}")
    
    elif cmd == "report":
        report()
    
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
