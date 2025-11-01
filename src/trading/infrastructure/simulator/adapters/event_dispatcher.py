"""Event dispatcher for simulator candle events"""


from trading.domain.entities import Candle
from trading.infrastructure.logging import get_debug_logger


class EventDispatcher:
    """Event dispatcher for complete candle events"""

    def __init__(self):
        self.complete_candle_listeners:[str[str[callable]]] = {}

    def add_complete_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        """Add listener for complete candle events"""
        symbol = symbol.lower()
        if symbol not in self.complete_candle_listeners:
            self.complete_candle_listeners[symbol] = {}
        if timeframe not in self.complete_candle_listeners[symbol]:
            self.complete_candle_listeners[symbol][timeframe] = []
        self.complete_candle_listeners[symbol][timeframe].append(listener)

    def remove_complete_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        """Remove listener for complete candle events"""
        symbol = symbol.lower()
        if symbol in self.complete_candle_listeners:
            if timeframe in self.complete_candle_listeners[symbol]:
                if listener in self.complete_candle_listeners[symbol][timeframe]:
                    self.complete_candle_listeners[symbol][timeframe].remove(listener)

    def dispatch_complete_candle(self, candle: Candle):
        """Dispatch complete candle event to all registered listeners"""
        debug_logger = get_debug_logger("event_dispatcher.debug")
        debug_logger.debug(
            f"dispatch_complete_candle: symbol={candle.symbol}, timeframe={candle.timeframe}, "
            f"timestamp={candle.timestamp}"
        )

        symbol = candle.symbol.lower()
        debug_logger.debug(
            f"Buscando listeners para {symbol}/{candle.timeframe}: "
            f"symbol en listeners={symbol in self.complete_candle_listeners}"
        )

        if symbol in self.complete_candle_listeners:
            if candle.timeframe in self.complete_candle_listeners[symbol]:
                listeners = self.complete_candle_listeners[symbol][candle.timeframe]
                debug_logger.debug(f"Encontrados {len(listeners)} listeners para {symbol}/{candle.timeframe}")

                for i, listener in enumerate(listeners):
                    listener_name = (
                        listener.__name__ if hasattr(listener, "__name__") else type(listener).__name__
                    )
                    debug_logger.debug(f"Ejecutando listener {i+1}/{len(listeners)}: {listener_name}")
                    try:
                        listener(candle)
                        debug_logger.debug(f"Listener {i+1}/{len(listeners)} ejecutado exitosamente")
                    except Exception as e:
                        # Log error but don't stop other listeners
                        debug_logger.error(f"Error en candle listener {i+1}/{len(listeners)}: {e}", exc_info=True)
                        print(f"Error in candle listener: {e}")

        debug_logger.debug(f"dispatch_complete_candle completado para {symbol}/{candle.timeframe}")

