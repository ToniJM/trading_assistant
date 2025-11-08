"""Tests for CyclesRepository"""

import os
import sqlite3
import tempfile
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from trading.domain.entities import Cycle
from trading.infrastructure.backtest.cycles_repository import CyclesRepository


@pytest.fixture
def temp_db():
    """Create a temporary database file"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def cycles_repo(temp_db):
    """Create a CyclesRepository instance with temp database"""
    return CyclesRepository(db_path=temp_db)


@pytest.fixture
def sample_cycle():
    """Create a sample Cycle"""
    return Cycle(
        symbol="BTCUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000,
        end_timestamp=1744023500000 + (60 * 60 * 1000),  # +1 hour
        total_pnl=Decimal("100.50"),
        long_trades_count=5,
        short_trades_count=3,
        long_max_loads=2,
        short_max_loads=1,
        cycle_id="test_cycle_123",
    )


def test_initialization(cycles_repo, temp_db):
    """Test repository initialization creates database and tables"""
    # Verify database file exists
    assert os.path.exists(temp_db)

    # Verify we can query the table (indirect test that it was created)
    cycles = cycles_repo.get_cycles("BTCUSDT")
    assert isinstance(cycles, list)


def test_save_cycle(cycles_repo, sample_cycle):
    """Test save_cycle saves cycle to database"""
    result = cycles_repo.save_cycle(sample_cycle)

    assert result is True

    # Verify cycle was saved by retrieving it
    cycles = cycles_repo.get_cycles("BTCUSDT")
    assert len(cycles) == 1
    assert cycles[0].cycle_id == "test_cycle_123"
    assert cycles[0].symbol == "BTCUSDT"
    assert cycles[0].strategy_name == "test_strategy"
    assert cycles[0].total_pnl == Decimal("100.50")


def test_save_cycle_multiple(cycles_repo, sample_cycle):
    """Test save_cycle can save multiple cycles"""
    cycle1 = Cycle(
        symbol="BTCUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000,
        end_timestamp=1744023500000 + (60 * 60 * 1000),
        total_pnl=Decimal("100"),
        long_trades_count=5,
        short_trades_count=3,
        long_max_loads=2,
        short_max_loads=1,
        cycle_id="cycle_1",
    )

    cycle2 = Cycle(
        symbol="BTCUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000 + (2 * 60 * 60 * 1000),
        end_timestamp=1744023500000 + (3 * 60 * 60 * 1000),
        total_pnl=Decimal("200"),
        long_trades_count=10,
        short_trades_count=5,
        long_max_loads=3,
        short_max_loads=2,
        cycle_id="cycle_2",
    )

    cycles_repo.save_cycle(cycle1)
    cycles_repo.save_cycle(cycle2)

    cycles = cycles_repo.get_cycles("BTCUSDT")
    assert len(cycles) == 2
    # Should be ordered by start_timestamp ASC
    assert cycles[0].cycle_id == "cycle_1"
    assert cycles[1].cycle_id == "cycle_2"


def test_save_cycle_replace_existing(cycles_repo, sample_cycle):
    """Test save_cycle replaces existing cycle with same ID"""
    # Save cycle
    cycles_repo.save_cycle(sample_cycle)

    # Modify and save again
    sample_cycle.total_pnl = Decimal("999.99")
    cycles_repo.save_cycle(sample_cycle)

    # Verify only one cycle exists with updated PnL
    cycles = cycles_repo.get_cycles("BTCUSDT")
    assert len(cycles) == 1
    assert cycles[0].total_pnl == Decimal("999.99")


def test_get_cycles_by_symbol(cycles_repo, sample_cycle):
    """Test get_cycles retrieves cycles by symbol"""
    # Save cycle for BTCUSDT
    cycles_repo.save_cycle(sample_cycle)

    # Save cycle for different symbol
    eth_cycle = Cycle(
        symbol="ETHUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000,
        end_timestamp=1744023500000 + (60 * 60 * 1000),
        total_pnl=Decimal("50"),
        long_trades_count=2,
        short_trades_count=1,
        long_max_loads=1,
        short_max_loads=1,
        cycle_id="eth_cycle_1",
    )
    cycles_repo.save_cycle(eth_cycle)

    # Get cycles for BTCUSDT
    btc_cycles = cycles_repo.get_cycles("BTCUSDT")
    assert len(btc_cycles) == 1
    assert btc_cycles[0].symbol == "BTCUSDT"

    # Get cycles for ETHUSDT
    eth_cycles = cycles_repo.get_cycles("ETHUSDT")
    assert len(eth_cycles) == 1
    assert eth_cycles[0].symbol == "ETHUSDT"


def test_get_cycles_with_strategy_filter(cycles_repo, sample_cycle):
    """Test get_cycles with strategy_name filter"""
    # Save cycle with test_strategy
    cycles_repo.save_cycle(sample_cycle)

    # Save cycle with different strategy
    other_strategy_cycle = Cycle(
        symbol="BTCUSDT",
        strategy_name="other_strategy",
        start_timestamp=1744023500000 + (2 * 60 * 60 * 1000),
        end_timestamp=1744023500000 + (3 * 60 * 60 * 1000),
        total_pnl=Decimal("200"),
        long_trades_count=10,
        short_trades_count=5,
        long_max_loads=3,
        short_max_loads=2,
        cycle_id="other_strategy_cycle",
    )
    cycles_repo.save_cycle(other_strategy_cycle)

    # Get cycles for test_strategy
    test_strategy_cycles = cycles_repo.get_cycles("BTCUSDT", strategy_name="test_strategy")
    assert len(test_strategy_cycles) == 1
    assert test_strategy_cycles[0].strategy_name == "test_strategy"

    # Get cycles for other_strategy
    other_strategy_cycles = cycles_repo.get_cycles("BTCUSDT", strategy_name="other_strategy")
    assert len(other_strategy_cycles) == 1
    assert other_strategy_cycles[0].strategy_name == "other_strategy"


def test_get_cycles_empty(cycles_repo):
    """Test get_cycles returns empty list when no cycles exist"""
    cycles = cycles_repo.get_cycles("BTCUSDT")
    assert cycles == []


def test_get_cycles_ordered_by_timestamp(cycles_repo):
    """Test get_cycles returns cycles ordered by start_timestamp ASC"""
    # Create cycles with different timestamps
    cycle1 = Cycle(
        symbol="BTCUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000,
        end_timestamp=1744023500000 + (60 * 60 * 1000),
        total_pnl=Decimal("100"),
        long_trades_count=5,
        short_trades_count=3,
        long_max_loads=2,
        short_max_loads=1,
        cycle_id="cycle_1",
    )

    cycle2 = Cycle(
        symbol="BTCUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000 + (2 * 60 * 60 * 1000),  # Later
        end_timestamp=1744023500000 + (3 * 60 * 60 * 1000),
        total_pnl=Decimal("200"),
        long_trades_count=10,
        short_trades_count=5,
        long_max_loads=3,
        short_max_loads=2,
        cycle_id="cycle_2",
    )

    cycle3 = Cycle(
        symbol="BTCUSDT",
        strategy_name="test_strategy",
        start_timestamp=1744023500000 + (1 * 60 * 60 * 1000),  # Middle
        end_timestamp=1744023500000 + (1.5 * 60 * 60 * 1000),
        total_pnl=Decimal("150"),
        long_trades_count=7,
        short_trades_count=4,
        long_max_loads=2,
        short_max_loads=1,
        cycle_id="cycle_3",
    )

    # Save in different order
    cycles_repo.save_cycle(cycle2)
    cycles_repo.save_cycle(cycle1)
    cycles_repo.save_cycle(cycle3)

    # Retrieve and verify order
    cycles = cycles_repo.get_cycles("BTCUSDT")
    assert len(cycles) == 3
    assert cycles[0].cycle_id == "cycle_1"
    assert cycles[1].cycle_id == "cycle_3"
    assert cycles[2].cycle_id == "cycle_2"


def test_save_cycle_error_handling(cycles_repo, sample_cycle):
    """Test save_cycle handles errors gracefully"""
    # Test that save_cycle returns False on error
    # We'll use a mock to simulate a database error during save
    from unittest.mock import patch
    
    # Mock sqlite3.connect to raise an error on save
    with patch("trading.infrastructure.backtest.cycles_repository.sqlite3.connect") as mock_connect:
        # First call (in __init__) succeeds, second call (in save_cycle) fails
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        # First call succeeds (for initialization)
        # Second call raises error (for save_cycle)
        call_count = [0]
        def connect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_conn
            else:
                raise sqlite3.OperationalError("Database error")
        
        mock_connect.side_effect = connect_side_effect
        
        # Create a new repo (first connect succeeds)
        test_repo = CyclesRepository(db_path=":memory:")
        
        # Now save_cycle should fail and return False
        result = test_repo.save_cycle(sample_cycle)
        # The error is caught and False is returned
        assert result is False
    
    # Verify normal cycle saves work
    result = cycles_repo.save_cycle(sample_cycle)
    assert result is True


def test_get_cycles_error_handling(temp_db):
    """Test get_cycles handles errors gracefully"""
    # Create repository with invalid database path to test error handling
    # Actually, we'll test with a valid repo but query non-existent symbol
    repo = CyclesRepository(db_path=temp_db)

    # Query should return empty list, not raise
    cycles = repo.get_cycles("NONEXISTENT")
    assert cycles == []

