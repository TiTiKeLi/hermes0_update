#!/usr/bin/env python3
"""
Memory Compactor - 当 MEMORY.md/USER.md 超过 95% 时执行全量压缩。
用法: python3 memory_compactor.py [--force]
"""
import json, os, sys, pathlib, argparse

DATA = pathlib.Path("/opt/data")
MEM_DIR = DATA / "memories"
LIMITS = {"MEMORY.md": 2000, "USER.md": 1375}
THRESHOLD = 0.95


def get_size(path):
    try:
        return len(path.read_text(encoding="utf-8", errors="replace"))
    except:
        return 0


def needs_compress(name):
    path = MEM_DIR / name
    size = get_size(path)
    limit = LIMITS.get(name, 2200)
    return size, limit, size > limit * THRESHOLD


def compress_content(text, target_name, api_key):
    """调用 DeepSeek 压缩内容"""
    import urllib.request

    prompt = f"""Compress the following {target_name} content. Rules:
1. Merge related entries into single lines
2. Preserve ALL unique facts, IDs, and tags
3. Remove redundant descriptions
4. Target: 50-60% of original size
5. Keep § as entry delimiter between entries
6. Return plain text only, no markdown

Content:
{text}"""
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000
        }).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    )
    r = urllib.request.urlopen(req, timeout=60)
    body = json.loads(r.read())
    return body["choices"][0]["message"]["content"]


def main():
    parser = argparse.ArgumentParser(description="Memory Compactor")
    parser.add_argument("--force", action="store_true", help="Force compress even if under 95%")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not set")
        sys.exit(1)

    MEM_DIR.mkdir(parents=True, exist_ok=True)

    for name, limit in LIMITS.items():
        path = MEM_DIR / name
        size, _, should = needs_compress(name)
        pct = size * 100 / limit if limit else 0

        if should or args.force:
            print(f"[{name}] {size}/{limit} chars ({pct:.0f}%) → compressing...")
            sys.stdout.flush()
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                compressed = compress_content(text, name, api_key)
                path.write_text(compressed, encoding="utf-8")
                new_size = len(compressed)
                reduction = 100 - new_size * 100 // size if size else 0
                print(f"  ✅ {size} → {new_size} chars ({reduction}% reduction)")
            except Exception as e:
                print(f"  ❌ Compression failed: {e}")
        else:
            print(f"[{name}] {size}/{limit} chars ({pct:.0f}%) → OK")


if __name__ == "__main__":
    main()
