# GitHub HTTP Scraping（无 web_search 工具时）

适用于容器仅有 `terminal`/`curl` 但无 `web_search` 工具的场景。
关键技术：利用 GitHub 搜索结果页内嵌的 JSON 数据负载。

---

## 方法 B：JSON 数据负载提取（推荐 — 最准确）

### 原理

GitHub 搜索页 HTML 中内嵌了完整的 JSON 数据：
```html
<script type="application/json" data-target="react-app.embeddedData">
{"payload":{"results":[{"id":"...","followers":10369,   # ← followers = star 数
                          "hl_name":"owner/repo",
                          "hl_trunc_description":"...",
                          "language":"Python",
                          "topics":["agent","hermes"],
                          "repo":{"repository":{"updated_at":"..."}}}
```

所有字段都在这个 JSON 里，解析一次就能拿到完整搜索列表。

### 完整操作

```
1. 搜索 + 保存
   timeout 10 curl -s -k \
     -o /tmp/gh_search.html \
     "https://github.com/search?q=<QUERY>&type=repositories&s=stars&o=desc" \
     -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

2. 提取 JSON 负载
   python3 -c "
   import json, re
   with open('/tmp/gh_search.html','r',encoding='utf-8',errors='replace') as f:
       html = f.read()
   m = re.search(r'<script[^>]*data-target=\"react-app\.embeddedData\"[^>]*>({.+?})</script>', html)
   if m:
       data = json.loads(m.group(1))
       for r in data['payload']['results']:
           stars = r.get('followers', '?')
           name = re.sub(r'<[^>]+>', '', r.get('hl_name', ''))  # strip <em> tags
           desc = re.sub(r'<[^>]+>', '', r.get('hl_trunc_description', ''))
           lang = r.get('language', '')
           topics = ', '.join(r.get('topics', [])[:3])
           print(f\"★{stars:>5} | {name}\")
           print(f\"    {desc[:100]}\")
           print(f\"    {lang} | {topics}\")
           print()
   "

3. 如果需要更多分页 → &p=2, &p=3 等追加 URL
```

---

## 方法 C：grep 轻量提取（Python 不可用时）

```
1. 搜索 + 保存（同上）

2. 提取仓库名
   grep -oP 'href=\"/[^\"]+/[^\"]+\"\|<a[^>]*href=\"/\K[^\"]+/[^\"]+(?=\")' /tmp/gh_search.html \
     | grep -v 'stargazers\|issues\|pull\|blob\|tree\|topics\|search\|login' \
     | sort -u | head -20

3. 提取星数（注意：这些星数未映射到具体仓库）
   grep -oP '\d+\s*(star|Star)' /tmp/gh_search.html | sort -u
```

---

## ⚠️ 关键 Pitfall

| 问题 | 后果 | 修复 |
|------|------|------|
| `curl ... | python3` 管道 | 容器 pipe buffer 导致超时 | **先 `-o` 保存到文件，再单独解析** |
| 缺少 `User-Agent` | GitHub 返回 429/403 | 加 `-H "User-Agent: Mozilla/5.0..."` |
| 缺少 `-k` | TLS 证书错（自签名容器） | 加 `-k` |
| 中文搜索词未编码 | 搜索结果偏差 | 用 `--data-urlencode` 或手动 percent-encode |
| 按需添加 `&o=desc` | 默认排序可能不相关 | 补 `&s=stars&o=desc` 按星数降序 |

---

## 验证清单

- [ ] `timeout` 时间设 8-12s（太短超时，太长阻塞流程）
- [ ] 保存文件 `-o /tmp/gh_<slug>.html` 先确认 exit code 0
- [ ] 提取后验证 `wc -c /tmp/gh_<slug>.html` > 10KB
- [ ] 至少前 5 个结果有星数、描述、语言信息
- [ ] 无敏感信息被写入 /tmp（纯公开搜索数据）
