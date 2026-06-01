"""
golden_cross.py — 金叉死叉策略

核心逻辑：
  - 检测短期均线上穿长期均线 → 金叉 (buy)
  - 检测短期均线下穿长期均线 → 死叉 (sell)
  - 支持多组均线对分析，综合评分

适用场景：趋势跟踪型策略，中长线持股
"""

import pandas as pd
import numpy as np
from typing import Any

from .base import BaseStrategy, Signal


class GoldenCrossStrategy(BaseStrategy):
    """
    金叉/死叉策略

    参数:
      fast_periods:  短周期列表，如 [5, 10, 20]
      slow_periods:  长周期列表，如 [20, 30, 60]
      cross_window:  检测交叉的前瞻窗口（交易日）
      confidence_weight: 多组均线对投票权重
    """

    def __init__(self, fast_periods: list[int] = None,
                 slow_periods: list[int] = None,
                 cross_window: int = 90,
                 min_ma_alive: int = 5):
        self._fast = fast_periods or [5, 10, 20]
        self._slow = slow_periods or [20, 30, 60]
        self._window = cross_window
        self._min_alive = min_ma_alive

        # 配对的 (快, 慢) 均线组合
        self._pairs = list(zip(self._fast, self._slow))

    @property
    def name(self) -> str:
        return "golden-cross"

    @property
    def description(self) -> str:
        return "金叉/死叉检测：短线上穿/下穿长线均线的交易信号"

    def get_config(self) -> dict:
        return {
            "fast_ma_periods": self._fast,
            "slow_ma_periods": self._slow,
            "ma_pairs": [[f, s] for f, s in self._pairs],
            "cross_window_days": self._window,
        }

    def _detect_cross(self, ma_fast: np.ndarray, ma_slow: np.ndarray) -> tuple[str, int]:
        """
        检测最近的金叉/死叉
        返回: ("golden"|"death"|"none", 距今交易日数)
        """
        min_len = min(len(ma_fast), len(ma_slow))
        if min_len < self._min_alive:
            return ("none", 999)

        # 只看最近 _window 个交易日
        start = max(0, min_len - self._window)
        for i in range(min_len - 1, start, -1):
            prev = i - 1
            if ma_fast[prev] <= ma_slow[prev] and ma_fast[i] > ma_slow[i]:
                return ("golden", min_len - 1 - i)
            if ma_fast[prev] >= ma_slow[prev] and ma_fast[i] < ma_slow[i]:
                return ("death", min_len - 1 - i)
        return ("none", 999)

    def evaluate(self, symbol: str, market: str, df: pd.DataFrame,
                 position: Any = None) -> list[Signal]:
        signals = []
        if df is None or len(df) < 50:
            return signals

        closes = df["close"].values

        golden_count = 0
        death_count = 0
        total_pairs = 0
        details = []

        for fast_p, slow_p in self._pairs:
            if len(closes) <= max(fast_p, slow_p) + 5:
                continue
            fa = pd.Series(closes).rolling(fast_p).mean().values
            sl = pd.Series(closes).rolling(slow_p).mean().values
            cross_type, days_ago = self._detect_cross(fa, sl)

            total_pairs += 1
            details.append({
                "pair": f"MA{fast_p}-MA{slow_p}",
                "cross": cross_type,
                "days_ago": days_ago,
                "fast_ma": round(float(fa[-1]), 2),
                "slow_ma": round(float(sl[-1]), 2),
            })

            if cross_type == "golden" and days_ago <= 10:
                golden_count += 1
            elif cross_type == "death" and days_ago <= 10:
                death_count += 1

        if total_pairs == 0:
            return signals

        current_price = round(float(closes[-1]), 4)

        # ── 综合判断 ──
        if golden_count > death_count:
            # 多组金叉 → 买入信号
            recent_pairs = [d for d in details if d["cross"] == "golden"]
            pairs_str = ", ".join(f"{p['pair']}({p['days_ago']}日前)" for p in recent_pairs[:3])
            confidence = min(0.9, 0.5 + golden_count / total_pairs * 0.4)
            signals.append(Signal(
                action="buy" if position is None or position.shares == 0 else "hold",
                symbol=symbol,
                market=market,
                price=current_price,
                confidence=confidence,
                strategy=self.name,
                reason=(
                    f"金叉信号：{golden_count}/{total_pairs}组均线对呈金叉，"
                    f"多头排列成立 ({pairs_str})"
                ),
                params={"cross_details": details, "golden_count": golden_count, "death_count": death_count},
            ))
        elif death_count >= golden_count and death_count > 0:
            # 多组死叉 → 卖出/减仓信号
            recent_pairs = [d for d in details if d["cross"] == "death"]
            pairs_str = ", ".join(f"{p['pair']}({p['days_ago']}日前)" for p in recent_pairs[:3])
            confidence = min(0.85, 0.4 + death_count / total_pairs * 0.4)
            signals.append(Signal(
                action="sell" if position and position.shares > 0 else "alert",
                symbol=symbol,
                market=market,
                price=current_price,
                confidence=confidence,
                strategy=self.name,
                reason=(
                    f"死叉信号：{death_count}/{total_pairs}组均线对呈死叉，"
                    f"空头排列成立 ({pairs_str})"
                ),
                params={"cross_details": details, "golden_count": golden_count, "death_count": death_count},
            ))
        else:
            # 中性
            signals.append(Signal(
                action="hold",
                symbol=symbol,
                market=market,
                price=current_price,
                confidence=0.3,
                strategy=self.name,
                reason=f"金叉{golden_count} vs 死叉{death_count}，趋势不明确",
                params={"cross_details": details},
            ))

        return signals
