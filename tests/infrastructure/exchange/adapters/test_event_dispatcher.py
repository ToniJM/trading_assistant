"""Tests for EventDispatcher (exchange)"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from trading.domain.entities import Order, Position, Trade
from trading.infrastructure.exchange.adapters.event_dispatcher import EventDispatcher


@pytest.fixture
def event_dispatcher():
    """Create an EventDispatcher instance"""
    return EventDispatcher()


@pytest.fixture
def sample_order():
    """Create a sample Order"""
    return Order(
        symbol="BTCUSDT",
        price=Decimal("50000"),
        quantity=Decimal("0.1"),
        position_side="long",
        side="buy",
        type="limit",
        order_id="order_123",
    )


@pytest.fixture
def sample_trade():
    """Create a sample Trade"""
    return Trade(
        order_id="order_123",
        timestamp=1744023500000,
        symbol="BTCUSDT",
        position_side="long",
        side="buy",
        price=Decimal("50000"),
        quantity=Decimal("0.1"),
        commission=Decimal("0.5"),
    )


@pytest.fixture
def sample_position():
    """Create a sample Position"""
    return Position(
        symbol="BTCUSDT",
        side="long",
        amount=Decimal("0.1"),
        entry_price=Decimal("50000"),
        break_even=Decimal("50025"),
    )


def test_initialization(event_dispatcher):
    """Test EventDispatcher initialization"""
    assert isinstance(event_dispatcher._orders_listeners, list)
    assert isinstance(event_dispatcher._positions_listeners, list)
    assert isinstance(event_dispatcher._trade_listeners, list)


def test_add_orders_listener(event_dispatcher):
    """Test add_orders_listener registers listener"""
    listener = MagicMock()

    event_dispatcher.add_orders_listener(listener)

    assert listener in event_dispatcher._orders_listeners


def test_remove_order_listener(event_dispatcher):
    """Test remove_order_listener removes listener"""
    listener = MagicMock()

    event_dispatcher.add_orders_listener(listener)
    event_dispatcher.remove_order_listener(listener)

    assert listener not in event_dispatcher._orders_listeners


def test_dispatch_order(event_dispatcher, sample_order):
    """Test dispatch_order calls all listeners"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_orders_listener(listener1)
    event_dispatcher.add_orders_listener(listener2)

    event_dispatcher.dispatch_order(sample_order)

    # Listeners should be called with order, and optionally old_order
    listener1.assert_called()
    listener2.assert_called()


def test_dispatch_order_with_old_order(event_dispatcher, sample_order):
    """Test dispatch_order with old_order parameter"""
    listener = MagicMock()

    event_dispatcher.add_orders_listener(listener)

    old_order = Order(
        symbol="BTCUSDT",
        price=Decimal("49000"),
        quantity=Decimal("0.1"),
        position_side="long",
        side="buy",
        type="limit",
        order_id="order_122",
    )

    event_dispatcher.dispatch_order(sample_order, old_order=old_order)

    # Listener should be called with both parameters
    listener.assert_called_with(sample_order, old_order)


def test_dispatch_order_listener_without_old_order_param(event_dispatcher, sample_order):
    """Test dispatch_order handles listeners that don't accept old_order"""
    def listener_without_old_order(order):
        pass

    listener = MagicMock(side_effect=listener_without_old_order)

    event_dispatcher.add_orders_listener(listener)

    old_order = MagicMock()
    event_dispatcher.dispatch_order(sample_order, old_order=old_order)

    # Should not raise TypeError, should fallback to calling with just order
    listener.assert_called()


def test_add_position_listener(event_dispatcher):
    """Test add_position_listener registers listener"""
    listener = MagicMock()

    event_dispatcher.add_position_listener(listener)

    assert listener in event_dispatcher._positions_listeners


def test_remove_position_listener(event_dispatcher):
    """Test remove_position_listener removes listener"""
    listener = MagicMock()

    event_dispatcher.add_position_listener(listener)
    event_dispatcher.remove_position_listener(listener)

    assert listener not in event_dispatcher._positions_listeners


def test_dispatch_positions(event_dispatcher, sample_position):
    """Test dispatch_positions calls all listeners"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_position_listener(listener1)
    event_dispatcher.add_position_listener(listener2)

    event_dispatcher.dispatch_positions(sample_position)

    listener1.assert_called()
    listener2.assert_called()


def test_add_trade_listener(event_dispatcher):
    """Test add_trade_listener registers listener"""
    listener = MagicMock()

    event_dispatcher.add_trade_listener(listener)

    assert listener in event_dispatcher._trade_listeners


def test_remove_trades_listener(event_dispatcher):
    """Test remove_trades_listener removes listener"""
    listener = MagicMock()

    event_dispatcher.add_trade_listener(listener)
    event_dispatcher.remove_trades_listener(listener)

    assert listener not in event_dispatcher._trade_listeners


def test_dispatch_trade(event_dispatcher, sample_trade):
    """Test dispatch_trade calls all listeners"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_trade_listener(listener1)
    event_dispatcher.add_trade_listener(listener2)

    event_dispatcher.dispatch_trade(sample_trade)

    listener1.assert_called_once_with(sample_trade)
    listener2.assert_called_once_with(sample_trade)


def test_dispatch_trade_listener_error(event_dispatcher, sample_trade, capsys):
    """Test dispatch_trade handles listener errors gracefully"""
    def failing_listener(trade):
        raise Exception("Listener error")

    def working_listener(trade):
        pass

    listener1 = MagicMock(side_effect=failing_listener)
    listener2 = MagicMock(side_effect=working_listener)

    event_dispatcher.add_trade_listener(listener1)
    event_dispatcher.add_trade_listener(listener2)

    # Should not raise, but continue with other listeners
    event_dispatcher.dispatch_trade(sample_trade)

    # Verify both were called (error didn't stop execution)
    assert listener1.called
    assert listener2.called

    # Verify error was printed
    captured = capsys.readouterr()
    assert "Error in trade listener" in captured.out

