#!/usr/bin/env python3
"""
GitHub API 搜索脚本 — 作为 harness 的一部分
用法: python3 search_github.py <query> [max_results=5]
"""
import json, sys, os, urllib.request, urllib.parse, time

def search(query, max_results=5):
    params = urllib.parse.urlencode({
        'q': query, 'per_page': min(max_results, 30),
        'sort': 'stars', 'order': 'desc'
    })
    url = f"https://api.github.com/search/repositories?{params}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Hermes-Research-Harness/1.0',
        'Accept': 'application/vnd.github.v3+json'
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            results = []
            for r in data.get('items', [])[:max_results]:
                results.append({
                    'name': r['full_name'],
                    'stars': r['stargazers_count'],
                    'description': r.get('description', ''),
                    'url': r['html_url'],
                    'topics': r.get('topics', []),
                    'updated': r.get('updated_at', ''),
                    'license': r.get('license', {}).get('spdx_id', '') if r.get('license') else ''
                })
            return results
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 search_github.py <query> [max_results]')
        sys.exit(1)
    query = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    result = search(query, n)
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)
    # Save to knowledge store
    out_dir = "/opt/data/research/sources"
    os.makedirs(out_dir, exist_ok=True)
    slug = query.lower().replace(' ', '-')[:40]
    ts = time.strftime('%Y%m%dT%H%M%S')
    path = f"{out_dir}/github-{slug}-{ts}.json"
    with open(path, 'w') as f:
        f.write(out)
    print(f"\n🗂️ saved to {path}")
