"""
ma_strategy.py — 均线排列策略

核心逻辑：
  - 多周期均线多头排列 → 上升趋势 → buy / hold
  - 多周期均线空头排列 → 下降趋势 → sell / avoid
  - 均线粘合向上发散 → 启动信号
  - 价格偏离均线过大 → 超买/超卖提示

适用场景：趋势判断，辅助其他策略做过滤
"""

import pandas as pd
import numpy as np
from typing import Any

from .base import BaseStrategy, Signal


class MovingAverageStrategy(BaseStrategy):
    """
    均线排列策略

    参数:
      ma_periods:      均线周期列表，默认 [5, 10, 20, 30, 60, 120]
      buy_threshold:   多头排列占比达到此值则买入 (默认 0.66)
      sell_threshold:  空头排列占比达到此值则卖出 (默认 0.66)
      overbought_pct:  价格偏离 MA120 百分比的超买阈值
      oversold_pct:    价格偏离 MA120 百分比的超卖阈值
    """

    def __init__(self, ma_periods: list[int] = None,
                 buy_threshold: float = 0.66,
                 sell_threshold: float = 0.66,
                 overbought_pct: float = 25.0,
                 oversold_pct: float = -15.0):
        self._mas = ma_periods or [5, 10, 20, 30, 60, 120]
        self._buy_th = buy_threshold
        self._sell_th = sell_threshold
        self._overbought = overbought_pct
        self._oversold = oversold_pct

    @property
    def name(self) -> str:
        return "ma-trend"

    @property
    def description(self) -> str:
        return "均线排列趋势：多头/空头排列判断 + 超买超卖提示"

    def get_config(self) -> dict:
        return {
            "ma_periods": self._mas,
            "buy_threshold": self._buy_th,
            "sell_threshold": self._sell_th,
            "overbought_pct": self._overbought,
            "oversold_pct": self._oversold,
        }

    def evaluate(self, symbol: str, market: str, df: pd.DataFrame,
                 position: Any = None) -> list[Signal]:
        signals = []
        if df is None or len(df) < max(self._mas) + 5:
            return signals

        closes = df["close"].values
        current_price = closes[-1]

        # 计算各周期均线当前值
        ma_values = {}
        for p in self._mas:
            if len(closes) >= p:
                ma_values[p] = pd.Series(closes).rolling(p).mean().values[-1]
            else:
                ma_values[p] = None

        valid_mas = {p: v for p, v in ma_values.items() if v is not None}
        if len(valid_mas) < 3:
            return signals

        sorted_p = sorted(valid_mas.keys())
        sorted_v = [valid_mas[p] for p in sorted_p]

        # 判断排列方向
        bullish_count = sum(1 for i in range(len(sorted_v) - 1) if sorted_v[i] > sorted_v[i + 1])
        bearish_count = sum(1 for i in range(len(sorted_v) - 1) if sorted_v[i] < sorted_v[i + 1])
        total_pairs = len(sorted_v) - 1

        # 计算偏离度（相对 MA120 或最长均线）
        longest_ma_p = sorted_p[-1]
        longest_ma_v = valid_mas[longest_ma_p]
        deviation_pct = (current_price - longest_ma_v) / longest_ma_v * 100 if longest_ma_v > 0 else 0

        # 计算均线粘合度（最近几条均线的标准差 / 均值）
        recent_mas = sorted_v[-4:]  # 最长4条
        ma_mean = np.mean(recent_mas)
        ma_std = np.std(recent_mas) / ma_mean * 100 if ma_mean > 0 else 0
        is_tight = ma_std < 2.0  # 均线粘合判断

        # 格式化均线值
        ma_str = ", ".join(f"MA{p}={v:.2f}" for p, v in zip(sorted_p, sorted_v))

        # ── 信号判断 ──
        has_position = position is not None and position.shares > 0

        # 1. 多头排列
        if bullish_count / total_pairs >= self._buy_th:
            confidence = min(0.85, 0.5 + bullish_count / total_pairs * 0.35)
            # 均线粘合后发散是更可靠的信号
            extra = "均线粘合后向上发散，" if is_tight else ""
            signals.append(Signal(
                action="hold" if has_position else "buy",
                symbol=symbol,
                market=market,
                price=round(current_price, 4),
                confidence=confidence,
                strategy=self.name,
                reason=(
                    f"多头排列 ({bullish_count}/{total_pairs})，{extra}"
                    f"MA趋势向上。{ma_str}"
                ),
                params={
                    "trend": "bullish",
                    "bullish_ratio": round(bullish_count / total_pairs, 2),
                    "ma_values": {str(k): round(v, 2) for k, v in valid_mas.items()},
                    "deviation_pct": round(deviation_pct, 2),
                    "is_tight": is_tight,
                },
            ))

        # 2. 空头排列
        elif bearish_count / total_pairs >= self._sell_th:
            confidence = min(0.8, 0.5 + bearish_count / total_pairs * 0.3)
            signals.append(Signal(
                action="sell" if has_position else "alert",
                symbol=symbol,
                market=market,
                price=round(current_price, 4),
                confidence=confidence,
                strategy=self.name,
                reason=(
                    f"空头排列 ({bearish_count}/{total_pairs})，"
                    f"MA趋势向下。{ma_str}"
                ),
                params={
                    "trend": "bearish",
                    "bearish_ratio": round(bearish_count / total_pairs, 2),
                    "ma_values": {str(k): round(v, 2) for k, v in valid_mas.items()},
                    "deviation_pct": round(deviation_pct, 2),
                },
            ))

        # 3. 均线粘合（变盘前兆）
        elif is_tight:
            signals.append(Signal(
                action="alert",
                symbol=symbol,
                market=market,
                price=round(current_price, 4),
                confidence=0.4,
                strategy=self.name,
                reason=(
                    f"均线粘合 (std={ma_std:.1f}%)，变盘信号，"
                    f"等待方向选择。{ma_str}"
                ),
                params={"trend": "tight", "ma_std_pct": round(ma_std, 2)},
            ))

        # ── 超买/超卖提示（辅助信号，独立判断） ──
        if deviation_pct > self._overbought:
            signals.append(Signal(
                action="alert",
                symbol=symbol,
                market=market,
                price=round(current_price, 4),
                confidence=0.5,
                strategy=self.name,
                reason=(
                    f"超买预警：价格偏离MA{longest_ma_p}达 +{deviation_pct:.1f}%，"
                    f"注意回调风险"
                ),
                params={
                    "deviation_type": "overbought",
                    "deviation_pct": round(deviation_pct, 2),
                    "longest_ma": longest_ma_p,
                },
            ))
        elif deviation_pct < self._oversold:
            signals.append(Signal(
                action="alert",
                symbol=symbol,
                market=market,
                price=round(current_price, 4),
                confidence=0.5,
                strategy=self.name,
                reason=(
                    f"超卖提示：价格偏离MA{longest_ma_p}达 {deviation_pct:.1f}%，"
                    f"可能超跌反弹"
                ),
                params={
                    "deviation_type": "oversold",
                    "deviation_pct": round(deviation_pct, 2),
                    "longest_ma": longest_ma_p,
                },
            ))

        return signals
