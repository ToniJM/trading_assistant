"""Tests for backtest exchange adapters"""
from decimal import Decimal

from trading.domain.ports import MarketDataPort
from trading.infrastructure.backtest.adapters.exchange_adapter import BacktestExchangeAdapter, SimulatorAdapter


class MockMarketDataPort(MarketDataPort):
    """Mock MarketDataPort for testing"""

    def get_candles(self, symbol: str, timeframe: str, limit: int, start_time: int = None, end_time: int = None):
        return []

    def get_symbol_info(self, symbol: str):
        from trading.domain.entities import SymbolInfo
        return SymbolInfo(
            symbol=symbol,
            base_asset="BTC",
            quote_asset="USDT",
            min_notional=Decimal("10"),
            price_precision=2,
            quantity_precision=3,
        )

    def add_complete_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        pass

    def remove_complete_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        pass

    def add_internal_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        pass

    def remove_internal_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        pass


def test_simulator_adapter_set_base_timeframe():
    """Test SimulatorAdapter set_base_timeframe passes timeframe to Exchange"""
    market_data = MockMarketDataPort()
    adapter = SimulatorAdapter(market_data=market_data)

    # Verify default
    assert adapter.simulator.base_timeframe == "1m"

    # Set custom timeframe
    adapter.set_base_timeframe("3m")
    assert adapter.simulator.base_timeframe == "3m"

    # Set another timeframe
    adapter.set_base_timeframe("15m")
    assert adapter.simulator.base_timeframe == "15m"


def test_backtest_exchange_adapter_set_base_timeframe():
    """Test BacktestExchangeAdapter set_base_timeframe passes timeframe to SimulatorAdapter"""
    market_data = MockMarketDataPort()
    adapter = BacktestExchangeAdapter(market_data_adapter=market_data)

    # Verify default
    assert adapter.exchange.base_timeframe == "1m"

    # Set custom timeframe
    adapter.set_base_timeframe("3m")
    assert adapter.exchange.base_timeframe == "3m"

    # Set another timeframe
    adapter.set_base_timeframe("15m")
    assert adapter.exchange.base_timeframe == "15m"

