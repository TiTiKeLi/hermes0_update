#!/usr/bin/env python3
"""WeChat State Bridge - Hermes side. Uses generalized INPUT states."""
import sys, os
sys.path.insert(0, "/opt/data/scripts")
import state_machine as sm

def pending():
    for s in sm.list_by_state("AWAITING_INPUT"):
        ctx = s.get("context", {})
        print("[" + s["id"] + "] " + s["type"] + ": " + ctx.get("summary", ""))

def provide_input(sm_id, input_data):
    return sm.transition(sm_id, "INPUT_PROVIDED", by="wechat_user", result=input_data)

def fail(sm_id, reason=None):
    return sm.transition(sm_id, "FAILED", by="wechat_user", error=reason)

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "pending":
        pending()
    elif len(sys.argv) >= 3 and sys.argv[1] == "input":
        data = sys.argv[3] if len(sys.argv) >= 4 else ""
        print("ok" if provide_input(sys.argv[2], data) else "failed")
    else:
        for s in sm.list_by_state("AWAITING_INPUT"):
            print("等待输入: [" + s["id"] + "] " + s["context"]["summary"])
