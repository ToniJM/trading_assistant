"""Tests for BaseAgent"""

from unittest.mock import MagicMock, patch

import pytest

from trading.agents.base_agent import BaseAgent
from trading.domain.messages import AgentMessage, ErrorResponse


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing"""

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle message - required by abstract method"""
        return self.create_message(to_agent=message.from_agent, flow_id=message.flow_id, payload={"status": "ok"})


@pytest.fixture
def concrete_agent():
    """Create a ConcreteAgent instance"""
    return ConcreteAgent(agent_name="test_agent", run_id="test_run_123")


def test_base_agent_initialization(concrete_agent):
    """Test BaseAgent initialization"""
    assert concrete_agent.agent_name == "test_agent"
    assert concrete_agent.run_id == "test_run_123"
    assert isinstance(concrete_agent.episodic_memory, dict)
    assert isinstance(concrete_agent.policies, dict)


def test_base_agent_initialization_without_run_id():
    """Test BaseAgent generates run_id if not provided"""
    agent = ConcreteAgent(agent_name="test_agent")
    assert agent.run_id is not None
    assert len(agent.run_id) > 0


def test_set_context(concrete_agent):
    """Test set_context updates run_id and logging context"""
    concrete_agent.set_context(run_id="new_run_456", flow_id="test_flow")

    assert concrete_agent.run_id == "new_run_456"


def test_store_memory(concrete_agent):
    """Test store_memory stores values"""
    concrete_agent.store_memory("key1", "value1")
    concrete_agent.store_memory("key2", {"nested": "data"})

    assert concrete_agent.episodic_memory["key1"] == "value1"
    assert concrete_agent.episodic_memory["key2"] == {"nested": "data"}


def test_get_memory(concrete_agent):
    """Test get_memory retrieves values"""
    concrete_agent.store_memory("key1", "value1")

    assert concrete_agent.get_memory("key1") == "value1"
    assert concrete_agent.get_memory("nonexistent") is None
    assert concrete_agent.get_memory("nonexistent", default="default_value") == "default_value"


def test_create_message(concrete_agent):
    """Test create_message creates AgentMessage with correct context"""
    payload = {"test": "data"}
    message = concrete_agent.create_message(to_agent="target_agent", flow_id="test_flow", payload=payload)

    assert isinstance(message, AgentMessage)
    assert message.from_agent == "test_agent"
    assert message.to_agent == "target_agent"
    assert message.flow_id == "test_flow"
    # Payload is stored as-is, so we can access it directly
    assert hasattr(message, "payload")
    assert message.message_id is not None


def test_create_message_with_custom_message_id(concrete_agent):
    """Test create_message with custom message_id"""
    message = concrete_agent.create_message(
        to_agent="target_agent", flow_id="test_flow", payload={}, message_id="custom_id_123"
    )

    assert message.message_id == "custom_id_123"


def test_create_error_response(concrete_agent):
    """Test create_error_response creates ErrorResponse"""
    error = concrete_agent.create_error_response(
        error_code="TEST_ERROR", error_message="Test error message", details={"key": "value"}
    )

    assert isinstance(error, ErrorResponse)
    assert error.error_code == "TEST_ERROR"
    assert error.error_message == "Test error message"
    assert error.error_details == {"key": "value"}
    assert error.run_id == "test_run_123"


def test_create_error_response_without_details(concrete_agent):
    """Test create_error_response without details"""
    error = concrete_agent.create_error_response(error_code="TEST_ERROR", error_message="Test error")

    assert error.error_details is None


def test_validate_policy_with_dict_policy_min(concrete_agent):
    """Test validate_policy with dict policy (min constraint)"""
    concrete_agent.policies = {"test_policy": {"min": 10}}

    assert concrete_agent.validate_policy("test_policy", 15) is True
    assert concrete_agent.validate_policy("test_policy", 5) is False
    assert concrete_agent.validate_policy("test_policy", 10) is True  # Boundary


def test_validate_policy_with_dict_policy_max(concrete_agent):
    """Test validate_policy with dict policy (max constraint)"""
    concrete_agent.policies = {"test_policy": {"max": 100}}

    assert concrete_agent.validate_policy("test_policy", 50) is True
    assert concrete_agent.validate_policy("test_policy", 150) is False
    assert concrete_agent.validate_policy("test_policy", 100) is True  # Boundary


def test_validate_policy_with_dict_policy_min_max(concrete_agent):
    """Test validate_policy with dict policy (min and max constraints)"""
    concrete_agent.policies = {"test_policy": {"min": 10, "max": 100}}

    assert concrete_agent.validate_policy("test_policy", 50) is True
    assert concrete_agent.validate_policy("test_policy", 5) is False
    assert concrete_agent.validate_policy("test_policy", 150) is False
    assert concrete_agent.validate_policy("test_policy", 10) is True  # Min boundary
    assert concrete_agent.validate_policy("test_policy", 100) is True  # Max boundary


def test_validate_policy_with_callable(concrete_agent):
    """Test validate_policy with callable policy"""
    def custom_policy(value):
        return value % 2 == 0  # Only even numbers

    concrete_agent.policies = {"test_policy": custom_policy}

    assert concrete_agent.validate_policy("test_policy", 2) is True
    assert concrete_agent.validate_policy("test_policy", 3) is False


def test_validate_policy_nonexistent_policy(concrete_agent):
    """Test validate_policy returns True for nonexistent policy"""
    # No policy defined
    assert concrete_agent.validate_policy("nonexistent_policy", 999) is True


@patch("trading.agents.base_agent.logging_context")
def test_log_event(mock_logging_context, concrete_agent):
    """Test log_event logs structured event"""
    event_data = {"flow_id": "test_flow", "message": "Test event", "key": "value"}

    concrete_agent.log_event("test_event_type", event_data)

    # Verify logging_context was used
    mock_logging_context.assert_called_once_with(
        run_id="test_run_123", agent="test_agent", flow="test_flow"
    )


def test_handle_message_abstract_method():
    """Test that handle_message is abstract and must be implemented"""
    # Cannot instantiate BaseAgent directly
    with pytest.raises(TypeError):
        BaseAgent(agent_name="test")  # Will fail because handle_message is abstract


def test_handle_message_concrete_implementation(concrete_agent):
    """Test that concrete implementation can handle messages"""
    message = AgentMessage(
        message_id="msg_123",
        from_agent="sender",
        to_agent="test_agent",
        flow_id="test_flow",
        payload={"test": "data"},
    )

    response = concrete_agent.handle_message(message)

    assert isinstance(response, AgentMessage)
    assert response.to_agent == "sender"
    assert response.flow_id == "test_flow"


def test_repr(concrete_agent):
    """Test __repr__ method"""
    repr_str = repr(concrete_agent)

    assert "ConcreteAgent" in repr_str
    assert "test_agent" in repr_str
    assert "test_run_123"[:8] in repr_str  # First 8 chars of run_id

