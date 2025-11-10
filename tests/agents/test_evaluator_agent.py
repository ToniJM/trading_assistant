"""Tests for EvaluatorAgent"""

from decimal import Decimal

import pytest

from trading.agents.evaluator_agent import EvaluatorAgent
from trading.domain.messages import BacktestResultsResponse, EvaluationRequest, EvaluationResponse


@pytest.fixture
def evaluator_agent():
    """Create an EvaluatorAgent instance"""
    return EvaluatorAgent(run_id="test_evaluator_run").initialize()


@pytest.fixture
def sample_backtest_results():
    """Create sample backtest results"""
    return BacktestResultsResponse(
        run_id="test_backtest",
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
        profit_factor=2.5,  # Above threshold (1.5)
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


def test_evaluator_agent_initialization(evaluator_agent):
    """Test EvaluatorAgent initialization"""
    assert evaluator_agent.agent_name == "evaluator"
    assert evaluator_agent.get_memory("initialized") is True


def test_evaluate_with_passing_kpis(evaluator_agent, sample_backtest_results):
    """Test evaluation with KPIs that pass"""
    # Create results with good metrics (Sharpe > 2.0, Drawdown < 10%, Profit Factor > 1.5)
    # Note: Sharpe ratio calculation is simplified, so we'll use custom KPIs
    request = EvaluationRequest(
        run_id="test_backtest",
        kpis={
            "max_drawdown": 10.0,  # 5.0 < 10.0 ✓
            "profit_factor": 1.5,  # 2.5 > 1.5 ✓
        },
    )

    evaluation = evaluator_agent.evaluate(request, backtest_results=sample_backtest_results)

    assert isinstance(evaluation, EvaluationResponse)
    assert evaluation.run_id == "test_backtest"
    assert evaluation.evaluation_passed is True
    assert "max_drawdown" in evaluation.kpi_compliance
    assert evaluation.kpi_compliance["max_drawdown"] is True
    assert "profit_factor" in evaluation.kpi_compliance
    assert evaluation.kpi_compliance["profit_factor"] is True
    assert evaluation.recommendation == "promote"


def test_evaluate_with_failing_kpis(evaluator_agent):
    """Test evaluation with KPIs that fail"""
    # Create results with poor metrics
    results = BacktestResultsResponse(
        run_id="test_backtest_fail",
        status="completed",
        start_time=1000000,
        end_time=2000000,
        duration_seconds=86400.0,
        total_candles_processed=1000,
        final_balance=Decimal("2000"),  # Lost money
        total_return=Decimal("-500"),
        return_percentage=-20.0,
        max_drawdown=25.0,  # High drawdown
        total_trades=50,
        win_rate=30.0,
        profit_factor=0.8,  # Below 1.0
        total_closed_positions=50,
        winning_positions=15,
        losing_positions=35,
        total_commission=Decimal("10"),
        commission_percentage=4.0,
        total_cycles=10,
        avg_cycle_duration=60.0,
        avg_cycle_pnl=Decimal("-50"),
        winning_cycles=2,
        losing_cycles=8,
        cycle_win_rate=20.0,
        strategy_name="test_strategy",
        symbol="BTCUSDT",
    )

    request = EvaluationRequest(
        run_id="test_backtest_fail",
        kpis={
            "max_drawdown": 10.0,  # 25.0 > 10.0 ✗
            "profit_factor": 1.5,  # 0.8 < 1.5 ✗
        },
    )

    evaluation = evaluator_agent.evaluate(request, backtest_results=results)

    assert evaluation.evaluation_passed is False
    assert evaluation.kpi_compliance["max_drawdown"] is False
    assert evaluation.kpi_compliance["profit_factor"] is False
    assert evaluation.recommendation == "reject"  # Critical failures


def test_evaluate_with_default_kpis(evaluator_agent, sample_backtest_results):
    """Test evaluation with default KPIs"""
    request = EvaluationRequest(run_id="test_backtest")

    evaluation = evaluator_agent.evaluate(request, backtest_results=sample_backtest_results)

    assert isinstance(evaluation, EvaluationResponse)
    assert "sharpe_ratio" in evaluation.kpi_compliance or "max_drawdown" in evaluation.kpi_compliance
    assert "profit_factor" in evaluation.kpi_compliance


def test_evaluate_recommendation_optimize(evaluator_agent):
    """Test that recommendation is 'optimize' when close to thresholds"""
    # Results that are close to but don't meet thresholds
    results = BacktestResultsResponse(
        run_id="test_backtest_optimize",
        status="completed",
        start_time=1000000,
        end_time=2000000,
        duration_seconds=86400.0,
        total_candles_processed=1000,
        final_balance=Decimal("2600"),
        total_return=Decimal("100"),
        return_percentage=4.0,
        max_drawdown=9.0,  # Just below 10% threshold
        total_trades=50,
        win_rate=55.0,
        profit_factor=1.4,  # Just below 1.5 threshold (within 20%)
        total_closed_positions=50,
        winning_positions=28,
        losing_positions=22,
        total_commission=Decimal("10"),
        commission_percentage=10.0,
        total_cycles=10,
        avg_cycle_duration=60.0,
        avg_cycle_pnl=Decimal("10"),
        winning_cycles=6,
        losing_cycles=4,
        cycle_win_rate=60.0,
        strategy_name="test_strategy",
        symbol="BTCUSDT",
    )

    request = EvaluationRequest(
        run_id="test_backtest_optimize",
        kpis={
            "max_drawdown": 10.0,
            "profit_factor": 1.5,
        },
    )

    evaluation = evaluator_agent.evaluate(request, backtest_results=results)

    # Should recommend optimize if close to thresholds but not passing
    assert evaluation.recommendation in ["optimize", "reject"]


def test_evaluate_with_specific_metrics(evaluator_agent, sample_backtest_results):
    """Test evaluation with specific metrics requested"""
    request = EvaluationRequest(
        run_id="test_backtest",
        metrics=["return_percentage", "win_rate"],  # Only these metrics
    )

    evaluation = evaluator_agent.evaluate(request, backtest_results=sample_backtest_results)

    assert "return_percentage" in evaluation.metrics
    assert "win_rate" in evaluation.metrics
    # Sharpe ratio might not be in metrics if not requested
    # (depends on implementation)


def test_evaluate_missing_backtest_results(evaluator_agent):
    """Test evaluation fails when backtest_results is None"""
    request = EvaluationRequest(run_id="test_backtest")

    with pytest.raises(ValueError, match="backtest_results must be provided"):
        evaluator_agent.evaluate(request, backtest_results=None)




