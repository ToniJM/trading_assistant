"""Tests for BacktestOperationsStatusRepository"""

import pytest

from trading.domain.types import ORDER_SIDE_TYPE, SIDE_TYPE
from trading.infrastructure.backtest.adapters.operations_status_repository import BacktestOperationsStatusRepository


@pytest.fixture
def operations_repo():
    """Create a BacktestOperationsStatusRepository instance"""
    return BacktestOperationsStatusRepository(symbol="BTCUSDT")


def test_initialization(operations_repo):
    """Test repository initialization"""
    assert operations_repo.symbol == "BTCUSDT"
    assert isinstance(operations_repo.operations, dict)
    assert "long" in operations_repo.operations
    assert "short" in operations_repo.operations
    assert "buy" in operations_repo.operations["long"]
    assert "sell" in operations_repo.operations["long"]
    assert "buy" in operations_repo.operations["short"]
    assert "sell" in operations_repo.operations["short"]


def test_initial_state_all_false(operations_repo):
    """Test initial state is all False"""
    assert operations_repo.get_operation_status("long", "buy") is False
    assert operations_repo.get_operation_status("long", "sell") is False
    assert operations_repo.get_operation_status("short", "buy") is False
    assert operations_repo.get_operation_status("short", "sell") is False


def test_set_operation_status_long_buy(operations_repo):
    """Test set_operation_status for long buy"""
    operations_repo.set_operation_status("long", "buy", True)

    assert operations_repo.get_operation_status("long", "buy") is True
    assert operations_repo.get_operation_status("long", "sell") is False
    assert operations_repo.get_operation_status("short", "buy") is False
    assert operations_repo.get_operation_status("short", "sell") is False


def test_set_operation_status_long_sell(operations_repo):
    """Test set_operation_status for long sell"""
    operations_repo.set_operation_status("long", "sell", True)

    assert operations_repo.get_operation_status("long", "sell") is True
    assert operations_repo.get_operation_status("long", "buy") is False


def test_set_operation_status_short_buy(operations_repo):
    """Test set_operation_status for short buy"""
    operations_repo.set_operation_status("short", "buy", True)

    assert operations_repo.get_operation_status("short", "buy") is True
    assert operations_repo.get_operation_status("short", "sell") is False


def test_set_operation_status_short_sell(operations_repo):
    """Test set_operation_status for short sell"""
    operations_repo.set_operation_status("short", "sell", True)

    assert operations_repo.get_operation_status("short", "sell") is True
    assert operations_repo.get_operation_status("short", "buy") is False


def test_set_operation_status_to_false(operations_repo):
    """Test set_operation_status can set to False"""
    # First set to True
    operations_repo.set_operation_status("long", "buy", True)
    assert operations_repo.get_operation_status("long", "buy") is True

    # Then set to False
    operations_repo.set_operation_status("long", "buy", False)
    assert operations_repo.get_operation_status("long", "buy") is False


def test_multiple_operations_independent(operations_repo):
    """Test multiple operations are independent"""
    operations_repo.set_operation_status("long", "buy", True)
    operations_repo.set_operation_status("long", "sell", True)
    operations_repo.set_operation_status("short", "buy", True)

    assert operations_repo.get_operation_status("long", "buy") is True
    assert operations_repo.get_operation_status("long", "sell") is True
    assert operations_repo.get_operation_status("short", "buy") is True
    assert operations_repo.get_operation_status("short", "sell") is False


def test_operations_in_memory_only(operations_repo):
    """Test operations are stored in memory only (no disk writes)"""
    # This is more of a documentation test - verify the operations dict is used
    operations_repo.set_operation_status("long", "buy", True)

    # Verify it's in the in-memory dict
    assert operations_repo.operations["long"]["buy"] is True

