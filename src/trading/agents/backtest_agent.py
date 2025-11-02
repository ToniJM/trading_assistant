"""Backtest Agent - Wraps BacktestRunner for A2A communication"""
from collections.abc import Callable

from trading.domain.messages import AgentMessage, BacktestResultsResponse, StartBacktestRequest
from trading.infrastructure.backtest.config import BacktestConfig
from trading.infrastructure.backtest.runner import BacktestRunner
from trading.infrastructure.logging import logging_context
from trading.strategies.factory import create_strategy_factory

from .base_agent import BaseAgent


class BacktestAgent(BaseAgent):
    """Agent that wraps BacktestRunner for backtest execution

    Role: Execute backtests and return results
    Tools: BacktestRunner, Exchange adapters
    Memory: Stores backtest configurations and results
    Policies: Max backtests per run, execution limits
    """

    def __init__(self, run_id: str | None = None):
        super().__init__(agent_name="backtest", run_id=run_id)
        self.runner: BacktestRunner | None = None

        # Policies
        self.policies = {
            "max_concurrent_backtests": {"max": 1},  # One at a time for now
            "max_loss_percentage": {"max": 0.5},  # 50% max loss
        }

    def initialize(self) -> "BacktestAgent":
        """Initialize the backtest agent"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="init"):
            self.logger.info("BacktestAgent initialized")
            self.store_memory("initialized", True)
            return self

    def execute_backtest(
        self,
        request: StartBacktestRequest,
        strategy_factory: Callable | None = None,
    ) -> BacktestResultsResponse:
        """Execute backtest from request"""
        # Use agent's run_id (from orchestrator) to ensure logs go to main run file
        run_id = self.run_id if self.run_id else request.run_id
        with logging_context(run_id=run_id, agent=self.agent_name, flow="execute_backtest"):
            try:
                # Validate policies
                if not self.validate_policy("max_loss_percentage", request.max_loss_percentage):
                    raise ValueError(f"Max loss percentage exceeds policy: {request.max_loss_percentage}")

                # Convert request to BacktestConfig
                # Use agent's run_id for logging context (orchestrator's run_id)
                # Extract run_id without "backtest_" prefix to avoid duplicate prefix in log filename
                backtest_id = (
                    request.run_id.replace("backtest_", "")
                    if request.run_id.startswith("backtest_")
                    else request.run_id
                )
                config = BacktestConfig(
                    symbol=request.symbol,
                    start_time=request.start_time,
                    end_time=request.end_time,
                    initial_balance=request.initial_balance,
                    leverage=request.leverage,
                    maker_fee=request.maker_fee,
                    taker_fee=request.taker_fee,
                    max_notional=request.max_notional,
                    strategy_name=request.strategy_name,
                    stop_on_loss=request.stop_on_loss,
                    max_loss_percentage=request.max_loss_percentage,
                    track_cycles=request.track_cycles,
                    timeframes=request.timeframes,
                    log_filename=f"backtest_{backtest_id}",
                    run_id=run_id,  # Use orchestrator's run_id for logging context
                )

                # Create runner
                self.runner = BacktestRunner(config=config)
                self.store_memory(f"backtest_{request.run_id}_config", config)

                # Create strategy factory if not provided
                if strategy_factory is None:
                    strategy_factory = create_strategy_factory(
                        strategy_name=request.strategy_name,
                        timeframes=request.timeframes,
                        rsi_limits=request.rsi_limits,
                    )

                # Setup exchange and strategy
                self.runner.setup_exchange_and_strategy(strategy_factory=strategy_factory)

                # Execute backtest
                self.log_event(
                    "backtest_started",
                    {
                        "run_id": request.run_id,
                        "symbol": request.symbol,
                        "start_time": request.start_time,
                        "flow_id": "execute_backtest",
                    },
                )

                results = self.runner.run()

                # Convert results to response
                response = BacktestResultsResponse(
                    run_id=request.run_id,
                    status="completed",
                    start_time=results.start_time,
                    end_time=results.end_time,
                    duration_seconds=results.duration_seconds,
                    total_candles_processed=results.total_candles_processed,
                    final_balance=results.final_balance,
                    total_return=results.total_return,
                    return_percentage=results.return_percentage,
                    max_drawdown=results.max_drawdown,
                    total_trades=results.total_trades,
                    win_rate=results.win_rate,
                    profit_factor=results.profit_factor,
                    total_closed_positions=results.total_closed_positions,
                    winning_positions=results.winning_positions,
                    losing_positions=results.losing_positions,
                    total_commission=results.total_commission,
                    commission_percentage=results.commission_percentage,
                    total_cycles=results.total_cycles,
                    avg_cycle_duration=results.avg_cycle_duration,
                    avg_cycle_pnl=results.avg_cycle_pnl,
                    winning_cycles=results.winning_cycles,
                    losing_cycles=results.losing_cycles,
                    cycle_win_rate=results.cycle_win_rate,
                    strategy_name=results.strategy_name,
                    symbol=results.symbol,
                )

                self.store_memory(f"backtest_{request.run_id}_results", response)
                self.log_event(
                    "backtest_completed",
                    {
                        "run_id": request.run_id,
                        "status": "completed",
                        "total_return": str(results.total_return),
                        "flow_id": "execute_backtest",
                    },
                )

                return response

            except Exception as e:
                self.logger.error(f"Error executing backtest: {e}", exc_info=True)
                # Return error response
                raise

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle incoming A2A message"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow=message.flow_id):
            try:
                payload = message.payload

                if isinstance(payload, StartBacktestRequest):
                    # Execute backtest
                    response = self.execute_backtest(payload)
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
        if self.runner:
            with logging_context(run_id=self.run_id, agent=self.agent_name, flow="cleanup"):
                # Runner cleanup happens automatically
                self.runner = None
                self.logger.info("BacktestAgent closed")

