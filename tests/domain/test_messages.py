"""Tests for A2A message contracts"""
from decimal import Decimal

from trading.domain.messages import (
    AgentMessage,
    BacktestResultsResponse,
    BacktestStatusUpdate,
    ErrorResponse,
    EvaluationRequest,
    EvaluationResponse,
    OptimizationRequest,
    StartBacktestRequest,
)


def test_start_backtest_request():
    """Test StartBacktestRequest creation"""
    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744109900000,
    )

    assert request.symbol == "BTCUSDT"
    assert request.start_time == 1744023500000
    assert request.end_time == 1744109900000
    assert request.initial_balance == Decimal("2500")  # Default
    assert request.leverage == Decimal("100")  # Default
    assert request.run_id is not None


def test_start_backtest_request_defaults():
    """Test StartBacktestRequest default values"""
    request = StartBacktestRequest(
        symbol="ETHUSDT",
        start_time=1744023500000,
    )

    assert request.end_time is None
    assert request.stop_on_loss is True
    assert request.max_loss_percentage == 0.5
    assert request.track_cycles is True


def test_backtest_status_update():
    """Test BacktestStatusUpdate creation"""
    update = BacktestStatusUpdate(
        run_id="test_run_123",
        status="running",
        candles_processed=1000,
        current_balance=Decimal("2600"),
        execution_time_seconds=5.5,
        candles_per_second=181.8,
    )

    assert update.run_id == "test_run_123"
    assert update.status == "running"
    assert update.candles_processed == 1000
    assert update.current_balance == Decimal("2600")


def test_backtest_results_response():
    """Test BacktestResultsResponse creation"""
    results = BacktestResultsResponse(
        run_id="test_run_123",
        status="completed",
        start_time=1744023500000,
        end_time=1744109900000,
        duration_seconds=86400.0,
        total_candles_processed=1000,
        final_balance=Decimal("2600"),
        total_return=Decimal("100"),
        return_percentage=4.0,
        max_drawdown=2.0,
        total_trades=100,
        win_rate=65.0,
        profit_factor=1.5,
        total_closed_positions=50,
        winning_positions=35,
        losing_positions=15,
        total_commission=Decimal("10"),
        commission_percentage=10.0,
        strategy_name="test_strategy",
        symbol="BTCUSDT",
    )

    assert results.run_id == "test_run_123"
    assert results.status == "completed"
    assert results.total_return == Decimal("100")
    assert results.win_rate == 65.0
    assert results.strategy_name == "test_strategy"


def test_optimization_request():
    """Test OptimizationRequest creation"""
    request = OptimizationRequest(
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
        parameter_space={
            "entry_threshold": [0.01, 0.02, 0.03],
            "exit_threshold": [0.005, 0.01],
        },
        objective="sharpe_ratio",
    )

    assert request.strategy_name == "carga_descarga"
    assert request.objective == "sharpe_ratio"
    assert len(request.parameter_space["entry_threshold"]) == 3


def test_evaluation_request():
    """Test EvaluationRequest creation"""
    request = EvaluationRequest(
        run_id="test_run_123",
        metrics=["sharpe_ratio", "max_drawdown"],
        kpis={"sharpe_ratio": 2.0, "max_drawdown": 0.1},
    )

    assert request.run_id == "test_run_123"
    assert len(request.metrics) == 2
    assert request.kpis["sharpe_ratio"] == 2.0


def test_evaluation_response():
    """Test EvaluationResponse creation"""
    response = EvaluationResponse(
        run_id="test_run_123",
        evaluation_passed=True,
        metrics={"sharpe_ratio": 2.1, "max_drawdown": 0.08},
        kpi_compliance={"sharpe_ratio": True, "max_drawdown": True},
        recommendation="promote",
    )

    assert response.evaluation_passed is True
    assert response.recommendation == "promote"
    assert response.kpi_compliance["sharpe_ratio"] is True


def test_agent_message():
    """Test AgentMessage wrapper"""
    request = StartBacktestRequest(symbol="BTCUSDT", start_time=1744023500000)
    message = AgentMessage(
        from_agent="orchestrator",
        to_agent="backtest",
        flow_id="flow_123",
        payload=request,
    )

    assert message.from_agent == "orchestrator"
    assert message.to_agent == "backtest"
    assert message.flow_id == "flow_123"
    assert isinstance(message.payload, StartBacktestRequest)


def test_error_response():
    """Test ErrorResponse creation"""
    error = ErrorResponse(
        error_code="INSUFFICIENT_BALANCE",
        error_message="Insufficient balance to execute order",
        run_id="test_run_123",
    )

    assert error.error_code == "INSUFFICIENT_BALANCE"
    assert error.error_message is not None
    assert error.run_id == "test_run_123"


def test_message_json_serialization():
    """Test that messages can be serialized to JSON"""
    request = StartBacktestRequest(symbol="BTCUSDT", start_time=1744023500000)
    json_str = request.model_dump_json()

    assert json_str is not None
    assert "BTCUSDT" in json_str
    assert "2500" in json_str  # Default balance


def test_start_backtest_request_timeframes_default():
    """Test StartBacktestRequest has default timeframes"""
    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000
    )
    assert request.timeframes == ["1m", "15m", "1h"]


def test_start_backtest_request_timeframes_custom():
    """Test StartBacktestRequest accepts custom timeframes"""
    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000,
        timeframes=["3m", "15m", "1h"]
    )
    assert request.timeframes == ["3m", "15m", "1h"]

    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000,
        timeframes=["1m", "15m"]
    )
    assert request.timeframes == ["1m", "15m"]


def test_start_backtest_request_rsi_limits_default():
    """Test StartBacktestRequest has None as default rsi_limits"""
    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000
    )
    assert request.rsi_limits is None


def test_start_backtest_request_rsi_limits_custom():
    """Test StartBacktestRequest accepts custom rsi_limits"""
    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000,
        rsi_limits=[10, 50, 90]
    )
    assert request.rsi_limits == [10, 50, 90]


def test_start_backtest_request_rsi_limits_validation_length():
    """Test StartBacktestRequest validates rsi_limits has exactly 3 values"""
    import pytest
    from pydantic import ValidationError

    # Test with 2 values - should fail
    with pytest.raises(ValidationError) as exc_info:
        StartBacktestRequest(
            symbol="BTCUSDT",
            start_time=1744023500000,
            rsi_limits=[10, 50]
        )
    assert "exactly 3 values" in str(exc_info.value).lower() or "rsi_limits" in str(exc_info.value).lower()

    # Test with 4 values - should fail
    with pytest.raises(ValidationError) as exc_info:
        StartBacktestRequest(
            symbol="BTCUSDT",
            start_time=1744023500000,
            rsi_limits=[10, 50, 90, 95]
        )
    assert "exactly 3 values" in str(exc_info.value).lower() or "rsi_limits" in str(exc_info.value).lower()


def test_start_backtest_request_rsi_limits_validation_range():
    """Test StartBacktestRequest validates rsi_limits values are in range 0-100"""
    import pytest
    from pydantic import ValidationError

    # Test with value < 0 - should fail
    with pytest.raises(ValidationError) as exc_info:
        StartBacktestRequest(
            symbol="BTCUSDT",
            start_time=1744023500000,
            rsi_limits=[-10, 50, 90]
        )
    assert "range 0-100" in str(exc_info.value).lower() or "rsi_limits" in str(exc_info.value).lower()

    # Test with value > 100 - should fail
    with pytest.raises(ValidationError) as exc_info:
        StartBacktestRequest(
            symbol="BTCUSDT",
            start_time=1744023500000,
            rsi_limits=[10, 50, 110]
        )
    assert "range 0-100" in str(exc_info.value).lower() or "rsi_limits" in str(exc_info.value).lower()

