"""Scheduler Agent - Executes continuous loop of backtests and optimizations"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trading.domain.messages import AgentMessage, StartBacktestRequest
from trading.infrastructure.logging import logging_context
from trading.infrastructure.scheduler.scheduler_config import SchedulerConfig
from trading.strategies.factory import create_strategy_factory

from .base_agent import BaseAgent
from .orchestrator_agent import OrchestratorAgent


class SchedulerAgent(BaseAgent):
    """Agent that executes continuous loop of backtests and optimizations

    Role: Execute cycle continuo de backtests y optimizaciones
    Tools: OrchestratorAgent para ejecutar backtests
    Memory: Estado del scheduler, historial de ejecuciones programadas
    Policies: schedule_interval_seconds, max_runs_per_day, auto_reset_memory
    """

    def __init__(self, config: SchedulerConfig, run_id: str | None = None):
        super().__init__(agent_name="scheduler", run_id=run_id)

        self.config = config
        self.orchestrator: OrchestratorAgent | None = None
        self.running = False
        self.last_reset_date: datetime | None = None

        # Policies
        self.policies = {
            "schedule_interval_seconds": {"min": 60, "max": 86400},  # 1 min to 24 hours
            "max_runs_per_day": {"max": 100},
            "auto_reset_memory": {"default": True},
        }

        # Track execution state
        self.cycle_count = 0
        self.executions_today = 0
        self.last_execution_date: datetime | None = None

        # Track parameter combinations and their backtest time ranges
        # Format: {parameter_key: [{"start": int, "end": int, "run_id": str}, ...]}
        self.parameter_combinations: dict[str, list[dict[str, int | str]]] = {}

        # Track incremental period state
        self.current_period_index: int = 0  # 0=1 día, 1=1 semana, 2=1 mes, 3=3 meses
        self.backtest_count_in_period: int = 0
        self.passed_backtests_in_period: int = 0
        # Track ranges per period: {period_index: {parameter_key: [{"start": int, "end": int, "run_id": str}, ...]}}
        self.period_parameter_combinations: dict[int, dict[str, list[dict[str, int | str]]]] = {}

    def initialize(self) -> "SchedulerAgent":
        """Initialize the scheduler agent"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="init"):
            self.logger.info("Initializing SchedulerAgent")
            self.logger.info(f"Config: symbol={self.config.symbol}, strategy={self.config.strategy_name}")
            self.logger.info(
                f"Schedule: interval={self.config.schedule_interval_seconds}s, "
                f"duration={self.config.backtest_duration_days}d"
            )
            self.logger.info(
                f"Incremental periods: {self.config.incremental_periods} days, "
                f"backtests per period: {self.config.backtests_per_period}, "
                f"min passed per period: {self.config.min_passed_backtests_per_period}"
            )
            self.logger.info(f"Starting at period {self.current_period_index} ({self.config.incremental_periods[self.current_period_index]} days)")

            # Initialize orchestrator
            self.orchestrator = OrchestratorAgent(run_id=self.run_id)
            self.orchestrator.initialize()

            self.store_memory("initialized", True)
            self.store_memory("config", self.config.model_dump())
            self.log_event("scheduler_initialized", {"run_id": self.run_id, "config": self.config.model_dump()})

            return self

    def start(self):
        """Start the continuous loop"""
        if self.running:
            with logging_context(run_id=self.run_id, agent=self.agent_name, flow="start"):
                self.logger.warning("Scheduler already running")
            return

        if self.orchestrator is None:
            raise ValueError("SchedulerAgent not initialized. Call initialize() first.")

        self.running = True
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="start"):
            self.logger.info("Scheduler started - entering continuous loop")
            self.log_event("scheduler_started", {"run_id": self.run_id})

        try:
            while self.running:
                # Check if we need to reset daily memory
                if self.config.auto_reset_memory and self._should_reset_daily():
                    with logging_context(run_id=self.run_id, agent=self.agent_name, flow="reset_daily_memory"):
                        self.reset_daily_memory()

                # Execute one cycle
                try:
                    self.run_cycle()
                except Exception as e:
                    with logging_context(run_id=self.run_id, agent=self.agent_name, flow="start"):
                        self.logger.error(f"Error in cycle execution: {e}", exc_info=True)
                    # Continue running despite errors

                # Wait for next interval
                if self.running:
                    with logging_context(run_id=self.run_id, agent=self.agent_name, flow="start"):
                        self.logger.debug(f"Waiting {self.config.schedule_interval_seconds} seconds until next cycle")
                    # Sleep outside of logging context to avoid any potential blocking
                    time.sleep(self.config.schedule_interval_seconds)
                    # Log after sleep to confirm we're continuing
                    with logging_context(run_id=self.run_id, agent=self.agent_name, flow="start"):
                        self.logger.debug(f"Sleep completed, continuing loop (running={self.running})")

        except KeyboardInterrupt:
            with logging_context(run_id=self.run_id, agent=self.agent_name, flow="start"):
                self.logger.info("Scheduler interrupted by user")
        finally:
            self.running = False
            with logging_context(run_id=self.run_id, agent=self.agent_name, flow="start"):
                self.logger.info("Scheduler stopped")

    def stop(self):
        """Stop the continuous loop"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="stop"):
            self.running = False
            self.logger.info("Scheduler stop requested")
            self.log_event("scheduler_stopped", {"run_id": self.run_id})

    def run_cycle(self):
        """Execute one complete cycle: backtest → evaluate → optimize if necessary"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="run_cycle"):
            self.cycle_count += 1
            self.executions_today += 1
            self.last_execution_date = datetime.now(UTC)

            # Get current period duration
            current_period_days = self.config.incremental_periods[self.current_period_index]
            self.logger.info(
                f"Starting cycle {self.cycle_count} - Period {self.current_period_index} "
                f"({current_period_days} days) - Backtest {self.backtest_count_in_period + 1}/{self.config.backtests_per_period}"
            )

            try:
                # Generate unique run_id for this cycle
                cycle_run_id = f"{self.run_id}_cycle_{self.cycle_count}_{int(time.time())}"

                # Get parameter combination key first (needed to check previous ranges)
                # Use a temporary request with default values to get the key
                temp_request = StartBacktestRequest(
                    symbol=self.config.symbol,
                    start_time=0,  # Placeholder
                    end_time=0,  # Placeholder
                    strategy_name=self.config.strategy_name,
                    initial_balance=Decimal(str(self.config.initial_balance)),
                    leverage=Decimal(str(self.config.leverage)),
                )
                param_key = self._get_parameter_key(temp_request)

                # Get previous backtest ranges for this parameter combination in current period
                period_ranges = self.period_parameter_combinations.get(self.current_period_index, {})
                previous_ranges = period_ranges.get(param_key, [])

                # Calculate backtest time range with 20% overlap within same period
                current_time_ms = int(datetime.now(UTC).timestamp() * 1000)
                ONE_MINUTE_MS = 60000
                duration_ms = int(current_period_days * 24 * 3600 * 1000)
                
                if not previous_ranges:
                    # Primer backtest del periodo: end_time = ahora - 1 minuto, start_time = end_time - duración
                    end_time = current_time_ms - ONE_MINUTE_MS
                    start_time = end_time - duration_ms
                else:
                    # Backtests siguientes: end_time = start_time del anterior + (20% × duración)
                    # Esto crea un solapamiento del 20% con el backtest anterior dentro del mismo periodo
                    most_recent = max(previous_ranges, key=lambda x: int(x["end"]))
                    prev_start = int(most_recent["start"])
                    prev_end = int(most_recent["end"])
                    target_overlap_duration = int(duration_ms * (self.config.max_overlap_percentage / 100.0))
                    
                    # Calcular end_time: prev_start + (20% × duración)
                    calculated_end_time = prev_start + target_overlap_duration
                    
                    # Asegurar que el end_time sea anterior al tiempo actual
                    if calculated_end_time >= current_time_ms:
                        end_time = current_time_ms - ONE_MINUTE_MS
                        self.logger.warning(
                            f"Calculated end_time {calculated_end_time} >= current_time {current_time_ms}, "
                            f"adjusting to {end_time}. This may cause overlap issues."
                        )
                    else:
                        end_time = calculated_end_time
                    
                    start_time = end_time - duration_ms
                    
                    self.logger.info(
                        f"Calculated time range for 20% overlap: "
                        f"start_time={start_time}, end_time={end_time}, "
                        f"prev_start={prev_start}, prev_end={prev_end}, "
                        f"overlap_duration={target_overlap_duration}ms"
                    )
                
                end_time_final = end_time

                # Create backtest request with unique run_id and adjusted time range
                self.logger.info(
                    f"Creating backtest request: start_time={start_time} ({datetime.fromtimestamp(start_time/1000, UTC)}), "
                    f"end_time={end_time_final} ({datetime.fromtimestamp(end_time_final/1000, UTC)})"
                )
                request = StartBacktestRequest(
                    run_id=cycle_run_id,
                    symbol=self.config.symbol,
                    start_time=start_time,
                    end_time=end_time_final,
                    strategy_name=self.config.strategy_name,
                    initial_balance=Decimal(str(self.config.initial_balance)),
                    leverage=Decimal(str(self.config.leverage)),
                )

                # Create strategy factory
                strategy_factory = create_strategy_factory(
                    strategy_name=self.config.strategy_name,
                )

                # Execute backtest
                self.logger.info(
                    f"Executing backtest for {current_period_days} days (run_id: {cycle_run_id})"
                )
                backtest_results = self.orchestrator.run_backtest(request, strategy_factory=strategy_factory)

                # Store time range for this parameter combination in current period using ACTUAL times
                actual_start_time = backtest_results.start_time
                actual_end_time = backtest_results.end_time
                if self.current_period_index not in self.period_parameter_combinations:
                    self.period_parameter_combinations[self.current_period_index] = {}
                if param_key not in self.period_parameter_combinations[self.current_period_index]:
                    self.period_parameter_combinations[self.current_period_index][param_key] = []
                self.period_parameter_combinations[self.current_period_index][param_key].append(
                    {"start": actual_start_time, "end": actual_end_time, "run_id": cycle_run_id}
                )

                # Evaluate results
                self.logger.info("Evaluating backtest results")
                evaluation = self.orchestrator.evaluate_backtest(
                    backtest_results=backtest_results, kpis=self.config.kpis
                )

                # Handle optimization: reset to first period if needed
                if evaluation.recommendation == "optimize":
                    self.logger.info("Optimization recommended - resetting to first period")
                    self._reset_to_first_period()
                    
                    if self.cycle_count <= self.config.max_iterations_per_cycle:
                        self.logger.info("Starting optimization")
                        try:
                            optimization_result = self.orchestrator.optimize_strategy(
                                strategy_name=self.config.strategy_name,
                                symbol=self.config.symbol,
                                objective="sharpe_ratio",
                            )
                            self.logger.info(
                                f"Optimization completed with confidence: {optimization_result.confidence:.2%}"
                            )
                        except Exception as e:
                            self.logger.warning(f"Optimization failed: {e}")

                # Track passed backtests
                if evaluation.evaluation_passed:
                    self.passed_backtests_in_period += 1
                    self.logger.info(
                        f"Backtest passed KPIs. Total passed in period: {self.passed_backtests_in_period}/{self.config.backtests_per_period}"
                    )

                # Increment backtest count in period
                self.backtest_count_in_period += 1

                # Check if we should advance to next period
                if self.backtest_count_in_period >= self.config.backtests_per_period:
                    if self.passed_backtests_in_period >= self.config.min_passed_backtests_per_period:
                        # Advance to next period
                        if self.current_period_index < len(self.config.incremental_periods) - 1:
                            self.current_period_index += 1
                            next_period_days = self.config.incremental_periods[self.current_period_index]
                            self.logger.info(
                                f"Period completed successfully. Advancing to period {self.current_period_index} "
                                f"({next_period_days} days)"
                            )
                            # Reset counters for new period
                            self.backtest_count_in_period = 0
                            self.passed_backtests_in_period = 0
                            # Clear previous period's ranges (keep current period for reference)
                            if self.current_period_index - 1 in self.period_parameter_combinations:
                                del self.period_parameter_combinations[self.current_period_index - 1]
                        else:
                            # Completed all periods (3 months) - promote to production
                            self._promote_to_production()
                            return
                    else:
                        # Not enough passed backtests - reset to first period
                        self.logger.warning(
                            f"Period failed: only {self.passed_backtests_in_period}/{self.config.min_passed_backtests_per_period} "
                            f"backtests passed KPIs. Resetting to first period."
                        )
                        self._reset_to_first_period()

                # Store cycle results in memory
                self.store_memory(
                    f"cycle_{self.cycle_count}",
                    {
                        "cycle_count": self.cycle_count,
                        "period_index": self.current_period_index,
                        "period_days": current_period_days,
                        "backtest_count_in_period": self.backtest_count_in_period,
                        "passed_backtests_in_period": self.passed_backtests_in_period,
                        "backtest_results": backtest_results.model_dump(),
                        "evaluation": evaluation.model_dump(),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

                self.log_event(
                    "cycle_completed",
                    {
                        "cycle_count": self.cycle_count,
                        "run_id": cycle_run_id,
                        "scheduler_run_id": self.run_id,
                        "period_index": self.current_period_index,
                        "period_days": current_period_days,
                        "backtest_count_in_period": self.backtest_count_in_period,
                        "passed_backtests_in_period": self.passed_backtests_in_period,
                        "evaluation_passed": evaluation.evaluation_passed,
                        "recommendation": evaluation.recommendation,
                        "flow_id": "run_cycle",
                    },
                )

                self.logger.info(
                    f"Cycle {self.cycle_count} completed - Period {self.current_period_index} "
                    f"({current_period_days} days) - Backtest {self.backtest_count_in_period}/{self.config.backtests_per_period} "
                    f"- Evaluation: {evaluation.recommendation} (run_id: {cycle_run_id})"
                )

            except Exception as e:
                self.logger.error(f"Error in cycle {self.cycle_count}: {e}", exc_info=True)
                raise

    def reset_daily_memory(self):
        """Reset episodic memory daily"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="reset_daily_memory"):
            self.logger.info("Resetting daily episodic memory")

            # Clear episodic memory (but keep config and state)
            config_backup = self.get_memory("config")
            self.episodic_memory.clear()
            if config_backup:
                self.store_memory("config", config_backup)

            # Clear parameter combinations tracking to allow fresh overlap calculations
            self.parameter_combinations.clear()

            # Reset counters
            self.executions_today = 0
            self.last_reset_date = datetime.now(UTC)

            self.log_event(
                "daily_memory_reset", {"run_id": self.run_id, "reset_date": self.last_reset_date.isoformat()}
            )
            self.logger.info("Daily memory reset completed")

    def _reset_to_first_period(self):
        """Reset state to first period (1 day)"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="reset_to_first_period"):
            self.logger.info("Resetting to first period (1 day)")
            
            self.current_period_index = 0
            self.backtest_count_in_period = 0
            self.passed_backtests_in_period = 0
            self.period_parameter_combinations.clear()
            
            self.log_event(
                "reset_to_first_period",
                {
                    "run_id": self.run_id,
                    "period_index": self.current_period_index,
                    "period_days": self.config.incremental_periods[self.current_period_index],
                },
            )
            self.logger.info("Reset to first period completed")

    def _promote_to_production(self):
        """Handle promotion to production after completing all periods"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="promote_to_production"):
            self.logger.info("🎉 All periods completed successfully - Promoting to production!")
            
            self.log_event(
                "promote_to_production",
                {
                    "run_id": self.run_id,
                    "strategy": self.config.strategy_name,
                    "symbol": self.config.symbol,
                    "total_cycles": self.cycle_count,
                    "final_period": self.config.incremental_periods[-1],
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            
            # Stop the scheduler
            self.stop()
            
            self.logger.info("Scheduler stopped after promotion to production")

    def _should_reset_daily(self) -> bool:
        """Check if daily reset should be performed"""
        if self.last_reset_date is None:
            return True

        now = datetime.now(UTC)
        # Reset if it's a new day (UTC)
        return now.date() > self.last_reset_date.date()

    def _get_parameter_key(self, request: StartBacktestRequest) -> str:
        """Generate unique key for parameter combination (strategy_name, rsi_limits, timeframes)"""
        strategy = request.strategy_name
        rsi_str = str(sorted(request.rsi_limits)) if request.rsi_limits else "default"
        tf_str = ",".join(sorted(request.timeframes or []))
        return f"{strategy}_rsi_{rsi_str}_tf_{tf_str}"

    def _calculate_overlap(self, start1: int, end1: int, start2: int, end2: int) -> float:
        """Calculate overlap percentage as (overlap_duration / current_backtest_duration) * 100"""
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        if overlap_start >= overlap_end:
            return 0.0
        overlap_duration = overlap_end - overlap_start
        current_backtest_duration = end1 - start1
        if current_backtest_duration == 0:
            return 0.0
        return (overlap_duration / current_backtest_duration) * 100

    def _adjust_time_range(
        self, end_time: int, duration_days: int, previous_ranges: list[dict[str, int | str]], current_time_ms: int
    ) -> tuple[int, int]:
        """
        Adjust time range to ensure max 20% overlap, moving entire range backward if needed.
        
        Important: The simulator may adjust the requested end_time to current_time - 1 minute
        if the requested end_time >= current_time. We account for this by using the expected
        actual end_time (which will be min(requested_end_time, current_time - 1 minute)) when
        calculating overlaps.
        """
        target_start = end_time - int(duration_days * 24 * 3600 * 1000)
        max_overlap = self.config.max_overlap_percentage
        duration_ms = int(duration_days * 24 * 3600 * 1000)
        target_overlap_duration = int(duration_ms * (max_overlap / 100.0))
        ONE_MINUTE_MS = 60000

        # Calculate expected actual end_time (simulator will adjust if end_time >= current_time)
        # If requested end_time < current_time, simulator won't adjust it
        # If requested end_time >= current_time, simulator will set it to current_time - 1 minute
        expected_actual_end_time = min(end_time, current_time_ms - ONE_MINUTE_MS)

        # Sort previous ranges by end_time descending (most recent first) for optimization
        sorted_ranges = sorted(previous_ranges, key=lambda x: int(x["end"]), reverse=True)

        # Initial check: calculate overlap using expected actual end_time
        max_found_overlap = 0.0
        overlapping_range = None
        for prev_range in sorted_ranges:
            prev_start = int(prev_range["start"])
            prev_end = int(prev_range["end"])
            # Use expected_actual_end_time for overlap calculation
            overlap = self._calculate_overlap(target_start, expected_actual_end_time, prev_start, prev_end)
            if overlap > max_found_overlap:
                max_found_overlap = overlap
                overlapping_range = {"start": prev_start, "end": prev_end}

        # If no overlap exceeds threshold, return original range
        if max_found_overlap <= max_overlap:
            return target_start, end_time

        # Initial adjustment based on the problematic range
        new_end_time = end_time
        new_start_time = target_start
        max_iterations = 10  # Prevent infinite loops

        for iteration in range(max_iterations):
            # Calculate expected actual end_time for current new_end_time
            expected_actual_end = min(new_end_time, current_time_ms - ONE_MINUTE_MS)
            
            # Find the range with maximum overlap using expected actual end_time
            max_overlap_found = 0.0
            problematic_range = None

            for prev_range in sorted_ranges:
                prev_start = int(prev_range["start"])
                prev_end = int(prev_range["end"])
                # Use expected_actual_end for overlap calculation
                overlap = self._calculate_overlap(new_start_time, expected_actual_end, prev_start, prev_end)
                if overlap > max_overlap_found:
                    max_overlap_found = overlap
                    problematic_range = prev_range

            # If all overlaps are <= 20%, we're done
            if max_overlap_found <= max_overlap:
                break

            # Otherwise, adjust again based on the problematic range
            if problematic_range:
                prev_start = int(problematic_range["start"])
                prev_end = int(problematic_range["end"])

                # Calculate target end_time: prev_start + target_overlap_duration (20% of duration)
                # This ensures the new backtest overlaps with the previous one by exactly 20%
                target_end_time = prev_start + target_overlap_duration

                # Calculate how much to move backward
                move_backward_ms = new_end_time - target_end_time

                # Move both end_time and start_time backward, maintaining duration
                new_end_time = new_end_time - move_backward_ms
                new_start_time = new_end_time - duration_ms

                # Ensure the new start_time is before prev_start (no overlap at start)
                if new_start_time > prev_start:
                    # Move additional amount to ensure new_start <= prev_start
                    additional_move = new_start_time - prev_start
                    move_backward_ms += additional_move
                    new_end_time = new_end_time - additional_move
                    new_start_time = new_end_time - duration_ms

                self.logger.debug(
                    f"Iteration {iteration + 1}: Max overlap {max_overlap_found:.2f}% > {max_overlap}%, "
                    f"adjusting based on range [{prev_start}, {prev_end}], "
                    f"new range: [{new_start_time}, {new_end_time}]"
                )

        # Final verification using expected actual end_time
        expected_final_end = min(new_end_time, current_time_ms - ONE_MINUTE_MS)
        final_max_overlap = 0.0
        for prev_range in sorted_ranges:
            prev_start = int(prev_range["start"])
            prev_end = int(prev_range["end"])
            overlap = self._calculate_overlap(new_start_time, expected_final_end, prev_start, prev_end)
            if overlap > final_max_overlap:
                final_max_overlap = overlap

        self.logger.debug(
            f"Final adjustment: end_time {end_time} -> {new_end_time}, "
            f"start_time {target_start} -> {new_start_time}, "
            f"expected actual end_time: {expected_final_end}, "
            f"final max overlap: {final_max_overlap:.2f}%"
        )

        return new_start_time, new_end_time

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle incoming A2A message"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow=message.flow_id):
            try:
                payload = message.payload

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
            self.stop()
            if self.orchestrator:
                self.orchestrator.close()
            self.logger.info("SchedulerAgent closed")
