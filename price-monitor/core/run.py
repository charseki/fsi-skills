#!/usr/bin/env python3
"""
run.py — price-monitor 主调度引擎

集中扫描所有监控标的，运行各策略生成交易信号。

用法:
  python3 run.py                          # 全量扫描
  python3 run.py --strategy drawdown-rebalance   # 只跑指定策略
  python3 run.py --symbol 512890                 # 只扫描指定标的
  python3 run.py --report                        # 输出报告到 reports/signals/
  python3 run.py --portfolio                     # 评估当前持仓
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import yaml

# 工程根目录
SKILL_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, SKILL_DIR)

from core.market_data import fetch_history, unified_quote, detect_market
from core.portfolio import Portfolio, Position, TradeRecord

# ── 加载策略 ────────────────────────────────────────
def _load_strategy(name: str, params: dict = None):
    """动态加载策略类"""
    p = params or {}
    if name == "drawdown-rebalance":
        from strategies.drawdown_rebalance import DrawdownRebalanceStrategy
        return DrawdownRebalanceStrategy(
            lookback_days=p.get("lookback_days", 120),
            add_thresholds=p.get("add_thresholds", [(-5, 10), (-10, 15), (-15, 25), (-20, 40)]),
            sell_recovery=p.get("sell_recovery", 50),
            min_interval_days=p.get("min_interval_days", 5),
            max_single_pct=p.get("max_single_pct", 20),
        )
    elif name == "golden-cross":
        from strategies.golden_cross import GoldenCrossStrategy
        return GoldenCrossStrategy(
            fast_periods=p.get("fast_periods", [5, 10, 20]),
            slow_periods=p.get("slow_periods", [20, 30, 60]),
            cross_window=p.get("cross_window", 90),
        )
    elif name == "ma-trend":
        from strategies.ma_strategy import MovingAverageStrategy
        return MovingAverageStrategy(
            ma_periods=p.get("ma_periods", [5, 10, 20, 30, 60, 120]),
            buy_threshold=p.get("buy_threshold", 0.66),
            sell_threshold=p.get("sell_threshold", 0.66),
            overbought_pct=p.get("overbought_pct", 25),
            oversold_pct=p.get("oversold_pct", -15),
        )
    elif name == "drawdown-personal":
        from strategies.drawdown_personal import PersonalDrawdownStrategy
        return PersonalDrawdownStrategy(
            thresholds=p.get("thresholds", [(-3, 5000, "轻度加仓"), (-5, 10000, "中度加仓"),
                                            (-8, 20000, "较大加仓"), (-10, 0, "观望等待")]),
            reset_at_pct=p.get("reset_at_pct", -1.0),
            lookback_days=p.get("lookback_days", 250),
        )
    else:
        raise ValueError(f"未知策略: {name}")


def load_config():
    """加载 symbols.yaml 和 strategies.yaml"""
    config_dir = os.path.join(SKILL_DIR, "config")

    symbols_path = os.path.join(config_dir, "symbols.yaml")
    with open(symbols_path, "r", encoding="utf-8") as f:
        sym_data = yaml.safe_load(f)

    strat_path = os.path.join(config_dir, "strategies.yaml")
    with open(strat_path, "r", encoding="utf-8") as f:
        strat_data = yaml.safe_load(f)

    return sym_data, strat_data


def _matches_scope(apply_to: str, symbol_info: dict) -> bool:
    """检查标的是否在策略适用范围内"""
    if apply_to == "all":
        return True
    if apply_to == "etf" and symbol_info.get("category") == "ETF":
        return True
    if apply_to == "stock" and symbol_info.get("category") == "股票":
        return True
    if apply_to == "fund" and symbol_info.get("category") == "基金":
        return True
    return False


def run_scan(strategy_filter: str = None,
             symbol_filter: str = None,
             output_json: bool = False) -> list[dict]:
    """执行全量扫描"""
    sym_data, strat_data = load_config()
    symbols = sym_data.get("symbols", [])
    global_cfg = strat_data.get("global", {})
    lookback = global_cfg.get("lookback_days", 120)
    strategies_cfg = strat_data.get("strategies", [])

    if symbol_filter:
        symbols = [s for s in symbols if s["symbol"] == symbol_filter]

    if strategy_filter:
        strategies_cfg = [s for s in strategies_cfg if s["name"] == strategy_filter]

    # 加载启用的策略
    strategies = []
    for sc in strategies_cfg:
        if not sc.get("enabled", True):
            continue
        try:
            strat = _load_strategy(sc["name"], sc.get("params", {}))
            strategies.append((strat, sc))
        except ValueError as e:
            print(f"⚠️  策略加载失败 {sc['name']}: {e}", file=sys.stderr)

    if not strategies:
        print("❌ 没有启用的策略", file=sys.stderr)
        return []

    # 加载最新持仓
    portfolio = Portfolio.load_latest()

    results = []
    print(f"\n{'='*55}")
    print(f"  📊 量化策略扫描  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  标的数: {len(symbols)} | 策略数: {len(strategies)}")
    print(f"{'='*55}\n")

    for sym_info in symbols:
        symbol = sym_info["symbol"]
        name = sym_info.get("name", symbol)
        market = sym_info.get("market", detect_market(symbol))

        print(f"  📈 {name} ({symbol}) ...", end=" ", flush=True)

        # 获取历史数据
        df = fetch_history(market, symbol, days=lookback)
        if df is None or len(df) < global_cfg.get("min_data_days", 20):
            print("⏭️ 数据不足")
            continue

        # 获取当前行情
        quote = unified_quote(symbol)
        current_price = quote.get("data", {}).get("price", 0) if quote else 0

        # 查找对应持仓
        position = None
        for p in portfolio.positions:
            if p.symbol == symbol:
                position = p
                break

        # 逐策略评估
        symbol_signals = []
        info = {"symbol": symbol, "name": name, "market": market, "price": current_price}

        for strat, sc in strategies:
            if not _matches_scope(sc.get("apply_to", "all"), sym_info):
                continue
            if symbol in sc.get("exclude", []):
                continue

            try:
                sigs = strat.evaluate(symbol, market, df, position)
                for s in sigs:
                    if not s.price and current_price:
                        s.price = round(float(current_price), 4)
                symbol_signals.extend(sigs)
            except Exception as e:
                print(f"⚠️ {strat.name} 异常: {e}")

        info["signals"] = [s.__dict__ for s in symbol_signals]
        results.append(info)

        # 打印结果
        action_emojis = {"buy": "🟢", "sell": "🔴", "add": "📈", "reduce": "📉",
                         "hold": "⏸️", "alert": "⚠️"}
        if symbol_signals:
            print(f"{current_price:.2f}" if current_price else "✅")
            for sig in symbol_signals:
                emoji = action_emojis.get(sig.action, "❓")
                print(f"    {emoji} [{sig.strategy}] {sig.action.upper()} "
                      f"(信心: {sig.confidence:.0%})")
                print(f"       📝 {sig.reason}")
        else:
            print(f"{current_price:.2f} 无信号" if current_price else "✅ 无信号")

        time.sleep(0.2)  # 限流保护

    # ── 汇总 ──
    buy_count = sum(1 for r in results for s in r["signals"] if s["action"] in ("buy", "add"))
    sell_count = sum(1 for r in results for s in r["signals"] if s["action"] in ("sell", "reduce"))
    alert_count = sum(1 for r in results for s in r["signals"] if s["action"] == "alert")

    print(f"\n{'='*55}")
    print(f"  📋 扫描汇总")
    print(f"     买入/加仓信号: {buy_count}")
    print(f"     卖出/减仓信号: {sell_count}")
    print(f"     预警/提示:     {alert_count}")
    print(f"     无信号标的:    {len(results) - buy_count - sell_count - alert_count}")
    print(f"{'='*55}")

    if output_json:
        output_path = os.path.join(SKILL_DIR, "reports", "signals",
                                   f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n  报告已保存: {output_path}")

    return results


def evaluate_portfolio():
    """评估当前持仓"""
    portfolio = Portfolio.load_latest()
    if not portfolio.positions:
        print("📭 当前无持仓")
        return

    print(f"\n{'='*55}")
    print(f"  💼 持仓评估  {portfolio.name}")
    print(f"{'='*55}")

    prices = {}
    details = []
    for p in portfolio.positions:
        quote = unified_quote(p.symbol)
        data = quote.get("data", {}) if quote else {}
        price = data.get("price", 0) if data else 0
        if not price:
            # 尝试从历史数据取最后收盘价
            df = fetch_history(p.market, p.symbol, days=5)
            if df is not None and not df.empty:
                price = float(df["close"].values[-1])
        prices[p.symbol] = price

        pl = p.profit_pct(price) if price else 0
        emoji = "🟢" if pl >= 0 else "🔴"
        print(f"  {emoji} {p.name} ({p.symbol})")
        print(f"     持仓: {p.shares:.2f} | 成本: {p.cost_price:.4f}")
        print(f"     现价: {price:.4f}" if price else "     现价: N/A")
        print(f"     盈亏: {pl:+.2f}% | 市值: {p.market_value(price):.2f}" if price else "")
        details.append((p, price, pl))

    # 汇总
    total_cost = sum(d[0].cost_total for d in details)
    total_value = sum(d[0].market_value(d[1]) for d in details)
    total_pl = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
    print(f"\n  📊 总成本: {total_cost:.2f}")
    print(f"  📊 总市值: {total_value:.2f}")
    print(f"  📊 总盈亏: {total_pl:+.2f}%")
    print(f"{'='*55}")


def main():
    parser = argparse.ArgumentParser(description="price-monitor 量化策略引擎")
    parser.add_argument("--strategy", help="只运行指定策略 (drawdown-rebalance / golden-cross / ma-trend)")
    parser.add_argument("--symbol", help="只扫描指定标的代码")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument("--portfolio", action="store_true", help="评估当前持仓")
    parser.add_argument("--add-position", nargs=4,
                        metavar=("SYMBOL", "NAME", "SHARES", "PRICE"),
                        help="添加持仓: --add-position 512890 红利低波ETF 1000 1.35")
    args = parser.parse_args()

    # 处理 --add-position
    if args.add_position:
        symbol, name, shares, price = args.add_position
        portfolio = Portfolio.load_latest()
        portfolio.record_trade(symbol, name, "buy",
                               float(shares), float(price),
                               strategy="manual", reason="用户手动添加")
        path = portfolio.save_snapshot("manual_add")
        print(f"✅ 已添加持仓 {name}({symbol}) {shares}份@{price}")
        print(f"   快照保存: {path}")
        return

    if args.portfolio:
        evaluate_portfolio()
        return

    run_scan(strategy_filter=args.strategy,
             symbol_filter=args.symbol,
             output_json=args.json)


if __name__ == "__main__":
    main()
