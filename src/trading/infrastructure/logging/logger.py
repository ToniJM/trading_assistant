"""Main logging module with daily and run-specific loggers"""
import logging
import os
import time

from dotenv import load_dotenv

from .formatters import ColoredADKFormatter
from .handlers import (
    APILogFilter,
    BacktestLogFilter,
    DailyRotatingFileHandler,
    RunRoutingHandler,
    RunSpecificFileHandler,
)

# Load configuration from .env
load_dotenv()

# Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE_BASENAME = os.getenv("LOG_FILE_BASENAME", "app.log")
LOG_ROTATION_TIME = os.getenv("LOG_ROTATION_TIME", "midnight")
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 7))
LOG_RUN_DIR = os.getenv("LOG_RUN_DIR", "logs/runs")
LOG_TO_CONSOLE = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"

# External libraries to silence
EXTERNAL_LIBRARIES = ["websockets", "urllib3", "binance", "asyncio", "urllib3.connectionpool"]

DATEFMT = "%Y-%m-%d %H:%M:%S"

# Global handlers (shared across loggers)
_daily_handler: DailyRotatingFileHandler | None = None
_console_handler: logging.StreamHandler | None = None
_run_routing_handler: logging.Handler | None = None
_global_run_handler: RunSpecificFileHandler | None = None

# Global run_id for the current execution (generated automatically)
_global_run_id: str | None = None

# Run-specific loggers (one per run_id) - kept for backward compatibility
_run_loggers: dict[str, tuple[logging.Logger, RunSpecificFileHandler]] = {}


def setup_logging():
    """Initialize logging infrastructure"""
    global _daily_handler, _console_handler, _run_routing_handler, _global_run_handler, _global_run_id

    # Generate global run_id for this execution (timestamp-based)
    if _global_run_id is None:
        _global_run_id = str(int(time.time() * 1000))

    # Create daily rotating handler
    _daily_handler = DailyRotatingFileHandler(
        log_dir=LOG_DIR,
        log_basename=LOG_FILE_BASENAME,
        when=LOG_ROTATION_TIME,
        backup_count=LOG_BACKUP_COUNT,
    )
    # Add filters to exclude backtest.* logs and verbose API logs from daily handler
    _daily_handler.addFilter(BacktestLogFilter())
    _daily_handler.addFilter(APILogFilter())

    # Create console handler with colors
    if LOG_TO_CONSOLE:
        _console_handler = logging.StreamHandler()
        _console_handler.setFormatter(ColoredADKFormatter(include_context=True))

    # Create global run handler that captures ALL logs (same content as app.log)
    if _global_run_handler is None:
        _global_run_handler = RunSpecificFileHandler(log_dir=LOG_RUN_DIR, run_id=_global_run_id)
        # Apply same filters as app.log
        _global_run_handler.addFilter(BacktestLogFilter())
        _global_run_handler.addFilter(APILogFilter())
        _global_run_handler.setLevel(getattr(logging, LOG_LEVEL))

    # Create routing handler for run logs (kept for backward compatibility)
    _run_routing_handler = RunRoutingHandler()
    _run_routing_handler.setLevel(getattr(logging, LOG_LEVEL))
    _run_routing_handler.addFilter(APILogFilter())  # Exclude verbose API logs from run logs too
    _run_routing_handler.set_run_loggers(_run_loggers)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))
    root_logger.addHandler(_daily_handler)
    if _console_handler:
        root_logger.addHandler(_console_handler)
    # Note: _global_run_handler is added to individual loggers, not root logger
    # This ensures all logs go to the run file without duplication
    # Add routing handler for backward compatibility (deprecated)
    root_logger.addHandler(_run_routing_handler)
    root_logger.propagate = False

    # Silence external libraries (especially urllib3 to prevent HTTP logging)
    for lib in EXTERNAL_LIBRARIES:
        lib_logger = logging.getLogger(lib)
        lib_logger.setLevel(logging.WARNING)
        lib_logger.propagate = False

    # Explicitly silence urllib3.connectionpool to prevent HTTP request/response logging
    urllib3_connectionpool = logging.getLogger("urllib3.connectionpool")
    urllib3_connectionpool.setLevel(logging.WARNING)
    urllib3_connectionpool.propagate = False


def get_logger(name: str, level: int | None = None) -> logging.Logger:
    """
    Get a logger that writes to daily log file and optionally console.
    All loggers share the same daily handler for consistency.

    Args:
        name: Logger name (typically __name__ or class name)
        level: log level (defaults to LOG_LEVEL from env)

    Returns:
        Logger instance configured with daily handler
    """
    if _daily_handler is None:
        setup_logging()

    logger = logging.getLogger(name)
    logger.handlers.clear()

    if level is None:
        level = getattr(logging, LOG_LEVEL)

    logger.setLevel(level)
    logger.addHandler(_daily_handler)

    # Add global run handler to capture all logs in run file
    if _global_run_handler:
        logger.addHandler(_global_run_handler)

    if _console_handler and LOG_TO_CONSOLE:
        logger.addHandler(_console_handler)

    logger.propagate = False

    return logger


def get_debug_logger(name: str) -> logging.Logger:
    """
    Get a logger specifically for debugging that always uses DEBUG level.
    This logger will always show DEBUG level logs regardless of LOG_LEVEL configuration.

    Args:
        name: Logger name (typically includes ".debug" suffix)

    Returns:
        Logger instance configured with DEBUG level always
    """
    if _daily_handler is None:
        setup_logging()

    logger = logging.getLogger(name)
    logger.handlers.clear()

    # Always set to DEBUG level for debug loggers
    logger.setLevel(logging.DEBUG)
    logger.addHandler(_daily_handler)

    # Add global run handler to capture all logs in run file
    if _global_run_handler:
        logger.addHandler(_global_run_handler)

    if _console_handler and LOG_TO_CONSOLE:
        logger.addHandler(_console_handler)

    logger.propagate = False

    return logger


def get_run_logger(run_id: str, level: int | None = None) -> tuple[logging.Logger, RunSpecificFileHandler]:
    """
    Get or create a logger specific to a run_id.
    This logger writes to a dedicated file: logs/runs/run_{run_id}.log

    Args:
        run_id: Unique identifier for the run/execution
        level: log level (defaults to LOG_LEVEL from env)

    Returns:
        Tuple of (logger, handler) - handler can be used for cleanup
    """
    if _daily_handler is None:
        setup_logging()

    # Return existing logger if already created
    if run_id in _run_loggers:
        return _run_loggers[run_id]

    # Create new run-specific handler
    run_handler = RunSpecificFileHandler(log_dir=LOG_RUN_DIR, run_id=run_id)

    # Create logger for this run
    logger_name = f"run.{run_id}"
    logger = logging.getLogger(logger_name)

    if level is None:
        level = getattr(logging, LOG_LEVEL)

    logger.setLevel(level)
    logger.addHandler(run_handler)

    # Also add daily handler so it appears in both logs
    logger.addHandler(_daily_handler)

    # Add global run handler to capture all logs in run file
    if _global_run_handler:
        logger.addHandler(_global_run_handler)

    if _console_handler and LOG_TO_CONSOLE:
        logger.addHandler(_console_handler)

    logger.propagate = False

    # Store for reuse
    _run_loggers[run_id] = (logger, run_handler)

    # Update routing handler with new run logger
    if _run_routing_handler:
        _run_routing_handler.set_run_loggers(_run_loggers)

    return logger, run_handler


def get_global_run_id() -> str | None:
    """
    Get the global run_id for the current execution.
    This run_id is automatically generated when logging is initialized.

    Returns:
        The global run_id string, or None if logging hasn't been initialized
    """
    if _daily_handler is None:
        setup_logging()
    return _global_run_id


def get_backtest_logger(
    backtest_name: str, log_dir: str = "logs/backtests"
) -> tuple[logging.Logger, logging.FileHandler]:
    """
    Create logger specific for a backtest (legacy support).
    Similar to get_run_logger but for backtest-specific naming.

    Args:
        backtest_name: Name of the backtest (can include subdirectories)
        log_dir: Base directory for backtest logs

    Returns:
        Tuple of (logger, handler) for cleanup
    """
    if _daily_handler is None:
        setup_logging()

    # Build full log path including subdirectories
    full_log_path = os.path.join(log_dir, backtest_name)
    os.makedirs(os.path.dirname(full_log_path), exist_ok=True)
    log_path = f"{full_log_path}.log"

    # Create handler specific to this backtest
    backtest_handler = logging.FileHandler(log_path, encoding="utf-8")
    backtest_handler.setFormatter(_daily_handler.formatter)

    # Create logger unique to this backtest
    logger_name = f"backtest.{backtest_name}"
    logger = logging.getLogger(logger_name)

    level = getattr(logging, LOG_LEVEL)
    logger.setLevel(level)
    logger.addHandler(backtest_handler)

    # Do NOT add daily handler or console handler - backtest logs only go to their specific file
    # This prevents backtest internal logs from appearing in app.log and runs/

    logger.propagate = False

    return logger, backtest_handler


# Initialize logging on import
setup_logging()

