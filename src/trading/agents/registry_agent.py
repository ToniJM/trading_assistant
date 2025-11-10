"""Registry Agent - Stores and retrieves results, metrics, and decisions"""

from pathlib import Path
from typing import Any

from trading.domain.messages import (
    AgentMessage,
    RetrieveResultsRequest,
    RetrieveResultsResponse,
    StoreResultsRequest,
    StoreResultsResponse,
)
from trading.infrastructure.logging import logging_context
from trading.infrastructure.registry.results_repository import ResultsRepository

from .base_agent import BaseAgent


class RegistryAgent(BaseAgent):
    """Agent that stores and retrieves results, metrics, and decisions

    Role: Store and retrieve backtest, evaluation, and optimization results
    Tools: ResultsRepository for persistent storage
    Memory: Cache of recent results, indices by strategy/symbol
    Policies: max_storage_size, retention_days
    """

    def __init__(self, run_id: str | None = None, base_path: Path | str | None = None):
        super().__init__(agent_name="registry", run_id=run_id)

        # Policies
        self.policies = {
            "max_storage_size": {"max": 10 * 1024 * 1024 * 1024},  # 10GB default
            "retention_days": {"min": 1, "max": 365},  # 1-365 days
        }

        # Initialize repository
        self.repository = ResultsRepository(base_path=base_path)

        # Cache of recent results
        self.recent_cache: dict[str, dict[str, Any]] = {}
        self.cache_size_limit = 100  # Max 100 entries in cache

    def initialize(self) -> "RegistryAgent":
        """Initialize the registry agent"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="init"):
            self.logger.info("RegistryAgent initialized")
            self.store_memory("initialized", True)
            return self

    def store_results(self, request: StoreResultsRequest) -> StoreResultsResponse:
        """Store results (backtest, evaluation, optimization)

        Args:
            request: StoreResultsRequest with results to store

        Returns:
            StoreResultsResponse confirming storage
        """
        with logging_context(run_id=request.run_id, agent=self.agent_name, flow="store_results"):
            try:
                storage_id = None

                # Store backtest results if provided
                if request.backtest_results:
                    backtest_data = request.backtest_results.model_dump()
                    backtest_data["strategy_name"] = request.strategy_name
                    backtest_data["symbol"] = request.symbol
                    backtest_data.update(request.metadata)
                    storage_id = self.repository.store_backtest(request.run_id, backtest_data)

                # Store evaluation results if provided
                if request.evaluation_results:
                    evaluation_data = request.evaluation_results.model_dump()
                    evaluation_data["strategy_name"] = request.strategy_name
                    evaluation_data["symbol"] = request.symbol
                    evaluation_data.update(request.metadata)
                    self.repository.store_evaluation(request.run_id, evaluation_data)

                # Store optimization results if provided
                if request.optimization_results:
                    optimization_data = request.optimization_results.model_dump()
                    optimization_data["strategy_name"] = request.strategy_name
                    optimization_data["symbol"] = request.symbol
                    optimization_data.update(request.metadata)
                    self.repository.store_optimization(request.run_id, optimization_data)

                # Generate storage_id if not set
                if storage_id is None:
                    storage_id = f"storage-{request.run_id}"

                # Update cache
                self._update_cache(request.run_id, {
                    "strategy_name": request.strategy_name,
                    "symbol": request.symbol,
                    "storage_id": storage_id,
                })

                self.log_event(
                    "results_stored",
                    {
                        "run_id": request.run_id,
                        "storage_id": storage_id,
                        "strategy_name": request.strategy_name,
                        "symbol": request.symbol,
                        "flow_id": "store_results",
                    },
                )

                return StoreResultsResponse(
                    run_id=request.run_id,
                    storage_id=storage_id,
                    success=True,
                )

            except Exception as e:
                self.logger.error(f"Error storing results: {e}", exc_info=True)
                return StoreResultsResponse(
                    run_id=request.run_id,
                    storage_id=f"error-{request.run_id}",
                    success=False,
                )

    def retrieve_results(self, request: RetrieveResultsRequest) -> RetrieveResultsResponse:
        """Retrieve results based on filters

        Args:
            request: RetrieveResultsRequest with filters

        Returns:
            RetrieveResultsResponse with matching results
        """
        with logging_context(
            run_id=request.run_id or "unknown",
            agent=self.agent_name,
            flow="retrieve_results",
        ):
            try:
                results: list[dict[str, Any]] = []

                # Retrieve by run_id if specified
                if request.run_id:
                    result = self.repository.retrieve_by_run_id(request.run_id)
                    if result:
                        results.append(result)
                # Retrieve by strategy if specified
                elif request.strategy_name:
                    results = self.repository.retrieve_by_strategy(
                        request.strategy_name, limit=request.limit, offset=request.offset
                    )
                # Retrieve by symbol if specified
                elif request.symbol:
                    results = self.repository.retrieve_by_symbol(
                        request.symbol, limit=request.limit, offset=request.offset
                    )
                # Retrieve all (limited)
                else:
                    # For "all", we need to get from index - simplified for now
                    # In production, would iterate through index
                    self.logger.warning("Retrieving all results not fully implemented, returning empty")
                    results = []

                # Get total count
                total_count = self.repository.get_total_count(
                    strategy_name=request.strategy_name, symbol=request.symbol
                )

                self.log_event(
                    "results_retrieved",
                    {
                        "run_id": request.run_id or "all",
                        "count": len(results),
                        "total_count": total_count,
                        "flow_id": "retrieve_results",
                    },
                )

                return RetrieveResultsResponse(
                    results=results,
                    total_count=total_count,
                    limit=request.limit,
                    offset=request.offset,
                )

            except Exception as e:
                self.logger.error(f"Error retrieving results: {e}", exc_info=True)
                return RetrieveResultsResponse(
                    results=[],
                    total_count=0,
                    limit=request.limit,
                    offset=request.offset,
                )

    def get_strategy_history(self, strategy_name: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get history of results for a strategy

        Args:
            strategy_name: Strategy name
            limit: Maximum number of results to return

        Returns:
            List of results
        """
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="get_strategy_history"):
            return self.repository.retrieve_by_strategy(strategy_name, limit=limit, offset=0)

    def _update_cache(self, run_id: str, data: dict[str, Any]):
        """Update cache with new entry"""
        # Remove oldest if cache is full
        if len(self.recent_cache) >= self.cache_size_limit:
            # Remove first (oldest) entry
            oldest_key = next(iter(self.recent_cache))
            del self.recent_cache[oldest_key]

        self.recent_cache[run_id] = data

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle incoming A2A message"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow=message.flow_id):
            try:
                payload = message.payload

                if isinstance(payload, StoreResultsRequest):
                    response = self.store_results(payload)
                    return self.create_message(
                        to_agent=message.from_agent, flow_id=message.flow_id, payload=response
                    )

                if isinstance(payload, RetrieveResultsRequest):
                    response = self.retrieve_results(payload)
                    return self.create_message(
                        to_agent=message.from_agent, flow_id=message.flow_id, payload=response
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
            self.logger.info("RegistryAgent closed")

