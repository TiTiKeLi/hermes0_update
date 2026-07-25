#!/usr/bin/env python3
"""Clean up old auto-* hooks and run full scan."""
import sys
sys.path.insert(0, "/opt/data/hooks")
from hooks_engine import HookDB

db = HookDB()
removed = 0
for hook in db.list_hooks():
    name = hook['name']
    if name.startswith('auto-'):
        db.delete_hook(hook['id'])
        print(f"Removed: #{hook['id']} {name}")
        removed += 1

if removed == 0:
    print("No auto-* hooks to remove")

print(f"Total active hooks: {len(db.list_hooks())}")
print("Ready for scan")
