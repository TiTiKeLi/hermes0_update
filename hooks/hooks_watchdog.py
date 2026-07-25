#!/usr/bin/env python3
"""
hooks_watchdog.py — Cron watchdog for hooks engine.
Fires cron_tick event, rebuilds trigger reference, reports issues only.

As a no_agent cron script: keeps silent on success,
prints only on errors or when action was taken.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from hooks_engine import HookEngine, utcnow
from skill_trigger_index import scan_all_skills, generate_triggers_reference
from skill_trigger_index import TRIGGERS_FILE


def fire_cron_tick(engine: HookEngine) -> list:
    """Fire cron_tick event through hooks engine."""
    from datetime import datetime
    return engine.fire_event("cron_tick", context={
        "timestamp": utcnow(),
        "source": "hooks_watchdog",
        "ts_iso": datetime.utcnow().isoformat()
    })


def rebuild_reference() -> int:
    """Rebuild TRIGGERS_REFERENCE.md from skill_trigger_index."""
    triggers = scan_all_skills()
    content = generate_triggers_reference(triggers)

    old_content = ""
    try:
        with open(TRIGGERS_FILE) as f:
            old_content = f.read()
    except FileNotFoundError:
        pass

    if old_content == content:
        return 0  # no change

    with open(TRIGGERS_FILE, "w") as f:
        f.write(content)
    return 1  # updated


def main():
    engine = HookEngine()
    actions = []

    # Fire cron_tick
    fired = fire_cron_tick(engine)
    if fired:
        actions.append(f"cron_tick: {len(fired)} hooks fired")
    else:
        actions.append("cron_tick: no event hooks matched")

    # Rebuild reference
    changed = rebuild_reference()
    if changed:
        actions.append("TRIGGERS_REFERENCE.md updated")

    # Report only if something meaningful happened
    if fired or changed:
        print(f"[hooks_watchdog] {' | '.join(actions)}")
    # else: silent


if __name__ == "__main__":
    main()
