"""Tests for evaluation metrics calculation"""

from decimal import Decimal

import pytest

from trading.domain.messages import BacktestResultsResponse
from trading.infrastructure.evaluation.metrics import (
    calculate_calmar_ratio,
    calculate_sharpe_ratio,
    extract_metrics_from_results,
)


def test_calculate_sharpe_ratio_with_balance_history():
    """Test Sharpe Ratio calculation with balance history"""
    # Create mock balance history with returns
    balance_history = [
        (1000000, Decimal("2500.0")),  # Initial
        (1000100, Decimal("2525.0")),  # +1%
        (1000200, Decimal("2500.0")),  # -1%
        (1000300, Decimal("2550.0")),  # +2%
    ]

    # Calculate Sharpe Ratio
    sharpe = calculate_sharpe_ratio(
        return_percentage=2.0,  # 2% total return
        duration_seconds=300,  # 5 minutes
        balance_history=balance_history,
    )

    # Should be positive (some return with volatility)
    assert isinstance(sharpe, float)
    assert sharpe >= 0


def test_calculate_sharpe_ratio_simplified():
    """Test simplified Sharpe Ratio calculation without balance history"""
    sharpe = calculate_sharpe_ratio(
        return_percentage=10.0,  # 10% return
        duration_seconds=86400,  # 1 day
        balance_history=None,
    )

    assert isinstance(sharpe, float)
    # With 10% return over 1 day, annualized would be very high
    # But simplified calculation should still give a reasonable value
    assert sharpe >= 0


def test_calculate_sharpe_ratio_zero_duration():
    """Test Sharpe Ratio with zero duration"""
    sharpe = calculate_sharpe_ratio(
        return_percentage=10.0,
        duration_seconds=0,
        balance_history=None,
    )

    assert sharpe == 0.0


def test_calculate_calmar_ratio():
    """Test Calmar Ratio calculation"""
    calmar = calculate_calmar_ratio(return_percentage=20.0, max_drawdown=10.0)

    assert calmar == 2.0  # 20 / 10 = 2.0


def test_calculate_calmar_ratio_zero_drawdown():
    """Test Calmar Ratio with zero drawdown"""
    calmar = calculate_calmar_ratio(return_percentage=20.0, max_drawdown=0.0)

    assert calmar == 0.0


def test_extract_metrics_from_results():
    """Test extracting metrics from BacktestResultsResponse"""
    results = BacktestResultsResponse(
        run_id="test_run",
        status="completed",
        start_time=1000000,
        end_time=2000000,
        duration_seconds=86400.0,  # 1 day
        total_candles_processed=1000,
        final_balance=Decimal("2750"),
        total_return=Decimal("250"),
        return_percentage=10.0,
        max_drawdown=5.0,
        total_trades=50,
        win_rate=60.0,
        profit_factor=1.8,
        total_closed_positions=50,
        winning_positions=30,
        losing_positions=20,
        total_commission=Decimal("10"),
        commission_percentage=4.0,
        total_cycles=10,
        avg_cycle_duration=60.0,
        avg_cycle_pnl=Decimal("25"),
        winning_cycles=7,
        losing_cycles=3,
        cycle_win_rate=70.0,
        strategy_name="test_strategy",
        symbol="BTCUSDT",
    )

    metrics = extract_metrics_from_results(results, calculate_advanced=True)

    assert "return_percentage" in metrics
    assert metrics["return_percentage"] == 10.0
    assert "max_drawdown" in metrics
    assert metrics["max_drawdown"] == 5.0
    assert "profit_factor" in metrics
    assert metrics["profit_factor"] == 1.8
    assert "win_rate" in metrics
    assert metrics["win_rate"] == 60.0
    assert "sharpe_ratio" in metrics
    assert isinstance(metrics["sharpe_ratio"], float)
    assert "calmar_ratio" in metrics
    assert metrics["calmar_ratio"] == 2.0  # 10 / 5 = 2.0


def test_extract_metrics_without_advanced():
    """Test extracting metrics without advanced calculations"""
    results = BacktestResultsResponse(
        run_id="test_run",
        status="completed",
        start_time=1000000,
        end_time=2000000,
        duration_seconds=86400.0,
        total_candles_processed=1000,
        final_balance=Decimal("2750"),
        total_return=Decimal("250"),
        return_percentage=10.0,
        max_drawdown=5.0,
        total_trades=50,
        win_rate=60.0,
        profit_factor=1.8,
        total_closed_positions=50,
        winning_positions=30,
        losing_positions=20,
        total_commission=Decimal("10"),
        commission_percentage=4.0,
        total_cycles=10,
        avg_cycle_duration=60.0,
        avg_cycle_pnl=Decimal("25"),
        winning_cycles=7,
        losing_cycles=3,
        cycle_win_rate=70.0,
        strategy_name="test_strategy",
        symbol="BTCUSDT",
    )

    metrics = extract_metrics_from_results(results, calculate_advanced=False)

    assert "return_percentage" in metrics
    assert "max_drawdown" in metrics
    assert "profit_factor" in metrics
    # Advanced metrics should not be included
    assert "sharpe_ratio" not in metrics
    assert "calmar_ratio" not in metrics



