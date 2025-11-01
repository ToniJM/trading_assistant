"""Context management for ADK tracing (run_id, agent, flow)"""
import threading
from contextlib import contextmanager


class LoggingContext:
    """Thread-local storage for logging context"""

    _thread_local = threading.local()

    @classmethod
    def set_run_id(cls, run_id: str):
        """Set the current run_id"""
        cls._thread_local.run_id = run_id

    @classmethod
    def get_run_id(cls) -> str | None:
        """Get the current run_id"""
        return getattr(cls._thread_local, "run_id", None)

    @classmethod
    def set_agent(cls, agent: str):
        """Set the current agent"""
        cls._thread_local.agent = agent

    @classmethod
    def get_agent(cls) -> str | None:
        """Get the current agent"""
        return getattr(cls._thread_local, "agent", None)

    @classmethod
    def set_flow(cls, flow: str):
        """Set the current flow"""
        cls._thread_local.flow = flow

    @classmethod
    def get_flow(cls) -> str | None:
        """Get the current flow"""
        return getattr(cls._thread_local, "flow", None)

    @classmethod
    def clear(cls):
        """Clear all context"""
        if hasattr(cls._thread_local, "run_id"):
            delattr(cls._thread_local, "run_id")
        if hasattr(cls._thread_local, "agent"):
            delattr(cls._thread_local, "agent")
        if hasattr(cls._thread_local, "flow"):
            delattr(cls._thread_local, "flow")

    @classmethod
    def get_context(cls) -> dict:
        """Get current context as dictionary"""
        ctx = {}
        run_id = cls.get_run_id()
        agent = cls.get_agent()
        flow = cls.get_flow()

        if run_id:
            ctx["run_id"] = run_id
        if agent:
            ctx["agent"] = agent
        if flow:
            ctx["flow"] = flow

        return ctx


@contextmanager
def logging_context(run_id: str | None = None, agent: str | None = None, flow: str | None = None):
    """Context manager for setting logging context"""
    old_run_id = LoggingContext.get_run_id()
    old_agent = LoggingContext.get_agent()
    old_flow = LoggingContext.get_flow()

    try:
        if run_id:
            LoggingContext.set_run_id(run_id)
        if agent:
            LoggingContext.set_agent(agent)
        if flow:
            LoggingContext.set_flow(flow)
        yield
    finally:
        LoggingContext.clear()
        if old_run_id:
            LoggingContext.set_run_id(old_run_id)
        if old_agent:
            LoggingContext.set_agent(old_agent)
        if old_flow:
            LoggingContext.set_flow(old_flow)

