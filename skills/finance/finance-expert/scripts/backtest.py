#!/usr/bin/env python3
"""
🎯 策略回测引擎 v1
支持: 均线策略 / 定投策略 / 自定义信号
用法: 
  python3 backtest.py --code sh000001 --strategy ma --params "5,20"
  python3 backtest.py --code sz399300 --strategy ma --params "10,30"
"""

import urllib.request, json, sys, argparse
from datetime import datetime, timedelta

headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.qq.com"}

# ====== 获取历史日K线 ======
def fetch_kline(code: str, days=120):
    """获取日K线数据（腾讯财经）"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq"
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
    except:
        return []
    
    # 腾讯返回格式: data -> [code] -> day -> [[日期, 开, 收, 高, 低, 成交量], ...]
    try:
        day_data = data.get("data", {}).get(code, {}).get("day", [])
    except:
        day_data = []
    
    candles = []
    for d in day_data:
        if len(d) >= 6:
            candles.append({
                "date": d[0],
                "open": float(d[1]),
                "close": float(d[2]),
                "high": float(d[3]),
                "low": float(d[4]),
                "volume": float(d[5]),
            })
    return candles

# ====== 均线策略 ======
def strategy_ma(candles, fast=5, slow=20):
    """金叉死叉均线策略"""
    closes = [c["close"] for c in candles]
    signals = [0] * len(candles)  # 0=持有, 1=买入, -1=卖出
    positions = [False] * len(candles)  # True=持仓
    
    for i in range(slow, len(candles)):
        ma_fast = sum(closes[i-fast:i]) / fast
        ma_slow = sum(closes[i-slow:i]) / slow
        
        prev_fast = sum(closes[i-fast-1:i-1]) / fast if i > fast else ma_fast
        prev_slow = sum(closes[i-slow-1:i-1]) / slow if i > slow else ma_slow
        
        if prev_fast <= prev_slow and ma_fast > ma_slow:
            signals[i] = 1  # 金叉买入
            positions[i] = True
        elif prev_fast >= prev_slow and ma_fast < ma_slow:
            signals[i] = -1  # 死叉卖出
            positions[i] = False
        else:
            positions[i] = positions[i-1] if i > 0 else False
    
    return signals, positions

# ====== 回测引擎 ======
def run_backtest(candles, signals, initial_capital=100000, fee_rate=0.0003):
    """运行回测"""
    capital = initial_capital
    shares = 0
    trades = []
    daily_values = []
    
    for i, c in enumerate(candles):
        price = c["close"]
        
        if signals[i] == 1 and capital > 0:  # 买入
            buy_amount = capital * 0.95  # 95%仓位
            shares = buy_amount / price * (1 - fee_rate)
            cost = shares * price / (1 - fee_rate)  # 还原不含费用的成本
            capital -= cost
            trades.append({"date": c["date"], "type": "买入", "price": price, "value": cost})
        
        elif signals[i] == -1 and shares > 0:  # 卖出
            sell_value = shares * price * (1 - fee_rate)
            capital += sell_value
            trades.append({"date": c["date"], "type": "卖出", "price": price, "value": sell_value})
            shares = 0
        
        # 每日总资产
        total = capital + shares * price
        daily_values.append(total)
    
    # 最终清仓
    if shares > 0:
        final_price = candles[-1]["close"]
        sell_value = shares * final_price * (1 - fee_rate)
        capital += sell_value
        trades.append({"date": candles[-1]["date"], "type": "清仓", "price": final_price, "value": sell_value})
        shares = 0
    
    # 计算绩效
    final_value = capital
    total_return = (final_value - initial_capital) / initial_capital * 100
    
    # 最大回撤
    peak = daily_values[0]
    max_drawdown = 0
    for v in daily_values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_drawdown:
            max_drawdown = dd
    
    # 年化收益（假设约240个交易日）
    n_days = len(daily_values)
    if n_days > 0:
        annual_return = ((final_value / initial_capital) ** (240 / n_days) - 1) * 100
    else:
        annual_return = 0
    
    # 夏普比（简化）
    returns = []
    for j in range(1, len(daily_values)):
        if daily_values[j-1] > 0:
            returns.append(daily_values[j] / daily_values[j-1] - 1)
    if returns and len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std_r = var_r ** 0.5
        sharpe = (mean_r / std_r * (240 ** 0.5)) if std_r > 0 else 0
    else:
        sharpe = 0
    
    return {
        "initial": initial_capital,
        "final": round(final_value, 2),
        "total_return": round(total_return, 2),
        "annual_return": round(annual_return, 2),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe": round(sharpe, 2),
        "trades": len([t for t in trades if t["type"] != "清仓"]),
        "trade_list": trades,
        "n_days": n_days,
    }

# ====== 控制台输出 ======
def print_report(result, params_str=""):
    print("=" * 50)
    print(f"🎯 策略回测报告")
    if params_str:
        print(f"   参数: {params_str}")
    print("=" * 50)
    print(f"  📅 回测天数: {result['n_days']} 个交易日")
    print(f"  💰 初始资金: {result['initial']:,.0f}")
    print(f"  💎 最终资产: {result['final']:,.0f}")
    print(f"  📈 总收益率: {result['total_return']:+.2f}%")
    print(f"  📈 年化收益: {result['annual_return']:+.2f}%")
    print(f"  📉 最大回撤: {result['max_drawdown']:.2f}%")
    print(f"  📊 夏普比率: {result['sharpe']}")
    print(f"  🔄 交易次数: {result['trades']}")
    print("-" * 50)
    
    # 评估
    score = 0
    if result['annual_return'] > 15: score += 3
    elif result['annual_return'] > 8: score += 2
    elif result['annual_return'] > 0: score += 1
    
    if result['max_drawdown'] < 10: score += 3
    elif result['max_drawdown'] < 20: score += 2
    elif result['max_drawdown'] < 30: score += 1
    
    if result['sharpe'] > 1.5: score += 3
    elif result['sharpe'] > 0.8: score += 2
    elif result['sharpe'] > 0: score += 1
    
    levels = ["⭐ 差（需大幅优化）", "⭐⭐ 一般", "⭐⭐⭐ 可接受", "⭐⭐⭐⭐ 良好", "⭐⭐⭐⭐⭐ 优秀"]
    idx = min(score // 2, 4)
    print(f"  🏆 综合评分: {levels[idx]} ({score}/9)")
    
    if result['trades'] > 0:
        print("\n  📋 最近5笔交易:")
        for t in result['trade_list'][-5:]:
            print(f"    {t['date']}  {t['type']} @ {t['price']:.2f}")

def main():
    parser = argparse.ArgumentParser(description="策略回测引擎")
    parser.add_argument("--code", default="sh000001", help="股票代码 (默认sh000001上证)")
    parser.add_argument("--strategy", default="ma", choices=["ma", "hold"], help="策略类型 (默认ma均线)")
    parser.add_argument("--params", default="5,20", help="策略参数 (均线: 快线天数,慢线天数)")
    parser.add_argument("--days", type=int, default=120, help="回测天数 (默认120)")
    args = parser.parse_args()
    
    # 获取数据
    print(f"📡 获取 {args.code} 历史数据 ({args.days}天)...")
    candles = fetch_kline(args.code, args.days)
    if not candles:
        print("❌ 获取K线数据失败")
        return
    print(f"✅ 获取到 {len(candles)} 条日K线")
    print(f"   时间范围: {candles[0]['date']} ~ {candles[-1]['date']}")
    print()
    
    if args.strategy == "hold":
        # 简单持有策略（基准）
        signals = [0] * len(candles)
        signals[0] = 1  # 第一天买入
        params_str = "买入持有"
    elif args.strategy == "ma":
        fast, slow = map(int, args.params.split(","))
        signals, _ = strategy_ma(candles, fast, slow)
        params_str = f"均线策略 MA({fast},{slow})"
    
    result = run_backtest(candles, signals)
    print_report(result, params_str)

if __name__ == "__main__":
    main()
