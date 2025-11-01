"""Orchestrator Agent - Coordinates backtests and evaluations"""
from collections.abc import Callable

from trading.domain.messages import (
    AgentMessage,
    BacktestResultsResponse,
    StartBacktestRequest,
)
from trading.infrastructure.logging import logging_context

from .backtest_agent import BacktestAgent
from .base_agent import BaseAgent
from .simulator_agent import SimulatorAgent


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent that coordinates backtests and evaluations

    Role: Coordinate backtests, receive results, trigger optimizations
    Tools: SimulatorAgent, BacktestAgent (future: EvaluatorAgent, OptimizerAgent)
    Memory: Stores orchestration state, backtest history
    Policies: Budget per run, execution limits
    """

    def __init__(self, run_id: str | None = None):
        super().__init__(agent_name="orchestrator", run_id=run_id)

        # Child agents
        self.simulator_agent: SimulatorAgent | None = None
        self.backtest_agent: BacktestAgent | None = None

        # Policies
        self.policies = {
            "max_concurrent_backtests": {"max": 1},
            "max_backtests_per_run": {"max": 10},
        }

        # Track execution state
        self.active_backtests: dict[str, StartBacktestRequest] = {}
        self.completed_backtests: dict[str, BacktestResultsResponse] = {}

    def initialize(self) -> "OrchestratorAgent":
        """Initialize orchestrator and child agents"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="init"):
            self.logger.info("Initializing OrchestratorAgent")

            # Initialize child agents
            self.simulator_agent = SimulatorAgent(run_id=self.run_id).initialize(is_backtest=True)
            self.backtest_agent = BacktestAgent(run_id=self.run_id).initialize()

            self.store_memory("initialized", True)
            self.log_event("orchestrator_initialized", {"run_id": self.run_id})

            return self

    def run_backtest(
        self,
        request: StartBacktestRequest,
        strategy_factory: Callable | None = None,
    ) -> BacktestResultsResponse:
        """Orchestrate a backtest execution"""
        with logging_context(run_id=request.run_id, agent=self.agent_name, flow="run_backtest"):
            try:
                # Validate policy: max concurrent backtests
                if len(self.active_backtests) >= self.policies["max_concurrent_backtests"]["max"]:
                    error = self.create_error_response(
                        "MAX_CONCURRENT_BACKTESTS",
                        f"Max concurrent backtests limit reached: {len(self.active_backtests)}",
                    )
                    raise ValueError(error.error_message)

                # Store active backtest
                self.active_backtests[request.run_id] = request

                # Configure simulator
                self.simulator_agent.set_times(
                    start_time=request.start_time,
                    end_time=request.end_time,
                    min_candles=10,
                )
                self.simulator_agent.add_symbol(request.symbol)

                # Use orchestrator's run_id for the request to ensure single run log file
                if request.run_id != self.run_id:
                    request.run_id = self.run_id

                # Execute backtest via BacktestAgent
                self.log_event(
                    "backtest_requested",
                    {
                        "run_id": request.run_id,
                        "symbol": request.symbol,
                        "strategy": request.strategy_name,
                        "flow_id": "run_backtest",
                    },
                )

                response = self.backtest_agent.execute_backtest(request, strategy_factory=strategy_factory)

                # Move to completed
                del self.active_backtests[request.run_id]
                self.completed_backtests[request.run_id] = response

                # Store in memory
                self.store_memory(f"backtest_{request.run_id}", response)

                self.log_event(
                    "backtest_completed",
                    {
                        "run_id": request.run_id,
                        "total_return": str(response.total_return),
                        "win_rate": response.win_rate,
                        "flow_id": "run_backtest",
                    },
                )

                return response

            except Exception as e:
                # Cleanup on error
                if request.run_id in self.active_backtests:
                    del self.active_backtests[request.run_id]

                self.logger.error(f"Error orchestrating backtest: {e}", exc_info=True)
                raise

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle incoming A2A message"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow=message.flow_id):
            try:
                payload = message.payload

                if isinstance(payload, StartBacktestRequest):
                    # Run backtest
                    response = self.run_backtest(payload)
                    return self.create_message(
                        to_agent=message.from_agent,
                        flow_id=message.flow_id,
                        payload=response,
                    )

                # Default: return error
                error = self.create_error_response(
                    "UNKNOWN_MESSAGE_TYPE",
                    f"Unknown message type: {type(payload)}",
                    details={"payload_type": str(type(payload))},
                )
                return self.create_message(to_agent=message.from_agent, flow_id=message.flow_id, payload=error)

            except Exception as e:
                self.logger.error(f"Error handling message: {e}", exc_info=True)
                error = self.create_error_response("HANDLER_ERROR", str(e))
                return self.create_message(to_agent=message.from_agent, flow_id=message.flow_id, payload=error)

    def close(self):
        """Cleanup resources"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="cleanup"):
            if self.simulator_agent:
                self.simulator_agent.close()
            if self.backtest_agent:
                self.backtest_agent.close()
            self.logger.info("OrchestratorAgent closed")

