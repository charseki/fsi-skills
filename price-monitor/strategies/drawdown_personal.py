"""
drawdown_personal.py — 个人专属回撤加仓策略

核心逻辑（你的规则）：
  每回撤3% → 提醒加仓 5,000 元
  每回撤5% → 提醒加仓 10,000 元
  每回撤8% → 提醒加仓 20,000 元
  回撤10%+ → 仅提醒观望，不加仓

关键设计：
  - 基于回撤趋势变化判断：只在「回撤正在加深」时触发
  - 每个档位每个标的只触发一次，直到价格回升后重置
  - 首次扫描时读取近10日回撤趋势，避免对历史深回撤重复报警
  - 价格回到峰值附近（回撤 < 1%）重置状态，进入下一轮监控

适用场景：A股/ETF/美股/基金的定投型加仓策略，帮你抓住正在发生的回调行情
"""

import pandas as pd
import numpy as np
from typing import Any

from .base import BaseStrategy, Signal


class PersonalDrawdownStrategy(BaseStrategy):
    """
    个人回撤加仓策略

    参数:
      thresholds:      回撤档位，格式 [(回撤%, 加仓金额, 标签)]
                       如 [(-3, 5000, "轻度加仓"), (-5, 10000, "中度加仓"),
                           (-8, 20000, "较大加仓"), (-10, 0, "观望")]
      reset_at_pct:   回撤恢复至此百分比时重置状态（默认 -1%，即接近峰值）
      lookback_days:  拉取历史数据的天数
      trend_days:     首次扫描时参考的近期回撤趋势天数（默认10日）
                      用于判断哪些回撤是"新发生的"
    """

    def __init__(self,
                 thresholds: list[tuple] = None,
                 reset_at_pct: float = -1.0,
                 lookback_days: int = 250,
                 trend_days: int = 10):
        self._thresholds = thresholds or [
            (-3, 5000, "轻度加仓"),
            (-5, 10000, "中度加仓"),
            (-8, 20000, "较大加仓"),
            (-10, 0, "观望等待"),
        ]
        # 按回撤深度排序（从浅到深）
        self._thresholds.sort(key=lambda x: x[0], reverse=True)
        self._reset_pct = reset_at_pct
        self._lookback = lookback_days
        self._trend_days = trend_days

        # 回撤趋势分析窗口（当前日往前看 trend_days 天）
        # 状态追踪
        # {symbol: {
        #   "last_dd": float,       # 上次扫描时的回撤值（用于判断趋势）
        #   "alerted": set[int],    # 已触发的档位 index
        #   "peak_price": float,    # 本周期峰值
        #   "peak_date": str,       # 峰值日期
        #   "first_scan": bool,     # 是否首次扫描
        #   "last_signal_date": str # 最近一次信号日期（避免同一天重复）
        # }}
        self._state: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return "drawdown-personal"

    @property
    def description(self) -> str:
        return "个人回撤加仓策略：3%/5%/8%阶梯加仓，10%+观望"

    def get_config(self) -> dict:
        return {
            "thresholds": [{"drawdown_pct": t[0], "amount": t[1], "label": t[2]}
                           for t in self._thresholds],
            "reset_at_pct": self._reset_pct,
            "lookback_days": self._lookback,
            "trend_days": self._trend_days,
        }

    def evaluate(self, symbol: str, market: str, df: pd.DataFrame,
                 position: Any = None) -> list[Signal]:
        """
        评估回撤状态，返回待触发的信号。

        状态机：
          1. 首次扫描：读取近 trend_days 日回撤走势，回撤已在加深的标的
             只触发「比已知最低点还低」的新档位
          2. 后续扫描：比较 last_dd 和当前回撤
             - 回撤加深 → 检查跨越了哪些档位
             - 回撤恢复 → 重置状态
             - 区间震荡 → 不发信号
        """
        signals = []
        if df is None or len(df) < 20:
            return signals

        closes = df["close"].values
        dates = df["date"].values
        current_price = closes[-1]
        current_date = str(dates[-1])[:10]

        # ── 计算滚动峰值和回撤 ──
        rolling_max = np.maximum.accumulate(closes)
        drawdown = (closes - rolling_max) / rolling_max * 100

        current_dd = drawdown[-1]           # 今日回撤
        peak_price = rolling_max[-1]        # 当前峰值
        peak_idx = int(np.argmax(rolling_max))
        peak_date = str(dates[peak_idx])[:10]

        # ── 初始化状态 ——
        if symbol not in self._state:
            # 首次扫描：分析近期回撤趋势
            trend_end = max(0, len(drawdown) - 1)          # 今日
            trend_start = max(0, len(drawdown) - 1 - self._trend_days)  # trend_days 日前

            # 近期的最大回撤（最深的值）
            recent_min_dd = float(np.min(drawdown[trend_start:trend_end + 1]))
            # 近期的起始回撤
            start_dd = float(drawdown[trend_start])
            # 近期的变化量
            dd_change = current_dd - start_dd

            self._state[symbol] = {
                "last_dd": start_dd,           # 趋势起点
                "alerted": set(),
                "peak_price": peak_price,
                "peak_date": peak_date,
                "first_scan": True,
                "last_signal_date": "",
            }

        state = self._state[symbol]
        last_dd = state["last_dd"]

        # ── 更新峰值 ──
        if peak_price > state.get("peak_price", 0):
            state["peak_price"] = peak_price
            state["peak_date"] = peak_date

        # ── 回撤已恢复 → 重置 ──
        if current_dd > self._reset_pct:
            if state["alerted"]:
                # 回撤恢复，发一条重置通知
                signals.append(Signal(
                    action="alert",
                    symbol=symbol,
                    market=market,
                    price=round(current_price, 4),
                    confidence=0.5,
                    strategy=self.name,
                    reason=(
                        f"🔄 回撤已恢复至 {current_dd:.1f}%，重置监控。"
                        f"上轮最深回撤 {state.get('last_dd', 0):.1f}%"
                    ),
                    params={"event": "cycle_reset"},
                ))
            # 重置
            state["alerted"] = set()
            state["last_dd"] = current_dd
            state["peak_price"] = peak_price
            state["peak_date"] = peak_date
            state["first_scan"] = True
            return signals

        # ── 回撤在加深 → 检查跨越的档位 ──
        if current_dd < last_dd:
            # 找到从 last_dd → current_dd 之间跨越的档位
            # 例如：last_dd=-2%, current_dd=-7%
            # 跨越了 -3% 和 -5% 两个档位
            for idx, (thresh, amount, label) in enumerate(self._thresholds):
                if idx in state["alerted"]:
                    continue  # 已触发过
                # 条件：last_dd 在 thresh 之上（-2% > -3%），
                #       current_dd 在 thresh 之下（-7% < -3%）
                # 即 thresh 在 (current_dd, last_dd) 区间内
                if last_dd > thresh >= current_dd:
                    state["alerted"].add(idx)
                    state["last_signal_date"] = current_date

                    pct_from_peak = (current_price - state["peak_price"]) / state["peak_price"] * 100

                    if amount > 0:
                        signals.append(Signal(
                            action="add",
                            symbol=symbol,
                            market=market,
                            price=round(current_price, 4),
                            confidence=min(0.9, abs(thresh) / 12),
                            strategy=self.name,
                            reason=(
                                f"📉 回撤加深至 {pct_from_peak:.1f}%（峰值 {state['peak_price']:.2f}），"
                                f"触发「{label}」档位 ({thresh}%)，建议加仓 ¥{amount:,}"
                            ),
                            params={
                                "threshold_pct": thresh,
                                "add_amount": amount,
                                "label": label,
                                "current_drawdown": round(pct_from_peak, 2),
                                "peak_price": round(state["peak_price"], 4),
                                "peak_date": state["peak_date"],
                                "last_dd": round(last_dd, 2),
                                "alerted_levels": sorted(state["alerted"]),
                            },
                        ))
                    else:
                        signals.append(Signal(
                            action="alert",
                            symbol=symbol,
                            market=market,
                            price=round(current_price, 4),
                            confidence=0.7,
                            strategy=self.name,
                            reason=(
                                f"⚠️ 深度回撤预警！回撤达 {pct_from_peak:.1f}%（峰值 {state['peak_price']:.2f}），"
                                f"触发「{label}」档位 ({thresh}%)，建议观望不加仓"
                            ),
                            params={
                                "threshold_pct": thresh,
                                "add_amount": 0,
                                "label": label,
                                "current_drawdown": round(pct_from_peak, 2),
                                "peak_price": round(state["peak_price"], 4),
                                "peak_date": state["peak_date"],
                                "last_dd": round(last_dd, 2),
                                "alerted_levels": sorted(state["alerted"]),
                            },
                        ))

            # 更新 last_dd
            state["last_dd"] = current_dd

        # ── 回撤在缩小（价格回升中） → 不发信号 ──
        # 但如果用户设置了首次扫描也告警，可以在这里加逻辑
        # 当前设计：首次扫描只发现「正在发生」的回撤

        return signals
