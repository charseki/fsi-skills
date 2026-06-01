"""
price-monitor — 量化交易策略引擎

定时扫描监控标的，运行多个量化策略，生成买入/卖出信号。
策略可插拔，后期随时添加新策略。

用法:
  source ~/venv/bin/activate && python3 core/run.py                            # 全量扫描
  python3 core/run.py --portfolio                                               # 评估当前持仓
  python3 core/run.py --strategy drawdown-rebalance                             # 只跑回撤策略
  python3 core/run.py --symbol 512890                                           # 只扫单个标的
  python3 core/run.py --json                                                    # 输出 JSON 报告
  python3 core/run.py --add-position 512890 红利低波ETF 1000 1.025               # 添加持仓
  python3 examples/quickstart.py                                               # 快速演示
"""

import argparse
import json
import os
import sys
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from core.run import run_scan, evaluate_portfolio, load_config


def main():
    parser = argparse.ArgumentParser(
        description="price-monitor — 量化交易策略引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--strategy", "-s", help="只运行指定策略")
    parser.add_argument("--symbol", help="只扫描指定标的代码")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 报告")
    parser.add_argument("--portfolio", "-p", action="store_true", help="评估当前持仓")
    parser.add_argument("--add-position", nargs=4,
                        metavar=("SYMBOL", "NAME", "SHARES", "PRICE"),
                        help="添加持仓: --add-position 512890 红利低波ETF 1000 1.025")
    parser.add_argument("--list-symbols", action="store_true", help="列出当前监控标的")
    parser.add_argument("--list-strategies", action="store_true", help="列出当前配置的策略")
    args = parser.parse_args()

    if args.list_symbols:
        sym_data, _ = load_config()
        print(f"\n📋 监控标的 ({len(sym_data.get('symbols', []))}个)")
        for s in sym_data.get("symbols", []):
            print(f"  {s['symbol']:>8s}  {s.get('name',''):20s}  [{s.get('market','a')}]  {s.get('category','')}")
        return

    if args.list_strategies:
        _, strat_data = load_config()
        print(f"\n📋 策略配置 ({len(strat_data.get('strategies', []))}个)")
        for sc in strat_data.get("strategies", []):
            enabled = "✅" if sc.get("enabled", True) else "❌"
            print(f"  {enabled} {sc['name']:24s} → {sc.get('apply_to', 'all')}  "
                  f"参数: {json.dumps(sc.get('params', {}), ensure_ascii=False)}")
        return

    if args.add_position:
        from core.portfolio import Portfolio
        symbol, name, shares, price = args.add_position
        pf = Portfolio.load_latest()
        pf.record_trade(symbol, name, "buy", float(shares), float(price),
                        strategy="manual", reason="用户手动添加")
        path = pf.save_snapshot("manual_add")
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
