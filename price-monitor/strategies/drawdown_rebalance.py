"""
drawdown_rebalance.py — 回撤再平衡策略

核心逻辑：
  - 计算当前回撤 = (当前价 - 区间最高价) / 区间最高价 × 100
  - 回撤超过 threshold_add % → 加仓信号 (越跌越买)
  - 回撤反弹到 threshold_sell % → 减仓信号 (反弹减仓)
  - 可配置多档位阶梯加仓

适用场景：定投型 ETF、指数基金、蓝筹股
"""

import pandas as pd
import numpy as np
from typing import Any

from .base import BaseStrategy, Signal


class DrawdownRebalanceStrategy(BaseStrategy):
    """
    回撤再平衡策略

    通过监控回撤幅度，在回调时加仓、反弹时减仓。

    参数（在 strategies.yaml 或构建时传入）:
      lookback_days:    回撤计算窗口（默认 120 交易日）
      add_thresholds:   加仓回撤档位 [(回撤%, 加仓比例%), ...]
                        如 [(-5, 10), (-10, 15), (-15, 25), (-20, 40)]
      sell_recovery:    反弹减仓阈值（从回撤低点反弹 %）
      min_interval_days: 同方向最小间隔天数
      max_single_pct:   单次操作上限（占持仓 %）
    """

    def __init__(self, lookback_days: int = 120,
                 add_thresholds: list[tuple] = None,
                 sell_recovery: float = 50.0,
                 min_interval_days: int = 5,
                 max_single_pct: float = 20.0):
        self._lookback = lookback_days
        self._add_thresholds = add_thresholds or [
            (-5, 10),   # 回撤 5%, 加仓 10%
            (-10, 15),  # 回撤 10%, 加仓 15%
            (-15, 25),  # 回撤 15%, 加仓 25%
            (-20, 40),  # 回撤 20%, 加仓 40%
        ]
        self._sell_recovery = sell_recovery  # 从低点反弹 % 就卖
        self._min_interval = min_interval_days
        self._max_single_pct = max_single_pct

        # 状态追踪：{symbol: {last_add_date, last_sell_date, last_bottom_price}}
        self._state: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return "drawdown-rebalance"

    @property
    def description(self) -> str:
        return "回撤再平衡：回撤加仓 + 反弹减仓，适合定投ETF"

    def get_config(self) -> dict:
        return {
            "lookback_days": self._lookback,
            "add_thresholds": self._add_thresholds,
            "sell_recovery_pct": self._sell_recovery,
            "min_interval_days": self._min_interval,
        }

    def evaluate(self, symbol: str, market: str, df: pd.DataFrame,
                 position: Any = None) -> list[Signal]:
        """评估回撤信号"""
        signals = []
        if df is None or len(df) < 20:
            return signals

        closes = df["close"].values
        dates = df["date"].values

        # 计算回撤序列
        rolling_max = np.maximum.accumulate(closes)
        drawdown = (closes - rolling_max) / rolling_max * 100

        current_dd = drawdown[-1]
        current_close = closes[-1]
        peak = rolling_max[-1]
        current_date = str(dates[-1])[:10] if len(dates) > 0 else ""

        # 从峰值回撤了多少
        dd_from_peak = (current_close - peak) / peak * 100

        # 找回撤低点（最近60日）
        recent_window = min(60, len(drawdown))
        min_dd_idx = np.argmin(drawdown[-recent_window:])
        min_dd = drawdown[-recent_window + min_dd_idx]
        bottom_price = closes[-recent_window + min_dd_idx]

        # 从低点反弹幅度
        recovery_pct = (current_close - bottom_price) / bottom_price * 100 if bottom_price > 0 else 0

        state = self._state.setdefault(symbol, {
            "last_add_date": "",
            "last_sell_date": "",
            "last_bottom_price": bottom_price,
            "last_bottom_dd": min_dd,
        })

        # ── 判断加仓信号 ──
        current_dd_actual = drawdown[-1]
        # 找到触发的档位（从深到浅，取最深触发的档位）
        triggered_add = None
        for threshold, pct in sorted(self._add_thresholds, key=lambda x: x[0], reverse=True):
            if current_dd_actual <= threshold:
                triggered_add = (threshold, pct)
                break

        if triggered_add is not None:
            # 检查间隔
            if current_date != state.get("last_add_date", ""):
                signals.append(Signal(
                    action="add",
                    symbol=symbol,
                    market=market,
                    price=round(current_close, 4),
                    confidence=min(0.9, abs(triggered_add[0]) / 25),
                    strategy=self.name,
                    reason=(
                        f"回撤 {current_dd_actual:.1f}% 触发加仓档位 {triggered_add[0]}%，"
                        f"建议加仓 {triggered_add[1]}% 持仓比例"
                    ),
                    params={
                        "drawdown_pct": round(current_dd_actual, 2),
                        "suggested_add_pct": triggered_add[1],
                        "peak_price": round(peak, 4),
                        "lookback_days": self._lookback,
                    },
                ))
                state["last_add_date"] = current_date

        # ── 判断减仓信号（从低点反弹） ──
        if recovery_pct >= self._sell_recovery:
            if current_date != state.get("last_sell_date", ""):
                # 反弹达到阈值，触发减仓
                sell_pct = min(self._max_single_pct, recovery_pct * 0.5)
                signals.append(Signal(
                    action="reduce",
                    symbol=symbol,
                    market=market,
                    price=round(current_close, 4),
                    confidence=min(0.8, recovery_pct / 80),
                    strategy=self.name,
                    reason=(
                        f"从低点反弹 {recovery_pct:.1f}%，达减仓阈值 {self._sell_recovery}%，"
                        f"建议减仓 {sell_pct:.0f}% 持仓"
                    ),
                    params={
                        "recovery_pct": round(recovery_pct, 2),
                        "suggested_sell_pct": round(sell_pct, 1),
                        "bottom_price": round(bottom_price, 4),
                        "min_drawdown": round(min_dd, 2),
                    },
                ))
                state["last_sell_date"] = current_date

        # 更新状态
        if min_dd < state.get("last_bottom_dd", 0):
            state["last_bottom_price"] = bottom_price
            state["last_bottom_dd"] = min_dd

        return signals
