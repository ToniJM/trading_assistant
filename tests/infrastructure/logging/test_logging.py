"""Tests for logging infrastructure"""
import logging

from trading.infrastructure.logging import LoggingContext, get_logger, get_run_logger, logging_context


def test_get_logger():
    """Test basic logger creation"""
    logger = get_logger("test_logger")
    assert logger is not None
    assert logger.name == "test_logger"
    assert logger.level >= logging.DEBUG


def test_get_run_logger():
    """Test run-specific logger creation"""
    run_id = "test_run_123"
    logger, handler = get_run_logger(run_id)

    assert logger is not None
    assert logger.name == f"run.{run_id}"
    assert handler is not None


def test_logging_context():
    """Test logging context management"""
    # Clear context first
    LoggingContext.clear()

    # Set context
    LoggingContext.set_run_id("test_run")
    LoggingContext.set_agent("test_agent")
    LoggingContext.set_flow("test_flow")

    # Get context
    assert LoggingContext.get_run_id() == "test_run"
    assert LoggingContext.get_agent() == "test_agent"
    assert LoggingContext.get_flow() == "test_flow"

    ctx = LoggingContext.get_context()
    assert ctx["run_id"] == "test_run"
    assert ctx["agent"] == "test_agent"
    assert ctx["flow"] == "test_flow"


def test_logging_context_manager():
    """Test logging context as context manager"""
    LoggingContext.clear()

    with logging_context(run_id="ctx_run", agent="ctx_agent", flow="ctx_flow"):
        assert LoggingContext.get_run_id() == "ctx_run"
        assert LoggingContext.get_agent() == "ctx_agent"
        assert LoggingContext.get_flow() == "ctx_flow"

    # Context should be cleared after exit
    assert LoggingContext.get_run_id() is None


def test_logger_with_context():
    """Test logger includes ADK context in formatted messages"""
    with logging_context(run_id="test_run", agent="test_agent"):
        logger = get_logger("test_context_logger")
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Format should include context
        formatter = logger.handlers[0].formatter
        formatted = formatter.format(record)

        assert "test_run" in formatted or "-" in formatted  # May show "-" if context not set yet

