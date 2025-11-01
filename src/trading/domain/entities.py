"""Domain entities for trading system"""
import uuid
from datetime import datetime
from decimal import Decimal

from .types import ORDER_SIDE_TYPE, ORDER_STATUS_TYPE, ORDER_TYPE_TYPE, SIDE_TYPE


class Candle:
    """Represents a price candle"""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        timestamp: int,
        open_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        close_price: Decimal,
        volume:[Decimal] = None,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.timestamp = timestamp
        self.open_price = open_price
        self.high_price = high_price
        self.low_price = low_price
        self.close_price = close_price
        self.volume = volume


class SymbolInfo:
    """Information about a trading symbol"""

    def __init__(
        self,
        symbol: str,
        min_qty: Decimal,
        min_step: Decimal,
        tick_size: Decimal,
        notional: Decimal,
    ):
        self.symbol = symbol
        self.min_qty = min_qty
        self.min_step = min_step
        self.tick_size = tick_size
        self.notional = notional


class Order:
    """Represents a trading order"""

    def __init__(
        self,
        symbol: str,
        price: Decimal,
        quantity: Decimal,
        position_side: SIDE_TYPE,
        side: ORDER_SIDE_TYPE,
        type: ORDER_TYPE_TYPE,
        order_id:[str] = None,
        status: ORDER_STATUS_TYPE = "new",
    ):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.position_side = position_side
        self.side = side
        self.type = type
        self.order_id = order_id
        self.status = status


class Trade:
    """Represents an executed trade"""

    def __init__(
        self,
        order_id: str,
        timestamp: str | int,
        symbol: str,
        position_side: SIDE_TYPE,
        side: ORDER_SIDE_TYPE,
        price: Decimal,
        quantity: Decimal,
        commission: Decimal,
        realized_pnl: Decimal = Decimal(0),
        closes_position_completely: bool = False,
    ):
        self.order_id = order_id
        self.timestamp = timestamp
        self.symbol = symbol
        self.position_side = position_side
        self.side = side
        self.price = price
        self.quantity = quantity
        self.commission = commission
        self.realized_pnl = realized_pnl
        self.closes_position_completely = closes_position_completely


class Position:
    """Represents a trading position"""

    def __init__(
        self,
        symbol: str,
        side: SIDE_TYPE,
        amount: Decimal,
        entry_price: Decimal,
        break_even: Decimal,
    ):
        self.symbol = symbol
        self.side = side
        self.amount = amount
        self.entry_price = entry_price
        self.break_even = break_even
        self.commission = Decimal(0)
        self.trades:[Trade] = []

    def add_trade(self, trade: Trade):
        """Add a trade to this position"""
        self.trades.append(trade)
        commission = abs(trade.commission)
        if (self.side == "long" and trade.side == "buy") or (self.side == "short" and trade.side == "sell"):
            self.commission += commission
        else:
            self.commission -= commission

        self.trades.sort(key=lambda x: int(x.timestamp) if isinstance(x.timestamp, str) else x.timestamp)

    def get_load_count(self, min_load_amount=None):
        """Calculate load count for position sizing"""
        count = 0
        if len(self.trades) > 0:
            if not min_load_amount:
                min_load_amount = min(self.trades, key=lambda p: abs(p.quantity)).quantity
            amount = abs(self.amount)
            while amount >= min_load_amount:
                count += 1
                amount /= 2
        return count


class Cycle:
    """Represents a complete trading cycle when both positions close to zero"""

    def __init__(
        self,
        symbol: str,
        strategy_name: str,
        start_timestamp: int,
        end_timestamp: int,
        total_pnl: Decimal,
        long_trades_count: int,
        short_trades_count: int,
        long_max_loads: int,
        short_max_loads: int,
        cycle_id:[str] = None,
    ):
        self.cycle_id = cycle_id or str(uuid.uuid4())
        self.symbol = symbol
        self.strategy_name = strategy_name
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp
        self.duration_minutes = (end_timestamp - start_timestamp) / (1000 * 60)  # Convert ms to minutes
        self.total_pnl = total_pnl
        self.long_trades_count = long_trades_count
        self.short_trades_count = short_trades_count
        self.long_max_loads = long_max_loads
        self.short_max_loads = short_max_loads
        self.created_at = int(datetime.now().timestamp() * 1000)

    def __str__(self):
        return (
            f"Cycle({self.cycle_id[:8]}...): {self.symbol} {self.strategy_name} | "
            f"PnL: {self.total_pnl} | Duration: {self.duration_minutes:.1f}min"
        )

    def to_dict(self):
        """Convert cycle to dictionary for storage"""
        return {
            "cycle_id": self.cycle_id,
            "symbol": self.symbol,
            "strategy_name": self.strategy_name,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "duration_minutes": self.duration_minutes,
            "total_pnl": str(self.total_pnl),  # Convert Decimal to string
            "long_trades_count": self.long_trades_count,
            "short_trades_count": self.short_trades_count,
            "long_max_loads": self.long_max_loads,
            "short_max_loads": self.short_max_loads,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create cycle from dictionary"""
        return cls(
            cycle_id=data["cycle_id"],
            symbol=data["symbol"],
            strategy_name=data["strategy_name"],
            start_timestamp=data["start_timestamp"],
            end_timestamp=data["end_timestamp"],
            total_pnl=Decimal(data["total_pnl"]),
            long_trades_count=data["long_trades_count"],
            short_trades_count=data["short_trades_count"],
            long_max_loads=data["long_max_loads"],
            short_max_loads=data["short_max_loads"],
        )

