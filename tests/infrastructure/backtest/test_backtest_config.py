"""Tests for backtest configuration"""

from decimal import Decimal

import pytest

from trading.infrastructure.backtest.config import BacktestConfig, BacktestConfigs, BacktestResults, validate_timeframes


def test_backtest_config_creation():
    """Test BacktestConfig creation"""
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        initial_balance=Decimal("2500"),
        leverage=Decimal("100"),
    )

    assert config.symbol == "BTCUSDT"
    assert config.initial_balance == Decimal("2500")
    assert config.leverage == Decimal("100")
    assert config.stop_on_loss is True  # Default value


def test_backtest_config_defaults():
    """Test BacktestConfig default values"""
    config = BacktestConfig(symbol="BTCUSDT", start_time=1744023500000)

    assert config.initial_balance == Decimal("2500")  # Default
    assert config.leverage == Decimal("100")  # Default
    assert config.maker_fee == Decimal("0.0002")  # Default
    assert config.taker_fee == Decimal("0.0005")  # Default
    assert config.max_notional == Decimal("50000")  # Default
    assert config.enable_frontend is False  # Default
    assert config.stop_on_loss is True  # Default
    assert config.max_loss_percentage == 0.5  # Default


def test_backtest_configs_quick_test():
    """Test quick test config preset"""
    config_dict = BacktestConfigs.get_quick_test_config()

    assert config_dict["symbol"] == "BTCUSDT"
    assert config_dict["initial_balance"] == Decimal("2500")
    assert "start_time" in config_dict
    assert "end_time" in config_dict


def test_backtest_configs_2hour_test():
    """Test 2-hour test config preset"""
    config_dict = BacktestConfigs.get_2hour_test_config()

    assert config_dict["symbol"] == "BTCUSDT"
    assert config_dict["max_loss_percentage"] == 0.05  # 5% for quick test


def test_backtest_results_creation():
    """Test BacktestResults creation"""
    results = BacktestResults(
        start_time=1744023500000,
        end_time=1744023501000,
        duration_seconds=1.0,
        total_candles_processed=100,
        final_balance=Decimal("2600"),
        total_return=Decimal("100"),
        return_percentage=4.0,
        max_drawdown=2.0,
        total_trades=10,
        win_rate=60.0,
        profit_factor=1.5,
        total_closed_positions=8,
        winning_positions=5,
        losing_positions=3,
        average_trade_size=Decimal("100"),
        total_commission=Decimal("10"),
        commission_percentage=10.0,
        total_closing_trades=8,
        partial_closing_trades=2,
        full_closing_trades=6,
        winning_closing_trades=5,
        losing_closing_trades=3,
        partial_winning_trades=1,
        partial_losing_trades=1,
        full_winning_trades=4,
        full_losing_trades=2,
        total_cycles=5,
        avg_cycle_duration=10.0,
        avg_cycle_pnl=Decimal("20"),
        winning_cycles=3,
        losing_cycles=2,
        cycle_win_rate=60.0,
    )

    assert results.final_balance == Decimal("2600")
    assert results.total_return == Decimal("100")
    assert results.return_percentage == 4.0
    assert results.win_rate == 60.0
    assert results.total_cycles == 5


def test_validate_timeframes_count_2():
    """Test validate_timeframes accepts 2 timeframes"""
    result = validate_timeframes(["1m", "15m"])
    assert result == ["1m", "15m"]

    result = validate_timeframes(["3m", "1h"])
    assert result == ["3m", "1h"]


def test_validate_timeframes_count_3():
    """Test validate_timeframes accepts 3 timeframes"""
    result = validate_timeframes(["1m", "15m", "1h"])
    assert result == ["1m", "15m", "1h"]

    result = validate_timeframes(["3m", "15m", "1h"])
    assert result == ["3m", "15m", "1h"]


def test_validate_timeframes_count_4():
    """Test validate_timeframes accepts 4 timeframes"""
    result = validate_timeframes(["1m", "5m", "15m", "1h"])
    assert result == ["1m", "5m", "15m", "1h"]

    result = validate_timeframes(["3m", "15m", "1h", "4h"])
    assert result == ["3m", "15m", "1h", "4h"]


def test_validate_timeframes_count_invalid():
    """Test validate_timeframes rejects invalid counts (1, 5 or more)"""
    with pytest.raises(ValueError, match="Number of timeframes must be 2, 3 or 4"):
        validate_timeframes(["1m"])

    with pytest.raises(ValueError, match="Number of timeframes must be 2, 3 or 4"):
        validate_timeframes(["1m", "15m", "1h", "4h", "1d"])

    # Empty list raises different error message
    with pytest.raises(ValueError, match="At least one timeframe must be provided"):
        validate_timeframes([])


def test_validate_timeframes_invalid_strings():
    """Test validate_timeframes rejects invalid timeframe strings"""
    with pytest.raises(ValueError, match="Invalid timeframes"):
        validate_timeframes(["invalid", "15m"])

    with pytest.raises(ValueError, match="Invalid timeframes"):
        validate_timeframes(["1m", "invalid"])

    with pytest.raises(ValueError, match="Invalid timeframes"):
        validate_timeframes(["xxx", "yyy"])


def test_backtest_config_timeframes_default():
    """Test BacktestConfig has default timeframes"""
    config = BacktestConfig(symbol="BTCUSDT", start_time=1744023500000)
    assert config.timeframes == ["1m", "15m", "1h"]


def test_backtest_config_timeframes_custom():
    """Test BacktestConfig accepts custom timeframes"""
    config = BacktestConfig(symbol="BTCUSDT", start_time=1744023500000, timeframes=["3m", "15m", "1h"])
    assert config.timeframes == ["3m", "15m", "1h"]

    config = BacktestConfig(symbol="BTCUSDT", start_time=1744023500000, timeframes=["1m", "15m"])
    assert config.timeframes == ["1m", "15m"]


def test_backtest_config_timeframes_validation_on_init():
    """Test BacktestConfig validates timeframes on initialization"""
    # Should raise error for invalid count
    with pytest.raises(ValueError, match="Number of timeframes must be 2, 3 or 4"):
        BacktestConfig(symbol="BTCUSDT", start_time=1744023500000, timeframes=["1m"])

    # Should raise error for invalid timeframe strings
    with pytest.raises(ValueError, match="Invalid timeframes"):
        BacktestConfig(symbol="BTCUSDT", start_time=1744023500000, timeframes=["invalid", "15m"])
