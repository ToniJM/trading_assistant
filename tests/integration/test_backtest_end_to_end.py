"""End-to-end integration tests for backtest workflow"""
from decimal import Decimal

import pytest

from trading.agents import OrchestratorAgent
from trading.domain.messages import StartBacktestRequest
from trading.strategies.factory import create_strategy_factory


@pytest.mark.skip(reason="Requires market data in database or API access. Enable when ready to test full workflow.")
def test_backtest_end_to_end_with_orchestrator():
    """Test complete backtest workflow: Orchestrator → Backtest → Strategy"""
    # Create orchestrator
    orchestrator = OrchestratorAgent(run_id="test_e2e_run")
    orchestrator.initialize()

    # Create backtest request (short time window for testing)
    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000,  # Fixed timestamp
        end_time=1744023500000 + (60 * 60 * 1000),  # +1 hour
        initial_balance=Decimal("2500"),
        leverage=Decimal("100"),
        strategy_name="carga_descarga",
        max_loss_percentage=0.5,
    )

    # Create strategy factory
    strategy_factory = create_strategy_factory(strategy_name="carga_descarga")

    try:
        # Execute backtest
        results = orchestrator.run_backtest(request, strategy_factory=strategy_factory)

        # Verify results
        assert results.status == "completed"
        assert results.total_candles_processed > 0
        assert results.duration_seconds > 0
        assert results.final_balance >= 0
        assert results.total_trades >= 0

    finally:
        orchestrator.close()


def test_strategy_factory_creation():
    """Test that strategy factory can be created"""
    factory = create_strategy_factory(strategy_name="carga_descarga")
    assert callable(factory)


def test_orchestrator_with_strategy_factory():
    """Test that orchestrator can be initialized with strategy factory"""
    orchestrator = OrchestratorAgent(run_id="test_factory_run")
    orchestrator.initialize()

    assert orchestrator.backtest_agent is not None
    assert orchestrator.simulator_agent is not None

    # Verify we can create a strategy factory
    factory = create_strategy_factory(strategy_name="carga_descarga")
    assert callable(factory)

    orchestrator.close()


def test_start_backtest_request_creation():
    """Test that StartBacktestRequest can be created with valid data"""
    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (60 * 60 * 1000),
        initial_balance=Decimal("2500"),
        leverage=Decimal("100"),
        strategy_name="carga_descarga",
    )

    assert request.symbol == "BTCUSDT"
    assert request.start_time == 1744023500000
    assert request.initial_balance == Decimal("2500")
    assert request.strategy_name == "carga_descarga"
    assert request.run_id is not None

