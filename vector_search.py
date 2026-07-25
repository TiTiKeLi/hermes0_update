#!/usr/bin/env python3
"""
Hermes 会话语义搜索模块
使用 Ollama nomic-embed-text 生成嵌入，numpy 计算余弦相似度
"""
import json
import sqlite3
import struct
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

import numpy as np
import urllib.request

# ===== 配置 =====
OLLAMA_URL = "http://host.docker.internal:11434"
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768
DB_PATH = Path("/opt/data/state.db")
VECTOR_TABLE = "message_embeddings"
BATCH_SIZE = 32

# ===== 嵌入生成 =====
def get_embedding(text: str) -> Optional[np.ndarray]:
    """调用 Ollama 生成文本嵌入"""
    try:
        data = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embeddings",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return np.array(result["embedding"], dtype=np.float32)
    except Exception as e:
        print(f"Embedding error: {e}", file=sys.stderr)
        return None

def get_embeddings_batch(texts: List[str]) -> List[Optional[np.ndarray]]:
    """批量生成嵌入"""
    results = []
    for text in texts:
        emb = get_embedding(text)
        results.append(emb)
    return results

# ===== 向量存储 =====
def init_vector_table():
    """初始化向量存储表"""
    db = sqlite3.connect(str(DB_PATH))
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS {VECTOR_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            message_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp REAL,
            embedding BLOB,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            UNIQUE(session_id, message_id)
        )
    """)
    db.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{VECTOR_TABLE}_session 
        ON {VECTOR_TABLE}(session_id)
    """)
    db.commit()
    db.close()

def emb_to_blob(emb: np.ndarray) -> bytes:
    """将嵌入向量转换为二进制存储"""
    return struct.pack(f'{len(emb)}f', *emb.tolist())

def blob_to_emb(blob: bytes) -> np.ndarray:
    """将二进制转换为嵌入向量"""
    n = len(blob) // 4
    return np.array(struct.unpack(f'{n}f', blob), dtype=np.float32)

def store_embedding(session_id: str, message_id: int, role: str, 
                    content: str, timestamp: float, embedding: np.ndarray):
    """存储单条消息的嵌入"""
    db = sqlite3.connect(str(DB_PATH))
    db.execute(f"""
        INSERT OR REPLACE INTO {VECTOR_TABLE} 
        (session_id, message_id, role, content, timestamp, embedding)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, message_id, role, content, timestamp, emb_to_blob(embedding)))
    db.commit()
    db.close()

def has_embedding(session_id: str, message_id: int) -> bool:
    """检查是否已存在嵌入"""
    db = sqlite3.connect(str(DB_PATH))
    cur = db.execute(
        f"SELECT COUNT(*) FROM {VECTOR_TABLE} WHERE session_id=? AND message_id=?",
        (session_id, message_id)
    )
    count = cur.fetchone()[0]
    db.close()
    return count > 0

# ===== 相似度搜索 =====
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """计算余弦相似度"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def search_similar(query: str, top_k: int = 10, 
                   session_id: Optional[str] = None) -> List[dict]:
    """语义相似度搜索"""
    query_emb = get_embedding(query)
    if query_emb is None:
        return []
    
    db = sqlite3.connect(str(DB_PATH))
    if session_id:
        cur = db.execute(
            f"SELECT session_id, message_id, role, content, timestamp, embedding "
            f"FROM {VECTOR_TABLE} WHERE session_id=?",
            (session_id,)
        )
    else:
        cur = db.execute(
            f"SELECT session_id, message_id, role, content, timestamp, embedding "
            f"FROM {VECTOR_TABLE}"
        )
    
    results = []
    for row in cur.fetchall():
        emb = blob_to_emb(row[5])
        sim = cosine_similarity(query_emb, emb)
        results.append({
            "session_id": row[0],
            "message_id": row[1],
            "role": row[2],
            "content": row[3],
            "timestamp": row[4],
            "similarity": sim
        })
    db.close()
    
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]

# ===== 增量同步 =====
def sync_embeddings(max_messages: int = 1000):
    """同步最近消息的嵌入"""
    init_vector_table()
    db = sqlite3.connect(str(DB_PATH))
    
    # 获取需要同步的消息
    cur = db.execute("""
        SELECT m.session_id, m.id, m.role, m.content, m.timestamp
        FROM messages m
        WHERE m.role IN ('user', 'assistant')
          AND m.content IS NOT NULL
          AND LENGTH(m.content) > 10
          AND NOT EXISTS (
              SELECT 1 FROM message_embeddings e 
              WHERE e.session_id = m.session_id AND e.message_id = m.id
          )
        ORDER BY m.timestamp DESC
        LIMIT ?
    """, (max_messages,))
    
    messages = cur.fetchall()
    db.close()
    
    if not messages:
        print("No new messages to sync")
        return 0
    
    print(f"Syncing {len(messages)} messages...")
    synced = 0
    
    for i in range(0, len(messages), BATCH_SIZE):
        batch = messages[i:i+BATCH_SIZE]
        texts = [m[3][:500] for m in batch]  # 截断过长内容
        
        embeddings = get_embeddings_batch(texts)
        
        for msg, emb in zip(batch, embeddings):
            if emb is not None:
                store_embedding(msg[0], msg[1], msg[2], msg[3], msg[4], emb)
                synced += 1
        
        print(f"  Progress: {min(i+BATCH_SIZE, len(messages))}/{len(messages)}")
    
    print(f"Synced {synced} embeddings")
    return synced

# ===== CLI =====
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: vector_search.py <command> [args]")
        print("  sync [max_messages]  - 同步消息嵌入")
        print("  search <query> [top_k] [session_id] - 语义搜索")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "sync":
        max_msg = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
        sync_embeddings(max_msg)
    
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: vector_search.py search <query> [top_k] [session_id]")
            sys.exit(1)
        query = sys.argv[2]
        top_k = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        session_id = sys.argv[4] if len(sys.argv) > 4 else None
        
        results = search_similar(query, top_k, session_id)
        for r in results:
            sim = r['similarity']
            content = r['content'][:80].replace('\n', ' ')
            print(f"[{sim:.3f}] {r['session_id']} | {r['role']}: {content}")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
