import sqlite3
db = sqlite3.connect('/opt/data/state.db')
cur = db.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('Tables:', [t[0] for t in tables])
for t in tables:
    cur.execute(f"PRAGMA table_info({t[0]})")
    cols = cur.fetchall()
    print(f"\n{t[0]}:", [(c[1], c[2]) for c in cols[:10]])
db.close()
