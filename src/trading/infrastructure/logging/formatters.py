"""Formatters for structured logging with ADK context"""
import json
import logging
from typing import Any

from colorlog import ColoredFormatter

from .context import LoggingContext


class ADKFormatter(logging.Formatter):
    """Formatter that includes ADK context (run_id, agent, flow) in logs"""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None, include_context: bool = True):
        if fmt is None:
            fmt = "%(asctime)s [%(levelname)s] %(name)s"
            if include_context:
                fmt += " [run_id=%(run_id)s] [agent=%(agent)s] [flow=%(flow)s]"
            fmt += " - %(message)s"

        super().__init__(fmt=fmt, datefmt=datefmt)
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with ADK context"""
        ctx = LoggingContext.get_context()

        if self.include_context:
            record.run_id = ctx.get("run_id", "-")
            record.agent = ctx.get("agent", "-")
            record.flow = ctx.get("flow", "-")
        else:
            record.run_id = "-"
            record.agent = "-"
            record.flow = "-"

        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging (optional, for observability tools)"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        ctx = LoggingContext.get_context()

        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add ADK context
        if ctx:
            log_data.update(ctx)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, ensure_ascii=False)


class ColoredADKFormatter(ColoredFormatter):
    """Colored formatter with ADK context for console output"""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None, include_context: bool = True):
        if fmt is None:
            fmt = "%(log_color)s%(asctime)s [%(levelname)s] %(name)s"
            if include_context:
                fmt += " [run_id=%(run_id)s] [agent=%(agent)s] [flow=%(flow)s]"
            fmt += " - %(message)s"

        super().__init__(
            fmt=fmt,
            datefmt=datefmt,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with ADK context"""
        ctx = LoggingContext.get_context()

        if self.include_context:
            record.run_id = ctx.get("run_id", "-")
            record.agent = ctx.get("agent", "-")
            record.flow = ctx.get("flow", "-")
        else:
            record.run_id = "-"
            record.agent = "-"
            record.flow = "-"

        return super().format(record)

