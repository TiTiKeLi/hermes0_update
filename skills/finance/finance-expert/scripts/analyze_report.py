#!/usr/bin/env python3
"""
📉 财报关键指标解析
入口: python3 analyze_report.py <股票代码>
使用新浪/腾讯的财务数据接口
"""

import urllib.request, json, sys, re

headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}

# ====== 腾讯基础财务 ======
def fetch_tencent_finance(code: str):
    """获取腾讯基本面"""
    url = f"https://qt.gtimg.cn/q={code}"
    req = urllib.request.Request(url, headers={"Referer": "https://finance.qq.com", "User-Agent": "Mozilla/5.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        raw = resp.read().decode("gbk")
        parts = raw.strip().split("=", 1)[1].strip(";").strip('"').split("~")
        return {
            "name": parts[1] if len(parts) > 1 else "",
            "code": parts[2] if len(parts) > 2 else "",
            "price": parts[3] if len(parts) > 3 else "",
            "pe": parts[39] if len(parts) > 39 else "",  # 动态市盈率
            "pb": parts[46] if len(parts) > 46 else "",
            "mkt_cap": parts[45] if len(parts) > 45 else "",  # 总市值(万)
            "circ_cap": parts[44] if len(parts) > 44 else "",  # 流通市值
            "roe": parts[53] if len(parts) > 53 else "",
            "profit_ratio": parts[54] if len(parts) > 54 else "",  # 净利率
            "eps": parts[55] if len(parts) > 55 else "",
            "industry": parts[57] if len(parts) > 57 else "",
        }
    except:
        return None

def fmt_cap(val_str):
    """格式化市值"""
    try:
        v = float(val_str)
        if v > 100000000:
            return f"{v/100000000:.2f}万亿"
        return f"{v/10000:.2f}亿"
    except:
        return val_str

def main():
    if len(sys.argv) < 2:
        print("用法: python3 analyze_report.py <股票代码>")
        print("示例: python3 analyze_report.py sh600519")
        return
    
    code = sys.argv[1]
    data = fetch_tencent_finance(code)
    if not data:
        print(f"❌ 获取 {code} 财报数据失败")
        return
    
    output = []
    output.append(f"📊 {data['name']}({data['code']}) — 基本面概览")
    output.append("=" * 40)
    output.append(f"  最新价: {data['price']}")
    
    pe = data['pe']
    pb = data['pb']
    roe = data['roe']
    eps = data['eps']
    profit_ratio = data['profit_ratio']
    industry = data['industry']
    mkt_cap = fmt_cap(data['mkt_cap'])
    
    output.append(f"  行业: {industry}")
    output.append(f"  总市值: {mkt_cap}")
    output.append(f"  PE(市盈率): {pe}")
    output.append(f"  PB(市净率): {pb}")
    output.append(f"  EPS(每股收益): {eps}")
    
    if roe:
        roe_val = float(roe)
        roe_note = "优秀" if roe_val > 15 else "良好" if roe_val > 8 else "偏低"
        output.append(f"  ROE(净资产收益率): {roe}% — {roe_note}")
    
    if profit_ratio:
        output.append(f"  净利率: {profit_ratio}%")
    
    output.append("")
    output.append("📌 解读要点:")
    if pe and float(pe) > 0:
        output.append(f"  · PE={pe}: {'偏高（注意估值风险）' if float(pe) > 50 else '合理' if float(pe) < 30 else '中等偏高'}")
    if roe:
        output.append(f"  · ROE={roe}%: {'公司盈利能力强' if float(roe) > 15 else '盈利能力一般'}")
    if pe and roe and float(pe) > 0:
        # PEG粗略估算
        peg = float(pe) / float(roe) if float(roe) > 0 else 0
        output.append(f"  · PEG(估): {peg:.2f} {'(便宜)' if peg < 1.5 else '(合理)' if peg < 2.5 else '(偏贵)'}")
    
    print("\n".join(output))

if __name__ == "__main__":
    main()
