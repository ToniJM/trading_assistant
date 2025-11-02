"""Tests for Exchange simulator"""

from decimal import Decimal

from trading.domain.entities import Candle
from trading.domain.ports import MarketDataPort
from trading.infrastructure.exchange.exchange import Exchange


class MockMarketDataPort(MarketDataPort):
    """Mock MarketDataPort for testing"""

    def __init__(self):
        self.candles = []
        self.get_candles_calls = []  # Track calls to get_candles
        self.listener_calls = []  # Track calls to add/remove listeners

    def get_candles(self, symbol: str, timeframe: str, limit: int, start_time: int = None, end_time: int = None):
        self.get_candles_calls.append((symbol, timeframe, limit))
        return self.candles[:limit]

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
        self.listener_calls.append(("add_complete", symbol, timeframe))

    def remove_complete_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        self.listener_calls.append(("remove_complete", symbol, timeframe))

    def add_internal_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        self.listener_calls.append(("add_internal", symbol, timeframe))

    def remove_internal_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        self.listener_calls.append(("remove_internal", symbol, timeframe))


def test_exchange_base_timeframe_default():
    """Test Exchange has default base_timeframe of '1m'"""
    market_data = MockMarketDataPort()
    exchange = Exchange(market_data)
    assert exchange.base_timeframe == "1m"


def test_exchange_set_base_timeframe():
    """Test Exchange set_base_timeframe updates the value"""
    market_data = MockMarketDataPort()
    exchange = Exchange(market_data)
    assert exchange.base_timeframe == "1m"

    exchange.set_base_timeframe("3m")
    assert exchange.base_timeframe == "3m"

    exchange.set_base_timeframe("15m")
    assert exchange.base_timeframe == "15m"


def test_exchange_uses_base_timeframe_in_new_order():
    """Test Exchange uses self.base_timeframe in new_order() instead of hardcoded '1m'"""
    market_data = MockMarketDataPort()
    # Create a candle for the test
    candle = Candle(
        symbol="BTCUSDT",
        timeframe="3m",
        timestamp=1744023500000,
        open_price=Decimal("50000"),
        high_price=Decimal("50100"),
        low_price=Decimal("49900"),
        close_price=Decimal("50050"),
        volume=Decimal("100"),
    )
    market_data.candles = [candle]

    exchange = Exchange(market_data)
    exchange.set_balance(Decimal("10000"))
    exchange.set_leverage("BTCUSDT", Decimal("100"))
    exchange.set_max_notional(Decimal("50000"))
    exchange.set_base_timeframe("3m")

    # Create a limit order
    exchange.new_order(
        symbol="BTCUSDT",
        position_side="long",
        side="buy",
        type="limit",
        quantity=Decimal("0.1"),
        price=Decimal("50000"),
    )

    # Verify that get_candles was called with base_timeframe ("3m")
    assert len(market_data.get_candles_calls) > 0
    # The first call should be with the base_timeframe
    first_call = market_data.get_candles_calls[0]
    assert first_call[1] == "3m", f"Expected '3m' but got '{first_call[1]}'"


def test_exchange_uses_base_timeframe_in_modify_order():
    """Test Exchange uses self.base_timeframe in modify_order()"""
    market_data = MockMarketDataPort()
    candle = Candle(
        symbol="BTCUSDT",
        timeframe="3m",
        timestamp=1744023500000,
        open_price=Decimal("50000"),
        high_price=Decimal("50100"),
        low_price=Decimal("49900"),
        close_price=Decimal("50050"),
        volume=Decimal("100"),
    )
    market_data.candles = [candle]

    exchange = Exchange(market_data)
    exchange.set_balance(Decimal("10000"))
    exchange.set_leverage("BTCUSDT", Decimal("100"))
    exchange.set_max_notional(Decimal("50000"))
    exchange.set_base_timeframe("3m")

    # Create an order first
    order = exchange.new_order(
        symbol="BTCUSDT",
        position_side="long",
        side="buy",
        type="limit",
        quantity=Decimal("0.1"),
        price=Decimal("50000"),
    )

    # Clear previous calls
    market_data.get_candles_calls.clear()

    # Modify the order
    exchange.modify_order(order)

    # Verify that get_candles was called with base_timeframe ("3m")
    assert len(market_data.get_candles_calls) > 0
    # Check that calls used "3m" instead of "1m"
    timeframe_calls = [call[1] for call in market_data.get_candles_calls]
    assert "3m" in timeframe_calls, f"Expected '3m' in calls but got {timeframe_calls}"


def test_exchange_uses_base_timeframe_in_cancel_order():
    """Test Exchange uses self.base_timeframe in cancel_order()"""
    market_data = MockMarketDataPort()
    candle = Candle(
        symbol="BTCUSDT",
        timeframe="3m",
        timestamp=1744023500000,
        open_price=Decimal("50000"),
        high_price=Decimal("50100"),
        low_price=Decimal("49900"),
        close_price=Decimal("50050"),
        volume=Decimal("100"),
    )
    market_data.candles = [candle]

    exchange = Exchange(market_data)
    exchange.set_balance(Decimal("10000"))
    exchange.set_leverage("BTCUSDT", Decimal("100"))
    exchange.set_max_notional(Decimal("50000"))
    exchange.set_base_timeframe("3m")

    # Create an order first
    order = exchange.new_order(
        symbol="BTCUSDT",
        position_side="long",
        side="buy",
        type="limit",
        quantity=Decimal("0.1"),
        price=Decimal("50000"),
    )

    # Clear previous calls
    market_data.listener_calls.clear()

    # Cancel the order (this should be the last order, so listener should be removed)
    cancelled = exchange.cancel_order(order.order_id)

    # Verify cancellation succeeded
    assert cancelled is True

    # Verify that remove_internal_candle_listener was called with base_timeframe
    remove_calls = [call for call in market_data.listener_calls if call[0] == "remove_internal"]
    if remove_calls:
        # Check that it used the base_timeframe ("3m")
        assert remove_calls[-1][2] == "3m", f"Expected '3m' but got '{remove_calls[-1][2]}'"
