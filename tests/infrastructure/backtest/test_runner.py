"""Tests for BacktestRunner"""

from unittest.mock import Mock

from trading.domain.ports import StrategyPort
from trading.infrastructure.backtest.config import BacktestConfig
from trading.infrastructure.backtest.runner import BacktestRunner
from trading.infrastructure.simulator.simulator import MarketDataSimulator, get_base_timeframe


def test_backtest_runner_calculates_base_timeframe():
    """Test BacktestRunner calculates base timeframe correctly from config.timeframes"""
    # Test with default timeframes (1m, 15m, 1h)
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        timeframes=["1m", "15m", "1h"],
    )
    base_timeframe = get_base_timeframe(config.timeframes)
    assert base_timeframe == "1m"

    # Test with custom timeframes (3m, 15m, 1h)
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        timeframes=["3m", "15m", "1h"],
    )
    base_timeframe = get_base_timeframe(config.timeframes)
    assert base_timeframe == "3m"

    # Test with 2 timeframes
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        timeframes=["15m", "1h"],
    )
    base_timeframe = get_base_timeframe(config.timeframes)
    assert base_timeframe == "15m"


def test_backtest_runner_configures_exchange_base_timeframe():
    """Test BacktestRunner configures Exchange with base timeframe"""
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        timeframes=["3m", "15m", "1h"],
    )

    # Create mock simulator
    simulator = MarketDataSimulator(is_backtest=True)
    simulator.set_times(start=config.start_time, end=config.end_time, min_candles=10)
    simulator.symbols_timeframes[config.symbol] = config.timeframes

    # Create runner
    runner = BacktestRunner(config=config, simulator=simulator)

    # Create a mock strategy factory
    mock_strategy = Mock(spec=StrategyPort)

    def strategy_factory(symbol, exchange, market_data, cycle_dispatcher, strategy_name):
        return mock_strategy

    # Setup exchange and strategy
    runner.setup_exchange_and_strategy(strategy_factory=strategy_factory)

    # Verify that exchange was configured with base timeframe
    # The base timeframe for ["3m", "15m", "1h"] should be "3m"
    expected_base_timeframe = get_base_timeframe(config.timeframes)
    assert expected_base_timeframe == "3m"

    # Access the exchange's base_timeframe through the adapter chain
    assert runner.exchange.exchange.base_timeframe == "3m"


def test_backtest_runner_timeframes_1m_15m_1h():
    """Test BacktestRunner with default timeframes (1m, 15m, 1h)"""
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        timeframes=["1m", "15m", "1h"],
    )

    simulator = MarketDataSimulator(is_backtest=True)
    simulator.set_times(start=config.start_time, end=config.end_time, min_candles=10)
    simulator.symbols_timeframes[config.symbol] = config.timeframes

    runner = BacktestRunner(config=config, simulator=simulator)

    mock_strategy = Mock(spec=StrategyPort)

    def strategy_factory(symbol, exchange, market_data, cycle_dispatcher, strategy_name):
        return mock_strategy

    runner.setup_exchange_and_strategy(strategy_factory=strategy_factory)

    # Verify base timeframe is "1m"
    assert runner.exchange.exchange.base_timeframe == "1m"


def test_backtest_runner_timeframes_3m_15m_1h():
    """Test BacktestRunner with custom timeframes (3m, 15m, 1h)"""
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        timeframes=["3m", "15m", "1h"],
    )

    simulator = MarketDataSimulator(is_backtest=True)
    simulator.set_times(start=config.start_time, end=config.end_time, min_candles=10)
    simulator.symbols_timeframes[config.symbol] = config.timeframes

    runner = BacktestRunner(config=config, simulator=simulator)

    mock_strategy = Mock(spec=StrategyPort)

    def strategy_factory(symbol, exchange, market_data, cycle_dispatcher, strategy_name):
        return mock_strategy

    runner.setup_exchange_and_strategy(strategy_factory=strategy_factory)

    # Verify base timeframe is "3m"
    assert runner.exchange.exchange.base_timeframe == "3m"
