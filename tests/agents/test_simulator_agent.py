"""Tests for SimulatorAgent"""

from unittest.mock import MagicMock, patch

import pytest

from trading.agents.simulator_agent import SimulatorAgent
from trading.domain.messages import AgentMessage, ErrorResponse


@pytest.fixture
def simulator_agent():
    """Create a SimulatorAgent instance"""
    return SimulatorAgent(run_id="test_simulator_run")


def test_simulator_agent_initialization(simulator_agent):
    """Test SimulatorAgent initialization"""
    assert simulator_agent.agent_name == "simulator"
    assert simulator_agent.run_id == "test_simulator_run"
    assert simulator_agent.simulator is None


def test_simulator_agent_policies(simulator_agent):
    """Test SimulatorAgent policies are configured correctly"""
    assert "max_symbols" in simulator_agent.policies
    assert "min_time_range" in simulator_agent.policies
    assert simulator_agent.policies["max_symbols"]["max"] == 10
    assert simulator_agent.policies["min_time_range"]["min"] == 60000


@patch("trading.agents.simulator_agent.MarketDataSimulator")
def test_initialize(mock_simulator_class, simulator_agent):
    """Test initialize() creates MarketDataSimulator"""
    mock_simulator = MagicMock()
    mock_simulator_class.return_value = mock_simulator

    result = simulator_agent.initialize(is_backtest=True)

    assert result == simulator_agent
    assert simulator_agent.simulator == mock_simulator
    mock_simulator_class.assert_called_once_with(is_backtest=True)
    assert simulator_agent.get_memory("initialized") is True


@patch("trading.agents.simulator_agent.MarketDataSimulator")
def test_initialize_with_is_backtest_false(mock_simulator_class, simulator_agent):
    """Test initialize() with is_backtest=False"""
    mock_simulator = MagicMock()
    mock_simulator_class.return_value = mock_simulator

    simulator_agent.initialize(is_backtest=False)

    mock_simulator_class.assert_called_once_with(is_backtest=False)


def test_set_times_not_initialized(simulator_agent):
    """Test set_times() raises error if simulator not initialized"""
    with pytest.raises(ValueError, match="Simulator not initialized"):
        simulator_agent.set_times(start_time=1000, end_time=2000)


@patch("trading.agents.simulator_agent.MarketDataSimulator")
def test_set_times_success(mock_simulator_class, simulator_agent):
    """Test set_times() successfully sets times"""
    mock_simulator = MagicMock()
    mock_simulator_class.return_value = mock_simulator
    simulator_agent.initialize()

    # Use a time range that meets the minimum (60000ms = 1 minute)
    start_time = 1000
    end_time = 1000 + 60000  # 60 seconds = 60000ms
    simulator_agent.set_times(start_time=start_time, end_time=end_time, min_candles=20)

    mock_simulator.set_times.assert_called_once_with(start=start_time, end=end_time, min_candles=20)
    assert simulator_agent.get_memory("start_time") == start_time
    assert simulator_agent.get_memory("end_time") == end_time


@patch("trading.agents.simulator_agent.MarketDataSimulator")
def test_set_times_without_end_time(mock_simulator_class, simulator_agent):
    """Test set_times() with end_time=None"""
    mock_simulator = MagicMock()
    mock_simulator_class.return_value = mock_simulator
    simulator_agent.initialize()

    simulator_agent.set_times(start_time=1000, end_time=None)

    mock_simulator.set_times.assert_called_once_with(start=1000, end=None, min_candles=10)
    assert simulator_agent.get_memory("end_time") is None


@patch("trading.agents.simulator_agent.MarketDataSimulator")
def test_set_times_policy_validation_failure(mock_simulator_class, simulator_agent):
    """Test set_times() fails when time range is too small"""
    mock_simulator = MagicMock()
    mock_simulator_class.return_value = mock_simulator
    simulator_agent.initialize()

    # Time range is 50000ms (50s) which is less than min_time_range (60000ms)
    with pytest.raises(ValueError, match="Time range too small"):
        simulator_agent.set_times(start_time=1000, end_time=51000)


def test_add_symbol_not_initialized(simulator_agent):
    """Test add_symbol() raises error if simulator not initialized"""
    with pytest.raises(ValueError, match="Simulator not initialized"):
        simulator_agent.add_symbol("BTCUSDT")


@patch("trading.agents.simulator_agent.MarketDataSimulator")
def test_add_symbol_success(mock_simulator_class, simulator_agent):
    """Test add_symbol() successfully adds symbol"""
    mock_simulator = MagicMock()
    mock_simulator.symbols_timeframes = {}
    mock_simulator_class.return_value = mock_simulator
    simulator_agent.initialize()

    simulator_agent.add_symbol("BTCUSDT", timeframes=["1m", "15m"])

    assert mock_simulator.symbols_timeframes["BTCUSDT"] == ["1m", "15m"]


@patch("trading.agents.simulator_agent.MarketDataSimulator")
def test_add_symbol_with_default_timeframes(mock_simulator_class, simulator_agent):
    """Test add_symbol() uses default timeframes if not provided"""
    mock_simulator = MagicMock()
    mock_simulator.symbols_timeframes = {}
    mock_simulator_class.return_value = mock_simulator
    simulator_agent.initialize()

    simulator_agent.add_symbol("BTCUSDT")

    assert mock_simulator.symbols_timeframes["BTCUSDT"] == ["1m", "15m", "1h"]


@patch("trading.agents.simulator_agent.MarketDataSimulator")
def test_add_symbol_policy_validation_failure(mock_simulator_class, simulator_agent):
    """Test add_symbol() fails when max_symbols limit reached"""
    mock_simulator = MagicMock()
    mock_simulator.symbols_timeframes = {f"SYMBOL{i}": [] for i in range(10)}  # Already 10 symbols
    mock_simulator_class.return_value = mock_simulator
    simulator_agent.initialize()

    with pytest.raises(ValueError, match="Max symbols limit reached"):
        simulator_agent.add_symbol("BTCUSDT")


def test_handle_message_initialize_action(simulator_agent):
    """Test handle_message with initialize action"""
    with patch.object(simulator_agent, "initialize") as mock_initialize:
        # Create a message and manually set payload as dict
        # The simulator_agent handler checks isinstance(payload, dict) for backwards compatibility
        message = MagicMock(spec=AgentMessage)
        message.payload = {"action": "initialize", "is_backtest": True}
        message.from_agent = "orchestrator"
        message.flow_id = "init_flow"
        
        # Mock create_message to return a proper response
        with patch.object(simulator_agent, "create_message") as mock_create_message:
            mock_response = MagicMock(spec=AgentMessage)
            mock_response.to_agent = "orchestrator"
            mock_response.flow_id = "init_flow"
            mock_response.payload = {"status": "initialized", "run_id": simulator_agent.run_id}
            mock_create_message.return_value = mock_response

            response = simulator_agent.handle_message(message)

            assert isinstance(response, AgentMessage) or hasattr(response, "to_agent")
            assert response.to_agent == "orchestrator"
            assert response.flow_id == "init_flow"
            assert response.payload["status"] == "initialized"
            mock_initialize.assert_called_once_with(True)


def test_handle_message_set_times_action(simulator_agent):
    """Test handle_message with set_times action"""
    with patch.object(simulator_agent, "set_times") as mock_set_times:
        start_time = 1000
        end_time = 1000 + 60000  # Meet minimum time range
        message = MagicMock(spec=AgentMessage)
        message.payload = {"action": "set_times", "start_time": start_time, "end_time": end_time, "min_candles": 20}
        message.from_agent = "orchestrator"
        message.flow_id = "config_flow"
        
        with patch.object(simulator_agent, "create_message") as mock_create_message:
            mock_response = MagicMock(spec=AgentMessage)
            mock_response.to_agent = "orchestrator"
            mock_response.flow_id = "config_flow"
            mock_response.payload = {"status": "configured"}
            mock_create_message.return_value = mock_response

            response = simulator_agent.handle_message(message)

            assert hasattr(response, "to_agent")
            assert response.payload["status"] == "configured"
            mock_set_times.assert_called_once_with(start_time=start_time, end_time=end_time, min_candles=20)


def test_handle_message_next_candle_action(simulator_agent):
    """Test handle_message with next_candle action"""
    mock_simulator = MagicMock()
    simulator_agent.simulator = mock_simulator

    message = MagicMock(spec=AgentMessage)
    message.payload = {"action": "next_candle"}
    message.from_agent = "orchestrator"
    message.flow_id = "process_flow"
    
    with patch.object(simulator_agent, "create_message") as mock_create_message:
        mock_response = MagicMock(spec=AgentMessage)
        mock_response.payload = {"status": "candle_processed"}
        mock_create_message.return_value = mock_response

        response = simulator_agent.handle_message(message)

        assert response.payload["status"] == "candle_processed"
        mock_simulator.next_candle.assert_called_once()


def test_handle_message_next_candle_without_simulator(simulator_agent):
    """Test handle_message with next_candle action when simulator is None"""
    simulator_agent.simulator = None

    message = MagicMock(spec=AgentMessage)
    message.payload = {"action": "next_candle"}
    message.from_agent = "orchestrator"
    message.flow_id = "process_flow"
    
    with patch.object(simulator_agent, "create_message") as mock_create_message:
        mock_response = MagicMock(spec=AgentMessage)
        mock_response.payload = {"status": "candle_processed"}
        mock_create_message.return_value = mock_response

        response = simulator_agent.handle_message(message)

        # Should not raise error, just return status
        assert response.payload["status"] == "candle_processed"


def test_handle_message_unknown_payload(simulator_agent):
    """Test handle_message with unknown payload"""
    message = AgentMessage(
        message_id="msg_123",
        from_agent="orchestrator",
        to_agent="simulator",
        flow_id="test_flow",
        payload={"unknown": "payload"},
    )

    response = simulator_agent.handle_message(message)

    assert isinstance(response, AgentMessage)
    assert isinstance(response.payload, ErrorResponse)
    assert response.payload.error_code == "UNKNOWN_MESSAGE_TYPE"


def test_handle_message_with_exception(simulator_agent):
    """Test handle_message error handling"""
    # Initialize simulator first
    with patch("trading.agents.simulator_agent.MarketDataSimulator") as mock_sim_class:
        mock_sim = MagicMock()
        mock_sim_class.return_value = mock_sim
        simulator_agent.initialize()

    with patch.object(simulator_agent, "set_times") as mock_set_times:
        mock_set_times.side_effect = Exception("Test error")

        start_time = 1000
        end_time = 1000 + 60000
        message = MagicMock(spec=AgentMessage)
        message.payload = {"action": "set_times", "start_time": start_time, "end_time": end_time}
        message.from_agent = "orchestrator"
        message.flow_id = "test_flow"
        
        with patch.object(simulator_agent, "create_message") as mock_create_message:
            from trading.domain.messages import ErrorResponse
            error_response = ErrorResponse(
                error_code="HANDLER_ERROR",
                error_message="Test error",
                run_id=simulator_agent.run_id,
            )
            mock_response = MagicMock(spec=AgentMessage)
            mock_response.payload = error_response
            mock_create_message.return_value = mock_response

            response = simulator_agent.handle_message(message)

            assert hasattr(response, "payload")
            assert isinstance(response.payload, ErrorResponse)
            assert response.payload.error_code == "HANDLER_ERROR"


def test_close_cleanup_resources(simulator_agent):
    """Test close() cleans up resources"""
    mock_simulator = MagicMock()
    simulator_agent.simulator = mock_simulator

    simulator_agent.close()

    mock_simulator.close.assert_called_once()
    assert simulator_agent.simulator is None


def test_close_handles_none_simulator(simulator_agent):
    """Test close() handles None simulator gracefully"""
    simulator_agent.simulator = None

    # Should not raise exception
    simulator_agent.close()

    assert simulator_agent.simulator is None

