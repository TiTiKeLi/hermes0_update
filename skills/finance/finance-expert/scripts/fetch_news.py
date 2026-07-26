#!/usr/bin/env python3
"""
📰 财经新闻获取 - 快讯/要闻/市场动态
来源: 新浪财经 + 雪球 + 东方财富
"""

import urllib.request, json, re, sys, html

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
}

# ====== 新浪财经滚动新闻 ======
def fetch_sina_news(count=20):
    """获取新浪财经最新新闻"""
    url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num={count}"
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        items = data.get("result", {}).get("data", [])
        news = []
        for item in items:
            title = item.get("title", "")
            intro = item.get("intro", "")
            link = item.get("link", "")
            ctime = item.get("ctime", "")
            if title:
                news.append({"title": html.unescape(title), "intro": html.unescape(intro), "link": link, "time": ctime})
        return news
    except Exception as e:
        return []

# ====== 东方财富要闻 ======
def fetch_eastmoney_news(count=10):
    """东方财富要闻"""
    url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=&fields=f14,f12&_=1"
    # 东方财富新闻API - 可能被频控
    try:
        # 使用东方头条
        url2 = f"https://push2ex.eastmoney.com/getArticle?pageSize={count}&type=1"
        req = urllib.request.Request(url2, headers=headers)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        articles = data.get("data", [])
        news = []
        for art in articles:
            title = art.get("title", "")
            art_time = art.get("showTime", "")
            digest = art.get("digest", "")[:100]
            if title:
                news.append({"title": title, "intro": digest, "time": art_time})
        return news
    except:
        return []

# ====== 输出 ======
def main():
    output = []
    output.append("📰 最新财经要闻")
    output.append("=" * 40)
    
    # 1. 新浪财经
    sina_news = fetch_sina_news(15)
    if sina_news:
        output.append(f"\n🟡 新浪财经 (共{len(sina_news)}条)")
        output.append("-" * 30)
        for i, n in enumerate(sina_news[:10], 1):
            title = n["title"]
            t = n["time"][:10] if len(n["time"]) > 10 else n["time"]
            output.append(f"  {i}. [{t}] {title}")
            if n.get("intro"):
                output.append(f"     {'...' + n['intro'][:80] if len(n['intro']) > 80 else n['intro']}")
    else:
        output.append("\n⚠️ 新浪财经新闻获取失败")
    
    # 2. 东方财富
    east_news = fetch_eastmoney_news(8)
    if east_news:
        output.append(f"\n🟠 东方财富 (共{len(east_news)}条)")
        output.append("-" * 30)
        for i, n in enumerate(east_news[:5], 1):
            t = n.get("time", "")[:10]
            output.append(f"  {i}. [{t}] {n['title']}")
    else:
        output.append("\n⚠️ 东方财富新闻获取失败")
    
    output.append("")
    output.append("📌 数据来源: 新浪财经 / 东方财富")
    output.append("⏱ 获取时间: 实时获取")
    
    # 子命令：-k <关键词> 搜索
    if len(sys.argv) > 2 and sys.argv[1] == "-k":
        kw = sys.argv[2]
        output.append(f"\n🔍 搜索关键词: {kw}")
        # 用新浪搜索
        url = f"https://search.sina.com.cn/news?q={urllib.parse.quote(kw)}&range=all&c=news"
        output.append(f"   可自行访问: {url}")
    
    print("\n".join(output))

if __name__ == "__main__":
    main()
