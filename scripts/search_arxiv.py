#!/usr/bin/env python3
"""
arXiv API 搜索脚本 — 作为 harness 的一部分
用法: python3 search_arxiv.py <query> [max_results=5]
"""
import json, sys, os, urllib.request, urllib.parse, time, xml.etree.ElementTree as ET

ARXIV_URL = "http://export.arxiv.org/api/query"

def search(query, max_results=5):
    params = urllib.parse.urlencode({
        'search_query': f'all:{query}',
        'start': 0,
        'max_results': min(max_results, 50),
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    })
    url = f"{ARXIV_URL}?{params}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Hermes-Research-Harness/1.0'
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode('utf-8')
        root = ET.fromstring(xml_data)
        ns = {'a': 'http://www.w3.org/2005/Atom',
              'arxiv': 'http://arxiv.org/schemas/atom'}
        results = []
        for entry in root.findall('a:entry', ns)[:max_results]:
            title = entry.find('a:title', ns)
            summary = entry.find('a:summary', ns)
            published = entry.find('a:published', ns)
            link = entry.find('a:id', ns)
            authors = [a.find('a:name', ns).text for a in entry.findall('a:author', ns) if a.find('a:name', ns) is not None]
            results.append({
                'title': (title.text or '').strip().replace('\n', ' ') if title is not None else '',
                'summary': (summary.text or '').strip().replace('\n', ' ')[:300] if summary is not None else '',
                'published': published.text if published is not None else '',
                'url': link.text if link is not None else '',
                'authors': authors[:5]
            })
        return results
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 search_arxiv.py <query> [max_results]')
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
    path = f"{out_dir}/arxiv-{slug}-{ts}.json"
    with open(path, 'w') as f:
        f.write(out)
    print(f"\n🗂️ saved to {path}")
