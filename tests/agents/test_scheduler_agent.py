"""Tests for SchedulerAgent"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from trading.agents import SchedulerAgent
from trading.infrastructure.scheduler.scheduler_config import SchedulerConfig


@pytest.fixture
def scheduler_config():
    """Create scheduler config for testing"""
    return SchedulerConfig(
        symbol="BTCUSDT",
        strategy_name="carga_descarga",
        schedule_interval_seconds=60,  # Short interval for testing
        backtest_duration_days=1,  # Short duration for testing
        max_iterations_per_cycle=2,
        kpis={"sharpe_ratio": 2.0, "max_drawdown": 10.0, "profit_factor": 1.5},
        auto_reset_memory=True,
    )


@pytest.fixture
def scheduler_agent(scheduler_config):
    """Create SchedulerAgent for testing"""
    with patch("trading.agents.scheduler_agent.OrchestratorAgent") as mock_orchestrator_class:
        mock_orchestrator = MagicMock()
        mock_orchestrator_class.return_value = mock_orchestrator

        agent = SchedulerAgent(config=scheduler_config, run_id="test_scheduler")
        agent.orchestrator = mock_orchestrator
        agent.initialize()

        yield agent
        agent.close()


def test_scheduler_agent_initialization(scheduler_agent):
    """Test SchedulerAgent initialization"""
    assert scheduler_agent.agent_name == "scheduler"
    assert scheduler_agent.config is not None
    assert scheduler_agent.orchestrator is not None
    assert scheduler_agent.running is False
    assert scheduler_agent.get_memory("initialized") is True


def test_scheduler_config_validation():
    """Test SchedulerConfig validation"""
    # Valid config
    config = SchedulerConfig(
        symbol="BTCUSDT",
        strategy_name="carga_descarga",
        schedule_interval_seconds=3600,
        backtest_duration_days=7,
    )
    assert config.symbol == "BTCUSDT"
    assert config.strategy_name == "carga_descarga"

    # Invalid interval (too short)
    with pytest.raises(Exception):  # Pydantic validation error
        SchedulerConfig(
            symbol="BTCUSDT",
            strategy_name="carga_descarga",
            schedule_interval_seconds=30,  # Less than 60
        )


def test_should_reset_daily(scheduler_agent):
    """Test daily reset check"""
    # First time should return True
    assert scheduler_agent._should_reset_daily() is True

    # Set last reset to today
    scheduler_agent.last_reset_date = datetime.now(timezone.utc)
    assert scheduler_agent._should_reset_daily() is False

    # Set last reset to yesterday
    scheduler_agent.last_reset_date = datetime.now(timezone.utc) - timedelta(days=1)
    assert scheduler_agent._should_reset_daily() is True


def test_reset_daily_memory(scheduler_agent):
    """Test daily memory reset"""
    # Store some memory
    scheduler_agent.store_memory("test_key", "test_value")
    scheduler_agent.store_memory("cycle_count", 5)

    # Reset
    scheduler_agent.reset_daily_memory()

    # Config should be preserved
    assert scheduler_agent.get_memory("config") is not None
    # Other memory should be cleared
    assert scheduler_agent.get_memory("test_key") is None
    # Counters should be reset
    assert scheduler_agent.executions_today == 0
    assert scheduler_agent.last_reset_date is not None


def test_stop_scheduler(scheduler_agent):
    """Test stopping scheduler"""
    scheduler_agent.running = True
    scheduler_agent.stop()

    assert scheduler_agent.running is False


@patch("trading.agents.scheduler_agent.create_strategy_factory")
@patch("trading.agents.scheduler_agent.datetime")
def test_run_cycle(mock_datetime, mock_factory, scheduler_agent):
    """Test running one cycle"""
    from decimal import Decimal

    from trading.domain.messages import BacktestResultsResponse, EvaluationResponse

    # Setup mocks
    mock_datetime.now.return_value = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    mock_factory.return_value = lambda: None

    # Mock orchestrator responses
    mock_backtest = BacktestResultsResponse(
        run_id="test_run",
        status="completed",
        start_time=1000000,
        end_time=2000000,
        duration_seconds=100.0,
        total_candles_processed=1000,
        final_balance=Decimal("2600"),
        total_return=Decimal("100"),
        return_percentage=4.0,
        max_drawdown=5.0,
        total_trades=50,
        win_rate=60.0,
        profit_factor=1.5,
        total_closed_positions=10,
        winning_positions=6,
        losing_positions=4,
        total_commission=Decimal("10"),
        commission_percentage=10.0,
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
    )

    mock_evaluation = EvaluationResponse(
        run_id="test_run",
        evaluation_passed=True,
        metrics={"sharpe_ratio": 2.5, "max_drawdown": 5.0, "profit_factor": 1.5},
        kpi_compliance={"sharpe_ratio": True, "max_drawdown": True, "profit_factor": True},
        recommendation="promote",
    )

    scheduler_agent.orchestrator.run_backtest.return_value = mock_backtest
    scheduler_agent.orchestrator.evaluate_backtest.return_value = mock_evaluation

    # Run cycle
    scheduler_agent.run_cycle()

    # Verify orchestrator was called
    assert scheduler_agent.orchestrator.run_backtest.called
    assert scheduler_agent.orchestrator.evaluate_backtest.called
    assert scheduler_agent.cycle_count == 1
    assert scheduler_agent.executions_today == 1


def test_handle_message_unknown_type(scheduler_agent):
    """Test handling unknown message type"""
    from trading.domain.messages import AgentMessage, StartBacktestRequest

    message = AgentMessage(
        from_agent="test",
        to_agent="scheduler",
        flow_id="test_flow",
        payload=StartBacktestRequest(
            symbol="BTCUSDT",
            start_time=1000000,
            strategy_name="carga_descarga",
        ),
    )

    response = scheduler_agent.handle_message(message)

    assert response.payload.error_code == "UNKNOWN_MESSAGE_TYPE"


def test_reset_to_first_period(scheduler_agent):
    """Test resetting to first period"""
    # Set to a later period
    scheduler_agent.current_period_index = 2
    scheduler_agent.backtest_count_in_period = 5
    scheduler_agent.passed_backtests_in_period = 3
    scheduler_agent.period_parameter_combinations[2] = {"test": []}

    # Reset
    scheduler_agent._reset_to_first_period()

    assert scheduler_agent.current_period_index == 0
    assert scheduler_agent.backtest_count_in_period == 0
    assert scheduler_agent.passed_backtests_in_period == 0
    assert len(scheduler_agent.period_parameter_combinations) == 0


@patch("trading.agents.scheduler_agent.create_strategy_factory")
@patch("trading.agents.scheduler_agent.datetime")
def test_period_progression(mock_datetime, mock_factory, scheduler_agent):
    """Test progression through periods (1 day → 1 week → 1 month → 3 months)"""
    from decimal import Decimal

    from trading.domain.messages import BacktestResultsResponse, EvaluationResponse

    # Setup mocks
    mock_datetime.now.return_value = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    mock_factory.return_value = lambda: None

    # Configure for incremental periods
    scheduler_agent.config.incremental_periods = [1, 7, 30, 90]
    scheduler_agent.config.backtests_per_period = 2  # Small for testing
    scheduler_agent.config.min_passed_backtests_per_period = 2

    # Mock orchestrator responses (all passing)
    mock_backtest = BacktestResultsResponse(
        run_id="test_run",
        status="completed",
        start_time=1000000,
        end_time=2000000,
        duration_seconds=100.0,
        total_candles_processed=1000,
        final_balance=Decimal("2600"),
        total_return=Decimal("100"),
        return_percentage=4.0,
        max_drawdown=5.0,
        total_trades=50,
        win_rate=60.0,
        profit_factor=1.5,
        total_closed_positions=10,
        winning_positions=6,
        losing_positions=4,
        total_commission=Decimal("10"),
        commission_percentage=10.0,
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
    )

    mock_evaluation = EvaluationResponse(
        run_id="test_run",
        evaluation_passed=True,
        metrics={"sharpe_ratio": 2.5, "max_drawdown": 5.0, "profit_factor": 1.5},
        kpi_compliance={"sharpe_ratio": True, "max_drawdown": True, "profit_factor": True},
        recommendation="promote",
    )

    scheduler_agent.orchestrator.run_backtest.return_value = mock_backtest
    scheduler_agent.orchestrator.evaluate_backtest.return_value = mock_evaluation

    # Start at period 0 (1 day)
    assert scheduler_agent.current_period_index == 0

    # Run 2 cycles for period 0 (should advance to period 1)
    scheduler_agent.run_cycle()
    scheduler_agent.run_cycle()

    assert scheduler_agent.current_period_index == 1
    assert scheduler_agent.backtest_count_in_period == 0  # Reset for new period
    assert scheduler_agent.passed_backtests_in_period == 0

    # Run 2 cycles for period 1 (should advance to period 2)
    scheduler_agent.run_cycle()
    scheduler_agent.run_cycle()

    assert scheduler_agent.current_period_index == 2


@patch("trading.agents.scheduler_agent.create_strategy_factory")
@patch("trading.agents.scheduler_agent.datetime")
def test_reset_on_optimize(mock_datetime, mock_factory, scheduler_agent):
    """Test reset to first period when optimization is needed"""
    from decimal import Decimal

    from trading.domain.messages import BacktestResultsResponse, EvaluationResponse

    # Setup mocks
    mock_datetime.now.return_value = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    mock_factory.return_value = lambda: None

    # Set to period 2 (1 month)
    scheduler_agent.current_period_index = 2
    scheduler_agent.backtest_count_in_period = 3

    # Mock orchestrator responses (optimization needed)
    mock_backtest = BacktestResultsResponse(
        run_id="test_run",
        status="completed",
        start_time=1000000,
        end_time=2000000,
        duration_seconds=100.0,
        total_candles_processed=1000,
        final_balance=Decimal("2600"),
        total_return=Decimal("100"),
        return_percentage=4.0,
        max_drawdown=5.0,
        total_trades=50,
        win_rate=60.0,
        profit_factor=1.5,
        total_closed_positions=10,
        winning_positions=6,
        losing_positions=4,
        total_commission=Decimal("10"),
        commission_percentage=10.0,
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
    )

    mock_evaluation = EvaluationResponse(
        run_id="test_run",
        evaluation_passed=False,
        metrics={"sharpe_ratio": 1.8, "max_drawdown": 8.0, "profit_factor": 1.4},
        kpi_compliance={"sharpe_ratio": False, "max_drawdown": True, "profit_factor": False},
        recommendation="optimize",
    )

    scheduler_agent.orchestrator.run_backtest.return_value = mock_backtest
    scheduler_agent.orchestrator.evaluate_backtest.return_value = mock_evaluation

    # Run cycle
    scheduler_agent.run_cycle()

    # Should reset to first period
    assert scheduler_agent.current_period_index == 0
    # After reset, the backtest count should be 1 because we just executed one backtest in the new period
    assert scheduler_agent.backtest_count_in_period == 1
    assert scheduler_agent.passed_backtests_in_period == 0


@patch("trading.agents.scheduler_agent.create_strategy_factory")
@patch("trading.agents.scheduler_agent.datetime")
def test_period_failure_reset(mock_datetime, mock_factory, scheduler_agent):
    """Test reset when period fails (not enough passed backtests)"""
    from decimal import Decimal

    from trading.domain.messages import BacktestResultsResponse, EvaluationResponse

    # Setup mocks
    mock_datetime.now.return_value = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    mock_factory.return_value = lambda: None

    # Configure for incremental periods
    scheduler_agent.config.incremental_periods = [1, 7, 30, 90]
    scheduler_agent.config.backtests_per_period = 2
    scheduler_agent.config.min_passed_backtests_per_period = 2

    # Mock orchestrator responses (failing)
    mock_backtest = BacktestResultsResponse(
        run_id="test_run",
        status="completed",
        start_time=1000000,
        end_time=2000000,
        duration_seconds=100.0,
        total_candles_processed=1000,
        final_balance=Decimal("2600"),
        total_return=Decimal("100"),
        return_percentage=4.0,
        max_drawdown=5.0,
        total_trades=50,
        win_rate=60.0,
        profit_factor=1.5,
        total_closed_positions=10,
        winning_positions=6,
        losing_positions=4,
        total_commission=Decimal("10"),
        commission_percentage=10.0,
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
    )

    mock_evaluation = EvaluationResponse(
        run_id="test_run",
        evaluation_passed=False,
        metrics={"sharpe_ratio": 1.0, "max_drawdown": 15.0, "profit_factor": 1.2},
        kpi_compliance={"sharpe_ratio": False, "max_drawdown": False, "profit_factor": False},
        recommendation="reject",
    )

    scheduler_agent.orchestrator.run_backtest.return_value = mock_backtest
    scheduler_agent.orchestrator.evaluate_backtest.return_value = mock_evaluation

    # Set to period 1
    scheduler_agent.current_period_index = 1

    # Run 2 cycles (both failing)
    scheduler_agent.run_cycle()
    scheduler_agent.run_cycle()

    # Should reset to first period (only 0 passed, need 2)
    assert scheduler_agent.current_period_index == 0
    assert scheduler_agent.backtest_count_in_period == 0
    assert scheduler_agent.passed_backtests_in_period == 0


@patch("trading.agents.scheduler_agent.create_strategy_factory")
@patch("trading.agents.scheduler_agent.datetime")
def test_promote_to_production(mock_datetime, mock_factory, scheduler_agent):
    """Test promotion to production after completing all periods"""
    from decimal import Decimal

    from trading.domain.messages import BacktestResultsResponse, EvaluationResponse

    # Setup mocks
    mock_datetime.now.return_value = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    mock_factory.return_value = lambda: None

    # Configure for incremental periods
    scheduler_agent.config.incremental_periods = [1, 7]  # Short for testing
    scheduler_agent.config.backtests_per_period = 2
    scheduler_agent.config.min_passed_backtests_per_period = 2

    # Mock orchestrator responses (all passing)
    mock_backtest = BacktestResultsResponse(
        run_id="test_run",
        status="completed",
        start_time=1000000,
        end_time=2000000,
        duration_seconds=100.0,
        total_candles_processed=1000,
        final_balance=Decimal("2600"),
        total_return=Decimal("100"),
        return_percentage=4.0,
        max_drawdown=5.0,
        total_trades=50,
        win_rate=60.0,
        profit_factor=1.5,
        total_closed_positions=10,
        winning_positions=6,
        losing_positions=4,
        total_commission=Decimal("10"),
        commission_percentage=10.0,
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
    )

    mock_evaluation = EvaluationResponse(
        run_id="test_run",
        evaluation_passed=True,
        metrics={"sharpe_ratio": 2.5, "max_drawdown": 5.0, "profit_factor": 1.5},
        kpi_compliance={"sharpe_ratio": True, "max_drawdown": True, "profit_factor": True},
        recommendation="promote",
    )

    scheduler_agent.orchestrator.run_backtest.return_value = mock_backtest
    scheduler_agent.orchestrator.evaluate_backtest.return_value = mock_evaluation

    # Set to last period (index 1 = 7 days) and mark as running
    scheduler_agent.current_period_index = 1
    scheduler_agent.running = True

    # Run 2 cycles to complete last period
    scheduler_agent.run_cycle()
    scheduler_agent.run_cycle()

    # Should stop scheduler (promote to production)
    assert scheduler_agent.running is False

