#!/usr/bin/env python3
"""
📊 行情数据获取 - 多源聚合
腾讯财经API (主力) + Yahoo Finance (美股备用)
支持: 全球指数 / 个股 / ETF
"""

import urllib.request, json, sys, re

# ====== 腾讯财经 ======
def fetch_tencent(codes: list) -> list:
    """获取腾讯行情"""
    qstr = ",".join(codes)
    url = f"https://qt.gtimg.cn/q={qstr}"
    req = urllib.request.Request(url, headers={"Referer": "https://finance.qq.com", "User-Agent": "Mozilla/5.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        raw = resp.read().decode("gbk")
    except:
        return []
    
    results = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        try:
            parts = line.split("=", 1)[1].strip(";").strip('"').split("~")
            if len(parts) < 5:
                continue
            name = parts[1]
            code = parts[2]
            price = parts[3]
            change_pct = parts[32] if len(parts) > 32 else ""
            change_val = parts[31] if len(parts) > 31 else ""
            high = parts[33] if len(parts) > 33 else ""
            low = parts[34] if len(parts) > 34 else ""
            open_ = parts[5] if len(parts) > 5 else ""
            pre_close = parts[4] if len(parts) > 4 else ""
            volume = parts[6] if len(parts) > 6 else ""
            amount = parts[37] if len(parts) > 37 else ""
            results.append({
                "source": "腾讯",
                "name": name, "code": code,
                "price": price, "change_val": change_val,
                "change_pct": change_pct,
                "open": open_, "high": high, "low": low,
                "pre_close": pre_close,
                "volume": volume, "amount": amount
            })
        except:
            continue
    return results

# ====== 新浪财经 ======
def fetch_sina(codes: list) -> list:
    """获取新浪行情"""
    import codecs
    qstr = ",".join(codes)
    url = f"https://hq.sinajs.cn/list={qstr}"
    req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        raw = resp.read().decode("gbk")
    except:
        return []
    
    results = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        try:
            parts = line.split("=", 1)[1].strip(";").strip('"').split(",")
            if len(parts) < 4:
                continue
            name = parts[0]
            price = parts[1]
            change_pct = parts[3]
            change_val = parts[2] if len(parts) > 3 else ""
            results.append({
                "source": "新浪",
                "name": name,
                "price": price,
                "change_pct": change_pct,
                "change_val": change_val,
            })
        except:
            continue
    return results

# ====== Yahoo Finance (美股备用) ======
def fetch_yahoo(ticker: str):
    """获取单一美股"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read())
        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        quotes = result.get("indicators", {}).get("quote", [{}])[0]
        closes = [c for c in quotes.get("close", []) if c is not None]
        opens = [o for o in quotes.get("open", []) if o is not None]
        return {
            "source": "Yahoo",
            "price": meta.get("regularMarketPrice", ""),
            "prev_close": meta.get("previousClose", ""),
            "change_pct": meta.get("chartPreviousClose", ""),
            "opens": opens[-1] if opens else "",
            "closes": closes[-1] if closes else "",
            "high": meta.get("regularMarketDayHigh", ""),
            "low": meta.get("regularMarketDayLow", ""),
        }
    except:
        return None

# ====== 预设指数代码 ======
INDEX_TENCENT = {
    "上证综指": "sh000001",
    "沪深300": "sh000300",
    "上证50": "sh000016",
    "创业板指": "sz399006",
    "科创50": "sh000688",
    "恒生指数": "hkHSI",
    "恒生科技": "hkHSTECH",
    "标普500": "usINX",
    "道琼斯": "usDJI",
    "纳斯达克": "usIXIC",
    "日经225": "usNI225",
    "富时A50": "usXIN9",
}

INDEX_SINA = {
    "标普500": "gb_$inx",
    "纳斯达克": "gb_ixic",
    "道琼斯": "gb_$dji",
    "恒生指数": "rt_hkHSI",
}

# ====== 输出格式化 ======
def fmt_stock(s):
    """格式化个股/指数"""
    p = s.get("price", "")
    cp = s.get("change_pct", "")
    cv = s.get("change_val", "")
    n = s.get("name", "")
    h = s.get("high", "") or ""
    l = s.get("low", "") or ""
    v = s.get("volume", "") or ""
    a = s.get("amount", "") or ""
    
    # 判断颜色
    sign = "🔴" if cp.startswith("-") else "🟢"
    line = f"  {sign} {n}: {p}  {cv} ({cp}%)"
    if h and l:
        line += f"  [高{h} 低{l}]"
    return line

def fmt_tencent_us(s):
    """美股腾讯格式"""
    n = s.get("name", "")
    p = s.get("price", "")
    cv = s.get("change_val", "")
    cp = s.get("change_pct", "")
    o = s.get("open", "")
    h = s.get("high", "")
    l = s.get("low", "")
    pc = s.get("pre_close", "")
    sign = "🔴" if float(cp) < 0 else "🟢"
    line = f"  {sign} {n}: {p}  {cv} ({cp}%)"
    if o:
        line += f"  开{o} 高{h} 低{l} 昨收{pc}"
    return line

# ====== 主流程 ======
def main():
    output_lines = []
    output_lines.append("📊 全球主要指数行情")
    output_lines.append("=" * 40)
    
    # 1. 腾讯 - 全量指数
    tencent_codes = list(INDEX_TENCENT.values())
    t_data = fetch_tencent(tencent_codes)
    
    # 美股索引
    us_names = {"usINX", "usDJI", "usIXIC", "usNI225", "usXIN9"}
    
    for d in t_data:
        code = d["code"]
        if code in us_names:
            output_lines.append(fmt_tencent_us(d))
        else:
            output_lines.append(fmt_stock(d))
    
    output_lines.append("")
    output_lines.append("📰 数据源: 腾讯财经 | Yahoo Finance")
    
    # 2. 如果有参数 -s <股票代码>，获取个股
    if len(sys.argv) > 2 and sys.argv[1] == "-s":
        stock_code = sys.argv[2]
        output_lines.append(f"\n🔍 个股查询: {stock_code}")
        s_data = fetch_tencent([stock_code])
        for d in s_data:
            output_lines.append(fmt_tencent_us(d))
    
    # 3. 如果有 -a 显示所有可用指数
    if "-a" in sys.argv:
        output_lines.append("\n📋 可用指数代码:")
        for name, code in INDEX_TENCENT.items():
            output_lines.append(f"   {name}: {code}")
    
    print("\n".join(output_lines))

if __name__ == "__main__":
    main()
