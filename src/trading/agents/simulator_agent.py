"""Simulator Agent - Wraps MarketDataSimulator for A2A communication"""

from trading.domain.messages import AgentMessage
from trading.infrastructure.logging import logging_context
from trading.infrastructure.simulator.simulator import MarketDataSimulator

from .base_agent import BaseAgent


class SimulatorAgent(BaseAgent):
    """Agent that wraps MarketDataSimulator for market data simulation

    Role: Provide market data simulation capabilities
    Tools: MarketDataSimulator
    Memory: Stores simulation state and candle history
    Policies: Time ranges, symbol limits
    """

    def __init__(self, run_id: str | None = None):
        super().__init__(agent_name="simulator", run_id=run_id)
        self.simulator: MarketDataSimulator | None = None

        # Policies
        self.policies = {
            "max_symbols": {"max": 10},
            "min_time_range": {"min": 60000},  # 1 minute minimum
        }

    def initialize(self, is_backtest: bool = True) -> "SimulatorAgent":
        """Initialize the market data simulator"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="init"):
            self.logger.info("Initializing MarketDataSimulator")
            self.simulator = MarketDataSimulator(is_backtest=is_backtest)
            self.store_memory("initialized", True)
            self.log_event("simulator_initialized", {"is_backtest": is_backtest})
            return self

    def set_times(self, start_time: int, end_time: int | None = None, min_candles: int = 10):
        """Set simulation time range"""
        if not self.simulator:
            raise ValueError("Simulator not initialized. Call initialize() first.")

        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="configure"):
            # Validate policy
            if end_time and not self.validate_policy("min_time_range", end_time - start_time):
                raise ValueError(f"Time range too small: {end_time - start_time}ms")

            self.simulator.set_times(start=start_time, end=end_time, min_candles=min_candles)
            self.store_memory("start_time", start_time)
            self.store_memory("end_time", end_time)
            self.logger.info(f"Set simulation times: {start_time} to {end_time or 'current'}")

    def add_symbol(self, symbol: str, timeframes: list[str] = None):
        """Add symbol to simulate"""
        if not self.simulator:
            raise ValueError("Simulator not initialized")

        if timeframes is None:
            timeframes = ["1m", "15m", "1h"]

        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="configure"):
            # Check symbol limit policy
            current_symbols = len(self.simulator.symbols_timeframes)
            if not self.validate_policy("max_symbols", current_symbols + 1):
                raise ValueError(f"Max symbols limit reached: {current_symbols}")

            self.simulator.symbols_timeframes[symbol] = timeframes
            self.logger.info(f"Added symbol {symbol} with timeframes {timeframes}")

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle incoming A2A message"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow=message.flow_id):
            try:
                payload = message.payload

                # Handle different message types
                if isinstance(payload, dict):
                    # Handle dict-based requests (backwards compatibility)
                    action = payload.get("action")
                    if action == "initialize":
                        self.initialize(payload.get("is_backtest", True))
                        return self.create_message(
                            to_agent=message.from_agent,
                            flow_id=message.flow_id,
                            payload={"status": "initialized", "run_id": self.run_id},
                        )
                    elif action == "set_times":
                        self.set_times(
                            start_time=payload["start_time"],
                            end_time=payload.get("end_time"),
                            min_candles=payload.get("min_candles", 10),
                        )
                        return self.create_message(
                            to_agent=message.from_agent,
                            flow_id=message.flow_id,
                            payload={"status": "configured"},
                        )
                    elif action == "next_candle":
                        if self.simulator:
                            self.simulator.next_candle()
                        return self.create_message(
                            to_agent=message.from_agent,
                            flow_id=message.flow_id,
                            payload={"status": "candle_processed"},
                        )

                # Default: return error
                error = self.create_error_response(
                    "UNKNOWN_MESSAGE_TYPE",
                    f"Unknown message type: {type(payload)}",
                    details={"payload_type": str(type(payload))},
                )
                return self.create_message(
                    to_agent=message.from_agent, flow_id=message.flow_id, payload=error
                )

            except Exception as e:
                self.logger.error(f"Error handling message: {e}", exc_info=True)
                error = self.create_error_response("HANDLER_ERROR", str(e))
                return self.create_message(to_agent=message.from_agent, flow_id=message.flow_id, payload=error)

    def close(self):
        """Cleanup resources"""
        if self.simulator:
            with logging_context(run_id=self.run_id, agent=self.agent_name, flow="cleanup"):
                self.simulator.close()
                self.simulator = None
                self.logger.info("Simulator closed")

