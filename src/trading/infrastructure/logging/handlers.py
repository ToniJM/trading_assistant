"""Custom handlers for daily and run-specific logs"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler

from .context import LoggingContext
from .formatters import ADKFormatter


class DailyRotatingFileHandler(TimedRotatingFileHandler):
    """Handler for daily rotating log files"""

    def __init__(self, log_dir: str, log_basename: str = "app.log", when: str = "midnight", backup_count: int = 7):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = os.path.join(log_dir, log_basename)

        super().__init__(
            filename=log_filename,
            when=when,
            interval=1,
            backupCount=backup_count,
            encoding="utf-8",
            utc=False,
        )

        self.setFormatter(ADKFormatter(include_context=True))


class RunSpecificFileHandler(logging.FileHandler):
    """Handler for run-specific log files (one per execution)"""

    def __init__(self, log_dir: str, run_id: str):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = os.path.join(log_dir, f"run_{run_id}.log")

        super().__init__(filename=log_filename, encoding="utf-8", mode="w")

        self.setFormatter(ADKFormatter(include_context=True))


class RunRoutingHandler(logging.Handler):
    """Handler that routes logs to run-specific loggers based on LoggingContext

    NOTE: This handler is kept for backward compatibility but is deprecated.
    The new approach uses a global run handler that captures all logs.
    """

    def __init__(self):
        super().__init__()
        self._run_loggers = {}

    def set_run_loggers(self, run_loggers: dict):
        """Set the dictionary of run loggers to route to"""
        self._run_loggers = run_loggers

    def emit(self, record: logging.LogRecord):
        """Route log record to appropriate run logger if run_id exists in context

        NOTE: This method is kept for backward compatibility but is deprecated.
        """
        run_id = LoggingContext.get_run_id()
        if run_id and run_id in self._run_loggers:
            run_logger, _ = self._run_loggers[run_id]
            # Emit to run logger (which will handle formatting and writing)
            run_logger.handle(record)


class BacktestLogFilter(logging.Filter):
    """Filter to exclude logs from backtest.* loggers from the daily handler"""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out logs from backtest.* loggers"""
        # Exclude logs from loggers starting with "backtest."
        if record.name.startswith("backtest."):
            return False
        return True


class APILogFilter(logging.Filter):
    """Filter to exclude verbose API response logs (URLs, large JSON responses)"""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out verbose API logs"""
        message = record.getMessage()

        # Exclude logs with URLs (API calls)
        if "url:" in message.lower() and ("http://" in message or "https://" in message):
            return False

        # Exclude very long messages (likely JSON responses or large data dumps)
        # Messages longer than 1000 characters are likely API responses
        if len(message) > 1000:
            return False

        # Exclude logs from root logger at DEBUG level that might be API-related
        if record.name == "root" and record.levelno == logging.DEBUG:
            # Common patterns that indicate API logging
            api_patterns = ["url:", "response", "request", "api", "json", "exchange_info"]
            if any(pattern in message.lower() for pattern in api_patterns):
                return False

        return True

