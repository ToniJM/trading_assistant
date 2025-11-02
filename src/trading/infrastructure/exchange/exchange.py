"""Exchange simulator for backtests"""
from decimal import Decimal

from trading.domain.entities import Candle, Order, Position, Trade
from trading.domain.ports import MarketDataPort
from trading.domain.types import ORDER_SIDE_TYPE, ORDER_TYPE_TYPE, SIDE_TYPE
from trading.infrastructure.exchange.adapters.event_dispatcher import EventDispatcher
from trading.infrastructure.exchange.adapters.market_data_adapter import ExchangeMarketDataAdapter
from trading.infrastructure.exchange.repositories import AccountRepository, OrdersRepository, TradesRepository
from trading.infrastructure.logging import get_debug_logger


class Exchange:
    """Exchange simulator for backtests"""

    def __init__(self, market_data: MarketDataPort):
        self.market_data_adapter = ExchangeMarketDataAdapter(market_data)
        self.account_repository = AccountRepository()
        self.orders_repository = OrdersRepository()
        self.trades_repository = TradesRepository()
        self.event_dispatcher = EventDispatcher()

        self.maker_fee = Decimal(0)
        self.taker_fee = Decimal(0)
        self.max_notional = Decimal(0)
        self.base_timeframe: str = "1m"  # Default for backwards compatibility

        self.current_candle:[Candle] = None

    def set_fees(self, maker: Decimal, taker: Decimal):
        """Set trading fees"""
        self.maker_fee = Decimal(maker)
        self.taker_fee = Decimal(taker)

    def set_balance(self, balance: Decimal):
        """Set account balance"""
        self.account_repository.set_balance(balance)

    def get_balance(self) -> Decimal:
        """Get current account balance"""
        return self.account_repository.get_balance()

    def set_leverage(self, symbol: str, leverage: Decimal):
        """Set leverage for symbol"""
        self.account_repository.set_leverage(symbol, leverage)

    def get_leverage(self, symbol: str) -> Decimal:
        """Get leverage for symbol"""
        return self.account_repository.get_leverage(symbol)

    def set_max_notional(self, notional: Decimal):
        """Set maximum notional"""
        self.max_notional = notional

    def set_base_timeframe(self, timeframe: str):
        """Set base timeframe for order execution

        Args:
            timeframe: The base timeframe to use (e.g., "1m", "3m")
        """
        self.base_timeframe = timeframe

    def get_candles(self, symbol: str, interval: str, limit: int) ->[Candle]:
        """Get candles from market data"""
        return self.market_data_adapter.get_candles(symbol, interval, limit)

    def add_complete_candle_listener(self, symbol: str, interval: str, listener: callable):
        """Add complete candle listener"""
        self.market_data_adapter.add_complete_candle_listener(symbol, interval, listener)

    def remove_complete_candle_listener(self, symbol: str, interval: str, listener: callable):
        """Remove complete candle listener"""
        self.market_data_adapter.remove_complete_candle_listener(symbol, interval, listener)

    def get_position(self, symbol: str, side: SIDE_TYPE) -> Position:
        """Get position for symbol and side"""
        return self.account_repository.get_position(symbol, side)

    def add_position_listener(self, listener: callable):
        """Add position event listener"""
        self.event_dispatcher.add_position_listener(listener)

    def remove_position_listener(self, listener: callable):
        """Remove position event listener"""
        self.event_dispatcher.remove_position_listener(listener)

    def add_orders_listener(self, listener: callable):
        """Add order event listener"""
        self.event_dispatcher.add_orders_listener(listener)

    def remove_order_listener(self, listener: callable):
        """Remove order event listener"""
        self.event_dispatcher.remove_order_listener(listener)

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
        # Validate price parameter based on order type
        if type == "market" and price is not None:
            raise ValueError("Market orders must not specify a price")
        if type == "limit" and price is None:
            raise ValueError("Limit orders must specify a price")

        candles = self.market_data_adapter.get_candles(symbol, self.base_timeframe, 10)
        if not candles:
            raise ValueError(f"No candles available for {symbol}")
        candle = candles[-1]

        # Check balance and notional for opening orders
        if (position_side == "long" and side == "buy") or (position_side == "short" and side == "sell"):
            long_position = self.get_position(symbol, "long")
            short_position = self.get_position(symbol, "short")
            positions_amount = abs(long_position.amount) + abs(short_position.amount)
            positions_notional = positions_amount * candle.close_price
            order_notional = abs(quantity) * candle.close_price

            if order_notional / self.get_leverage(symbol) > self.get_balance():
                raise ValueError("Insufficient balance")
            if positions_notional + order_notional > self.max_notional:
                raise ValueError("Max notional exceeded")

        order = self.orders_repository.new_order(symbol, position_side, side, type, quantity, price, order_id)

        if type == "market":
            order.price = candle.close_price
            self._complete_order(order, candle)
        else:
            self.market_data_adapter.add_internal_candle_listener(symbol, self.base_timeframe, self._on_candle_update)
            self.event_dispatcher.dispatch_order(order)

        return order

    def modify_order(self, order: Order) ->[Order]:
        """Modify existing order"""
        if (order.position_side == "long" and order.side == "buy") or (
            order.position_side == "short" and order.side == "sell"
        ):
            candles = self.market_data_adapter.get_candles(order.symbol, self.base_timeframe, 10)
            if not candles:
                return None
            candle = candles[-1]

            long_position = self.get_position(order.symbol, "long")
            short_position = self.get_position(order.symbol, "short")
            positions_amount = abs(long_position.amount) + abs(short_position.amount)
            positions_notional = positions_amount * candle.close_price
            order_notional = abs(order.quantity) * candle.close_price

            if order_notional / self.get_leverage(order.symbol) > self.get_balance():
                raise ValueError("Insufficient balance")
            if positions_notional + order_notional > self.max_notional:
                raise ValueError("Max notional exceeded")

        if order.type == "market":
            candles = self.market_data_adapter.get_candles(order.symbol, self.base_timeframe, 10)
            if candles:
                candle = candles[-1]
                order.price = candle.close_price
                self._complete_order(order, candle)
            self.orders_repository.delete_order(order.order_id)
        else:
            modified = self.orders_repository.modify_order(order)
            if modified:
                self.event_dispatcher.dispatch_order(order)
                return modified

        return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        order = self.orders_repository.get_order(order_id)
        if order is None:
            return False

        deleted = self.orders_repository.delete_order(order_id)
        order.status = "canceled"
        self.event_dispatcher.dispatch_order(order)

        orders = self.orders_repository.get_symbol_orders(order.symbol)
        if len(orders) == 0:
            self.market_data_adapter.remove_internal_candle_listener(order.symbol, self.base_timeframe, self._on_candle_update)

        return deleted

    def get_orders(self, symbol: str) ->[Order]:
        """Get all orders for symbol"""
        return self.orders_repository.get_symbol_orders(symbol)

    def add_trade_listener(self, listener: callable):
        """Add trade event listener"""
        self.event_dispatcher.add_trade_listener(listener)

    def _on_candle_update(self, candle: Candle):
        """Handle candle update - check and execute orders"""
        debug_logger = get_debug_logger("exchange.debug")
        orders:[Order] = self.orders_repository.get_symbol_orders(candle.symbol)

        # Check for liquidation (simplified)
        long_position = self.get_position(candle.symbol, "long")
        short_position = self.get_position(candle.symbol, "short")
        
        # Calculate unrealized P&L for long position (using worst case: low_price)
        long_unrealized_pnl = Decimal(0)
        if long_position.amount > 0:
            long_unrealized_pnl = long_position.amount * (candle.low_price - long_position.entry_price)
        
        # Calculate unrealized P&L for short position (using worst case: high_price)
        short_unrealized_pnl = Decimal(0)
        if short_position.amount < 0:
            short_unrealized_pnl = abs(short_position.amount) * (short_position.entry_price - candle.high_price)
        
        total_unrealized_pnl = long_unrealized_pnl + short_unrealized_pnl
        balance = self.get_balance()
        real_balance = balance + total_unrealized_pnl
        
        debug_logger.debug(
            f"_on_candle_update DEBUG - balance={balance}, "
            f"long_amount={long_position.amount}, long_entry={long_position.entry_price}, "
            f"long_unrealized_pnl={long_unrealized_pnl}, "
            f"short_amount={short_position.amount}, short_entry={short_position.entry_price}, "
            f"short_unrealized_pnl={short_unrealized_pnl}, "
            f"total_unrealized_pnl={total_unrealized_pnl}, "
            f"real_balance={real_balance}"
        )

        if real_balance < 0:
            debug_logger.debug(
                f"_on_candle_update DEBUG - LIQUIDATION TRIGGERED: "
                f"real_balance={real_balance} < 0, setting balance to 0"
            )
            # Liquidation - reset positions
            self.set_balance(Decimal(0))
            long_position = Position(
                symbol=candle.symbol,
                side="long",
                amount=Decimal(0),
                entry_price=Decimal(0),
                break_even=Decimal(0),
            )
            short_position = Position(
                symbol=candle.symbol,
                side="short",
                amount=Decimal(0),
                entry_price=Decimal(0),
                break_even=Decimal(0),
            )
            self.account_repository.set_position(long_position)
            self.account_repository.set_position(short_position)
            self.event_dispatcher.dispatch_positions(long_position)
            self.event_dispatcher.dispatch_positions(short_position)

        # Check orders for execution
        for order in orders:
            if order.position_side == "long":
                if (
                    (
                        order.side.lower() == "buy"
                        and (order.price >= candle.close_price or order.price >= candle.low_price)
                    )
                    or (
                        order.side.lower() == "sell"
                        and (order.price <= candle.close_price or order.price <= candle.high_price)
                    )
                ):
                    self._complete_order(order, candle)
            else:  # short
                if (
                    (
                        order.side.lower() == "sell"
                        and (order.price <= candle.close_price or order.price <= candle.high_price)
                    )
                    or (
                        order.side.lower() == "buy"
                        and (order.price >= candle.close_price or order.price >= candle.low_price)
                    )
                ):
                    self._complete_order(order, candle)

    def _complete_order(self, order: Order, candle: Candle):
        """Complete order execution - create trade and update position"""
        debug_logger = get_debug_logger("exchange.debug")
        balance_before = self.account_repository.get_balance()
        
        fee = self.maker_fee if order.type == "limit" else self.taker_fee

        trade_quantity = order.quantity
        if order.side == "sell":
            trade_quantity = -trade_quantity
        trade_size = trade_quantity * order.price

        position = self.account_repository.get_position(order.symbol, order.position_side)
        value = order.quantity * (order.price - position.entry_price)
        
        # Debug: log before state
        debug_logger.debug(
            f"_complete_order DEBUG - order: {order.position_side} {order.side} "
            f"qty={order.quantity} price={order.price}, balance_before={balance_before}, "
            f"position_amount={position.amount}, entry_price={position.entry_price}"
        )

        # Calculate realized P&L
        realized_pnl = Decimal(0)
        is_opening_position = (order.position_side == "long" and order.side == "buy") or (
            order.position_side == "short" and order.side == "sell"
        )
        is_closing_position = (order.position_side == "long" and order.side == "sell") or (
            order.position_side == "short" and order.side == "buy"
        )
        
        commission = abs(order.quantity * order.price * fee)
        
        # Update balance based on trade type
        if order.position_side == "long" and order.side == "sell":
            # For long position close:
            # - Add P&L (price difference * quantity)
            # - Subtract commission
            total_change = value - commission
            debug_logger.debug(
                f"_complete_order DEBUG - CLOSING long: value={value}, commission={commission}, "
                f"total_balance_change={total_change}"
            )
            self.account_repository.update_balance(total_change)
            realized_pnl = value - commission
        elif order.position_side == "short" and order.side == "buy":
            # For short position close:
            # - Subtract P&L (negative for shorts: entry_price - exit_price)
            # - Subtract commission
            total_change = -value - commission
            debug_logger.debug(
                f"_complete_order DEBUG - CLOSING short: value={-value}, commission={commission}, "
                f"total_balance_change={total_change}"
            )
            self.account_repository.update_balance(total_change)
            realized_pnl = -value - commission
        else:
            # Opening position: deduct commission only
            total_change = Decimal(0)
            if is_opening_position:
                total_change = -commission
                debug_logger.debug(
                    f"_complete_order DEBUG - OPENING position: commission={commission}, "
                    f"total_balance_change={total_change}"
                )
                self.account_repository.update_balance(total_change)
            else:
                # Should not happen, but if it does, at least deduct commission
                debug_logger.debug(
                    f"_complete_order DEBUG - Unexpected case, deducting commission: {commission}"
                )
                self.account_repository.update_balance(-commission)
        
        balance_after = self.account_repository.get_balance()
        debug_logger.debug(
            f"_complete_order DEBUG - balance_before={balance_before}, "
            f"balance_after={balance_after}, realized_pnl={realized_pnl}, "
            f"total_change={balance_after - balance_before}"
        )

        # Determine if position closes completely
        new_position_amount = position.amount + trade_quantity
        closes_completely = new_position_amount == 0

        # Create trade
        trade = Trade(
            order_id=order.order_id or "",
            timestamp=candle.timestamp,  # int timestamp
            symbol=order.symbol,
            position_side=order.position_side,
            side=order.side,
            price=order.price,
            quantity=order.quantity,
            commission=abs(order.quantity * order.price * fee),
            realized_pnl=realized_pnl,
            closes_position_completely=closes_completely,
        )

        self.trades_repository.add_trade(trade)
        self.event_dispatcher.dispatch_trade(trade)

        order.status = "filled"
        self.orders_repository.delete_order(order.order_id or "")
        self.event_dispatcher.dispatch_order(order)

        # Update position
        new_position_amount = position.amount + trade_quantity
        position.commission += abs(trade.commission) if trade_quantity > 0 else -abs(trade.commission)

        if new_position_amount == 0:
            # Position closed
            position = Position(
                symbol=trade.symbol,
                side=trade.position_side,
                amount=new_position_amount,
                entry_price=Decimal(0),
                break_even=Decimal(0),
            )
        else:
            # Update position entry price and break even
            if (position.side == "long" and trade.side == "buy") or (position.side == "short" and trade.side == "sell"):
                # Opening position
                # For entry price calculation, use absolute value of trade_size
                # entry_price should always be positive (price at which position was opened)
                trade_size_abs = abs(trade_size)
                position.break_even = (
                    ((position.break_even * abs(position.amount)) + trade_size_abs) + (trade.commission * 2)
                ) / abs(new_position_amount)
                position.entry_price = (
                    ((position.entry_price * abs(position.amount)) + trade_size_abs) / abs(new_position_amount)
                )
            else:
                # Closing position
                trade_size_abs = abs(trade_size)
                position.break_even = (
                    ((position.break_even * abs(position.amount)) + trade_size_abs) / abs(new_position_amount)
                )

            position.add_trade(trade)
            position.amount = new_position_amount

        self.account_repository.set_position(position)
        self.event_dispatcher.dispatch_positions(position)
