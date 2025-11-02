"""Tests for strategy factory"""
from unittest.mock import Mock

from trading.domain.ports import CycleListenerPort, ExchangePort, MarketDataPort
from trading.strategies.factory import create_strategy_factory


def test_strategy_factory_passes_timeframes():
    """Test strategy factory passes timeframes to strategy"""
    # Create mocks
    mock_exchange = Mock(spec=ExchangePort)
    mock_market_data = Mock(spec=MarketDataPort)
    mock_cycle_dispatcher = Mock(spec=CycleListenerPort)

    # Create factory with custom timeframes
    factory_func = create_strategy_factory(
        strategy_name="carga_descarga",
        timeframes=["3m", "15m", "1h"]
    )

    # Create strategy using factory
    strategy = factory_func(
        symbol="BTCUSDT",
        exchange=mock_exchange,
        market_data=mock_market_data,
        cycle_dispatcher=mock_cycle_dispatcher,
        strategy_name="carga_descarga",
    )

    # Verify strategy was created with correct timeframes
    assert strategy.timeframes == ["3m", "15m", "1h"]


def test_strategy_factory_default_timeframes():
    """Test strategy factory with no timeframes uses strategy default"""
    # Create mocks
    mock_exchange = Mock(spec=ExchangePort)
    mock_market_data = Mock(spec=MarketDataPort)
    mock_cycle_dispatcher = Mock(spec=CycleListenerPort)

    # Create factory without timeframes
    factory_func = create_strategy_factory(strategy_name="carga_descarga")

    # Create strategy using factory
    strategy = factory_func(
        symbol="BTCUSDT",
        exchange=mock_exchange,
        market_data=mock_market_data,
        cycle_dispatcher=mock_cycle_dispatcher,
        strategy_name="carga_descarga",
    )

    # Verify strategy was created with default timeframes
    assert strategy.timeframes == ["1m", "15m", "1h"]

