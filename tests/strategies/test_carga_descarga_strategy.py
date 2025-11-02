"""Unit tests for CargaDescargaStrategy helper methods"""
from unittest.mock import Mock

from trading.domain.ports import ExchangePort, MarketDataPort
from trading.infrastructure.backtest.adapters.operations_status_repository import (
    BacktestOperationsStatusRepository,
)
from trading.strategies.carga_descarga.carga_descarga_strategy import CargaDescargaStrategy


def create_mock_strategy(timeframes: list[str]) -> CargaDescargaStrategy:
    """Helper to create a CargaDescargaStrategy instance with mocked dependencies"""
    mock_exchange = Mock(spec=ExchangePort)
    mock_market_data = Mock(spec=MarketDataPort)
    ops_repo = BacktestOperationsStatusRepository(symbol="BTCUSDT")

    strategy = CargaDescargaStrategy(
        symbol="BTCUSDT",
        exchange=mock_exchange,
        market_data=mock_market_data,
        operation_status_repository=ops_repo,
        cycle_dispatcher=None,
        strategy_name="test_strategy",
        timeframes=timeframes,
    )
    return strategy


def test_get_loads_per_timeframe_with_2_timeframes():
    """Test _get_loads_per_timeframe with 2 timeframes: should return 4 (9 // 2 = 4)"""
    strategy = create_mock_strategy(timeframes=["15m", "1h"])
    loads_per_tf = strategy._get_loads_per_timeframe()
    assert loads_per_tf == 4


def test_get_loads_per_timeframe_with_3_timeframes():
    """Test _get_loads_per_timeframe with 3 timeframes: should return 3 (9 // 3 = 3)"""
    strategy = create_mock_strategy(timeframes=["1m", "15m", "1h"])
    loads_per_tf = strategy._get_loads_per_timeframe()
    assert loads_per_tf == 3


def test_get_loads_per_timeframe_with_4_timeframes():
    """Test _get_loads_per_timeframe with 4 timeframes: should return 2 (9 // 4 = 2)"""
    strategy = create_mock_strategy(timeframes=["1m", "5m", "15m", "1h"])
    loads_per_tf = strategy._get_loads_per_timeframe()
    assert loads_per_tf == 2


def test_calculate_timeframe_index_with_2_timeframes():
    """Test _calculate_timeframe_index with 2 timeframes"""
    strategy = create_mock_strategy(timeframes=["15m", "1h"])
    # loads=0 → index=0
    assert strategy._calculate_timeframe_index(0) == 0
    # loads=4 → index=1 (last timeframe)
    assert strategy._calculate_timeframe_index(4) == 1
    # loads=8 → index=1 (capped at max_index)
    assert strategy._calculate_timeframe_index(8) == 1


def test_calculate_timeframe_index_with_3_timeframes():
    """Test _calculate_timeframe_index with 3 timeframes"""
    strategy = create_mock_strategy(timeframes=["1m", "15m", "1h"])
    # loads=0 → index=0
    assert strategy._calculate_timeframe_index(0) == 0
    # loads=3 → index=1
    assert strategy._calculate_timeframe_index(3) == 1
    # loads=6 → index=2 (last timeframe)
    assert strategy._calculate_timeframe_index(6) == 2
    # loads=9 → index=2 (capped)
    assert strategy._calculate_timeframe_index(9) == 2


def test_calculate_timeframe_index_with_4_timeframes():
    """Test _calculate_timeframe_index with 4 timeframes"""
    strategy = create_mock_strategy(timeframes=["1m", "5m", "15m", "1h"])
    # loads=0 → index=0
    assert strategy._calculate_timeframe_index(0) == 0
    # loads=2 → index=1
    assert strategy._calculate_timeframe_index(2) == 1
    # loads=4 → index=2
    assert strategy._calculate_timeframe_index(4) == 2
    # loads=6 → index=3 (last timeframe)
    assert strategy._calculate_timeframe_index(6) == 3


def test_is_last_tf_load_with_3_timeframes():
    """Test _is_last_tf_load with 3 timeframes (loads_per_tf=3)"""
    strategy = create_mock_strategy(timeframes=["1m", "15m", "1h"])
    # loads=0 → False
    assert strategy._is_last_tf_load(0) is False
    # loads=1 → False
    assert strategy._is_last_tf_load(1) is False
    # loads=2 → False
    assert strategy._is_last_tf_load(2) is False
    # loads=3 → True
    assert strategy._is_last_tf_load(3) is True
    # loads=4 → False
    assert strategy._is_last_tf_load(4) is False
    # loads=6 → True
    assert strategy._is_last_tf_load(6) is True


def test_is_last_tf_load_with_2_timeframes():
    """Test _is_last_tf_load with 2 timeframes (loads_per_tf=4)"""
    strategy = create_mock_strategy(timeframes=["15m", "1h"])
    # loads=4 → True
    assert strategy._is_last_tf_load(4) is True
    # loads=8 → True
    assert strategy._is_last_tf_load(8) is True
    # loads=5 → False
    assert strategy._is_last_tf_load(5) is False


def test_get_threshold_loads_with_3_timeframes():
    """Test _get_threshold_loads with 3 timeframes (scale_factor=1.0)"""
    strategy = create_mock_strategy(timeframes=["1m", "15m", "1h"])
    # base_threshold=3 → 3
    assert strategy._get_threshold_loads(3) == 3
    # base_threshold=4 → 4
    assert strategy._get_threshold_loads(4) == 4


def test_get_threshold_loads_with_2_timeframes():
    """Test _get_threshold_loads with 2 timeframes (scale_factor=0.67)"""
    strategy = create_mock_strategy(timeframes=["15m", "1h"])
    # base_threshold=3 → 2 (int(3 * 2/3) = 2)
    assert strategy._get_threshold_loads(3) == 2
    # base_threshold=4 → 2 (int(4 * 2/3) = 2)
    assert strategy._get_threshold_loads(4) == 2


def test_get_threshold_loads_with_4_timeframes():
    """Test _get_threshold_loads with 4 timeframes (scale_factor=1.33)"""
    strategy = create_mock_strategy(timeframes=["1m", "5m", "15m", "1h"])
    # base_threshold=3 → 4 (int(3 * 4/3) = 4)
    assert strategy._get_threshold_loads(3) == 4
    # base_threshold=4 → 5 (int(4 * 4/3) = 5)
    assert strategy._get_threshold_loads(4) == 5


def test_get_threshold_loads_minimum_value():
    """Test _get_threshold_loads ensures at least 1 for small values"""
    strategy = create_mock_strategy(timeframes=["15m", "1h"])
    # base_threshold=1 with 2 timeframes → 1 (max(1, int(1 * 2/3)) = 1)
    assert strategy._get_threshold_loads(1) == 1

