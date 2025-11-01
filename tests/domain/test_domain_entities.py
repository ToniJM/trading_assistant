"""Tests for domain entities"""
from decimal import Decimal

from trading.domain.entities import Candle, Cycle, Order, Position, Trade


def test_candle_creation():
    """Test Candle entity creation"""
    candle = Candle(
        symbol="BTCUSDT",
        timeframe="1m",
        timestamp=1744023500000,
        open_price=Decimal("50000"),
        high_price=Decimal("51000"),
        low_price=Decimal("49000"),
        close_price=Decimal("50500"),
        volume=Decimal("100"),
    )

    assert candle.symbol == "BTCUSDT"
    assert candle.timeframe == "1m"
    assert candle.close_price == Decimal("50500")


def test_order_creation():
    """Test Order entity creation"""
    order = Order(
        symbol="BTCUSDT",
        price=Decimal("50000"),
        quantity=Decimal("0.1"),
        position_side="long",
        side="buy",
        type="limit",
        order_id="test_order_123",
        status="new",
    )

    assert order.symbol == "BTCUSDT"
    assert order.position_side == "long"
    assert order.side == "buy"
    assert order.type == "limit"


def test_position_creation():
    """Test Position entity creation"""
    position = Position(
        symbol="BTCUSDT",
        side="long",
        amount=Decimal("0.1"),
        entry_price=Decimal("50000"),
        break_even=Decimal("50010"),
    )

    assert position.symbol == "BTCUSDT"
    assert position.side == "long"
    assert position.amount == Decimal("0.1")
    assert len(position.trades) == 0


def test_position_add_trade():
    """Test adding trades to position"""
    position = Position(
        symbol="BTCUSDT",
        side="long",
        amount=Decimal("0.1"),
        entry_price=Decimal("50000"),
        break_even=Decimal("50010"),
    )

    trade = Trade(
        order_id="trade_1",
        timestamp=1744023500000,
        symbol="BTCUSDT",
        position_side="long",
        side="buy",
        price=Decimal("50000"),
        quantity=Decimal("0.1"),
        commission=Decimal("5"),
    )

    position.add_trade(trade)

    assert len(position.trades) == 1
    assert position.trades[0] == trade


def test_cycle_creation():
    """Test Cycle entity creation"""
    cycle = Cycle(
        symbol="BTCUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000,
        end_timestamp=1744023501000,
        total_pnl=Decimal("100"),
        long_trades_count=5,
        short_trades_count=3,
        long_max_loads=3,
        short_max_loads=2,
    )

    assert cycle.symbol == "BTCUSDT"
    assert cycle.strategy_name == "test_strategy"
    assert cycle.total_pnl == Decimal("100")
    assert cycle.cycle_id is not None
    assert cycle.duration_minutes > 0


def test_cycle_to_dict():
    """Test Cycle conversion to dictionary"""
    cycle = Cycle(
        symbol="BTCUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000,
        end_timestamp=1744023501000,
        total_pnl=Decimal("100"),
        long_trades_count=5,
        short_trades_count=3,
        long_max_loads=3,
        short_max_loads=2,
    )

    cycle_dict = cycle.to_dict()

    assert cycle_dict["symbol"] == "BTCUSDT"
    assert cycle_dict["total_pnl"] == "100"  # Decimal converted to string
    assert cycle_dict["long_trades_count"] == 5


def test_cycle_from_dict():
    """Test Cycle creation from dictionary"""
    cycle_dict = {
        "cycle_id": "test_cycle_id",
        "symbol": "BTCUSDT",
        "strategy_name": "test_strategy",
        "start_timestamp": 1744023500000,
        "end_timestamp": 1744023501000,
        "duration_minutes": 0.0167,
        "total_pnl": "100",
        "long_trades_count": 5,
        "short_trades_count": 3,
        "long_max_loads": 3,
        "short_max_loads": 2,
    }

    cycle = Cycle.from_dict(cycle_dict)

    assert cycle.cycle_id == "test_cycle_id"
    assert cycle.symbol == "BTCUSDT"
    assert cycle.total_pnl == Decimal("100")

