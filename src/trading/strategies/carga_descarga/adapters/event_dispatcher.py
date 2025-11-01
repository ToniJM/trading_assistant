"""Event dispatcher for strategy events"""


from trading.domain.entities import Cycle


class EventDispatcher:
    """Event dispatcher for strategy events, specifically cycle completion events"""

    def __init__(self):
        self.cycle_listeners:[str] = {}

    def add_cycle_listener(self, symbol: str, listener):
        """Add a listener for cycle completion events for a specific symbol"""
        symbol = symbol.lower()
        if symbol not in self.cycle_listeners:
            self.cycle_listeners[symbol] = []
        self.cycle_listeners[symbol].append(listener)

    def remove_cycle_listener(self, symbol: str, listener):
        """Remove a cycle completion listener for a specific symbol"""
        symbol = symbol.lower()
        if symbol in self.cycle_listeners:
            if listener in self.cycle_listeners[symbol]:
                self.cycle_listeners[symbol].remove(listener)

    def dispatch_cycle_completion(self, cycle: Cycle):
        """Dispatch cycle completion event to all registered listeners for the symbol"""
        symbol = cycle.symbol.lower()
        if symbol in self.cycle_listeners:
            for listener in self.cycle_listeners[symbol]:
                try:
                    listener(cycle)
                except Exception as e:
                    # Log error but don't stop other listeners
                    print(f"Error in cycle listener: {e}")

    def has_cycle_listeners(self, symbol: str) -> bool:
        """Check if there are any cycle listeners for a symbol"""
        symbol = symbol.lower()
        return symbol in self.cycle_listeners and len(self.cycle_listeners[symbol]) > 0

