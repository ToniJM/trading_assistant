"""Backtest configuration and preset configs"""
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

# Note: These imports are not used in this module but kept for consistency
# from trading.infrastructure.logging import get_backtest_logger, get_logger

# For backwards compatibility with BacktestRunner imports
LOG_LEVEL = "INFO"  # Will be read from env in actual logger

# Minimal backtest mode functions (simplified for now)
BACKTEST_MODE = False


def set_backtest_mode(enabled: bool):
    """Activate/deactivate backtest mode for logging optimization"""
    global BACKTEST_MODE
    BACKTEST_MODE = enabled


def is_backtest_mode() -> bool:
    """Check if we're in backtest mode"""
    return BACKTEST_MODE


def disable_logging_for_backtest():
    """Disable verbose logging during backtest to improve performance"""
    set_backtest_mode(True)


def enable_logging_after_backtest():
    """Re-enable normal logging after backtest"""
    set_backtest_mode(False)


@dataclass
class BacktestConfig:
    """Backtest configuration"""

    symbol: str
    start_time: int
    end_time:[int] = None
    initial_balance: Decimal = Decimal("2500")
    leverage: Decimal = Decimal("100")
    maker_fee: Decimal = Decimal("0.0002")
    taker_fee: Decimal = Decimal("0.0005")
    max_notional: Decimal = Decimal("50000")
    enable_frontend: bool = False
    progress_callback:[Callable] = None
    stop_on_loss: bool = True
    max_loss_percentage: float = 0.5  # 50% max loss
    strategy_name: str = "default"
    track_cycles: bool = True
    log_filename:[str] = None  # Auto-generated if None
    run_id:[str] = None  # Run ID for logging to runs/ directory


@dataclass
class BacktestResults:
    """Backtest results"""

    start_time: int
    end_time: int
    duration_seconds: float
    total_candles_processed: int
    final_balance: Decimal
    total_return: Decimal
    return_percentage: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    profit_factor: float

    # Additional fields
    total_closed_positions: int
    winning_positions: int
    losing_positions: int
    average_trade_size: Decimal
    total_commission: Decimal
    commission_percentage: float

    # Closing trade details
    total_closing_trades: int
    partial_closing_trades: int
    full_closing_trades: int
    winning_closing_trades: int
    losing_closing_trades: int
    partial_winning_trades: int
    partial_losing_trades: int
    full_winning_trades: int
    full_losing_trades: int

    # Cycle statistics
    total_cycles: int
    avg_cycle_duration: float
    avg_cycle_pnl: float
    winning_cycles: int
    losing_cycles: int
    cycle_win_rate: float

    # Metadata
    strategy_name: str = ""
    symbol: str = ""


class BacktestConfigs:
    """Predefined configurations for different types of backtests"""

    @staticmethod
    def get_quick_test_config() -> dict:
        """Configuration for quick test (1 day)"""
        return {
            "symbol": "BTCUSDT",
            "start_time": 1744023500000,  # Specific date
            "end_time": 1744023500000 + (24 * 60 * 60 * 1000),  # +1 day
            "initial_balance": Decimal("2500"),
            "leverage": Decimal("100"),
            "maker_fee": Decimal("0.0002"),
            "taker_fee": Decimal("0.0005"),
            "max_notional": Decimal("50000"),
            "enable_frontend": False,
            "stop_on_loss": True,
            "max_loss_percentage": 0.1,  # 10% max loss
        }

    @staticmethod
    def get_2hour_test_config() -> dict:
        """Configuration for 2-hour quick test"""
        return {
            "symbol": "BTCUSDT",
            "start_time": 1744023500000,  # Specific date
            "end_time": 1744023500000 + (2 * 60 * 60 * 1000),  # +2 hours
            "initial_balance": Decimal("2500"),
            "leverage": Decimal("100"),
            "maker_fee": Decimal("0.0002"),
            "taker_fee": Decimal("0.0005"),
            "max_notional": Decimal("50000"),
            "enable_frontend": False,
            "stop_on_loss": True,
            "max_loss_percentage": 0.05,  # 5% max loss
        }

