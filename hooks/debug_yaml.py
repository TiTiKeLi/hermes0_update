#!/usr/bin/env python3
"""Debug YAML parser output for a skill with triggers."""
import sys
sys.path.insert(0, "/opt/data/hooks")
from skill_trigger_index import extract_yaml_frontmatter, _parse_simple_yaml

# Test the parser directly
test_yaml = """
name: test-skill
category: test
triggers:
  keywords:
    - test1
    - test2
  tool_calls:
    - terminal
  events:
    - session_start
"""

result = _parse_simple_yaml(test_yaml)
print("Parsed result:", result)
print()

# Test a real file
fm = extract_yaml_frontmatter("/opt/data/skills/behavior/caveman-compress/SKILL.md")
print("Real caveman-compress:", fm)
print()
if 'triggers' in fm:
    print("triggers content:", fm['triggers'])
else:
    print("NO triggers key found!")
    print("Keys:", list(fm.keys()))
