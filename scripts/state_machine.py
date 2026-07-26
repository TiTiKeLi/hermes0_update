#!/usr/bin/env python3
"""Unified State Machine for Codex-Hermes interactions.

Generalized for ANY input type, not just confirm/reject.
Input can be: choice, text, data, file reference — anything.

状态名（对齐实际使用中的命名）：
  PENDING → PROCESSING → AWAITING_CONFIRMATION → CONFIRMED → PROCESSING → COMPLETED
                                                     → REJECTED
                                                             → TIMEOUT
"""
import json, os, time

SM_DIR = "/opt/data/codex-bridge/state-machine"
ARCHIVE_DIR = os.path.join(SM_DIR, "archive")

STATES = [
    "PENDING",                  # 已创建，等待处理
    "PROCESSING",               # 正在处理
    "AWAITING_CONFIRMATION",    # 等待用户确认
    "CONFIRMED",                # 用户已确认
    "REJECTED",                 # 用户已否决
    "COMPLETED",                # 处理完成
    "FAILED",                   # 处理失败
    "TIMEOUT",                  # 等待超时
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


def create(sm_type, context, created_by="codex"):
    sm_id = "sm-" + time.strftime("%Y%m%d-%H%M%S")
    sm = {"id": sm_id, "type": sm_type, "state": "PENDING",
           "created_by": created_by, "context": context, "result": None,
           "error": None, "history": [], "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    sm["history"].append({"state": "PENDING", "at": sm["created_at"], "by": created_by})
    _save(sm)
    return sm


def transition(sm_id, new_state, by="system", result=None, error=None):
    sm = read(sm_id)
    if not sm: return None
    if new_state not in VALID_TRANSITIONS.get(sm["state"], []):
        return None
    # 进入 AWAITING_CONFIRMATION 时触发 hooks 事件
    if new_state == "AWAITING_CONFIRMATION":
        import subprocess
        subprocess.Popen(
            ["python3", "/opt/data/hooks/hooks_engine.py", "broadcast", "state_machine_input_needed"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    sm["state"] = new_state
    sm["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    sm["history"].append({"state": new_state, "at": sm["updated_at"], "by": by})
    if result is not None: sm["result"] = result
    if error: sm["error"] = error
    _save(sm)
    if new_state in ("COMPLETED", "FAILED", "REJECTED"):
        _archive(sm)
    return sm


def read(sm_id):
    for d in [SM_DIR, ARCHIVE_DIR]:
        p = os.path.join(d, sm_id + ".json")
        if os.path.exists(p):
            return json.load(open(p))
    return None


def list_active():
    r = []
    for f in os.listdir(SM_DIR):
        if f.endswith(".json") and not os.path.isdir(os.path.join(SM_DIR, f)):
            s = json.load(open(os.path.join(SM_DIR, f)))
            if s["state"] not in ("COMPLETED", "FAILED", "REJECTED"):
                r.append(s)
    return r


def list_by_state(target_state):
    r = []
    for f in os.listdir(SM_DIR):
        if f.endswith(".json") and not os.path.isdir(os.path.join(SM_DIR, f)):
            s = json.load(open(os.path.join(SM_DIR, f)))
            if s["state"] == target_state:
                r.append(s)
    return r


def _save(sm):
    os.makedirs(SM_DIR, exist_ok=True)
    json.dump(sm, open(os.path.join(SM_DIR, sm["id"]+".json"), "w"), indent=2, ensure_ascii=False)

def _archive(sm):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    s = os.path.join(SM_DIR, sm["id"]+".json")
    d = os.path.join(ARCHIVE_DIR, sm["id"]+".json")
    if os.path.exists(s): os.rename(s, d)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "create":
        s = create(sys.argv[2], {"summary": sys.argv[3] if len(sys.argv) >= 4 else ""})
        print("created: " + s["id"])
    elif len(sys.argv) >= 3 and sys.argv[1] == "transition":
        r = transition(sys.argv[2], sys.argv[3], by=sys.argv[4] if len(sys.argv) >= 5 else "system")
        print("state: " + (r["state"] if r else "failed"))
    elif len(sys.argv) >= 2 and sys.argv[1] == "list":
        for s in list_active(): print("  " + s["id"] + ": " + s["state"])
    elif len(sys.argv) >= 2 and sys.argv[1] == "awaiting":
        for s in list_by_state("AWAITING_CONFIRMATION"): print("  " + s["id"] + ": " + s["context"]["summary"])
    else:
        print("usage: state_machine.py {create|transition|list|awaiting}")

