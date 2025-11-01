"""Port interfaces for trading system (Hexagonal Architecture)"""
from abc import ABC, abstractmethod
from decimal import Decimal

from .entities import Candle, Cycle, Order, Position, SymbolInfo, Trade
from .types import ORDER_SIDE_TYPE, ORDER_TYPE_TYPE, SIDE_TYPE


class MarketDataPort(ABC):
    """Port for market data operations"""

    @abstractmethod
    def add_complete_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        """Add listener for complete candles"""
        raise NotImplementedError

    @abstractmethod
    def add_internal_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        """Add internal candle listener (for exchange order execution)"""
        raise NotImplementedError

    @abstractmethod
    def remove_internal_candle_listener(self, symbol: str, timeframe: str, listener: callable):
        """Remove internal candle listener"""
        raise NotImplementedError

    @abstractmethod
    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get symbol information"""
        raise NotImplementedError

    @abstractmethod
    def get_candles(
        self, symbol: str, timeframe: str, limit: int, start_time: int = None, end_time: int = None
    ) -> list[Candle]:
        """Get historical candles"""
        raise NotImplementedError


class ExchangePort(ABC):
    """Port for exchange operations"""

    @abstractmethod
    def get_orders(self, symbol: str) -> list[Order]:
        """Get open orders for symbol"""
        raise NotImplementedError

    @abstractmethod
    def new_order(
        self,
        symbol: str,
        position_side: SIDE_TYPE,
        side: ORDER_SIDE_TYPE,
        type: ORDER_TYPE_TYPE,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> Order:
        """Create a new order"""
        raise NotImplementedError

    @abstractmethod
    def modify_order(self, order: Order) -> Order:
        """Modify an existing order"""
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order"""
        raise NotImplementedError

    @abstractmethod
    def add_trade_listener(self, symbol: str, listener: callable):
        """Add listener for trade events"""
        raise NotImplementedError

    @abstractmethod
    def add_position_listener(self, listener: callable):
        """Add listener for position changes"""
        raise NotImplementedError

    @abstractmethod
    def add_orders_listener(self, listener: callable):
        """Add listener for order events"""
        raise NotImplementedError

    @abstractmethod
    def get_position(self, symbol: str, side: SIDE_TYPE) -> Position:
        """Get position for symbol and side"""
        raise NotImplementedError

    @abstractmethod
    def get_balance(self) -> Decimal:
        """Get current account balance"""
        raise NotImplementedError

    @abstractmethod
    def get_trades(self, symbol: str) -> list[Trade]:
        """Get all trades for symbol"""
        raise NotImplementedError


class OperationsStatusRepositoryPort(ABC):
    """Port for operations status repository"""

    @abstractmethod
    def get_operation_status(self, side: SIDE_TYPE, type: ORDER_SIDE_TYPE) -> bool:
        """Get operation status"""
        raise NotImplementedError

    @abstractmethod
    def set_operation_status(self, side: SIDE_TYPE, type: ORDER_SIDE_TYPE, status: bool):
        """Set operation status"""
        raise NotImplementedError


class CycleListenerPort(ABC):
    """Port for cycle event listeners"""

    @abstractmethod
    def add_cycle_listener(self, symbol: str, listener: callable):
        """Add a listener for cycle completion events"""
        raise NotImplementedError

    @abstractmethod
    def remove_cycle_listener(self, symbol: str, listener: callable):
        """Remove a cycle completion listener"""
        raise NotImplementedError

    @abstractmethod
    def dispatch_cycle_completion(self, cycle: Cycle):
        """Dispatch cycle completion event"""
        raise NotImplementedError

