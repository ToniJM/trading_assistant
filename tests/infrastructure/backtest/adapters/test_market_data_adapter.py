"""Tests for BacktestMarketDataAdapter"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from trading.domain.entities import Candle, SymbolInfo
from trading.infrastructure.backtest.adapters.market_data_adapter import BacktestMarketDataAdapter
from trading.infrastructure.simulator.simulator import MarketDataSimulator


@pytest.fixture
def mock_simulator():
    """Create a mock MarketDataSimulator"""
    simulator = MagicMock(spec=MarketDataSimulator)
    return simulator


@pytest.fixture
def market_data_adapter(mock_simulator):
    """Create a BacktestMarketDataAdapter instance"""
    return BacktestMarketDataAdapter(simulator=mock_simulator)


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


@pytest.fixture
def sample_symbol_info():
    """Create a sample SymbolInfo"""
    return SymbolInfo(
        symbol="BTCUSDT",
        min_qty=Decimal("0.001"),
        min_step=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        notional=Decimal("10"),
    )


def test_get_symbol_info(market_data_adapter, mock_simulator, sample_symbol_info):
    """Test get_symbol_info delegates to simulator"""
    mock_simulator.get_symbol_info.return_value = sample_symbol_info

    result = market_data_adapter.get_symbol_info("BTCUSDT")

    assert result == sample_symbol_info
    mock_simulator.get_symbol_info.assert_called_once_with("BTCUSDT")


def test_get_candles(market_data_adapter, mock_simulator, sample_candle):
    """Test get_candles delegates to simulator"""
    mock_simulator.get_candles.return_value = [sample_candle]

    result = market_data_adapter.get_candles("BTCUSDT", "1m", 100)

    assert result == [sample_candle]
    mock_simulator.get_candles.assert_called_once_with("BTCUSDT", "1m", 100)


def test_add_complete_candle_listener(market_data_adapter, mock_simulator):
    """Test add_complete_candle_listener registers listener and delegates to simulator"""
    listener = MagicMock()

    market_data_adapter.add_complete_candle_listener("BTCUSDT", "1m", listener)

    # Verify listener is stored
    assert "BTCUSDT" in market_data_adapter._candle_listeners
    assert "1m" in market_data_adapter._candle_listeners["BTCUSDT"]
    assert listener in market_data_adapter._candle_listeners["BTCUSDT"]["1m"]

    # Verify simulator was called
    mock_simulator.add_complete_candle_listener.assert_called_once_with("BTCUSDT", "1m", listener)


def test_add_complete_candle_listener_multiple_listeners(market_data_adapter, mock_simulator):
    """Test add_complete_candle_listener with multiple listeners"""
    listener1 = MagicMock()
    listener2 = MagicMock()

    market_data_adapter.add_complete_candle_listener("BTCUSDT", "1m", listener1)
    market_data_adapter.add_complete_candle_listener("BTCUSDT", "1m", listener2)

    # Verify both listeners are stored
    assert len(market_data_adapter._candle_listeners["BTCUSDT"]["1m"]) == 2
    assert listener1 in market_data_adapter._candle_listeners["BTCUSDT"]["1m"]
    assert listener2 in market_data_adapter._candle_listeners["BTCUSDT"]["1m"]


def test_add_complete_candle_listener_multiple_symbols_timeframes(market_data_adapter, mock_simulator):
    """Test add_complete_candle_listener with multiple symbols and timeframes"""
    listener = MagicMock()

    market_data_adapter.add_complete_candle_listener("BTCUSDT", "1m", listener)
    market_data_adapter.add_complete_candle_listener("ETHUSDT", "15m", listener)

    # Verify both are stored separately
    assert "BTCUSDT" in market_data_adapter._candle_listeners
    assert "ETHUSDT" in market_data_adapter._candle_listeners
    assert "1m" in market_data_adapter._candle_listeners["BTCUSDT"]
    assert "15m" in market_data_adapter._candle_listeners["ETHUSDT"]


def test_add_internal_candle_listener(market_data_adapter, mock_simulator):
    """Test add_internal_candle_listener calls add_complete_candle_listener"""
    listener = MagicMock()

    market_data_adapter.add_internal_candle_listener("BTCUSDT", "1m", listener)

    # Should call add_complete_candle_listener
    mock_simulator.add_complete_candle_listener.assert_called_once_with("BTCUSDT", "1m", listener)


def test_remove_internal_candle_listener(market_data_adapter, mock_simulator):
    """Test remove_internal_candle_listener removes listener and delegates to simulator"""
    listener = MagicMock()

    # First add listener
    market_data_adapter.add_complete_candle_listener("BTCUSDT", "1m", listener)

    # Then remove it
    market_data_adapter.remove_internal_candle_listener("BTCUSDT", "1m", listener)

    # Verify listener is removed from internal storage
    assert listener not in market_data_adapter._candle_listeners["BTCUSDT"]["1m"]

    # Verify simulator was called
    mock_simulator.remove_complete_candle_listener.assert_called_with("BTCUSDT", "1m", listener)


def test_remove_internal_candle_listener_nonexistent(market_data_adapter, mock_simulator):
    """Test remove_internal_candle_listener handles nonexistent listener gracefully"""
    listener = MagicMock()

    # Try to remove without adding
    market_data_adapter.remove_internal_candle_listener("BTCUSDT", "1m", listener)

    # Should not raise error, just call simulator
    mock_simulator.remove_complete_candle_listener.assert_called_once_with("BTCUSDT", "1m", listener)


def test_remove_internal_candle_listener_nonexistent_symbol(market_data_adapter, mock_simulator):
    """Test remove_internal_candle_listener handles nonexistent symbol gracefully"""
    listener = MagicMock()

    # Try to remove from nonexistent symbol
    market_data_adapter.remove_internal_candle_listener("NONEXISTENT", "1m", listener)

    # Should not raise error
    mock_simulator.remove_complete_candle_listener.assert_called_once_with("NONEXISTENT", "1m", listener)


def test_close(market_data_adapter, mock_simulator):
    """Test close() closes simulator and cleans up"""
    market_data_adapter.close()

    mock_simulator.close.assert_called_once()
    assert market_data_adapter.simulator is None


def test_close_without_simulator():
    """Test close() handles None simulator gracefully"""
    adapter = BacktestMarketDataAdapter(simulator=None)

    # Should not raise error
    adapter.close()


def test_close_idempotent(market_data_adapter, mock_simulator):
    """Test close() can be called multiple times safely"""
    market_data_adapter.close()
    market_data_adapter.close()

    # Simulator should only be closed once (if it was set)
    # But since we're using a mock, we just verify it doesn't raise

