"""Tests for BacktestAgent"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from trading.agents.backtest_agent import BacktestAgent
from trading.domain.messages import AgentMessage, BacktestResultsResponse, ErrorResponse, StartBacktestRequest
from trading.infrastructure.backtest.config import BacktestResults


@pytest.fixture
def backtest_agent():
    """Create a BacktestAgent instance"""
    return BacktestAgent(run_id="test_backtest_run").initialize()


@pytest.fixture
def sample_start_backtest_request():
    """Create sample StartBacktestRequest"""
    return StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (60 * 60 * 1000),  # +1 hour
        strategy_name="test_strategy",
        initial_balance=Decimal("2500"),
        leverage=Decimal("100"),
        max_loss_percentage=0.3,  # 30% max loss
    )


@pytest.fixture
def sample_backtest_results():
    """Create sample BacktestResults from runner"""
    return BacktestResults(
        start_time=1744023500000,
        end_time=1744023500000 + (60 * 60 * 1000),
        duration_seconds=3600.0,
        total_candles_processed=1000,
        final_balance=Decimal("2750"),
        total_return=Decimal("250"),
        return_percentage=10.0,
        max_drawdown=5.0,
        total_trades=50,
        win_rate=60.0,
        profit_factor=2.5,
        total_closed_positions=50,
        winning_positions=30,
        losing_positions=20,
        average_trade_size=Decimal("5"),
        total_commission=Decimal("10"),
        commission_percentage=4.0,
        total_closing_trades=50,
        partial_closing_trades=10,
        full_closing_trades=40,
        winning_closing_trades=30,
        losing_closing_trades=20,
        partial_winning_trades=5,
        partial_losing_trades=5,
        full_winning_trades=25,
        full_losing_trades=15,
        total_cycles=10,
        avg_cycle_duration=60.0,
        avg_cycle_pnl=25.0,
        winning_cycles=7,
        losing_cycles=3,
        cycle_win_rate=70.0,
        strategy_name="test_strategy",
        symbol="BTCUSDT",
    )


def test_backtest_agent_initialization(backtest_agent):
    """Test BacktestAgent initialization"""
    assert backtest_agent.agent_name == "backtest"
    assert backtest_agent.run_id == "test_backtest_run"
    assert backtest_agent.get_memory("initialized") is True
    assert backtest_agent.runner is None


def test_backtest_agent_policies(backtest_agent):
    """Test BacktestAgent policies are configured correctly"""
    assert "max_concurrent_backtests" in backtest_agent.policies
    assert "max_loss_percentage" in backtest_agent.policies
    assert backtest_agent.policies["max_concurrent_backtests"]["max"] == 1
    assert backtest_agent.policies["max_loss_percentage"]["max"] == 0.5


@patch("trading.agents.backtest_agent.BacktestRunner")
@patch("trading.agents.backtest_agent.create_strategy_factory")
def test_execute_backtest_success(
    mock_strategy_factory, mock_backtest_runner_class, backtest_agent, sample_start_backtest_request, sample_backtest_results
):
    """Test successful backtest execution"""
    # Setup mocks
    mock_runner = MagicMock()
    mock_runner.run.return_value = sample_backtest_results
    mock_backtest_runner_class.return_value = mock_runner
    mock_strategy_factory.return_value = MagicMock()

    # Execute backtest
    response = backtest_agent.execute_backtest(sample_start_backtest_request)

    # Verify response
    assert isinstance(response, BacktestResultsResponse)
    assert response.run_id == sample_start_backtest_request.run_id
    assert response.status == "completed"
    assert response.final_balance == Decimal("2750")
    assert response.total_return == Decimal("250")
    assert response.strategy_name == "test_strategy"
    assert response.symbol == "BTCUSDT"

    # Verify runner was created and configured
    mock_backtest_runner_class.assert_called_once()
    mock_runner.setup_exchange_and_strategy.assert_called_once()

    # Verify memory storage
    assert backtest_agent.get_memory(f"backtest_{sample_start_backtest_request.run_id}_config") is not None
    assert backtest_agent.get_memory(f"backtest_{sample_start_backtest_request.run_id}_results") == response


@patch("trading.agents.backtest_agent.BacktestRunner")
@patch("trading.agents.backtest_agent.create_strategy_factory")
def test_execute_backtest_with_custom_strategy_factory(
    mock_strategy_factory, mock_backtest_runner_class, backtest_agent, sample_start_backtest_request, sample_backtest_results
):
    """Test backtest execution with custom strategy factory"""
    # Setup mocks
    mock_runner = MagicMock()
    mock_runner.run.return_value = sample_backtest_results
    mock_backtest_runner_class.return_value = mock_runner
    custom_factory = MagicMock()

    # Execute with custom factory
    response = backtest_agent.execute_backtest(sample_start_backtest_request, strategy_factory=custom_factory)

    # Verify custom factory was used
    mock_strategy_factory.assert_not_called()
    mock_runner.setup_exchange_and_strategy.assert_called_once_with(strategy_factory=custom_factory)

    assert isinstance(response, BacktestResultsResponse)


def test_execute_backtest_policy_validation_failure(backtest_agent, sample_start_backtest_request):
    """Test backtest execution fails when policy validation fails"""
    # Set max_loss_percentage that exceeds policy (max is 0.5)
    sample_start_backtest_request.max_loss_percentage = 0.6  # 60% > 50% max

    with pytest.raises(ValueError, match="Max loss percentage exceeds policy"):
        backtest_agent.execute_backtest(sample_start_backtest_request)


@patch("trading.agents.backtest_agent.BacktestRunner")
@patch("trading.agents.backtest_agent.create_strategy_factory")
def test_execute_backtest_run_id_normalization(
    mock_strategy_factory, mock_backtest_runner_class, backtest_agent, sample_backtest_results
):
    """Test that run_id is normalized (removes 'backtest_' prefix)"""
    # Setup mocks
    mock_runner = MagicMock()
    mock_runner.run.return_value = sample_backtest_results
    mock_backtest_runner_class.return_value = mock_runner
    mock_strategy_factory.return_value = MagicMock()

    # Create request with 'backtest_' prefix
    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (60 * 60 * 1000),
        strategy_name="test_strategy",
        run_id="backtest_test_run_123",
    )

    response = backtest_agent.execute_backtest(request)

    # Verify BacktestConfig was created with normalized log_filename
    call_args = mock_backtest_runner_class.call_args
    config = call_args[1]["config"]
    assert config.log_filename == "backtest_test_run_123"  # Should not have duplicate prefix


@patch("trading.agents.backtest_agent.BacktestRunner")
@patch("trading.agents.backtest_agent.create_strategy_factory")
def test_execute_backtest_uses_agent_run_id(
    mock_strategy_factory, mock_backtest_runner_class, backtest_agent, sample_start_backtest_request, sample_backtest_results
):
    """Test that agent's run_id is used for logging context"""
    # Setup mocks
    mock_runner = MagicMock()
    mock_runner.run.return_value = sample_backtest_results
    mock_backtest_runner_class.return_value = mock_runner
    mock_strategy_factory.return_value = MagicMock()

    # Execute backtest
    backtest_agent.execute_backtest(sample_start_backtest_request)

    # Verify config uses agent's run_id
    call_args = mock_backtest_runner_class.call_args
    config = call_args[1]["config"]
    assert config.run_id == "test_backtest_run"  # Agent's run_id


@patch("trading.agents.backtest_agent.BacktestRunner")
@patch("trading.agents.backtest_agent.create_strategy_factory")
def test_execute_backtest_error_handling(
    mock_strategy_factory, mock_backtest_runner_class, backtest_agent, sample_start_backtest_request
):
    """Test error handling during backtest execution"""
    # Setup mocks to raise exception
    mock_runner = MagicMock()
    mock_runner.run.side_effect = Exception("Backtest failed")
    mock_backtest_runner_class.return_value = mock_runner
    mock_strategy_factory.return_value = MagicMock()

    # Execute should raise exception
    with pytest.raises(Exception, match="Backtest failed"):
        backtest_agent.execute_backtest(sample_start_backtest_request)


def test_handle_message_with_start_backtest_request(backtest_agent, sample_start_backtest_request, sample_backtest_results):
    """Test handle_message with StartBacktestRequest"""
    with patch.object(backtest_agent, "execute_backtest") as mock_execute:
        mock_execute.return_value = BacktestResultsResponse(
            run_id=sample_start_backtest_request.run_id,
            status="completed",
            start_time=1744023500000,
            end_time=1744023500000 + (60 * 60 * 1000),
            duration_seconds=3600.0,
            total_candles_processed=1000,
            final_balance=Decimal("2750"),
            total_return=Decimal("250"),
            return_percentage=10.0,
            max_drawdown=5.0,
            total_trades=50,
            win_rate=60.0,
            profit_factor=2.5,
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

        message = AgentMessage(
            message_id="msg_123",
            from_agent="orchestrator",
            to_agent="backtest",
            flow_id="backtest_flow",
            payload=sample_start_backtest_request,
        )

        response = backtest_agent.handle_message(message)

        # Verify response
        assert isinstance(response, AgentMessage)
        assert response.to_agent == "orchestrator"
        assert response.from_agent == "backtest"
        assert response.flow_id == "backtest_flow"
        assert isinstance(response.payload, BacktestResultsResponse)
        mock_execute.assert_called_once_with(sample_start_backtest_request)


def test_handle_message_with_unknown_payload(backtest_agent):
    """Test handle_message with unknown payload type"""
    message = AgentMessage(
        message_id="msg_123",
        from_agent="orchestrator",
        to_agent="backtest",
        flow_id="backtest_flow",
        payload={"unknown": "payload"},
    )

    response = backtest_agent.handle_message(message)

    # Verify error response
    assert isinstance(response, AgentMessage)
    assert isinstance(response.payload, ErrorResponse)
    assert response.payload.error_code == "UNKNOWN_MESSAGE_TYPE"


def test_handle_message_with_exception(backtest_agent, sample_start_backtest_request):
    """Test handle_message error handling"""
    with patch.object(backtest_agent, "execute_backtest") as mock_execute:
        mock_execute.side_effect = Exception("Test error")

        message = AgentMessage(
            message_id="msg_123",
            from_agent="orchestrator",
            to_agent="backtest",
            flow_id="backtest_flow",
            payload=sample_start_backtest_request,
        )

        response = backtest_agent.handle_message(message)

        # Verify error response
        assert isinstance(response, AgentMessage)
        assert isinstance(response.payload, ErrorResponse)
        assert response.payload.error_code == "HANDLER_ERROR"


def test_close_cleanup_resources(backtest_agent):
    """Test close() cleans up resources"""
    # Set runner
    backtest_agent.runner = MagicMock()

    # Close agent
    backtest_agent.close()

    # Verify runner is None
    assert backtest_agent.runner is None


def test_close_handles_none_runner(backtest_agent):
    """Test close() handles None runner gracefully"""
    backtest_agent.runner = None

    # Should not raise exception
    backtest_agent.close()

    assert backtest_agent.runner is None

