"""Integration tests for agent workflows"""

import pytest

from trading.agents import BacktestAgent, OrchestratorAgent, SimulatorAgent
from trading.domain.messages import AgentMessage, StartBacktestRequest


def test_simulator_agent_initialization():
    """Test SimulatorAgent initialization"""
    agent = SimulatorAgent(run_id="test_run_123")
    agent.initialize(is_backtest=True)

    assert agent.simulator is not None
    assert agent.get_memory("initialized") is True


def test_backtest_agent_initialization():
    """Test BacktestAgent initialization"""
    agent = BacktestAgent(run_id="test_run_123")
    agent.initialize()

    assert agent.get_memory("initialized") is True


def test_orchestrator_agent_initialization():
    """Test OrchestratorAgent initialization"""
    orchestrator = OrchestratorAgent(run_id="test_run_123")
    orchestrator.initialize()

    assert orchestrator.simulator_agent is not None
    assert orchestrator.backtest_agent is not None
    assert orchestrator.get_memory("initialized") is True


def test_agent_messaging():
    """Test A2A messaging between agents"""
    simulator = SimulatorAgent(run_id="test_run_123")
    simulator.initialize(is_backtest=True)

    # Create message
    request_payload = {
        "action": "set_times",
        "start_time": 1744023500000,
        "end_time": 1744023500000 + (24 * 60 * 60 * 1000),
        "min_candles": 10,
    }

    message = simulator.create_message(
        to_agent="simulator",
        flow_id="test_flow",
        payload=request_payload,
    )

    assert message.from_agent == "simulator"
    assert message.to_agent == "simulator"
    assert message.flow_id == "test_flow"


def test_orchestrator_agent_message_handling():
    """Test OrchestratorAgent message handling"""
    orchestrator = OrchestratorAgent(run_id="test_run_123")
    orchestrator.initialize()

    # Create backtest request
    request = StartBacktestRequest(
        symbol="BTCUSDT",
        start_time=1744023500000,
        end_time=1744023500000 + (60 * 60 * 1000),  # 1 hour
        strategy_name="test_strategy",
    )

    message = orchestrator.create_message(
        to_agent="orchestrator",
        flow_id="test_flow",
        payload=request,
    )

    # Note: This would require actual strategy factory to fully test
    # For now, just verify message creation
    assert isinstance(message, AgentMessage)
    assert isinstance(message.payload, StartBacktestRequest)


def test_agent_context_management():
    """Test agent context management"""
    agent = SimulatorAgent(run_id="test_run_123")
    agent.set_context(run_id="new_run_456", flow_id="flow_test")

    assert agent.run_id == "new_run_456"


def test_agent_memory_storage():
    """Test agent episodic memory"""
    agent = SimulatorAgent(run_id="test_run_123")
    agent.store_memory("test_key", "test_value")

    assert agent.get_memory("test_key") == "test_value"
    assert agent.get_memory("nonexistent", "default") == "default"


def test_agent_policy_validation():
    """Test agent policy validation"""
    agent = SimulatorAgent(run_id="test_run_123")

    # Test valid value
    assert agent.validate_policy("max_symbols", 5) is True

    # Test invalid value (exceeds max)
    assert agent.validate_policy("max_symbols", 15) is False


def test_agent_error_response():
    """Test agent error response creation"""
    agent = SimulatorAgent(run_id="test_run_123")

    error = agent.create_error_response(
        error_code="TEST_ERROR",
        error_message="Test error message",
        details={"detail": "value"},
    )

    assert error.error_code == "TEST_ERROR"
    assert error.error_message == "Test error message"
    assert error.run_id == "test_run_123"


@pytest.mark.skip(reason="Requires full strategy implementation and market data")
def test_full_backtest_workflow():
    """Test complete backtest workflow through agents"""
    # This test would require:
    # - Full strategy implementation
    # - Market data setup
    # - Complete backtest execution
    # TODO: Implement when strategy is available

    orchestrator = OrchestratorAgent(run_id="integration_test")
    orchestrator.initialize()

    # This would execute the full backtest
    # request = StartBacktestRequest(
    #     symbol="BTCUSDT",
    #     start_time=1744023500000,
    #     end_time=1744023500000 + (60 * 60 * 1000),
    #     strategy_name="test_strategy",
    # )
    # response = orchestrator.run_backtest(request)
    # assert isinstance(response, BacktestResultsResponse)

