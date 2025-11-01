"""Orders repository for exchange simulator"""
import secrets
from decimal import Decimal

from trading.domain.entities import Order
from trading.domain.types import ORDER_SIDE_TYPE, ORDER_TYPE_TYPE, SIDE_TYPE


class OrdersRepository:
    """Repository for storing and retrieving orders"""

    def __init__(self):
        self.orders:[str[Order]] = {}

    def new_order(
        self,
        symbol: str,
        position_side: SIDE_TYPE,
        side: ORDER_SIDE_TYPE,
        type: ORDER_TYPE_TYPE,
        quantity: Decimal,
        price:[Decimal] = None,
        order_id:[str] = None,
    ) -> Order:
        """Create new order"""
        if not order_id:
            order_id = secrets.token_hex(8)
        symbol = symbol.lower()

        if symbol not in self.orders:
            self.orders[symbol] = []

        order = Order(
            symbol=symbol,
            position_side=position_side,
            side=side,
            price=price if price is not None else Decimal(0),
            quantity=quantity,
            type=type,
            status="new",
            order_id=order_id,
        )
        self.orders[symbol].append(order)
        return order

    def modify_order(self, order: Order) ->[Order]:
        """Modify existing order"""
        symbol = order.symbol.lower()
        if symbol not in self.orders:
            return None

        for idx, o in enumerate(self.orders[symbol]):
            if o.order_id == order.order_id:
                self.orders[symbol][idx] = order
                return order
        return None

    def delete_order(self, order_id: str) -> bool:
        """Delete order by order_id"""
        for symbol in self.orders:
            for idx, order in enumerate(self.orders[symbol]):
                if order.order_id == order_id:
                    del self.orders[symbol][idx]
                    return True
        return False

    def get_order(self, order_id: str) ->[Order]:
        """Get order by order_id"""
        for symbol in self.orders:
            for order in self.orders[symbol]:
                if order.order_id == order_id:
                    return order
        return None

    def get_symbol_orders(self, symbol: str) ->[Order]:
        """Get all orders for symbol"""
        symbol = symbol.lower()
        return self.orders.get(symbol, [])

    def delete_symbol_orders(self, symbol: str) -> bool:
        """Delete all orders for symbol"""
        symbol = symbol.lower()
        if symbol in self.orders:
            del self.orders[symbol]
            return True
        return False

