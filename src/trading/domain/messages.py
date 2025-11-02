"""Pydantic contracts for A2A messaging between agents"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class StartBacktestRequest(BaseModel):
    """Request to start a backtest"""

    run_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique run identifier")
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    start_time: int = Field(..., description="Start timestamp in milliseconds")
    end_time: int | None = Field(None, description="End timestamp in milliseconds (None = current time)")
    initial_balance: Decimal = Field(Decimal("2500"), description="Initial account balance")
    leverage: Decimal = Field(Decimal("100"), description="Leverage")
    maker_fee: Decimal = Field(Decimal("0.0002"), description="Maker fee rate")
    taker_fee: Decimal = Field(Decimal("0.0005"), description="Taker fee rate")
    max_notional: Decimal = Field(Decimal("50000"), description="Maximum notional value")
    strategy_name: str = Field("default", description="Strategy name")
    stop_on_loss: bool = Field(True, description="Stop backtest if loss threshold reached")
    max_loss_percentage: float = Field(0.5, description="Maximum loss percentage (0.5 = 50%)")
    track_cycles: bool = Field(True, description="Track trading cycles")
    timeframes: list[str] = Field(
        default_factory=lambda: ["1m", "15m", "1h"],
        description="List of timeframes to use (e.g., ['1m', '15m', '1h'])",
    )
    rsi_limits: list[int] | None = Field(
        None,
        description="RSI threshold values [low, medium, high]. Must be 3 values in range 0-100. Default: [15, 50, 85]",
    )

    @field_validator("rsi_limits")
    @classmethod
    def validate_rsi_limits(cls, v: list[int] | None) -> list[int] | None:
        """Validate RSI limits: must be exactly 3 values, all in range 0-100"""
        if v is None:
            return v
        if len(v) != 3:
            raise ValueError(f"rsi_limits must have exactly 3 values, got {len(v)}")
        if not all(0 <= val <= 100 for val in v):
            raise ValueError(f"All rsi_limits values must be in range 0-100, got {v}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "symbol": "BTCUSDT",
                "start_time": 1744023500000,
                "end_time": 1744109900000,
                "initial_balance": "2500",
                "leverage": "100",
                "strategy_name": "carga_descarga",
                "timeframes": ["1m", "15m", "1h"],
            }
        }
    )


class BacktestStatusUpdate(BaseModel):
    """Status update during backtest execution"""

    run_id: str = Field(..., description="Run identifier")
    status: str = Field(..., description="Status: running, paused, completed, failed")
    candles_processed: int = Field(0, description="Number of candles processed")
    current_balance: Decimal = Field(..., description="Current account balance")
    execution_time_seconds: float = Field(0, description="Execution time in seconds")
    candles_per_second: float = Field(0, description="Processing rate")

    @field_serializer("current_balance")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class BacktestResultsResponse(BaseModel):
    """Response with backtest results"""

    run_id: str = Field(..., description="Run identifier")
    status: str = Field(..., description="Final status: completed, failed, stopped")
    start_time: int = Field(..., description="Start timestamp")
    end_time: int = Field(..., description="End timestamp")
    duration_seconds: float = Field(..., description="Total duration in seconds")

    # Basic metrics
    total_candles_processed: int = Field(..., description="Total candles processed")
    final_balance: Decimal = Field(..., description="Final account balance")
    total_return: Decimal = Field(..., description="Total return (PnL)")
    return_percentage: float = Field(..., description="Return percentage")
    max_drawdown: float = Field(..., description="Maximum drawdown percentage")

    # Trading metrics
    total_trades: int = Field(..., description="Total number of trades")
    win_rate: float = Field(..., description="Win rate percentage")
    profit_factor: float = Field(..., description="Profit factor")

    # Position metrics
    total_closed_positions: int = Field(..., description="Total closed positions")
    winning_positions: int = Field(..., description="Winning positions count")
    losing_positions: int = Field(..., description="Losing positions count")

    # Commission metrics
    total_commission: Decimal = Field(..., description="Total commission paid")
    commission_percentage: float = Field(..., description="Commission as percentage of return")

    # Cycle metrics
    total_cycles: int = Field(0, description="Total trading cycles")
    avg_cycle_duration: float = Field(0, description="Average cycle duration in minutes")
    avg_cycle_pnl: Decimal = Field(Decimal(0), description="Average cycle PnL")
    winning_cycles: int = Field(0, description="Winning cycles count")
    losing_cycles: int = Field(0, description="Losing cycles count")
    cycle_win_rate: float = Field(0, description="Cycle win rate percentage")

    # Metadata
    strategy_name: str = Field(..., description="Strategy name used")
    symbol: str = Field(..., description="Trading symbol")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "total_trades": 100,
                "win_rate": 65.0,
                "profit_factor": 1.5,
                "final_balance": "2600",
                "total_return": "100",
            }
        }
    )

    @field_serializer("final_balance", "total_return", "total_commission", "avg_cycle_pnl")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class OptimizationRequest(BaseModel):
    """Request to optimize strategy parameters"""

    run_id: str = Field(default_factory=lambda: str(uuid4()), description="Optimization run identifier")
    strategy_name: str = Field(..., description="Strategy to optimize")
    symbol: str = Field(..., description="Trading symbol")
    parameter_space: dict[str, list[float]] = Field(..., description="Parameter space to explore")
    objective: str = Field("sharpe_ratio", description="Optimization objective: sharpe_ratio, profit_factor, etc.")
    backtest_config: StartBacktestRequest | None = Field(None, description="Base backtest configuration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "opt-550e8400-e29b-41d4-a716-446655440000",
                "strategy_name": "carga_descarga",
                "symbol": "BTCUSDT",
                "parameter_space": {
                    "entry_threshold": [0.01, 0.02, 0.03],
                    "exit_threshold": [0.005, 0.01, 0.015],
                },
                "objective": "sharpe_ratio",
            }
        }
    )


class EvaluationRequest(BaseModel):
    """Request to evaluate backtest results"""

    run_id: str = Field(..., description="Run identifier to evaluate")
    metrics: list[str] | None = Field(None, description="Specific metrics to evaluate (None = all metrics)")
    kpis: dict[str, float] | None = Field(
        None,
        description="KPIs to check: {'sharpe_ratio': 2.0, 'max_drawdown': 0.1, 'profit_factor': 1.5}",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "metrics": ["sharpe_ratio", "max_drawdown"],
                "kpis": {"sharpe_ratio": 2.0, "max_drawdown": 0.1},
            }
        }
    )


class EvaluationResponse(BaseModel):
    """Response with evaluation results"""

    run_id: str = Field(..., description="Run identifier")
    evaluation_passed: bool = Field(..., description="Whether KPIs are met")
    metrics: dict[str, float] = Field(..., description="Calculated metrics")
    kpi_compliance: dict[str, bool] = Field(..., description="KPI compliance status")
    recommendation: str = Field(..., description="Recommendation: promote, reject, optimize")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "evaluation_passed": True,
                "metrics": {"sharpe_ratio": 2.1, "max_drawdown": 0.08},
                "kpi_compliance": {"sharpe_ratio": True, "max_drawdown": True},
                "recommendation": "promote",
            }
        }
    )


class AgentMessage(BaseModel):
    """Base message wrapper for agent communication"""

    message_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique message identifier")
    from_agent: str = Field(..., description="Sender agent name")
    to_agent: str = Field(..., description="Receiver agent name")
    flow_id: str = Field(..., description="Flow identifier for traceability")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    payload: BaseModel = Field(..., description="Message payload (request/response)")

    @field_serializer("timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()


class ErrorResponse(BaseModel):
    """Error response for failed operations"""

    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    error_details: dict[str, Any] | None = Field(None, description="Additional error details")
    run_id: str | None = Field(None, description="Run identifier if applicable")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "INSUFFICIENT_BALANCE",
                "error_message": "Insufficient balance to execute order",
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        }
    )
