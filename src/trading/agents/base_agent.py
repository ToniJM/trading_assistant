"""Base agent class for ADK agents"""
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from trading.domain.messages import AgentMessage, ErrorResponse
from trading.infrastructure.logging import LoggingContext, get_logger, logging_context


class BaseAgent(ABC):
    """Base class for all ADK agents

    Following ADK-first principles:
    - Role: agent responsibility
    - Tools: capabilities exposed
    - Memory: episodic and vectorial
    - Policies: validation and limits
    """

    def __init__(self, agent_name: str, run_id: str | None = None):
        self.agent_name = agent_name
        self.run_id = run_id or str(uuid4())

        # Always use regular logger - it already has the global run handler attached
        # All logs will go to the global run file (logs/runs/run_{global_run_id}.log)
        self.logger = get_logger(f"agent.{agent_name}")
        self._run_handler = None

        # Memory: episodic storage for run context
        self.episodic_memory: dict[str, Any] = {}

        # Policies: agent-specific policies (override in subclasses)
        self.policies: dict[str, Any] = {}

    def set_context(self, run_id: str, flow_id: str):
        """Set logging context for this agent"""
        LoggingContext.set_run_id(run_id)
        LoggingContext.set_agent(self.agent_name)
        LoggingContext.set_flow(flow_id)
        self.run_id = run_id

    def log_event(self, event_type: str, event_data: dict[str, Any]):
        """Log structured event with ADK context"""
        with logging_context(
            run_id=self.run_id, agent=self.agent_name, flow=event_data.get("flow_id", "unknown")
        ):
            self.logger.info(
                f"[{event_type}] {event_data.get('message', '')}",
                extra={"event": event_data},
            )

    def store_memory(self, key: str, value: Any):
        """Store episodic memory"""
        self.episodic_memory[key] = value

    def get_memory(self, key: str, default: Any | None = None) -> Any | None:
        """Retrieve episodic memory"""
        return self.episodic_memory.get(key, default)

    def create_message(
        self, to_agent: str, flow_id: str, payload: Any, message_id: str | None = None
    ) -> AgentMessage:
        """Create A2A message with proper context"""
        return AgentMessage(
            message_id=message_id or str(uuid4()),
            from_agent=self.agent_name,
            to_agent=to_agent,
            flow_id=flow_id,
            payload=payload,
        )

    def create_error_response(
        self, error_code: str, error_message: str, details: dict[str, Any] | None = None
    ) -> ErrorResponse:
        """Create standardized error response"""
        return ErrorResponse(
            error_code=error_code,
            error_message=error_message,
            error_details=details,
            run_id=self.run_id,
        )

    @abstractmethod
    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle incoming A2A message - must be implemented by subclasses"""
        raise NotImplementedError

    def validate_policy(self, policy_name: str, value: Any) -> bool:
        """Validate value against agent policy"""
        if policy_name not in self.policies:
            return True  # No policy = allow

        policy = self.policies[policy_name]
        if isinstance(policy, dict):
            min_val = policy.get("min")
            max_val = policy.get("max")
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False
        elif callable(policy):
            return policy(value)

        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.agent_name}, run_id={self.run_id[:8]}...)"

