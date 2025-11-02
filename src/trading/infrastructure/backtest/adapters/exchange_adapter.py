"""Backtest exchange adapter"""
from decimal import Decimal

from trading.domain.entities import Order, Position, Trade
from trading.domain.ports import ExchangePort, MarketDataPort
from trading.domain.types import ORDER_SIDE_TYPE, ORDER_TYPE_TYPE, SIDE_TYPE
from trading.infrastructure.exchange.exchange import Exchange


class SimulatorAdapter(ExchangePort):
    """Adapter that wraps Exchange simulator to ExchangePort"""

    def __init__(self, market_data: MarketDataPort):
        self.simulator = Exchange(market_data)

    def set_balance(self, balance: Decimal):
        """Set account balance"""
        self.simulator.set_balance(balance)

    def set_leverage(self, symbol: str, leverage: Decimal):
        """Set leverage for symbol"""
        self.simulator.set_leverage(symbol, leverage)

    def set_fees(self, maker_fee: Decimal, taker_fee: Decimal):
        """Set trading fees"""
        self.simulator.set_fees(maker_fee, taker_fee)

    def set_max_notional(self, max_notional: Decimal):
        """Set maximum notional"""
        self.simulator.set_max_notional(max_notional)

    def set_base_timeframe(self, timeframe: str):
        """Set base timeframe for order execution"""
        self.simulator.set_base_timeframe(timeframe)

    def get_balance(self) -> Decimal:
        """Get current account balance"""
        return self.simulator.get_balance()

    def get_orders(self, symbol: str) ->[Order]:
        """Get all orders for symbol"""
        return self.simulator.get_orders(symbol)

    def get_trades(self, symbol: str) ->[Trade]:
        """Get all trades for symbol"""
        all_trades:[Trade] = []
        symbol_lower = symbol.lower()
        symbol_trades = self.simulator.trades_repository.get_symbol_trades(symbol_lower)
        for position_side, trades in symbol_trades.items():
            for trade in trades:
                all_trades.append(trade)
        return all_trades

    def new_order(
        self,
        symbol: str,
        position_side: SIDE_TYPE,
        side: ORDER_SIDE_TYPE,
        type: ORDER_TYPE_TYPE,
        quantity: Decimal,
        price:[Decimal] = None,
    ) -> Order:
        """Create new order"""
        return self.simulator.new_order(symbol, position_side, side, type, quantity, price)

    def modify_order(self, order: Order) -> Order:
        """Modify existing order"""
        modified = self.simulator.modify_order(order)
        if modified:
            return modified
        return order

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel order"""
        return self.simulator.cancel_order(order_id)

    def add_trade_listener(self, symbol: str, listener: callable):
        """Add trade event listener"""
        return self.simulator.add_trade_listener(listener)

    def add_position_listener(self, listener: callable):
        """Add position event listener"""
        return self.simulator.add_position_listener(listener)

    def add_orders_listener(self, listener: callable):
        """Add order event listener"""
        return self.simulator.add_orders_listener(listener)

    def get_position(self, symbol: str, side: SIDE_TYPE) -> Position:
        """Get position for symbol and side"""
        position = self.simulator.get_position(symbol, side)
        # Load trades into position
        if abs(position.amount) > Decimal(0):
            symbol_trades = self.simulator.trades_repository.get_symbol_trades(symbol.lower())
            position_side_trades = symbol_trades.get(side, [])
            for trade in reversed(position_side_trades):
                if trade.position_side != side:
                    continue
                position.add_trade(trade)
                if abs(position.amount) == 0:
                    break
        return position


class BacktestExchangeAdapter(ExchangePort):
    """Exchange adapter for backtests"""

    def __init__(self, market_data_adapter: MarketDataPort):
        self.simulator_adapter = SimulatorAdapter(market_data=market_data_adapter)
        self.exchange = self.simulator_adapter.simulator

    def set_balance(self, balance: Decimal):
        """Set account balance"""
        self.simulator_adapter.set_balance(balance)

    def set_leverage(self, symbol: str, leverage: Decimal):
        """Set leverage for symbol"""
        self.simulator_adapter.set_leverage(symbol, leverage)

    def set_fees(self, maker_fee: Decimal, taker_fee: Decimal):
        """Set trading fees"""
        self.simulator_adapter.set_fees(maker_fee, taker_fee)

    def set_max_notional(self, notional: Decimal):
        """Set maximum notional"""
        self.simulator_adapter.set_max_notional(notional)

    def set_base_timeframe(self, timeframe: str):
        """Set base timeframe for order execution"""
        self.simulator_adapter.set_base_timeframe(timeframe)

    def get_balance(self) -> Decimal:
        """Get current account balance"""
        return self.simulator_adapter.get_balance()

    def get_position(self, symbol: str, side: SIDE_TYPE) -> Position:
        """Get position for symbol and side"""
        return self.simulator_adapter.get_position(symbol, side)

    def get_orders(self, symbol: str) ->[Order]:
        """Get all orders for symbol"""
        return self.simulator_adapter.get_orders(symbol)

    def get_trades(self, symbol: str) ->[Trade]:
        """Get all trades for symbol"""
        return self.simulator_adapter.get_trades(symbol)

    def new_order(
        self,
        symbol: str,
        position_side: SIDE_TYPE,
        side: ORDER_SIDE_TYPE,
        type: ORDER_TYPE_TYPE,
        quantity: Decimal,
        price:[Decimal] = None,
    ) -> Order:
        """Create new order"""
        return self.simulator_adapter.new_order(symbol, position_side, side, type, quantity, price)

    def modify_order(self, order: Order) -> Order:
        """Modify existing order"""
        return self.simulator_adapter.modify_order(order)

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel order"""
        return self.simulator_adapter.cancel_order(symbol, order_id)

    def add_trade_listener(self, symbol: str, listener: callable):
        """Add trade event listener"""
        return self.simulator_adapter.add_trade_listener(symbol, listener)

    def add_position_listener(self, listener: callable):
        """Add position event listener"""
        return self.simulator_adapter.add_position_listener(listener)

    def add_orders_listener(self, listener: callable):
        """Add order event listener"""
        return self.simulator_adapter.add_orders_listener(listener)

