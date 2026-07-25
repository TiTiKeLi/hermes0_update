import urllib.request
import json

data = json.dumps({"model": "nomic-embed-text", "prompt": "test"}).encode()
req = urllib.request.Request(
    "http://host.docker.internal:11434/api/embeddings",
    data=data,
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        print(f"Embedding length: {len(result['embedding'])}")
        print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
