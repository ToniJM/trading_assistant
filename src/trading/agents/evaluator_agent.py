"""Evaluator Agent - Analyzes backtest results and generates recommendations"""

from trading.domain.messages import (
    AgentMessage,
    BacktestResultsResponse,
    EvaluationRequest,
    EvaluationResponse,
)
from trading.infrastructure.evaluation.metrics import extract_metrics_from_results
from trading.infrastructure.logging import logging_context

from .base_agent import BaseAgent


class EvaluatorAgent(BaseAgent):
    """Agent that evaluates backtest results and generates recommendations

    Role: Analyze metrics, verify KPIs, generate recommendations
    Tools: Metrics calculators (Sharpe Ratio, Calmar Ratio, etc.)
    Memory: Stores evaluation history
    Policies: KPI thresholds (configurable via EvaluationRequest)
    """

    # Default KPI thresholds (can be overridden via EvaluationRequest)
    DEFAULT_KPIS = {
        "sharpe_ratio": 2.0,
        "max_drawdown": 10.0,  # 10% max
        "profit_factor": 1.5,
    }

    def __init__(self, run_id: str | None = None):
        super().__init__(agent_name="evaluator", run_id=run_id)

        # Policies: default KPI thresholds
        self.policies = {
            "sharpe_ratio_threshold": {"min": 2.0},
            "max_drawdown_threshold": {"max": 10.0},
            "profit_factor_threshold": {"min": 1.5},
        }

    def initialize(self) -> "EvaluatorAgent":
        """Initialize the evaluator agent"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="init"):
            self.logger.info("EvaluatorAgent initialized")
            self.store_memory("initialized", True)
            return self

    def evaluate(
        self,
        request: EvaluationRequest,
        backtest_results: BacktestResultsResponse | None = None,
    ) -> EvaluationResponse:
        """Evaluate backtest results against KPIs

        Args:
            request: Evaluation request with run_id and optional KPIs/metrics
            backtest_results: Backtest results to evaluate (if None, must be retrieved)

        Returns:
            EvaluationResponse with metrics, KPI compliance, and recommendation

        Raises:
            ValueError: If backtest_results is None and cannot be retrieved
        """
        with logging_context(run_id=request.run_id, agent=self.agent_name, flow="evaluate"):
            try:
                if backtest_results is None:
                    raise ValueError(
                        "backtest_results must be provided. Retrieval from OrchestratorAgent not yet implemented."
                    )

                # Extract metrics
                metrics_to_calculate = request.metrics if request.metrics else None
                calculate_advanced = metrics_to_calculate is None or "sharpe_ratio" in metrics_to_calculate
                all_metrics = extract_metrics_from_results(backtest_results, calculate_advanced=calculate_advanced)

                # Filter metrics if specific ones requested
                if metrics_to_calculate:
                    filtered_metrics = {k: v for k, v in all_metrics.items() if k in metrics_to_calculate}
                else:
                    filtered_metrics = all_metrics

                # Get KPI thresholds (from request or defaults)
                kpis = request.kpis if request.kpis else self.DEFAULT_KPIS.copy()

                # Check KPI compliance
                kpi_compliance: dict[str, bool] = {}
                for kpi_name, threshold in kpis.items():
                    metric_value = filtered_metrics.get(kpi_name)
                    if metric_value is None:
                        self.logger.warning(f"Metric '{kpi_name}' not found in results, skipping KPI check")
                        kpi_compliance[kpi_name] = False
                        continue

                    # Check compliance based on metric type
                    if kpi_name == "max_drawdown":
                        # Max drawdown: should be <= threshold (lower is better)
                        kpi_compliance[kpi_name] = abs(metric_value) <= abs(threshold)
                    else:
                        # Other metrics: should be >= threshold (higher is better)
                        kpi_compliance[kpi_name] = metric_value >= threshold

                # Determine if evaluation passed (all KPIs met)
                evaluation_passed = all(kpi_compliance.values()) if kpi_compliance else False

                # Generate recommendation
                recommendation = self._generate_recommendation(
                    evaluation_passed=evaluation_passed,
                    kpi_compliance=kpi_compliance,
                    metrics=filtered_metrics,
                    kpis=kpis,
                )

                # Store in memory
                self.store_memory(f"evaluation_{request.run_id}", {
                    "metrics": filtered_metrics,
                    "kpi_compliance": kpi_compliance,
                    "recommendation": recommendation,
                })

                self.log_event(
                    "evaluation_completed",
                    {
                        "run_id": request.run_id,
                        "evaluation_passed": evaluation_passed,
                        "recommendation": recommendation,
                        "flow_id": "evaluate",
                    },
                )

                return EvaluationResponse(
                    run_id=request.run_id,
                    evaluation_passed=evaluation_passed,
                    metrics=filtered_metrics,
                    kpi_compliance=kpi_compliance,
                    recommendation=recommendation,
                )

            except Exception as e:
                self.logger.error(f"Error evaluating backtest: {e}", exc_info=True)
                raise

    def _generate_recommendation(
        self,
        evaluation_passed: bool,
        kpi_compliance: dict[str, bool],
        metrics: dict[str, float],
        kpis: dict[str, float],
    ) -> str:
        """Generate recommendation based on evaluation results

        Args:
            evaluation_passed: Whether all KPIs are met
            kpi_compliance: Dictionary of KPI compliance status
            metrics: Calculated metrics
            kpis: KPI thresholds

        Returns:
            Recommendation: "promote", "reject", or "optimize"
        """
        if evaluation_passed:
            return "promote"

        # Check if close to thresholds (within 20% for optimization opportunity)
        close_to_threshold = False
        for kpi_name, passed in kpi_compliance.items():
            if not passed:
                threshold = kpis[kpi_name]
                metric_value = metrics.get(kpi_name, 0.0)

                if kpi_name == "max_drawdown":
                    # For drawdown, check if within 20% above threshold
                    if abs(metric_value) <= abs(threshold) * 1.2:
                        close_to_threshold = True
                        break
                else:
                    # For other metrics, check if within 20% below threshold
                    if metric_value >= threshold * 0.8:
                        close_to_threshold = True
                        break

        # Check critical failures (very bad metrics)
        critical_failures = False
        for kpi_name, passed in kpi_compliance.items():
            if not passed:
                threshold = kpis[kpi_name]
                metric_value = metrics.get(kpi_name, 0.0)

                if kpi_name == "max_drawdown":
                    # Critical: drawdown > 2x threshold
                    if abs(metric_value) > abs(threshold) * 2.0:
                        critical_failures = True
                        break
                elif kpi_name == "profit_factor":
                    # Critical: profit factor < 1.0 (losing money)
                    if metric_value < 1.0:
                        critical_failures = True
                        break
                elif kpi_name == "sharpe_ratio":
                    # Critical: negative Sharpe (negative returns)
                    if metric_value < 0:
                        critical_failures = True
                        break

        if critical_failures:
            return "reject"

        if close_to_threshold:
            return "optimize"

        # Default: reject if not close to threshold
        return "reject"

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle incoming A2A message"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow=message.flow_id):
            try:
                payload = message.payload

                if isinstance(payload, EvaluationRequest):
                    # EvaluationRequest alone is not enough - need BacktestResultsResponse
                    # This should be called programmatically with both request and results
                    error = self.create_error_response(
                        "INVALID_REQUEST",
                        "EvaluationRequest requires BacktestResultsResponse. Use evaluate() method directly.",
                        details={"payload_type": str(type(payload))},
                    )
                    return self.create_message(to_agent=message.from_agent, flow_id=message.flow_id, payload=error)

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
            self.logger.info("EvaluatorAgent closed")



