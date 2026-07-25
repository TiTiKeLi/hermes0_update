import sqlite3
from datetime import datetime

db = sqlite3.connect('/opt/data/state.db')
cur = db.cursor()

# Get latest sessions
cur.execute("SELECT id, source, model, started_at, ended_at FROM sessions ORDER BY started_at DESC LIMIT 5")
sessions = cur.fetchall()
print("Latest sessions:")
for s in sessions:
    started = datetime.fromtimestamp(s[3]).strftime('%Y-%m-%d %H:%M') if s[3] else 'N/A'
    print(f"  {s[0]} | {s[1]} | {s[2]} | started: {started}")

# Get message count per session
print("\nMessage counts:")
cur.execute("SELECT session_id, COUNT(*) as cnt FROM messages GROUP BY session_id ORDER BY cnt DESC LIMIT 5")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]} messages")

# Get latest messages
print("\nLatest 5 messages:")
cur.execute("SELECT session_id, role, content, timestamp FROM messages ORDER BY timestamp DESC LIMIT 5")
for m in cur.fetchall():
    ts = datetime.fromtimestamp(m[3]).strftime('%Y-%m-%d %H:%M:%S') if m[3] else 'N/A'
    content = (m[2] or '')[:80]
    print(f"  [{ts}] {m[0]} | {m[1]}: {content}")

db.close()
