"""
base.py — 策略基类

所有量化策略继承 BaseStrategy，实现 evaluate() 接口。
evaluate() 返回 Signal 列表，每个 Signal 包含操作建议。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Signal:
    """
    交易信号

    action: buy / sell / add / reduce / hold / alert
    symbol: 标的代码
    name: 标的中文名称
    market: a / us / hk / fund
    price: 触发信号时的价格
    confidence: 信心分数 0.0 ~ 1.0
    strategy: 策略名称
    reason: 触发理由描述
    params: 额外参数
    """
    action: str
    symbol: str
    name: str = ""
    market: str = "a"
    price: float = 0.0
    confidence: float = 0.5
    strategy: str = ""
    reason: str = ""
    params: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class BaseStrategy(ABC):
    """
    策略基类

    子类需实现：
      - name: 策略名称
      - evaluate(symbol, market, df) -> list[Signal]
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        ...

    @property
    def description(self) -> str:
        """策略简介"""
        return ""

    @abstractmethod
    def evaluate(self, symbol: str, market: str, df: "pd.DataFrame",
                 position: Any = None) -> list[Signal]:
        """
        对单个标的进行策略评估

        参数:
          symbol:  标的代码
          market:  市场类型 (a/us/hk/fund)
          df:      历史行情 DataFrame (列: date, open, close, high, low, volume)
          position: 当前持仓信息 (Position 对象或 None)

        返回:
          Signal 列表
        """
        ...

    def get_config(self) -> dict:
        """返回策略可配置参数（子类可重写）"""
        return {}

    def validate(self) -> bool:
        """策略参数验证"""
        return True

    def __repr__(self) -> str:
        return f"<Strategy: {self.name}>"
