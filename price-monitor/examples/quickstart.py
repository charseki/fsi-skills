#!/usr/bin/env python3
"""
quickstart.py — price-monitor 快速上手指南

运行方式:
  python3 examples/quickstart.py

展示:
  1. 连接数据源获取行情
  2. 运行策略生成信号
  3. 模拟建仓与评估
"""

import os
import sys

SKILL_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, SKILL_DIR)

from core.market_data import fetch_history, unified_quote, detect_market
from core.portfolio import Portfolio, Position
from strategies.drawdown_rebalance import DrawdownRebalanceStrategy
from strategies.golden_cross import GoldenCrossStrategy
from strategies.ma_strategy import MovingAverageStrategy


def demo_data():
    print("=" * 55)
    print("  1. 数据源演示")
    print("=" * 55)

    for sym in ["512890", "600519", "AAPL"]:
        print(f"\n  📡 查询 {sym} ...")
        quote = unified_quote(sym)
        if quote and quote.get("data"):
            d = quote["data"]
            print(f"     {d.get('name', 'N/A')} 现价: {d.get('price', 'N/A')}  "
                  f"涨跌: {d.get('chg_pct', 'N/A')}%")


def demo_strategies():
    print(f"\n{'='*55}")
    print("  2. 策略信号演示")
    print("=" * 55)

    symbols = {
        "512890": ("红利低波ETF", "a"),
        "515220": ("煤炭ETF", "a"),
        "600519": ("贵州茅台", "a"),
    }

    strategies = [
        DrawdownRebalanceStrategy(),
        GoldenCrossStrategy(),
        MovingAverageStrategy(),
    ]

    for sym, (name, market) in symbols.items():
        print(f"\n  📈 {name} ({sym})")
        df = fetch_history(market, sym, days=180)
        if df is None or df.empty:
            print("     ⏭️ 无数据")
            continue
        print(f"     数据: {len(df)} 个交易日 ({df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')})")
        print(f"     最新价: {df['close'].iloc[-1]:.4f}")

        for strat in strategies:
            try:
                sigs = strat.evaluate(sym, market, df)
                for s in sigs:
                    emoji = {"buy": "🟢", "sell": "🔴", "add": "📈", "reduce": "📉",
                             "hold": "⏸️", "alert": "⚠️"}.get(s.action, "❓")
                    print(f"     {emoji} [{strat.name}] {s.action.upper()} "
                          f"(信心: {s.confidence:.0%})")
                    print(f"        {s.reason[:80]}...")
            except Exception as e:
                print(f"     ⚠️ {strat.name}: {e}")


def demo_portfolio():
    print(f"\n{'='*55}")
    print("  3. 持仓模拟")
    print("=" * 55)

    pf = Portfolio("演示组合")
    pf.record_trade("512890", "红利低波ETF", "buy", 1000, 1.025,
                    strategy="manual", reason="开仓")
    pf.record_trade("515220", "煤炭ETF", "buy", 800, 1.125,
                    strategy="manual", reason="开仓")
    pf.record_trade("600519", "贵州茅台", "buy", 100, 1320.0,
                    strategy="manual", reason="开仓")

    prices = {}
    for p in pf.positions:
        quote = unified_quote(p.symbol)
        if quote and quote.get("data"):
            d = quote["data"]
            prices[p.symbol] = d.get("price", 0)
        else:
            df = fetch_history(p.market, p.symbol, days=5)
            if df is not None and not df.empty:
                prices[p.symbol] = float(df["close"].values[-1])

    result = pf.evaluate(prices)
    print(f"\n  组合: {result['portfolio']}")
    print(f"  总成本: ¥{result['total_cost']:.2f}")
    print(f"  总市值: ¥{result['total_value']:.2f}")
    print(f"  总盈亏: {result['total_profit_pct']:+.2f}%")
    print()
    for pos in result["positions"]:
        emoji = "🟢" if pos["profit_pct"] >= 0 else "🔴"
        print(f"  {emoji} {pos['name']} ({pos['symbol']})")
        print(f"     持仓: {pos['shares']} | 成本: {pos['cost_price']:.4f}")
        print(f"     现价: {pos.get('current_price', 0):.4f} | 盈亏: {pos['profit_pct']:+.2f}%")

    path = pf.save_snapshot("demo")
    print(f"\n  快照已保存: {path}")


if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  🏭 price-monitor 快速入门")
    print(f"  {os.path.dirname(SKILL_DIR)}")
    print(f"{'='*55}")

    demo_data()
    demo_strategies()
    demo_portfolio()

    print(f"\n{'='*55}")
    print("  ✅ 演示完成")
    print(f"{'='*55}")
