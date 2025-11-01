"""Tests for exchange repositories"""
from decimal import Decimal

import pytest

from trading.domain.entities import Position, Trade
from trading.infrastructure.exchange.repositories import AccountRepository, OrdersRepository, TradesRepository


def test_account_repository():
    """Test AccountRepository"""
    repo = AccountRepository()

    # Test balance
    repo.set_balance(Decimal("1000"))
    assert repo.get_balance() == Decimal("1000")

    repo.update_balance(Decimal("100"))
    assert repo.get_balance() == Decimal("1100")

    repo.update_balance(Decimal("-50"))
    assert repo.get_balance() == Decimal("1050")

    # Test leverage
    repo.set_leverage("BTCUSDT", Decimal("100"))
    assert repo.get_leverage("BTCUSDT") == Decimal("100")

    with pytest.raises(ValueError):
        repo.get_leverage("ETHUSDT")


def test_account_repository_positions():
    """Test AccountRepository position management"""
    repo = AccountRepository()

    # Get position (should create default)
    position = repo.get_position("BTCUSDT", "long")
    assert position.symbol == "btcusdt"
    assert position.side == "long"
    assert position.amount == Decimal("0")

    # Set position
    position = Position(
        symbol="BTCUSDT",
        side="long",
        amount=Decimal("0.1"),
        entry_price=Decimal("50000"),
        break_even=Decimal("50010"),
    )
    repo.set_position(position)
    retrieved = repo.get_position("BTCUSDT", "long")
    assert retrieved.amount == Decimal("0.1")
    assert retrieved.entry_price == Decimal("50000")


def test_orders_repository():
    """Test OrdersRepository"""
    repo = OrdersRepository()

    # Create order
    order = repo.new_order(
        symbol="BTCUSDT",
        position_side="long",
        side="buy",
        type="limit",
        quantity=Decimal("0.1"),
        price=Decimal("50000"),
    )

    assert order.symbol == "btcusdt"
    assert order.position_side == "long"
    assert order.side == "buy"
    assert order.type == "limit"
    assert order.quantity == Decimal("0.1")
    assert order.price == Decimal("50000")
    assert order.status == "new"
    assert order.order_id is not None

    # Get order
    retrieved = repo.get_order(order.order_id)
    assert retrieved is not None
    assert retrieved.order_id == order.order_id

    # Get symbol orders
    orders = repo.get_symbol_orders("BTCUSDT")
    assert len(orders) == 1

    # Delete order
    deleted = repo.delete_order(order.order_id)
    assert deleted is True

    orders = repo.get_symbol_orders("BTCUSDT")
    assert len(orders) == 0


def test_trades_repository():
    """Test TradesRepository"""
    repo = TradesRepository()

    # Create trade
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

    repo.add_trade(trade)

    # Get symbol trades
    symbol_trades = repo.get_symbol_trades("BTCUSDT")
    assert "long" in symbol_trades
    assert len(symbol_trades["long"]) == 1

    # Get position trades
    position_trades = repo.get_position_trades("BTCUSDT", "long")
    assert len(position_trades) == 1
    assert position_trades[0].order_id == "trade_1"

