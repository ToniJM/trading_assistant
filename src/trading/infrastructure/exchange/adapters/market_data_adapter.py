"""Market data adapter for exchange simulator"""


from trading.domain.entities import Candle
from trading.domain.ports import MarketDataPort


class ExchangeMarketDataAdapter:
    """Adapter to wrap MarketDataPort for Exchange simulator"""

    def __init__(self, market_data: MarketDataPort):
        self.market_data = market_data
        self.internal_candle_listener: dict[str[str]] = {}

    def get_candles(self, symbol: str, timeframe: str, limit: int) ->[Candle]:
        """Get candles from market data port"""
        return self.market_data.get_candles(symbol, timeframe, limit)

    def add_internal_candle_listener(self, symbol: str, timeframe: str, callback: callable):
        """Add internal candle listener (for order execution)"""
        if symbol not in self.internal_candle_listener:
            self.internal_candle_listener[symbol] = []
        if timeframe not in self.internal_candle_listener[symbol]:
            self.internal_candle_listener[symbol].append(timeframe)
            self.market_data.add_internal_candle_listener(symbol, timeframe, callback)

    def remove_internal_candle_listener(self, symbol: str, timeframe: str, callback: callable):
        """Remove internal candle listener"""
        if symbol in self.internal_candle_listener:
            if timeframe in self.internal_candle_listener[symbol]:
                self.internal_candle_listener[symbol].remove(timeframe)
                self.market_data.remove_internal_candle_listener(symbol, timeframe, callback)

    def add_complete_candle_listener(self, symbol: str, timeframe: str, callback: callable):
        """Add complete candle listener"""
        self.market_data.add_complete_candle_listener(symbol, timeframe, callback)

    def remove_complete_candle_listener(self, symbol: str, timeframe: str, callback: callable):
        """Remove complete candle listener"""
        self.market_data.remove_internal_candle_listener(symbol, timeframe, callback)

