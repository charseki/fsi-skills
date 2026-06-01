"""
portfolio.py — 持仓管理与交易模拟

支持：
  - 定义持仓标的、数量、成本价
  - 计算当前市值、盈亏
  - 记录交易历史
  - 导出持仓快照 JSON
"""

import json
import os
from datetime import datetime
from typing import Any

_SNAPSHOTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports", "snapshots")
)
os.makedirs(_SNAPSHOTS_DIR, exist_ok=True)


class Position:
    """单个持仓"""

    def __init__(self, symbol: str, name: str, market: str,
                 shares: float, cost_price: float,
                 category: str = "ETF", note: str = ""):
        self.symbol = symbol          # 代码
        self.name = name              # 名称
        self.market = market          # a / us / hk / fund
        self.shares = shares          # 持仓份额/股数
        self.cost_price = cost_price  # 成本价
        self.category = category      # ETF / 股票 / 基金
        self.note = note              # 备注

    @property
    def cost_total(self) -> float:
        return self.shares * self.cost_price

    def market_value(self, current_price: float) -> float:
        return self.shares * current_price

    def profit_pct(self, current_price: float) -> float:
        if self.cost_price == 0:
            return 0.0
        return (current_price - self.cost_price) / self.cost_price * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "shares": self.shares,
            "cost_price": self.cost_price,
            "cost_total": self.cost_total,
            "category": self.category,
            "note": self.note,
        }

    @staticmethod
    def from_dict(d: dict) -> "Position":
        return Position(
            symbol=d["symbol"],
            name=d.get("name", ""),
            market=d.get("market", "a"),
            shares=d["shares"],
            cost_price=d["cost_price"],
            category=d.get("category", "ETF"),
            note=d.get("note", ""),
        )


class TradeRecord:
    """一笔交易记录"""

    def __init__(self, symbol: str, name: str, action: str,
                 shares: float, price: float, date: str = None,
                 strategy: str = "", reason: str = ""):
        self.symbol = symbol
        self.name = name
        self.action = action        # buy / sell / add / reduce
        self.shares = shares
        self.price = price
        self.date = date or datetime.now().strftime("%Y-%m-%d %H:%M")
        self.strategy = strategy
        self.reason = reason

    @property
    def amount(self) -> float:
        return self.shares * self.price

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "action": self.action,
            "shares": self.shares,
            "price": self.price,
            "amount": self.amount,
            "date": self.date,
            "strategy": self.strategy,
            "reason": self.reason,
        }


class Portfolio:
    """持仓组合"""

    def __init__(self, name: str = "默认组合"):
        self.name = name
        self.positions: list[Position] = []
        self.trades: list[TradeRecord] = []
        self._loaded_from = None

    def add_position(self, position: Position):
        """追加或更新持仓"""
        for p in self.positions:
            if p.symbol == position.symbol:
                # 摊平成本
                old_cost = p.cost_total
                new_shares = p.shares + position.shares
                new_cost = old_cost + position.cost_total
                p.cost_price = new_cost / new_shares if new_shares > 0 else 0
                p.shares = new_shares
                return
        self.positions.append(position)

    def remove_position(self, symbol: str, shares: float = None):
        """减少或清仓"""
        for p in self.positions:
            if p.symbol == symbol:
                if shares is None or shares >= p.shares:
                    self.positions.remove(p)
                else:
                    p.shares -= shares
                return

    def record_trade(self, symbol: str, name: str, action: str,
                     shares: float, price: float,
                     strategy: str = "", reason: str = ""):
        trade = TradeRecord(symbol, name, action, shares, price,
                            strategy=strategy, reason=reason)
        self.trades.append(trade)
        # 同步持仓
        if action in ("buy", "add"):
            self.add_position(Position(symbol, name, "a", shares, price))
        elif action in ("sell", "reduce"):
            self.remove_position(symbol, shares)

    def total_cost(self) -> float:
        return sum(p.cost_total for p in self.positions)

    def evaluate(self, prices: dict[str, float]) -> dict:
        """按当前市价评估组合"""
        total_value = 0.0
        total_cost_val = 0.0
        details = []
        for p in self.positions:
            cur = prices.get(p.symbol, 0)
            mv = p.market_value(cur)
            pl = p.profit_pct(cur)
            total_value += mv
            total_cost_val += p.cost_total
            details.append({
                **p.to_dict(),
                "current_price": cur,
                "market_value": mv,
                "profit_pct": round(pl, 2),
            })
        total_pl_pct = ((total_value - total_cost_val) / total_cost_val * 100) if total_cost_val > 0 else 0
        return {
            "portfolio": self.name,
            "total_cost": round(total_cost_val, 2),
            "total_value": round(total_value, 2),
            "total_profit_pct": round(total_pl_pct, 2),
            "positions": details,
        }

    def save_snapshot(self, tag: str = ""):
        """保存持仓快照到 reports/snapshots/"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag_suffix = f"_{tag}" if tag else ""
        path = os.path.join(_SNAPSHOTS_DIR, f"{ts}{tag_suffix}.json")
        data = {
            "portfolio": self.name,
            "snapshot_time": datetime.now().isoformat(),
            "positions": [p.to_dict() for p in self.positions],
            "recent_trades": [t.to_dict() for t in self.trades[-20:]],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load_latest(cls) -> "Portfolio":
        """加载最新快照"""
        snapshots = sorted(
            [f for f in os.listdir(_SNAPSHOTS_DIR) if f.endswith(".json")],
            reverse=True
        )
        if not snapshots:
            return cls()
        path = os.path.join(_SNAPSHOTS_DIR, snapshots[0])
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        p = cls(data.get("portfolio", "恢复的组合"))
        for pos_data in data.get("positions", []):
            p.positions.append(Position.from_dict(pos_data))
        for trade_data in data.get("recent_trades", []):
            t = TradeRecord(
                symbol=trade_data["symbol"],
                name=trade_data.get("name", ""),
                action=trade_data["action"],
                shares=trade_data["shares"],
                price=trade_data["price"],
                date=trade_data.get("date", ""),
                strategy=trade_data.get("strategy", ""),
                reason=trade_data.get("reason", ""),
            )
            p.trades.append(t)
        p._loaded_from = path
        return p
