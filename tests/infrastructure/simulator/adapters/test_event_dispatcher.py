"""Tests for EventDispatcher (simulator)"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from trading.domain.entities import Candle
from trading.infrastructure.simulator.adapters.event_dispatcher import EventDispatcher


@pytest.fixture
def event_dispatcher():
    """Create an EventDispatcher instance"""
    return EventDispatcher()


@pytest.fixture
def sample_candle():
    """Create a sample Candle"""
    return Candle(
        symbol="BTCUSDT",
        timeframe="1m",
        timestamp=1744023500000,
        open_price=Decimal("50000"),
        high_price=Decimal("51000"),
        low_price=Decimal("49000"),
        close_price=Decimal("50500"),
        volume=Decimal("100"),
    )


def test_initialization(event_dispatcher):
    """Test EventDispatcher initialization"""
    assert isinstance(event_dispatcher.complete_candle_listeners, dict)
    assert len(event_dispatcher.complete_candle_listeners) == 0


def test_add_complete_candle_listener(event_dispatcher):
    """Test add_complete_candle_listener registers listener"""
    listener = MagicMock()

    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener)

    assert "btcusdt" in event_dispatcher.complete_candle_listeners  # Should be lowercased
    assert "1m" in event_dispatcher.complete_candle_listeners["btcusdt"]
    assert listener in event_dispatcher.complete_candle_listeners["btcusdt"]["1m"]


def test_add_complete_candle_listener_multiple_listeners(event_dispatcher):
    """Test add_complete_candle_listener with multiple listeners"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener1)
    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener2)

    assert len(event_dispatcher.complete_candle_listeners["btcusdt"]["1m"]) == 2


def test_add_complete_candle_listener_multiple_timeframes(event_dispatcher):
    """Test add_complete_candle_listener with multiple timeframes"""
    listener = MagicMock()

    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener)
    event_dispatcher.add_complete_candle_listener("BTCUSDT", "15m", listener)

    assert "1m" in event_dispatcher.complete_candle_listeners["btcusdt"]
    assert "15m" in event_dispatcher.complete_candle_listeners["btcusdt"]


def test_add_complete_candle_listener_multiple_symbols(event_dispatcher):
    """Test add_complete_candle_listener with multiple symbols"""
    listener = MagicMock()

    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener)
    event_dispatcher.add_complete_candle_listener("ETHUSDT", "1m", listener)

    assert "btcusdt" in event_dispatcher.complete_candle_listeners
    assert "ethusdt" in event_dispatcher.complete_candle_listeners


def test_remove_complete_candle_listener(event_dispatcher):
    """Test remove_complete_candle_listener removes listener"""
    listener = MagicMock()

    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener)
    assert listener in event_dispatcher.complete_candle_listeners["btcusdt"]["1m"]

    event_dispatcher.remove_complete_candle_listener("BTCUSDT", "1m", listener)
    assert listener not in event_dispatcher.complete_candle_listeners["btcusdt"]["1m"]


def test_remove_complete_candle_listener_nonexistent(event_dispatcher):
    """Test remove_complete_candle_listener handles nonexistent listener gracefully"""
    listener = MagicMock()

    # Try to remove without adding
    event_dispatcher.remove_complete_candle_listener("BTCUSDT", "1m", listener)

    # Should not raise error
    assert "btcusdt" not in event_dispatcher.complete_candle_listeners or len(
        event_dispatcher.complete_candle_listeners.get("btcusdt", {}).get("1m", [])
    ) == 0


def test_dispatch_complete_candle(event_dispatcher, sample_candle):
    """Test dispatch_complete_candle calls all listeners"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener1)
    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener2)

    event_dispatcher.dispatch_complete_candle(sample_candle)

    listener1.assert_called_once_with(sample_candle)
    listener2.assert_called_once_with(sample_candle)


def test_dispatch_complete_candle_no_listeners(event_dispatcher, sample_candle):
    """Test dispatch_complete_candle with no listeners"""
    # Should not raise error
    event_dispatcher.dispatch_complete_candle(sample_candle)


def test_dispatch_complete_candle_different_timeframe(event_dispatcher, sample_candle):
    """Test dispatch_complete_candle only calls listeners for matching timeframe"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener1)
    event_dispatcher.add_complete_candle_listener("BTCUSDT", "15m", listener2)

    # Dispatch for 1m
    event_dispatcher.dispatch_complete_candle(sample_candle)

    listener1.assert_called_once_with(sample_candle)
    listener2.assert_not_called()


def test_dispatch_complete_candle_different_symbol(event_dispatcher, sample_candle):
    """Test dispatch_complete_candle only calls listeners for matching symbol"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener1)
    event_dispatcher.add_complete_candle_listener("ETHUSDT", "1m", listener2)

    # Dispatch for BTCUSDT
    event_dispatcher.dispatch_complete_candle(sample_candle)

    listener1.assert_called_once_with(sample_candle)
    listener2.assert_not_called()


def test_dispatch_complete_candle_listener_error(event_dispatcher, sample_candle, capsys):
    """Test dispatch_complete_candle handles listener errors gracefully"""
    def failing_listener(candle):
        raise Exception("Listener error")

    def working_listener(candle):
        pass

    listener1 = MagicMock(side_effect=failing_listener)
    listener2 = MagicMock(side_effect=working_listener)

    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener1)
    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener2)

    # Should not raise, but continue with other listeners
    event_dispatcher.dispatch_complete_candle(sample_candle)

    # Verify both were called (error didn't stop execution)
    assert listener1.called
    assert listener2.called

    # Verify error was printed
    captured = capsys.readouterr()
    assert "Error in candle listener" in captured.out


def test_dispatch_complete_candle_case_insensitive(event_dispatcher):
    """Test dispatch_complete_candle is case insensitive"""
    listener = MagicMock()
    event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener)

    # Candle with lowercase symbol
    candle = Candle(
        symbol="btcusdt",  # Lowercase
        timeframe="1m",
        timestamp=1744023500000,
        open_price=Decimal("50000"),
        high_price=Decimal("51000"),
        low_price=Decimal("49000"),
        close_price=Decimal("50500"),
        volume=Decimal("100"),
    )

    event_dispatcher.dispatch_complete_candle(candle)

    listener.assert_called_once_with(candle)

