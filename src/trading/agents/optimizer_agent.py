"""Optimizer Agent - Uses AI to optimize strategy parameters"""
import json
from typing import Any

from trading.domain.messages import (
    AgentMessage,
    BacktestResultsResponse,
    OptimizationRequest,
    OptimizationResult,
)
from trading.infrastructure.llm import get_groq_client
from trading.infrastructure.logging import logging_context

from .base_agent import BaseAgent


class OptimizerAgent(BaseAgent):
    """Agent that optimizes strategy parameters using AI

    Role: Adjust strategy parameters based on feedback using LLM
    Tools: Groq LLM client, episodic memory (backtest history)
    Memory: Stores optimization history, context from previous backtests
    Policies: Max optimization iterations, min confidence threshold
    """

    def __init__(self, run_id: str | None = None):
        super().__init__(agent_name="optimizer", run_id=run_id)

        # Policies
        self.policies = {
            "max_optimization_iterations": {"max": 5},
            "min_confidence_threshold": {"min": 0.5},
        }

        # LLM client (lazy initialization)
        self._llm_client = None

    def initialize(self) -> "OptimizerAgent":
        """Initialize the optimizer agent"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow="init"):
            try:
                # Initialize LLM client (will raise if GROQ_API_KEY not set)
                self._llm_client = get_groq_client()
                self.logger.info("OptimizerAgent initialized with LLM client")
            except ValueError as e:
                self.logger.warning(
                    f"LLM client not available: {e}. OptimizerAgent will use fallback optimization."
                )
                self._llm_client = None

            self.store_memory("initialized", True)
            return self

    def optimize(
        self,
        request: OptimizationRequest,
        previous_results: list[BacktestResultsResponse] | None = None,
    ) -> OptimizationResult:
        """Optimize strategy parameters using AI analysis

        Args:
            request: Optimization request with strategy and parameter space
            previous_results: List of previous backtest results for context

        Returns:
            OptimizationResult with suggested parameters and reasoning

        Raises:
            ValueError: If LLM client not available and no fallback possible
        """
        with logging_context(run_id=request.run_id, agent=self.agent_name, flow="optimize"):
            try:
                if self._llm_client is None:
                    # Fallback to basic deterministic optimization
                    return self._fallback_optimize(request, previous_results)

                # Build prompt with context
                prompt = self._build_optimization_prompt(request, previous_results or [])

                # Call LLM
                self.logger.info(f"Calling LLM for optimization (strategy={request.strategy_name})")
                llm_response = self._llm_client.chat_json(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert quantitative trading strategy optimizer. "
                            "Analyze backtest results and suggest parameter improvements based on patterns.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,  # Lower temperature for more deterministic optimization
                    max_tokens=2048,
                )

                # Parse and validate response
                result = self._parse_llm_response(request, llm_response)

                # Store in memory
                self.store_memory(f"optimization_{request.run_id}", result)

                self.log_event(
                    "optimization_completed",
                    {
                        "run_id": request.run_id,
                        "strategy": request.strategy_name,
                        "confidence": result.confidence,
                        "flow_id": "optimize",
                    },
                )

                return result

            except Exception as e:
                self.logger.error(f"Error during optimization: {e}", exc_info=True)
                # Fallback to deterministic optimization
                self.logger.warning("Falling back to deterministic optimization")
                return self._fallback_optimize(request, previous_results)

    def _build_optimization_prompt(
        self,
        request: OptimizationRequest,
        previous_results: list[BacktestResultsResponse],
    ) -> str:
        """Build structured prompt for LLM optimization

        Args:
            request: Optimization request
            previous_results: Previous backtest results for context

        Returns:
            Formatted prompt string
        """
        # Extract current parameters from backtest_config if available
        current_params = {}
        if request.backtest_config:
            if request.backtest_config.rsi_limits:
                current_params["rsi_limits"] = request.backtest_config.rsi_limits
            if request.backtest_config.timeframes:
                current_params["timeframes"] = request.backtest_config.timeframes

        # Build context from previous results
        context_summary = []
        if previous_results:
            # Import here to avoid circular dependency
            from trading.infrastructure.evaluation.metrics import extract_metrics_from_results

            for i, result in enumerate(previous_results[-5:], 1):  # Last 5 results
                # Extract advanced metrics including sharpe_ratio
                all_metrics = extract_metrics_from_results(result, calculate_advanced=True)

                # Get parameters from memory if available
                params = {}
                if request.backtest_config:
                    if request.backtest_config.rsi_limits:
                        params["rsi_limits"] = request.backtest_config.rsi_limits
                    if request.backtest_config.timeframes:
                        params["timeframes"] = request.backtest_config.timeframes

                context_summary.append(
                    {
                        "run": i,
                        "metrics": {
                            "sharpe_ratio": all_metrics.get("sharpe_ratio"),
                            "max_drawdown": result.max_drawdown,
                            "profit_factor": result.profit_factor,
                            "win_rate": result.win_rate,
                            "return_percentage": result.return_percentage,
                        },
                        "parameters": params,
                    }
                )

        prompt = f"""You are optimizing a trading strategy called "{request.strategy_name}" for symbol {request.symbol}.

OBJECTIVE: Maximize {request.objective}

CURRENT PARAMETERS:
{json.dumps(current_params, indent=2)}

PARAMETER SPACE (valid ranges):
{json.dumps(request.parameter_space, indent=2)}

HISTORICAL RESULTS:
{json.dumps(context_summary, indent=2) if context_summary else "No previous results available"}

STRATEGY CONTEXT:
- Strategy: {request.strategy_name}
- This is a "carga-descarga" (load-unload) strategy that uses RSI indicators
- RSI limits: [low, medium, high] where low < medium < high, all in range 0-100
- Timeframes: List of timeframes like ["1m", "15m", "1h"]
- Lower RSI thresholds = more aggressive entries (more trades, higher risk)
- Higher RSI thresholds = more conservative entries (fewer trades, lower risk)

TASK:
1. Analyze the historical results and identify patterns
2. Suggest optimized parameter values within the parameter space
3. Explain your reasoning based on the metrics
4. Estimate expected improvements for key metrics
5. Provide confidence level (0.0-1.0) for your suggestions

RESPONSE FORMAT (JSON only):
{{
  "optimized_parameters": {{
    "rsi_limits": [low, medium, high] or null,
    "timeframes": ["1m", "15m", "1h"] or null
  }},
  "reasoning": "Detailed explanation of why these parameters should improve performance",
  "confidence": 0.75,
  "expected_improvement": {{
    "sharpe_ratio": 0.3,
    "profit_factor": 0.2,
    "max_drawdown": -0.05
  }}
}}

IMPORTANT:
- Only suggest parameters that are in the parameter_space
- For rsi_limits: must be exactly 3 values, ascending order, all 0-100
- For timeframes: must be valid timeframe strings
- If a parameter shouldn't change, set it to null
- Be specific and data-driven in your reasoning
"""

        return prompt

    def _parse_llm_response(
        self, request: OptimizationRequest, llm_response: dict[str, Any]
    ) -> OptimizationResult:
        """Parse and validate LLM response

        Args:
            request: Original optimization request
            llm_response: Raw LLM response dict

        Returns:
            Validated OptimizationResult

        Raises:
            ValueError: If response is invalid
        """
        content = llm_response.get("content")
        if isinstance(content, dict):
            parsed = content
        else:
            # Try to parse as JSON if it's a string
            try:
                parsed = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in LLM response: {content}")

        # Extract fields
        optimized_params = parsed.get("optimized_parameters", {})
        reasoning = parsed.get("reasoning", "No reasoning provided")
        confidence = float(parsed.get("confidence", 0.5))
        expected_improvement = parsed.get("expected_improvement", {})

        # Validate parameters
        validated_params = self._validate_parameters(optimized_params, request.parameter_space)

        # Build metadata
        metadata = {
            "model": llm_response.get("model", "unknown"),
            "usage": llm_response.get("usage", {}),
            "finish_reason": llm_response.get("finish_reason", "unknown"),
        }

        return OptimizationResult(
            run_id=request.run_id,
            strategy_name=request.strategy_name,
            optimized_parameters=validated_params,
            reasoning=reasoning,
            confidence=max(0.0, min(1.0, confidence)),  # Clamp to [0, 1]
            expected_improvement=expected_improvement,
            metadata=metadata,
        )

    def _validate_parameters(
        self, suggested_params: dict[str, Any], parameter_space: dict[str, list[float]]
    ) -> dict[str, Any]:
        """Validate and sanitize suggested parameters

        Args:
            suggested_params: Parameters suggested by LLM
            parameter_space: Valid parameter space from request

        Returns:
            Validated parameters dict
        """
        validated: dict[str, Any] = {}

        # Validate RSI limits
        if "rsi_limits" in suggested_params and suggested_params["rsi_limits"] is not None:
            rsi_vals = suggested_params["rsi_limits"]
            if isinstance(rsi_vals, list) and len(rsi_vals) == 3:
                # Convert to int and validate range
                rsi_int = [int(v) for v in rsi_vals]
                if all(0 <= v <= 100 for v in rsi_int) and rsi_int[0] < rsi_int[1] < rsi_int[2]:
                    validated["rsi_limits"] = rsi_int
                else:
                    self.logger.warning(f"Invalid RSI limits from LLM: {rsi_vals}, ignoring")
            else:
                self.logger.warning(f"RSI limits must be list of 3 values, got: {rsi_vals}")

        # Validate timeframes
        if "timeframes" in suggested_params and suggested_params["timeframes"] is not None:
            timeframes = suggested_params["timeframes"]
            if isinstance(timeframes, list) and all(isinstance(tf, str) for tf in timeframes):
                # Validate timeframe format (basic check)
                valid_timeframes = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]
                if all(tf in valid_timeframes for tf in timeframes):
                    validated["timeframes"] = timeframes
                else:
                    self.logger.warning(f"Invalid timeframes from LLM: {timeframes}, ignoring")
            else:
                self.logger.warning(f"Timeframes must be list of strings, got: {timeframes}")

        # Check if any parameters from parameter_space are missing
        for param_name, valid_values in parameter_space.items():
            if param_name not in validated and param_name in suggested_params:
                # Try to validate against parameter space
                suggested_val = suggested_params[param_name]
                if isinstance(suggested_val, (int, float)) and suggested_val in valid_values:
                    validated[param_name] = suggested_val
                elif isinstance(suggested_val, list) and all(v in valid_values for v in suggested_val):
                    validated[param_name] = suggested_val

        if not validated:
            self.logger.warning("No valid parameters from LLM, using empty dict")

        return validated

    def _fallback_optimize(
        self,
        request: OptimizationRequest,
        previous_results: list[BacktestResultsResponse] | None,
    ) -> OptimizationResult:
        """Fallback deterministic optimization when LLM unavailable

        Args:
            request: Optimization request
            previous_results: Previous backtest results

        Returns:
            OptimizationResult with basic parameter adjustments
        """
        self.logger.info("Using fallback deterministic optimization")

        # Simple heuristic: if profit_factor < 1.5, lower RSI thresholds
        # If max_drawdown > 10%, raise RSI thresholds
        optimized_params: dict[str, Any] = {}

        if previous_results:
            latest = previous_results[-1]
            if latest.profit_factor < 1.5:
                # Lower RSI thresholds for more aggressive entries
                if "rsi_limits" in request.parameter_space:
                    current = request.backtest_config.rsi_limits if request.backtest_config else [15, 50, 85]
                    optimized_params["rsi_limits"] = [
                        max(5, current[0] - 5),
                        current[1],
                        min(95, current[2] + 5),
                    ]
            elif latest.max_drawdown > 10.0:
                # Raise RSI thresholds for more conservative entries
                if "rsi_limits" in request.parameter_space:
                    current = request.backtest_config.rsi_limits if request.backtest_config else [15, 50, 85]
                    optimized_params["rsi_limits"] = [
                        min(30, current[0] + 5),
                        current[1],
                        max(70, current[2] - 5),
                    ]

        reasoning = (
            "Fallback optimization: Adjusted RSI thresholds based on profit_factor and max_drawdown. "
            "Lower thresholds for better profit factor, higher thresholds for lower drawdown."
        )

        return OptimizationResult(
            run_id=request.run_id,
            strategy_name=request.strategy_name,
            optimized_parameters=optimized_params,
            reasoning=reasoning,
            confidence=0.4,  # Lower confidence for fallback
            expected_improvement={},
            metadata={"method": "fallback_deterministic"},
        )

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle incoming A2A message"""
        with logging_context(run_id=self.run_id, agent=self.agent_name, flow=message.flow_id):
            try:
                payload = message.payload

                if isinstance(payload, OptimizationRequest):
                    # OptimizationRequest alone is not enough - need previous_results
                    # This should be called programmatically with both request and results
                    error = self.create_error_response(
                        "INVALID_REQUEST",
                        "OptimizationRequest requires previous_results. Use optimize() method directly.",
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
            self.logger.info("OptimizerAgent closed")

