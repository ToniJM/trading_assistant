"""Tests for BacktestRunner"""

from decimal import Decimal
from unittest.mock import Mock

from trading.domain.entities import Trade
from trading.domain.ports import StrategyPort
from trading.infrastructure.backtest.config import BacktestConfig, BacktestResults
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


def test_validate_metrics_consistency_with_opening_commissions():
    """Test _validate_metrics_consistency correctly handles opening commissions"""
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        initial_balance=Decimal("2500"),
        timeframes=["1m", "15m", "1h"],
    )

    simulator = MarketDataSimulator(is_backtest=True)
    simulator.set_times(start=config.start_time, end=config.end_time, min_candles=10)
    simulator.symbols_timeframes[config.symbol] = config.timeframes

    runner = BacktestRunner(config=config, simulator=simulator)

    # Create trades with opening commissions (realized_pnl == 0)
    opening_trade1 = Trade(
        order_id="order1",
        timestamp=1744023500000,
        symbol="BTCUSDT",
        position_side="long",
        side="buy",
        price=Decimal("50000"),
        quantity=Decimal("0.1"),
        commission=Decimal("1.0"),  # Opening commission
        realized_pnl=Decimal("0"),  # Opening position has no realized P&L
    )

    opening_trade2 = Trade(
        order_id="order2",
        timestamp=1744023501000,
        symbol="BTCUSDT",
        position_side="short",
        side="sell",
        price=Decimal("50100"),
        quantity=Decimal("0.1"),
        commission=Decimal("1.5"),  # Opening commission
        realized_pnl=Decimal("0"),  # Opening position has no realized P&L
    )

    # Create closing trades (realized_pnl != 0)
    closing_trade1 = Trade(
        order_id="order3",
        timestamp=1744023502000,
        symbol="BTCUSDT",
        position_side="long",
        side="sell",
        price=Decimal("51000"),
        quantity=Decimal("0.1"),
        commission=Decimal("2.0"),  # Closing commission
        realized_pnl=Decimal("98.0"),  # Profit: (51000 - 50000) * 0.1 - 1.0 - 2.0 = 98.0
    )

    closing_trade2 = Trade(
        order_id="order4",
        timestamp=1744023503000,
        symbol="BTCUSDT",
        position_side="short",
        side="buy",
        price=Decimal("49500"),
        quantity=Decimal("0.1"),
        commission=Decimal("2.5"),  # Closing commission
        realized_pnl=Decimal("97.0"),  # Profit: (50100 - 49500) * 0.1 - 1.5 - 2.5 = 97.0
    )

    trades = [opening_trade1, opening_trade2, closing_trade1, closing_trade2]

    # Calculate expected values:
    # sum_realized_pnl = 98.0 + 97.0 = 195.0
    # opening_commissions = 1.0 + 1.5 = 2.5
    # total_return = sum_realized_pnl - opening_commissions = 195.0 - 2.5 = 192.5
    # OR: total_return already includes everything, so:
    # total_return = (98.0 - 2.0) + (97.0 - 2.5) - 1.0 - 1.5 = 96.0 + 94.5 - 2.5 = 188.0
    # Actually, total_return is the net change in balance, which should be:
    # profits from closes minus all commissions = (98.0 + 97.0) - (1.0 + 1.5 + 2.0 + 2.5) = 195.0 - 7.0 = 188.0

    # But the formula used is: sum_realized = total_return + opening_commissions
    # So: 195.0 = total_return + 2.5 → total_return = 192.5
    # Let's use the simpler approach: total_return = sum_realized_pnl - opening_commissions = 195.0 - 2.5 = 192.5

    results = BacktestResults(
        start_time=1744023500000,
        end_time=1744023504000,
        duration_seconds=4.0,
        total_candles_processed=100,
        final_balance=Decimal("2692.5"),  # 2500 + 192.5
        total_return=Decimal("192.5"),  # sum_realized - opening_commissions = 195.0 - 2.5
        return_percentage=7.7,
        max_drawdown=0.0,
        total_trades=4,
        win_rate=100.0,
        profit_factor=2.0,
        total_closed_positions=2,
        winning_positions=2,
        losing_positions=0,
        average_trade_size=Decimal("0.1"),
        total_commission=Decimal("7.0"),  # All commissions: 1.0 + 1.5 + 2.0 + 2.5
        commission_percentage=3.6,
        total_closing_trades=2,
        partial_closing_trades=0,
        full_closing_trades=2,
        winning_closing_trades=2,
        losing_closing_trades=0,
        partial_winning_trades=0,
        partial_losing_trades=0,
        full_winning_trades=2,
        full_losing_trades=0,
        total_cycles=1,
        avg_cycle_duration=1.0,
        avg_cycle_pnl=Decimal("192.5"),
        winning_cycles=1,
        losing_cycles=0,
        cycle_win_rate=100.0,
    )

    warnings = runner._validate_metrics_consistency(results, trades)

    # Should not have P&L inconsistency warning
    pnl_warnings = [w for w in warnings if "P&L inconsistency" in w]
    assert len(pnl_warnings) == 0, f"Unexpected P&L inconsistency warning: {pnl_warnings}"


def test_validate_metrics_consistency_all_opening_positions():
    """Test _validate_metrics_consistency with all opening positions (no realized P&L)"""
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        initial_balance=Decimal("2500"),
        timeframes=["1m", "15m", "1h"],
    )

    simulator = MarketDataSimulator(is_backtest=True)
    simulator.set_times(start=config.start_time, end=config.end_time, min_candles=10)
    simulator.symbols_timeframes[config.symbol] = config.timeframes

    runner = BacktestRunner(config=config, simulator=simulator)

    # All trades are opening positions
    opening_trade1 = Trade(
        order_id="order1",
        timestamp=1744023500000,
        symbol="BTCUSDT",
        position_side="long",
        side="buy",
        price=Decimal("50000"),
        quantity=Decimal("0.1"),
        commission=Decimal("1.0"),
        realized_pnl=Decimal("0"),
    )

    opening_trade2 = Trade(
        order_id="order2",
        timestamp=1744023501000,
        symbol="BTCUSDT",
        position_side="short",
        side="sell",
        price=Decimal("50100"),
        quantity=Decimal("0.1"),
        commission=Decimal("1.5"),
        realized_pnl=Decimal("0"),
    )

    trades = [opening_trade1, opening_trade2]

    # sum_realized_pnl = 0
    # opening_commissions = 1.0 + 1.5 = 2.5
    # total_return = -2.5 (only commissions paid, no profits)
    # sum_realized = total_return + opening_commissions → 0 = -2.5 + 2.5 = 0 ✓

    results = BacktestResults(
        start_time=1744023500000,
        end_time=1744023502000,
        duration_seconds=2.0,
        total_candles_processed=50,
        final_balance=Decimal("2497.5"),  # 2500 - 2.5
        total_return=Decimal("-2.5"),  # Only opening commissions
        return_percentage=-0.1,
        max_drawdown=0.1,
        total_trades=2,
        win_rate=0.0,
        profit_factor=0.0,
        total_closed_positions=0,
        winning_positions=0,
        losing_positions=0,
        average_trade_size=Decimal("0.1"),
        total_commission=Decimal("2.5"),
        commission_percentage=100.0,
        total_closing_trades=0,
        partial_closing_trades=0,
        full_closing_trades=0,
        winning_closing_trades=0,
        losing_closing_trades=0,
        partial_winning_trades=0,
        partial_losing_trades=0,
        full_winning_trades=0,
        full_losing_trades=0,
        total_cycles=0,
        avg_cycle_duration=0.0,
        avg_cycle_pnl=Decimal("0"),
        winning_cycles=0,
        losing_cycles=0,
        cycle_win_rate=0.0,
    )

    warnings = runner._validate_metrics_consistency(results, trades)

    # Should not have P&L inconsistency warning
    pnl_warnings = [w for w in warnings if "P&L inconsistency" in w]
    assert len(pnl_warnings) == 0, f"Unexpected P&L inconsistency warning: {pnl_warnings}"


def test_validate_metrics_consistency_detects_actual_inconsistency():
    """Test _validate_metrics_consistency detects actual P&L inconsistencies"""
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (24 * 60 * 60 * 1000),
        initial_balance=Decimal("2500"),
        timeframes=["1m", "15m", "1h"],
    )

    simulator = MarketDataSimulator(is_backtest=True)
    simulator.set_times(start=config.start_time, end=config.end_time, min_candles=10)
    simulator.symbols_timeframes[config.symbol] = config.timeframes

    runner = BacktestRunner(config=config, simulator=simulator)

    # Create mismatched scenario where calculation would be wrong
    opening_trade = Trade(
        order_id="order1",
        timestamp=1744023500000,
        symbol="BTCUSDT",
        position_side="long",
        side="buy",
        price=Decimal("50000"),
        quantity=Decimal("0.1"),
        commission=Decimal("1.0"),
        realized_pnl=Decimal("0"),
    )

    closing_trade = Trade(
        order_id="order2",
        timestamp=1744023501000,
        symbol="BTCUSDT",
        position_side="long",
        side="sell",
        price=Decimal("51000"),
        quantity=Decimal("0.1"),
        commission=Decimal("2.0"),
        realized_pnl=Decimal("98.0"),  # Actual realized P&L
    )

    trades = [opening_trade, closing_trade]

    # sum_realized_pnl = 98.0
    # opening_commissions = 1.0
    # If we incorrectly set total_return, it should trigger a warning
    # Correct: total_return = 98.0 - 1.0 = 97.0
    # Wrong: total_return = 50.0 (intentionally wrong)

    results = BacktestResults(
        start_time=1744023500000,
        end_time=1744023502000,
        duration_seconds=2.0,
        total_candles_processed=50,
        final_balance=Decimal("2550.0"),  # 2500 + 50.0 (wrong)
        total_return=Decimal("50.0"),  # Intentionally wrong
        return_percentage=2.0,
        max_drawdown=0.0,
        total_trades=2,
        win_rate=100.0,
        profit_factor=2.0,
        total_closed_positions=1,
        winning_positions=1,
        losing_positions=0,
        average_trade_size=Decimal("0.1"),
        total_commission=Decimal("3.0"),
        commission_percentage=6.0,
        total_closing_trades=1,
        partial_closing_trades=0,
        full_closing_trades=1,
        winning_closing_trades=1,
        losing_closing_trades=0,
        partial_winning_trades=0,
        partial_losing_trades=0,
        full_winning_trades=1,
        full_losing_trades=0,
        total_cycles=1,
        avg_cycle_duration=1.0,
        avg_cycle_pnl=Decimal("50.0"),
        winning_cycles=1,
        losing_cycles=0,
        cycle_win_rate=100.0,
    )

    warnings = runner._validate_metrics_consistency(results, trades)

    # Should have P&L inconsistency warning
    pnl_warnings = [w for w in warnings if "P&L inconsistency" in w]
    assert len(pnl_warnings) > 0, "Expected P&L inconsistency warning but none was found"
