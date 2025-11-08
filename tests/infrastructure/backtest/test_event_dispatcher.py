"""Tests for EventDispatcher"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from trading.domain.entities import Cycle
from trading.infrastructure.backtest.event_dispatcher import EventDispatcher


@pytest.fixture
def event_dispatcher():
    """Create an EventDispatcher instance"""
    return EventDispatcher()


@pytest.fixture
def sample_cycle():
    """Create a sample Cycle"""
    return Cycle(
        symbol="BTCUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000,
        end_timestamp=1744023500000 + (60 * 60 * 1000),
        total_pnl=Decimal("100.50"),
        long_trades_count=5,
        short_trades_count=3,
        long_max_loads=2,
        short_max_loads=1,
        cycle_id="test_cycle_123",
    )


def test_initialization(event_dispatcher):
    """Test EventDispatcher initialization"""
    assert isinstance(event_dispatcher.cycle_listeners, dict)
    assert len(event_dispatcher.cycle_listeners) == 0


def test_add_cycle_listener(event_dispatcher):
    """Test add_cycle_listener registers listener"""
    listener = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener)

    assert "btcusdt" in event_dispatcher.cycle_listeners  # Should be lowercased
    assert listener in event_dispatcher.cycle_listeners["btcusdt"]


def test_add_cycle_listener_multiple_listeners(event_dispatcher):
    """Test add_cycle_listener with multiple listeners for same symbol"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener1)
    event_dispatcher.add_cycle_listener("BTCUSDT", listener2)

    assert len(event_dispatcher.cycle_listeners["btcusdt"]) == 2
    assert listener1 in event_dispatcher.cycle_listeners["btcusdt"]
    assert listener2 in event_dispatcher.cycle_listeners["btcusdt"]


def test_add_cycle_listener_multiple_symbols(event_dispatcher):
    """Test add_cycle_listener with multiple symbols"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener1)
    event_dispatcher.add_cycle_listener("ETHUSDT", listener2)

    assert "btcusdt" in event_dispatcher.cycle_listeners
    assert "ethusdt" in event_dispatcher.cycle_listeners
    assert listener1 in event_dispatcher.cycle_listeners["btcusdt"]
    assert listener2 in event_dispatcher.cycle_listeners["ethusdt"]


def test_add_cycle_listener_case_insensitive(event_dispatcher):
    """Test add_cycle_listener is case insensitive"""
    listener = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener)
    event_dispatcher.add_cycle_listener("btcusdt", listener)  # Same symbol, different case

    # Should still be one entry (lowercased)
    assert len(event_dispatcher.cycle_listeners) == 1
    assert "btcusdt" in event_dispatcher.cycle_listeners


def test_remove_cycle_listener(event_dispatcher):
    """Test remove_cycle_listener removes listener"""
    listener = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener)
    assert listener in event_dispatcher.cycle_listeners["btcusdt"]

    event_dispatcher.remove_cycle_listener("BTCUSDT", listener)
    assert listener not in event_dispatcher.cycle_listeners["btcusdt"]


def test_remove_cycle_listener_nonexistent(event_dispatcher):
    """Test remove_cycle_listener handles nonexistent listener gracefully"""
    listener = MagicMock()

    # Try to remove without adding
    event_dispatcher.remove_cycle_listener("BTCUSDT", listener)

    # Should not raise error
    assert "btcusdt" not in event_dispatcher.cycle_listeners or len(event_dispatcher.cycle_listeners.get("btcusdt", [])) == 0


def test_remove_cycle_listener_nonexistent_symbol(event_dispatcher):
    """Test remove_cycle_listener handles nonexistent symbol gracefully"""
    listener = MagicMock()

    # Try to remove from nonexistent symbol
    event_dispatcher.remove_cycle_listener("NONEXISTENT", listener)

    # Should not raise error
    assert "nonexistent" not in event_dispatcher.cycle_listeners


def test_remove_cycle_listener_case_insensitive(event_dispatcher):
    """Test remove_cycle_listener is case insensitive"""
    listener = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener)
    event_dispatcher.remove_cycle_listener("btcusdt", listener)  # Different case

    assert listener not in event_dispatcher.cycle_listeners["btcusdt"]


def test_dispatch_cycle_completion(event_dispatcher, sample_cycle):
    """Test dispatch_cycle_completion calls all listeners"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener1)
    event_dispatcher.add_cycle_listener("BTCUSDT", listener2)

    event_dispatcher.dispatch_cycle_completion(sample_cycle)

    listener1.assert_called_once_with(sample_cycle)
    listener2.assert_called_once_with(sample_cycle)


def test_dispatch_cycle_completion_no_listeners(event_dispatcher, sample_cycle):
    """Test dispatch_cycle_completion with no listeners"""
    # Should not raise error
    event_dispatcher.dispatch_cycle_completion(sample_cycle)


def test_dispatch_cycle_completion_different_symbol(event_dispatcher, sample_cycle):
    """Test dispatch_cycle_completion only calls listeners for matching symbol"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener1)
    event_dispatcher.add_cycle_listener("ETHUSDT", listener2)

    # Dispatch for BTCUSDT
    event_dispatcher.dispatch_cycle_completion(sample_cycle)

    listener1.assert_called_once_with(sample_cycle)
    listener2.assert_not_called()


def test_dispatch_cycle_completion_case_insensitive(event_dispatcher):
    """Test dispatch_cycle_completion is case insensitive"""
    listener = MagicMock()
    event_dispatcher.add_cycle_listener("BTCUSDT", listener)

    # Cycle with different case
    cycle = Cycle(
        symbol="btcusdt",  # Lowercase
        strategy_name="test_strategy",
        start_timestamp=1744023500000,
        end_timestamp=1744023500000 + (60 * 60 * 1000),
        total_pnl=Decimal("100"),
        long_trades_count=5,
        short_trades_count=3,
        long_max_loads=2,
        short_max_loads=1,
    )

    event_dispatcher.dispatch_cycle_completion(cycle)

    listener.assert_called_once_with(cycle)


def test_dispatch_cycle_completion_listener_error(event_dispatcher, sample_cycle, capsys):
    """Test dispatch_cycle_completion handles listener errors gracefully"""
    def failing_listener(cycle):
        raise Exception("Listener error")

    def working_listener(cycle):
        pass

    listener1 = MagicMock(side_effect=failing_listener)
    listener2 = MagicMock(side_effect=working_listener)

    event_dispatcher.add_cycle_listener("BTCUSDT", listener1)
    event_dispatcher.add_cycle_listener("BTCUSDT", listener2)

    # Should not raise, but continue with other listeners
    event_dispatcher.dispatch_cycle_completion(sample_cycle)

    # Verify both were called (error didn't stop execution)
    assert listener1.called
    assert listener2.called

    # Verify error was printed
    captured = capsys.readouterr()
    assert "Error in cycle listener" in captured.out


def test_has_cycle_listeners(event_dispatcher):
    """Test has_cycle_listeners returns True when listeners exist"""
    listener = MagicMock()

    assert event_dispatcher.has_cycle_listeners("BTCUSDT") is False

    event_dispatcher.add_cycle_listener("BTCUSDT", listener)

    assert event_dispatcher.has_cycle_listeners("BTCUSDT") is True


def test_has_cycle_listeners_after_removal(event_dispatcher):
    """Test has_cycle_listeners returns False after removing all listeners"""
    listener = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener)
    assert event_dispatcher.has_cycle_listeners("BTCUSDT") is True

    event_dispatcher.remove_cycle_listener("BTCUSDT", listener)
    assert event_dispatcher.has_cycle_listeners("BTCUSDT") is False


def test_has_cycle_listeners_case_insensitive(event_dispatcher):
    """Test has_cycle_listeners is case insensitive"""
    listener = MagicMock()

    event_dispatcher.add_cycle_listener("BTCUSDT", listener)

    assert event_dispatcher.has_cycle_listeners("btcusdt") is True
    assert event_dispatcher.has_cycle_listeners("BtcUsdt") is True

