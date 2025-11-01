"""Tests for market data simulator"""

from trading.infrastructure.simulator import MarketDataSimulator
from trading.infrastructure.simulator.domain import ONE_MINUTE, TIMEFRAME_MINUTES


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

