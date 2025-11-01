"""Event dispatcher for exchange events"""


from trading.domain.entities import Order, Position, Trade


class EventDispatcher:
    """Event dispatcher for exchange events (orders, positions, trades)"""

    def __init__(self):
        self._orders_listeners:[callable] = []
        self._positions_listeners:[callable] = []
        self._trade_listeners:[callable] = []

    def add_orders_listener(self, listener: callable):
        """Add listener for order events"""
        self._orders_listeners.append(listener)

    def remove_order_listener(self, listener: callable):
        """Remove order event listener"""
        if listener in self._orders_listeners:
            self._orders_listeners.remove(listener)

    def dispatch_order(self, order: Order, old_order:[Order] = None):
        """Dispatch order event"""
        for listener in self._orders_listeners:
            try:
                listener(order, old_order)
            except TypeError:
                # Some listeners might not accept old_order parameter
                listener(order)

    def add_position_listener(self, listener: callable):
        """Add listener for position events"""
        self._positions_listeners.append(listener)

    def remove_position_listener(self, listener: callable):
        """Remove position event listener"""
        if listener in self._positions_listeners:
            self._positions_listeners.remove(listener)

    def dispatch_positions(self, position: Position, old_position:[Position] = None):
        """Dispatch position event"""
        for listener in self._positions_listeners:
            try:
                listener(position, old_position)
            except TypeError:
                # Some listeners might not accept old_position parameter
                listener(position)

    def add_trade_listener(self, listener: callable):
        """Add listener for trade events"""
        self._trade_listeners.append(listener)

    def remove_trades_listener(self, listener: callable):
        """Remove trade event listener"""
        if listener in self._trade_listeners:
            self._trade_listeners.remove(listener)

    def dispatch_trade(self, trade: Trade):
        """Dispatch trade event"""
        for listener in self._trade_listeners:
            try:
                listener(trade)
            except Exception as e:
                # Log error but don't stop other listeners
                print(f"Error in trade listener: {e}")

