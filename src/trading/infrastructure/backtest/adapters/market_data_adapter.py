"""Backtest market data adapter"""


from trading.domain.entities import Candle, SymbolInfo
from trading.domain.ports import MarketDataPort
from trading.infrastructure.simulator.simulator import MarketDataSimulator


class BacktestMarketDataAdapter(MarketDataPort):
    """Market data adapter for backtests"""

    def __init__(self, simulator: MarketDataSimulator):
        self.simulator = simulator
        self._candle_listeners: dict[str, dict[str, list[callable]]] = {}

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get symbol information from simulator"""
        return self.simulator.get_symbol_info(symbol)

    def get_candles(self, symbol: str, timeframe: str, limit: int) ->[Candle]:
        """Get candles from simulator"""
        return self.simulator.get_candles(symbol, timeframe, limit)

    def add_complete_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        """Add listener for complete candle events"""
        if symbol not in self._candle_listeners:
            self._candle_listeners[symbol] = {}
        if timeframe not in self._candle_listeners[symbol]:
            self._candle_listeners[symbol][timeframe] = []

        self._candle_listeners[symbol][timeframe].append(listener)
        self.simulator.add_complete_candle_listener(symbol, timeframe, listener)

    def add_internal_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        """Add internal candle listener (used by exchange for order execution)"""
        # For backtest, internal listeners are the same as complete listeners
        # since we process candle by candle
        self.add_complete_candle_listener(symbol, timeframe, listener)

    def remove_internal_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        """Remove internal candle listener"""
        if symbol in self._candle_listeners and timeframe in self._candle_listeners[symbol]:
            if listener in self._candle_listeners[symbol][timeframe]:
                self._candle_listeners[symbol][timeframe].remove(listener)
        self.simulator.remove_complete_candle_listener(symbol, timeframe, listener)

    def close(self):
        """Close simulator and cleanup resources"""
        if hasattr(self, "simulator") and self.simulator:
            self.simulator.close()
            self.simulator = None

