"""Orchestrator Agent - Coordinates backtests and evaluations"""

from collections.abc import Callable

from trading.domain.messages import (
    AgentMessage,
    BacktestResultsResponse,
    EvaluationRequest,
    EvaluationResponse,
    OptimizationRequest,
    OptimizationResult,
    StartBacktestRequest,
)
from trading.infrastructure.logging import logging_context

from .backtest_agent import BacktestAgent
from .base_agent import BaseAgent
from .evaluator_agent import EvaluatorAgent
from .optimizer_agent import OptimizerAgent
from .simulator_agent import SimulatorAgent


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent that coordinates backtests and evaluations

    Role: Coordinate backtests, receive results, trigger optimizations
    Tools: SimulatorAgent, BacktestAgent, EvaluatorAgent, OptimizerAgent
    Memory: Stores orchestration state, backtest history
    Policies: Budget per run, execution limits
    """

    def __init__(self, run_id: str | None = None):
        super().__init__(agent_name="orchestrator", run_id=run_id)

        # Child agents
        self.simulator_agent: SimulatorAgent | None = None
        self.backtest_agent: BacktestAgent | None = None
        self.evaluator_agent: EvaluatorAgent | None = None
        self.optimizer_agent: OptimizerAgent | None = None

        # Policies
        self.policies = {
            "max_concurrent_backtests": {"max": 1},
            "max_backtests_per_run": {"max": 10},
            "max_optimization_iterations": {"max": 5},
        }

        # Track execution state
        self.active_backtests: dict[str, StartBacktestRequest] = {}
        self.completed_backtests: dict[str, BacktestResultsResponse] = {}
        self.optimization_history: dict[str, OptimizationResult] = {}

    def initialize(self) -> "OrchestratorAgent":
        """Initialize orchestrator and child agents"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="init"):
            self.logger.info("Initializing OrchestratorAgent")

            # Initialize child agents
            self.simulator_agent = SimulatorAgent(run_id=self.run_id).initialize(is_backtest=True)
            self.backtest_agent = BacktestAgent(run_id=self.run_id).initialize()
            self.evaluator_agent = EvaluatorAgent(run_id=self.run_id).initialize()
            self.optimizer_agent = OptimizerAgent(run_id=self.run_id).initialize()

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
                self.simulator_agent.add_symbol(request.symbol, timeframes=request.timeframes)

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

    def evaluate_backtest(
        self,
        run_id: str | None = None,
        backtest_results: BacktestResultsResponse | None = None,
        kpis: dict[str, float] | None = None,
    ) -> EvaluationResponse:
        """Evaluate a completed backtest

        Args:
            run_id: Run identifier of the backtest to evaluate. If backtest_results is provided, run_id is taken from it.
            backtest_results: Backtest results to evaluate. If None, retrieved from completed_backtests using run_id.
            kpis: Optional KPI thresholds to check. If None, uses default KPIs.

        Returns:
            EvaluationResponse with metrics, KPI compliance, and recommendation

        Raises:
            ValueError: If neither run_id nor backtest_results is provided, or if backtest not found
        """
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="evaluate_backtest"):
            try:
                # Get backtest results
                if backtest_results is None:
                    if run_id is None:
                        raise ValueError("Either run_id or backtest_results must be provided")
                    if run_id not in self.completed_backtests:
                        raise ValueError(f"Backtest {run_id} not found in completed_backtests")
                    backtest_results = self.completed_backtests[run_id]
                else:
                    run_id = backtest_results.run_id

                # Create evaluation request
                request = EvaluationRequest(
                    run_id=run_id,
                    metrics=None,  # Calculate all metrics
                    kpis=kpis,  # Use provided KPIs or defaults
                )

                # Evaluate via EvaluatorAgent
                evaluation = self.evaluator_agent.evaluate(request, backtest_results=backtest_results)

                # Store evaluation in memory
                self.store_memory(f"evaluation_{run_id}", evaluation)

                self.log_event(
                    "evaluation_completed",
                    {
                        "run_id": run_id,
                        "evaluation_passed": evaluation.evaluation_passed,
                        "recommendation": evaluation.recommendation,
                        "flow_id": "evaluate_backtest",
                    },
                )

                return evaluation

            except Exception as e:
                self.logger.error(f"Error evaluating backtest: {e}", exc_info=True)
                raise

    def optimize_strategy(
        self,
        strategy_name: str,
        symbol: str,
        objective: str = "sharpe_ratio",
        parameter_space: dict[str, list[float]] | None = None,
        base_config: StartBacktestRequest | None = None,
    ) -> OptimizationResult:
        """Optimize strategy parameters using OptimizerAgent

        Args:
            strategy_name: Strategy to optimize
            symbol: Trading symbol
            objective: Optimization objective (sharpe_ratio, profit_factor, etc.)
            parameter_space: Parameter space to explore (if None, uses defaults)
            base_config: Base backtest configuration (if None, uses last backtest config)

        Returns:
            OptimizationResult with suggested parameters

        Raises:
            ValueError: If optimizer agent not initialized
        """
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="optimize_strategy"):
            try:
                if self.optimizer_agent is None:
                    raise ValueError("OptimizerAgent not initialized. Call initialize() first.")

                # Collect previous backtest results for this strategy
                previous_results = [
                    result
                    for result in self.completed_backtests.values()
                    if result.strategy_name == strategy_name and result.symbol == symbol
                ]

                # Use default parameter space if not provided
                if parameter_space is None:
                    parameter_space = {
                        "rsi_limits": list(range(10, 91, 5)),  # 10-90 in steps of 5
                    }

                # Use base config or create from last backtest
                if base_config is None and previous_results:
                    last_result = previous_results[-1]
                    base_config = StartBacktestRequest(
                        symbol=symbol,
                        start_time=last_result.start_time,
                        end_time=last_result.end_time,
                        strategy_name=strategy_name,
                        rsi_limits=getattr(last_result, "rsi_limits", None),
                        timeframes=getattr(last_result, "timeframes", None),
                    )

                # Create optimization request
                request = OptimizationRequest(
                    run_id=f"opt_{self.run_id}",
                    strategy_name=strategy_name,
                    symbol=symbol,
                    parameter_space=parameter_space,
                    objective=objective,
                    backtest_config=base_config,
                )

                # Call optimizer agent
                result = self.optimizer_agent.optimize(request, previous_results=previous_results)

                # Store in memory
                self.optimization_history[request.run_id] = result
                self.store_memory(f"optimization_{request.run_id}", result)

                self.log_event(
                    "optimization_completed",
                    {
                        "run_id": request.run_id,
                        "strategy": strategy_name,
                        "confidence": result.confidence,
                        "flow_id": "optimize_strategy",
                    },
                )

                return result

            except Exception as e:
                self.logger.error(f"Error optimizing strategy: {e}", exc_info=True)
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
            if self.evaluator_agent:
                self.evaluator_agent.close()
            if self.optimizer_agent:
                self.optimizer_agent.close()
            self.logger.info("OrchestratorAgent closed")
