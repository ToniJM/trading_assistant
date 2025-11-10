"""Scheduler configuration"""

from pydantic import BaseModel, Field


class SchedulerConfig(BaseModel):
    """Configuration for SchedulerAgent"""

    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    strategy_name: str = Field(..., description="Strategy name")
    schedule_interval_seconds: int = Field(3600, ge=60, description="Interval between executions in seconds (default: 1 hour)")
    backtest_duration_days: int = Field(30, ge=1, le=365, description="Duration of each backtest in days (default: 30)")
    max_iterations_per_cycle: int = Field(5, ge=1, le=20, description="Maximum optimization iterations per cycle")
    max_overlap_percentage: float = Field(20.0, ge=0.0, le=100.0, description="Maximum overlap percentage allowed for same parameter combination (default: 20.0)")
    kpis: dict[str, float] = Field(
        default_factory=lambda: {"sharpe_ratio": 2.0, "max_drawdown": 10.0, "profit_factor": 1.5},
        description="KPI thresholds",
    )
    auto_reset_memory: bool = Field(True, description="Reset episodic memory daily")
    initial_balance: float = Field(2500.0, ge=0, description="Initial balance for backtests")
    leverage: float = Field(100.0, ge=1, description="Leverage for backtests")
    backtests_per_period: int = Field(10, ge=1, description="Number of backtests per period (default: 10)")
    min_passed_backtests_per_period: int = Field(
        10, ge=1, description="Minimum number of backtests that must pass KPIs to advance to next period (default: 10)"
    )
    incremental_periods: list[int] = Field(
        default_factory=lambda: [1, 7, 30, 90],
        description="Incremental periods in days: [1 day, 1 week, 1 month, 3 months]",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "strategy_name": "carga_descarga",
                "schedule_interval_seconds": 3600,
                "backtest_duration_days": 30,
                "max_iterations_per_cycle": 5,
                "max_overlap_percentage": 20.0,
                "kpis": {"sharpe_ratio": 2.0, "max_drawdown": 10.0, "profit_factor": 1.5},
                "auto_reset_memory": True,
                "backtests_per_period": 10,
                "min_passed_backtests_per_period": 10,
                "incremental_periods": [1, 7, 30, 90],
            }
        }
    }

