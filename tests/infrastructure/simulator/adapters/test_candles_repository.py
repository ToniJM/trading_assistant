"""Tests for CandlesRepository"""

import os
import tempfile
from decimal import Decimal

import pytest

from trading.domain.entities import Candle
from trading.infrastructure.simulator.adapters.candles_repository import CandlesRepository


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
def candles_repo_backtest(temp_db):
    """Create a CandlesRepository instance in backtest mode"""
    repo = CandlesRepository(is_backtest=True, db_path=temp_db)
    yield repo
    repo.close()


@pytest.fixture
def candles_repo_production(temp_db):
    """Create a CandlesRepository instance in production mode"""
    repo = CandlesRepository(is_backtest=False, db_path=temp_db)
    yield repo
    repo.close()


@pytest.fixture
def sample_candles():
    """Create sample candles"""
    return [
        Candle(
            symbol="BTCUSDT",
            timeframe="1m",
            timestamp=1744023500000,
            open_price=Decimal("50000"),
            high_price=Decimal("51000"),
            low_price=Decimal("49000"),
            close_price=Decimal("50500"),
            volume=Decimal("100"),
        ),
        Candle(
            symbol="BTCUSDT",
            timeframe="1m",
            timestamp=1744023500000 + 60000,  # +1 minute
            open_price=Decimal("50500"),
            high_price=Decimal("51500"),
            low_price=Decimal("50000"),
            close_price=Decimal("51000"),
            volume=Decimal("150"),
        ),
    ]


def test_initialization_backtest(candles_repo_backtest, temp_db):
    """Test repository initialization in backtest mode"""
    assert candles_repo_backtest.is_backtest is True
    assert os.path.exists(temp_db)


def test_initialization_production(candles_repo_production, temp_db):
    """Test repository initialization in production mode"""
    assert candles_repo_production.is_backtest is False
    assert os.path.exists(temp_db)


def test_add_candles_creates_table(candles_repo_backtest, sample_candles):
    """Test add_candles creates table if it doesn't exist"""
    candles_repo_backtest.add_candles(sample_candles)

    # Verify table was created by querying it
    candles_repo_backtest.cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='btcusdt_kline'"
    )
    table = candles_repo_backtest.cursor.fetchone()
    assert table is not None


def test_add_candles_empty_list(candles_repo_backtest):
    """Test add_candles handles empty list gracefully"""
    # Should not raise error
    candles_repo_backtest.add_candles([])


def test_add_candles_inserts_data(candles_repo_backtest, sample_candles):
    """Test add_candles inserts candles into database"""
    candles_repo_backtest.add_candles(sample_candles)

    # Verify data was inserted
    candles_repo_backtest.cursor.execute(
        "SELECT COUNT(*) FROM btcusdt_kline WHERE timeframe='1m'"
    )
    count = candles_repo_backtest.cursor.fetchone()[0]
    assert count == 2


def test_add_candles_replace_existing(candles_repo_backtest, sample_candles):
    """Test add_candles replaces existing candles with same timestamp/timeframe"""
    # Add candles
    candles_repo_backtest.add_candles(sample_candles)

    # Modify and add again (same timestamp)
    modified_candles = [
        Candle(
            symbol="BTCUSDT",
            timeframe="1m",
            timestamp=1744023500000,  # Same timestamp
            open_price=Decimal("60000"),  # Different price
            high_price=Decimal("61000"),
            low_price=Decimal("59000"),
            close_price=Decimal("60500"),
            volume=Decimal("200"),
        )
    ]

    candles_repo_backtest.add_candles(modified_candles)

    # Verify only one candle exists with updated price
    candles_repo_backtest.cursor.execute(
        "SELECT close FROM btcusdt_kline WHERE timestamp=1744023500000 AND timeframe='1m'"
    )
    close_price = candles_repo_backtest.cursor.fetchone()[0]
    # Price is stored as string in DB, but retrieved as float
    assert float(close_price) == 60500.0


def test_get_next_candle(candles_repo_backtest, sample_candles):
    """Test get_next_candle retrieves next candle after timestamp"""
    candles_repo_backtest.add_candles(sample_candles)

    # Get next candle after first timestamp
    next_candle = candles_repo_backtest.get_next_candle("BTCUSDT", 1744023500000, "1m")

    assert next_candle is not None
    assert next_candle.timestamp == 1744023500000 + 60000
    assert next_candle.close_price == Decimal("51000")


def test_get_next_candle_nonexistent(candles_repo_backtest):
    """Test get_next_candle returns None when no next candle exists"""
    next_candle = candles_repo_backtest.get_next_candle("BTCUSDT", 9999999999999, "1m")

    assert next_candle is None


def test_get_next_candle_nonexistent_table(candles_repo_backtest):
    """Test get_next_candle returns None when table doesn't exist"""
    next_candle = candles_repo_backtest.get_next_candle("NONEXISTENT", 1000, "1m")

    assert next_candle is None


def test_get_candles(candles_repo_backtest, sample_candles):
    """Test get_candles retrieves candles from start_time"""
    candles_repo_backtest.add_candles(sample_candles)

    # Get candles from start_time
    candles = candles_repo_backtest.get_candles("BTCUSDT", "1m", 10, start_time=1744023500000)

    assert len(candles) == 2
    assert candles[0].timestamp == 1744023500000
    assert candles[1].timestamp == 1744023500000 + 60000


def test_get_candles_with_limit(candles_repo_backtest, sample_candles):
    """Test get_candles respects limit"""
    # Add more candles
    extra_candles = [
        Candle(
            symbol="BTCUSDT",
            timeframe="1m",
            timestamp=1744023500000 + (i * 60000),
            open_price=Decimal("50000"),
            high_price=Decimal("51000"),
            low_price=Decimal("49000"),
            close_price=Decimal("50500"),
            volume=Decimal("100"),
        )
        for i in range(5)
    ]
    candles_repo_backtest.add_candles(extra_candles)

    # Get with limit
    candles = candles_repo_backtest.get_candles("BTCUSDT", "1m", 3, start_time=1744023500000)

    assert len(candles) == 3


def test_get_candles_empty_table(candles_repo_backtest):
    """Test get_candles returns empty list when table doesn't exist"""
    candles = candles_repo_backtest.get_candles("NONEXISTENT", "1m", 10, start_time=1000)

    assert candles == []


def test_get_candles_ordered_by_timestamp(candles_repo_backtest):
    """Test get_candles returns candles ordered by timestamp ASC"""
    # Add candles in random order
    candles = [
        Candle(
            symbol="BTCUSDT",
            timeframe="1m",
            timestamp=1744023500000 + (i * 60000),
            open_price=Decimal("50000"),
            high_price=Decimal("51000"),
            low_price=Decimal("49000"),
            close_price=Decimal("50500"),
            volume=Decimal("100"),
        )
        for i in [3, 1, 4, 0, 2]  # Random order
    ]
    candles_repo_backtest.add_candles(candles)

    # Retrieve and verify order
    retrieved = candles_repo_backtest.get_candles("BTCUSDT", "1m", 10, start_time=1744023500000)

    assert len(retrieved) == 5
    for i in range(4):
        assert retrieved[i].timestamp < retrieved[i + 1].timestamp


def test_close(candles_repo_backtest):
    """Test close() closes database connection"""
    candles_repo_backtest.close()

    # Verify connection is closed
    with pytest.raises(Exception):  # Should raise when trying to use closed connection
        candles_repo_backtest.cursor.execute("SELECT 1")

