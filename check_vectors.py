import sqlite3

db = sqlite3.connect('/opt/data/state.db')
try:
    cur = db.execute("SELECT COUNT(*) FROM message_embeddings")
    count = cur.fetchone()[0]
    print(f"Embeddings stored: {count}")
    
    cur = db.execute("SELECT COUNT(*) FROM messages WHERE role IN ('user', 'assistant')")
    total = cur.fetchone()[0]
    print(f"Total messages: {total}")
except Exception as e:
    print(f"Table not exists or error: {e}")
db.close()
