#!/usr/bin/env python3
"""Quick test: parse a skill frontmatter with triggers."""
import sys
import json
sys.path.insert(0, "/opt/data/hooks")

# Use yaml directly
import yaml

with open("/opt/data/skills/behavior/caveman-compress/SKILL.md") as f:
    content = f.read()

end = content.find("---", 3)
front = content[3:end].strip()
data = yaml.safe_load(front)
print("triggers:" in front)
print("keys:", list(data.keys()))
print("triggers =>", json.dumps(data.get("triggers"), ensure_ascii=False))
print("triggers.keywords =>", data.get("triggers", {}).get("keywords"))
