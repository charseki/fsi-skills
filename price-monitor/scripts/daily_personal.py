#!/usr/bin/env python3
"""
daily_personal.py — 个人回撤加仓策略每日监控脚本

专为 cronjob 设计：
  - 只跑 drawdown-personal 策略
  - 只输出有信号的标的
  - 格式化输出方便推送
"""

import os
import sys
import json
from datetime import datetime

SKILL_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, SKILL_DIR)

from core.run import load_config, _load_strategy
from core.market_data import fetch_history
from core.portfolio import Portfolio


def run_personal_scan():
    """运行个人回撤策略扫描，返回格式化推送文本"""
    sym_data, strat_data = load_config()
    symbols = sym_data.get("symbols", [])
    global_cfg = strat_data.get("global", {})
    lookback = global_cfg.get("lookback_days", 250)

    # 加载个人策略
    for sc in strat_data.get("strategies", []):
        if sc["name"] == "drawdown-personal" and sc.get("enabled", True):
            strategy = _load_strategy("drawdown-personal", sc.get("params", {}))
            break
    else:
        return "❌ 个人回撤策略未启用"

    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"📊 个人回撤监控日报 — {today}")
    lines.append("")

    total_signals = 0
    for sym_info in symbols:
        symbol = sym_info["symbol"]
        name = sym_info.get("name", symbol)
        market = sym_info.get("market", "a")

        df = fetch_history(market, symbol, days=lookback)
        if df is None or len(df) < 20:
            continue

        sigs = strategy.evaluate(symbol, market, df)
        if not sigs:
            continue

        total_signals += len(sigs)
        current_price = float(df["close"].values[-1])
        lines.append(f"  📈 {name} ({symbol})  现价: {current_price:.4f}")

        for s in sigs:
            amt = s.params.get("add_amount", 0)
            if amt > 0:
                lines.append(f"     📉 +¥{amt:,} — {s.reason.split('，')[-1]}")
            else:
                lines.append(f"     ⚠️ {s.reason.split('，')[-1]}")
        lines.append("")

    if total_signals == 0:
        lines.append("  ✅ 暂无标的触发回撤加仓信号，安心持有。")
        lines.append("")

    lines.append("───")
    lines.append(f"{total_signals} 个信号 | {today}")

    return "\n".join(lines)


def main():
    result = run_personal_scan()
    print(result)


if __name__ == "__main__":
    main()
