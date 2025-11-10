"""Tests for RegistryAgent"""

import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from trading.agents import RegistryAgent
from trading.domain.messages import (
    BacktestResultsResponse,
    EvaluationResponse,
    RetrieveResultsRequest,
    StoreResultsRequest,
)
from trading.infrastructure.registry.results_repository import ResultsRepository


@pytest.fixture
def temp_registry_dir():
    """Create temporary directory for registry"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def registry_agent(temp_registry_dir):
    """Create RegistryAgent with temporary directory"""
    agent = RegistryAgent(run_id=str(uuid4()), base_path=temp_registry_dir)
    agent.initialize()
    yield agent
    agent.close()


@pytest.fixture
def sample_backtest_results():
    """Sample backtest results"""
    from decimal import Decimal

    return BacktestResultsResponse(
        run_id="test_run_123",
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


@pytest.fixture
def sample_evaluation_results():
    """Sample evaluation results"""
    return EvaluationResponse(
        run_id="test_run_123",
        evaluation_passed=True,
        metrics={"sharpe_ratio": 2.5, "max_drawdown": 5.0, "profit_factor": 1.5},
        kpi_compliance={"sharpe_ratio": True, "max_drawdown": True, "profit_factor": True},
        recommendation="promote",
    )


def test_registry_agent_initialization(registry_agent):
    """Test RegistryAgent initialization"""
    assert registry_agent.agent_name == "registry"
    assert registry_agent.repository is not None
    assert registry_agent.get_memory("initialized") is True


def test_store_backtest_results(registry_agent, sample_backtest_results):
    """Test storing backtest results"""
    request = StoreResultsRequest(
        run_id="test_run_123",
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
        backtest_results=sample_backtest_results,
    )

    response = registry_agent.store_results(request)

    assert response.success is True
    assert response.run_id == "test_run_123"
    assert response.storage_id is not None


def test_store_evaluation_results(registry_agent, sample_evaluation_results):
    """Test storing evaluation results"""
    request = StoreResultsRequest(
        run_id="test_run_123",
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
        evaluation_results=sample_evaluation_results,
    )

    response = registry_agent.store_results(request)

    assert response.success is True
    assert response.run_id == "test_run_123"


def test_retrieve_by_run_id(registry_agent, sample_backtest_results, sample_evaluation_results):
    """Test retrieving results by run_id"""
    # Store both backtest and evaluation
    store_request = StoreResultsRequest(
        run_id="test_run_123",
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
        backtest_results=sample_backtest_results,
        evaluation_results=sample_evaluation_results,
    )
    registry_agent.store_results(store_request)

    # Retrieve
    retrieve_request = RetrieveResultsRequest(run_id="test_run_123")
    response = registry_agent.retrieve_results(retrieve_request)

    assert len(response.results) == 1
    assert response.total_count == 1
    assert "backtest" in response.results[0]
    assert "evaluation" in response.results[0]


def test_retrieve_by_strategy(registry_agent, sample_backtest_results):
    """Test retrieving results by strategy"""
    # Store multiple results
    for i in range(3):
        request = StoreResultsRequest(
            run_id=f"test_run_{i}",
            strategy_name="carga_descarga",
            symbol="BTCUSDT",
            backtest_results=sample_backtest_results,
        )
        registry_agent.store_results(request)

    # Retrieve
    retrieve_request = RetrieveResultsRequest(strategy_name="carga_descarga", limit=10)
    response = registry_agent.retrieve_results(retrieve_request)

    assert len(response.results) == 3
    assert response.total_count == 3


def test_get_strategy_history(registry_agent, sample_backtest_results):
    """Test getting strategy history"""
    # Store multiple results
    for i in range(5):
        request = StoreResultsRequest(
            run_id=f"test_run_{i}",
            strategy_name="carga_descarga",
            symbol="BTCUSDT",
            backtest_results=sample_backtest_results,
        )
        registry_agent.store_results(request)

    # Get history
    history = registry_agent.get_strategy_history("carga_descarga", limit=3)

    assert len(history) == 3  # Limited to 3


def test_handle_store_message(registry_agent, sample_backtest_results):
    """Test handling StoreResultsRequest message"""
    from trading.domain.messages import AgentMessage

    request = StoreResultsRequest(
        run_id="test_run_123",
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
        backtest_results=sample_backtest_results,
    )

    message = AgentMessage(
        from_agent="orchestrator",
        to_agent="registry",
        flow_id="test_flow",
        payload=request,
    )

    response_message = registry_agent.handle_message(message)

    assert response_message.payload.success is True


def test_handle_retrieve_message(registry_agent, sample_backtest_results):
    """Test handling RetrieveResultsRequest message"""
    from trading.domain.messages import AgentMessage

    # Store first
    store_request = StoreResultsRequest(
        run_id="test_run_123",
        strategy_name="carga_descarga",
        symbol="BTCUSDT",
        backtest_results=sample_backtest_results,
    )
    registry_agent.store_results(store_request)

    # Retrieve via message
    retrieve_request = RetrieveResultsRequest(run_id="test_run_123")
    message = AgentMessage(
        from_agent="orchestrator",
        to_agent="registry",
        flow_id="test_flow",
        payload=retrieve_request,
    )

    response_message = registry_agent.handle_message(message)

    assert len(response_message.payload.results) == 1

