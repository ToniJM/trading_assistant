"""Tests for market data simulator"""

from trading.infrastructure.simulator import MarketDataSimulator
from trading.infrastructure.simulator.domain import ONE_MINUTE, TIMEFRAME_MINUTES
from trading.infrastructure.simulator.simulator import get_base_timeframe


def test_simulator_initialization():
    """Test MarketDataSimulator initialization"""
    simulator = MarketDataSimulator(is_backtest=True)

    assert simulator.symbols_timeframes == {}
    assert simulator.start_time == 0
    assert simulator.end_time == 0
    assert simulator.current_time == 0


def test_simulator_set_times():
    """Test setting simulation times"""
    simulator = MarketDataSimulator(is_backtest=True)

    start_time = 1744023500000
    end_time = start_time + (24 * 60 * 60 * 1000)  # 24 hours later

    simulator.set_times(start=start_time, end=end_time, min_candles=10)

    assert simulator.start_time == start_time
    assert simulator.end_time == end_time
    assert simulator.current_time == start_time
    assert simulator.min_candles == 10


def test_simulator_ended():
    """Test symbol ended status"""
    simulator = MarketDataSimulator(is_backtest=True)

    assert simulator.ended("BTCUSDT") is False

    simulator.end("BTCUSDT")
    assert simulator.ended("BTCUSDT") is True


def test_timeframe_constants():
    """Test timeframe constants"""
    assert TIMEFRAME_MINUTES["1m"] == 1
    assert TIMEFRAME_MINUTES["1h"] == 60
    assert TIMEFRAME_MINUTES["1d"] == 1440
    assert ONE_MINUTE == 60000


def test_simulator_event_dispatcher():
    """Test simulator event dispatcher"""
    simulator = MarketDataSimulator(is_backtest=True)

    received_candles = []

    def listener(candle):
        received_candles.append(candle)

    simulator.event_dispatcher.add_complete_candle_listener("BTCUSDT", "1m", listener)
    assert len(received_candles) == 0

    # Test removing listener
    simulator.event_dispatcher.remove_complete_candle_listener("BTCUSDT", "1m", listener)


def test_get_base_timeframe_single_timeframe():
    """Test get_base_timeframe with a single valid timeframe"""
    result = get_base_timeframe(["1m"])
    assert result == "1m"

    result = get_base_timeframe(["15m"])
    assert result == "15m"

    result = get_base_timeframe(["1h"])
    assert result == "1h"


def test_get_base_timeframe_multiple_timeframes():
    """Test get_base_timeframe with multiple timeframes, should return shortest"""
    result = get_base_timeframe(["1m", "15m", "1h"])
    assert result == "1m"

    result = get_base_timeframe(["3m", "15m", "1h"])
    assert result == "3m"

    result = get_base_timeframe(["15m", "1h", "4h"])
    assert result == "15m"


def test_get_base_timeframe_empty_list():
    """Test get_base_timeframe with empty list, should return default "1m" """
    result = get_base_timeframe([])
    assert result == "1m"


def test_get_base_timeframe_invalid_timeframes():
    """Test get_base_timeframe with invalid timeframes, should return default "1m" """
    result = get_base_timeframe(["invalid"])
    assert result == "1m"

    result = get_base_timeframe(["xxx", "yyy"])
    assert result == "1m"


def test_get_base_timeframe_mixed_valid_invalid():
    """Test get_base_timeframe with mixed valid and invalid timeframes, should use only valid ones"""
    result = get_base_timeframe(["invalid", "15m", "invalid2", "1h"])
    assert result == "15m"

    result = get_base_timeframe(["invalid", "3m", "15m"])
    assert result == "3m"


def test_get_base_timeframe_ordering():
    """Test get_base_timeframe returns the shortest timeframe correctly"""
    # Test ordering: 1m < 3m < 5m < 15m < 30m < 1h
    assert get_base_timeframe(["1m", "3m"]) == "1m"
    assert get_base_timeframe(["3m", "1m"]) == "1m"
    assert get_base_timeframe(["15m", "3m", "1h"]) == "3m"
    assert get_base_timeframe(["1h", "30m", "15m"]) == "15m"
    assert get_base_timeframe(["5m", "3m", "1m"]) == "1m"

