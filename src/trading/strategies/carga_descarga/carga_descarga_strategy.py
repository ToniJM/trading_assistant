"""CargaDescarga trading strategy"""

import datetime
import time
from decimal import ROUND_DOWN, ROUND_UP, Decimal, getcontext

from trading.domain.entities import Candle, Cycle, Order, Trade
from trading.domain.ports import (
    CycleListenerPort,
    ExchangePort,
    MarketDataPort,
    OperationsStatusRepositoryPort,
    StrategyPort,
)
from trading.domain.types import ORDER_SIDE_TYPE, ORDER_TYPE_TYPE, SIDE_TYPE
from trading.infrastructure.logging import get_debug_logger, get_logger

from .adapters.event_dispatcher import EventDispatcher
from .adapters.logger_decorator import method_logger


# Lazy imports to avoid blocking on startup
def _get_indicators():
    """Lazy import for stock_indicators - only import specific functions to reduce memory usage"""
    import os

    from trading.infrastructure.logging import get_debug_logger

    debug_logger = get_debug_logger("strategy.debug")
    debug_logger.debug("_get_indicators(): iniciando import de stock_indicators")

    # Configure pythonnet to use .NET Core instead of Mono (required on macOS)
    # This must be done BEFORE importing any stock_indicators module
    if "PYTHONNET_RUNTIME" not in os.environ:
        debug_logger.debug("_get_indicators(): configurando PYTHONNET_RUNTIME=coreclr")
        os.environ["PYTHONNET_RUNTIME"] = "coreclr"

    try:
        debug_logger.debug("_get_indicators(): importando stock_indicators.indicators.stoch_rsi.get_stoch_rsi...")
        from stock_indicators.indicators.stoch_rsi import get_stoch_rsi

        debug_logger.debug("_get_indicators(): get_stoch_rsi importado exitosamente")

        debug_logger.debug("_get_indicators(): importando stock_indicators.indicators.fractal.get_fractal...")
        from stock_indicators.indicators.fractal import get_fractal

        debug_logger.debug("_get_indicators(): get_fractal importado exitosamente")

        debug_logger.debug("_get_indicators(): creando clase Indicators...")

        # Return a simple object with only the functions we need
        class Indicators:
            @staticmethod
            def get_stoch_rsi(quotes, rsi_periods, stoch_periods, signal_periods, smooth_periods):
                return get_stoch_rsi(quotes, rsi_periods, stoch_periods, signal_periods, smooth_periods)

            @staticmethod
            def get_fractal(quotes, left_span, right_span):
                return get_fractal(quotes, left_span, right_span)

        debug_logger.debug("_get_indicators(): clase Indicators creada exitosamente")

        debug_logger.debug("_get_indicators(): instanciando Indicators...")
        indicators = Indicators()
        debug_logger.debug("_get_indicators(): Indicators instanciado exitosamente, retornando...")

        return indicators

    except ImportError as e:
        debug_logger.error(f"_get_indicators(): ImportError durante import: {e}")
        debug_logger.error(f"_get_indicators(): tipo de error: {type(e).__name__}")
        raise
    except Exception as e:
        debug_logger.error(f"_get_indicators(): Error inesperado durante import: {e}")
        debug_logger.error(f"_get_indicators(): tipo de error: {type(e).__name__}")
        debug_logger.error(f"_get_indicators(): traceback: {e.__traceback__}")
        raise


def _get_quote():
    """Lazy import for Quote"""
    from stock_indicators.indicators.common.quote import Quote

    return Quote


def _get_rich():
    """Lazy import for rich (only used for rendering)"""
    from rich.columns import Columns
    from rich.console import Console
    from rich.panel import Panel

    return Columns, Console, Panel


class CargaDescargaStrategy(StrategyPort):
    rsi_limits = [15, 50, 85]

    def __init__(
        self,
        symbol,
        exchange: ExchangePort,
        market_data: MarketDataPort,
        operation_status_repository: OperationsStatusRepositoryPort,
        cycle_dispatcher: CycleListenerPort = None,
        strategy_name: str = "default",
        timeframes: list[str] = None,
    ):
        self.logger = get_logger(self.__class__.__name__)
        self.logger.debug("__init__")

        self._symbol = symbol
        self._strategy_name = strategy_name
        
        # Set timeframes: use provided or default
        if timeframes is None:
            self.timeframes = ["1m", "15m", "1h"]
        else:
            self.timeframes = timeframes

        self.market_data = market_data
        self.exchange = exchange
        self.operations_status = operation_status_repository
        self.cycle_dispatcher = cycle_dispatcher or EventDispatcher()

        self.market_data.add_complete_candle_listener(self.symbol, self.timeframes[0], self.on_kline)
        self.exchange.add_trade_listener(self.symbol, self.on_trade)

        self.render_data = {}

        # Cache para RSI y fractales - evita recálculos innecesarios
        self._rsi_cache = {}
        self._fractals_cache = {}
        self._last_candle_timestamp = None

        # Cache para datos constantes que no cambian durante el backtest
        self._symbol_info_cache = None
        self._qty_decimals_cache = None
        self._price_decimals_cache = None

        # Cycle tracking state
        self._current_cycle_start = None
        self._current_cycle_long_max_loads = 0
        self._current_cycle_short_max_loads = 0
        self._current_cycle_long_trades = 0
        self._current_cycle_short_trades = 0
        self._previous_long_amount = 0
        self._previous_short_amount = 0

    @property
    def symbol(self) -> str:
        """Get the trading symbol this strategy operates on"""
        return self._symbol

    @property
    def strategy_name(self) -> str:
        """Get the name of this strategy"""
        return self._strategy_name

    @method_logger()
    def on_trade(self, trade: Trade):
        debug_logger = get_debug_logger("strategy.debug")

        self.logger.info(f"Trade: {trade.symbol} {trade.position_side} {trade.side} {trade.quantity} {trade.price}")

        # Debug logs para diagnosticar realized_pnl
        debug_logger.debug(
            f"on_trade DEBUG - trade.symbol={trade.symbol}, "
            f"trade.position_side={trade.position_side}, trade.side={trade.side}"
        )
        debug_logger.debug(f"on_trade DEBUG - trade.quantity={trade.quantity}, trade.price={trade.price}")
        debug_logger.debug(
            f"on_trade DEBUG - trade.realized_pnl value={trade.realized_pnl}, type={type(trade.realized_pnl)}"
        )
        debug_logger.debug(
            f"on_trade DEBUG - trade.realized_pnl as float={float(trade.realized_pnl)}, "
            f"as str={str(trade.realized_pnl)}"
        )
        debug_logger.debug(f"on_trade DEBUG - trade.realized_pnl != 0: {trade.realized_pnl != 0}")
        debug_logger.debug(f"on_trade DEBUG - trade.realized_pnl != Decimal(0): {trade.realized_pnl != Decimal(0)}")
        debug_logger.debug(f"on_trade DEBUG - bool(trade.realized_pnl): {bool(trade.realized_pnl)}")
        debug_logger.debug(f"on_trade DEBUG - trade.closes_position_completely={trade.closes_position_completely}")

        # Log PnL when trade closes position (total or partial)
        if trade.realized_pnl != 0:
            debug_logger.debug("on_trade DEBUG - ENTERING if trade.realized_pnl != 0 block")
            close_type = "complete" if trade.closes_position_completely else "partial"
            self.logger.info(
                f"Position close ({close_type}): {trade.symbol} {trade.position_side} "
                f"PnL={trade.realized_pnl} quantity={trade.quantity} price={trade.price}"
            )
        else:
            debug_logger.debug("on_trade DEBUG - NOT entering if trade.realized_pnl != 0 block (realized_pnl is 0)")

        self.operations_status.set_operation_status(trade.position_side, trade.side, True)

        # Track cycle state
        self._track_cycle_state(trade)

        orders = self.exchange.get_orders(self.symbol)
        for order in orders:
            self.exchange.cancel_order(self.symbol, order.order_id)
            order_info = (
                f"{order.order_id} {order.symbol} {order.position_side} "
                f"{order.side} {order.type} {order.price} {order.quantity}"
            )
            self.logger.info(f"Cancel order: {order_info}")

    def on_kline(self, candle: Candle):
        debug_logger = get_debug_logger("strategy.debug")
        debug_logger.debug(
            f"on_kline() iniciado: symbol={candle.symbol}, timeframe={candle.timeframe}, "
            f"timestamp={candle.timestamp}, close_price={candle.close_price}"
        )

        # Limpiar cache cuando llega una nueva vela
        if self._last_candle_timestamp != candle.timestamp:
            self._rsi_cache.clear()
            self._fractals_cache.clear()
            self._last_candle_timestamp = candle.timestamp
            debug_logger.debug("Cache de RSI y fractales limpiado")

        self.render_data = {}
        debug_logger.debug("Obteniendo posiciones del exchange...")
        long_position = self.exchange.get_position(self.symbol, "long")
        short_position = self.exchange.get_position(self.symbol, "short")
        debug_logger.debug(
            f"Posiciones obtenidas: long_amount={long_position.amount}, short_amount={short_position.amount}"
        )

        self.render_data["long_position"] = long_position
        self.render_data["short_position"] = short_position

        debug_logger.debug("Llamando _get_symbol_info()...")
        symbol_info = self._get_symbol_info()
        debug_logger.debug(f"_get_symbol_info() retornó: symbol={symbol_info.symbol}, notional={symbol_info.notional}")
        amount = symbol_info.notional / candle.close_price
        min_amount = self.round_up(amount, self._get_qty_decimals())

        long_loads = long_position.get_load_count()
        short_loads = short_position.get_load_count(min_amount)

        long_tf = min(long_loads // 3, 2)
        short_tf = min(short_loads // 3, 2)
        is_long_last_tf_load = long_loads % 3 == 0 if long_loads > 0 else False
        is_short_last_tf_load = short_loads % 3 == 0 if short_loads > 0 else False
        r = max(long_tf, short_tf)
        increase_long = True
        decrease_long = True
        increase_short = True
        decrease_short = True

        debug_logger.debug(
            f"Cálculos iniciales completados: long_loads={long_loads}, short_loads={short_loads}, "
            f"long_tf={long_tf}, short_tf={short_tf}, r={r}"
        )

        long_commission = long_position.commission
        short_commission = short_position.commission
        if long_position.amount > Decimal("0") and candle.close_price < long_position.entry_price + (
            long_commission * 2
        ):
            decrease_long = False
            debug_logger.debug("cancel_orders(long, sell) - condición 1")
            self.cancel_orders("long", "sell")
        if abs(short_position.amount) > Decimal("0") and candle.close_price > short_position.entry_price - (
            short_commission * 2
        ):
            decrease_short = False
            debug_logger.debug("cancel_orders(short, buy) - condición 1")
            self.cancel_orders("short", "buy")

        if long_loads >= 3 and candle.close_price > long_position.entry_price - (long_commission * 2):
            increase_long = False
            debug_logger.debug("cancel_orders(long, buy) - condición 2")
            self.cancel_orders("long", "buy")
        if short_loads >= 3 and candle.close_price < short_position.entry_price + (short_commission * 2):
            increase_short = False
            debug_logger.debug("cancel_orders(short, sell) - condición 2")
            self.cancel_orders("short", "sell")

        timeframes_list = [self.timeframes[i] for i in reversed(range(r + 1))]
        debug_logger.debug(f"Iniciando loop de RSI: r={r}, timeframes={timeframes_list}")
        self.render_data["rsi_levels"] = []
        for i in reversed(range(r + 1)):
            timeframe = self.timeframes[i]
            debug_logger.debug(f"Loop RSI iteración {i}: llamando _get_rsi({timeframe})")
            candle_rsi = self._get_rsi(timeframe)
            debug_logger.debug(f"_get_rsi({timeframe}) retornó: {candle_rsi}")
            self.render_data["rsi_levels"].append(candle_rsi)
            if i > 0:
                if candle_rsi > self.rsi_limits[0]:
                    if i <= long_tf:
                        increase_long = False
                        self.cancel_orders("long", "buy")
                    if (is_short_last_tf_load and i < short_tf) or (not is_short_last_tf_load and i <= short_tf):
                        decrease_short = False
                        self.cancel_orders("short", "buy")
                if candle_rsi < self.rsi_limits[2]:
                    if (is_long_last_tf_load and i < long_tf) or (not is_long_last_tf_load and i <= long_tf):
                        decrease_long = False
                        self.cancel_orders("long", "sell")
                    if i <= short_tf:
                        increase_short = False
                        self.cancel_orders("short", "sell")
            if candle_rsi > self.rsi_limits[1]:
                if i == long_tf and self.operations_status.get_operation_status("long", "buy"):
                    self.operations_status.set_operation_status("long", "buy", False)
                if (
                    i == short_tf or (is_short_last_tf_load and i == short_tf - 1)
                ) and self.operations_status.get_operation_status("short", "buy"):
                    self.operations_status.set_operation_status("short", "buy", False)
            if candle_rsi < self.rsi_limits[1]:
                if (
                    i == long_tf or (is_long_last_tf_load and i == long_tf - 1)
                ) and self.operations_status.get_operation_status("long", "sell"):
                    self.operations_status.set_operation_status("long", "sell", False)
                if i == short_tf and self.operations_status.get_operation_status("short", "sell"):
                    self.operations_status.set_operation_status("short", "sell", False)

        if long_position.amount == 0:
            decrease_long = False
        if short_position.amount == 0:
            decrease_short = False

        debug_logger.debug(
            f"Antes de crear órdenes: increase_long={increase_long}, decrease_long={decrease_long}, "
            f"increase_short={increase_short}, decrease_short={decrease_short}"
        )

        if increase_long or decrease_long or increase_short or decrease_short:
            debug_logger.debug("Creando órdenes: obteniendo órdenes existentes...")
            orders = self.exchange.get_orders(self.symbol)

            posible_prices = self.get_posible_prices(candle.close_price)
            candle_rsi = self._get_rsi(self.timeframes[0])
            sell_price = candle.close_price
            buy_price = candle.close_price
            if candle_rsi < self.rsi_limits[0]:
                sell_price = posible_prices["up"][-1]
                buy_price = posible_prices["down"][0]
            elif candle_rsi > self.rsi_limits[2]:
                sell_price = posible_prices["up"][0]
                buy_price = posible_prices["down"][-1]
            elif candle_rsi < self.rsi_limits[1]:
                sell_price = posible_prices["up"][2]
                buy_price = posible_prices["down"][1]
            else:
                sell_price = posible_prices["up"][1]
                buy_price = posible_prices["down"][2]

            sell_price = self.round_up(sell_price, self._get_price_decimals())
            buy_price = self.round_down(buy_price, self._get_price_decimals())

            long_value = long_position.amount * (
                candle.close_price - long_position.entry_price
            )  # Valor de la posición long
            short_value = short_position.amount * (
                candle.close_price - short_position.entry_price
            )  # Valor de la posición short
            positions_value = long_value + short_value

            if long_loads >= 4 and short_loads >= 4:
                if increase_long and decrease_short and positions_value > 0:
                    if long_loads <= short_loads:
                        increase_long = False
                        self.cancel_orders("long", "buy")
                        self.new_order(
                            self.symbol,
                            "long",
                            "sell",
                            "market",
                            abs(long_position.amount),
                        )
                        decrease_short = False
                        self.cancel_orders("short", "buy")
                        self.new_order(
                            self.symbol,
                            "short",
                            "buy",
                            "market",
                            abs(short_position.amount),
                        )

                if increase_short and decrease_long and positions_value > 0:
                    if short_loads <= long_loads:
                        increase_short = False
                        self.cancel_orders("short", "sell")
                        self.new_order(
                            self.symbol,
                            "short",
                            "buy",
                            "market",
                            abs(short_position.amount),
                        )
                        decrease_long = False
                        self.cancel_orders("long", "sell")
                        self.new_order(
                            self.symbol,
                            "long",
                            "sell",
                            "market",
                            abs(long_position.amount),
                        )

            if increase_long and not self.operations_status.get_operation_status("long", "buy"):
                buy_long = next(
                    (order for order in orders if order.position_side == "long" and order.side == "buy"),
                    None,
                )
                qty = min_amount
                if long_position.amount > 0:
                    qty = long_position.amount
                if buy_long is not None:
                    if buy_long.price != buy_price or buy_long.quantity != qty:
                        buy_long.quantity = Decimal(str(qty))
                        buy_long.price = buy_price
                        buy_long.type = "limit"
                        self.modify_order(buy_long)
                else:
                    self.new_order(
                        self.symbol,
                        "long",
                        "buy",
                        "limit",
                        Decimal(str(qty)),
                        buy_price,
                    )
            if decrease_long and not self.operations_status.get_operation_status("long", "sell"):
                commissions = long_commission
                if sell_price > long_position.entry_price + (commissions * 2):
                    sell_long = next(
                        (order for order in orders if order.position_side == "long" and order.side == "sell"),
                        None,
                    )
                    qty = self.round_up(long_position.amount / 2, self._get_qty_decimals())
                    if qty < min_amount:
                        qty = long_position.amount
                    if sell_long is not None:
                        if sell_long.price != sell_price or sell_long.quantity != qty:
                            sell_long.quantity = Decimal(str(qty))
                            sell_long.price = sell_price
                            sell_long.type = "limit"
                            self.modify_order(sell_long)
                    else:
                        self.new_order(
                            self.symbol,
                            "long",
                            "sell",
                            "limit",
                            Decimal(str(qty)),
                            sell_price,
                        )
            if increase_short and not self.operations_status.get_operation_status("short", "sell"):
                sell_short = next(
                    (order for order in orders if order.position_side == "short" and order.side == "sell"),
                    None,
                )
                qty = min_amount
                if short_position.amount < 0:
                    qty = abs(short_position.amount)
                if sell_short is not None:
                    if sell_short.price != sell_price or sell_short.quantity != qty:
                        sell_short.quantity = Decimal(str(qty))
                        sell_short.price = sell_price
                        sell_short.type = "limit"
                        self.modify_order(sell_short)
                else:
                    self.new_order(
                        self.symbol,
                        "short",
                        "sell",
                        "limit",
                        Decimal(str(qty)),
                        sell_price,
                    )
            if decrease_short and not self.operations_status.get_operation_status("short", "buy"):
                commissions = short_commission
                if buy_price < short_position.entry_price - (commissions * 2):
                    buy_short = next(
                        (order for order in orders if order.position_side == "short" and order.side == "buy"),
                        None,
                    )
                    qty = abs(self.round_up(short_position.amount / 2, self._get_qty_decimals()))
                    if qty < min_amount:
                        qty = abs(short_position.amount)
                    if buy_short is not None:
                        if buy_short.price != buy_price or buy_short.quantity != qty:
                            buy_short.quantity = Decimal(str(qty))
                            buy_short.price = buy_price
                            buy_short.type = "limit"
                            self.modify_order(buy_short)
                    else:
                        self.new_order(
                            self.symbol,
                            "short",
                            "buy",
                            "limit",
                            Decimal(str(qty)),
                            buy_price,
                        )

        self.render_data["orders"] = self.exchange.get_orders(self.symbol)
        self.render_data["operations_status"] = {
            "long": {
                "buy": self.operations_status.get_operation_status("long", "buy"),
                "sell": self.operations_status.get_operation_status("long", "sell"),
            },
            "short": {
                "buy": self.operations_status.get_operation_status("short", "buy"),
                "sell": self.operations_status.get_operation_status("short", "sell"),
            },
        }
        # Deshabilitar renderizado durante backtest para mejorar rendimiento
        # self.render()

    def _get_rsi(self, timeframe: str) -> Decimal:
        debug_logger = get_debug_logger("strategy.debug")
        debug_logger.debug(f"_get_rsi({timeframe}): iniciando")

        # Verificar si ya tenemos el RSI calculado para este timeframe
        if timeframe in self._rsi_cache:
            debug_logger.debug(f"_get_rsi({timeframe}): usando cache, valor={self._rsi_cache[timeframe]}")
            return self._rsi_cache[timeframe]

        debug_logger.debug(f"_get_rsi({timeframe}): cache vacío, calculando RSI...")
        # Calcular RSI solo si no está en cache
        debug_logger.debug(f"_get_rsi({timeframe}): llamando _get_indicators()...")
        indicators = _get_indicators()
        debug_logger.debug(f"_get_rsi({timeframe}): _get_indicators() retornó exitosamente")
        debug_logger.debug(f"_get_rsi({timeframe}): obteniendo 100 velas para {self.symbol}")
        candles = self.market_data.get_candles(self.symbol, timeframe, 100)
        debug_logger.debug(f"_get_rsi({timeframe}): obtenidas {len(candles)} velas, convirtiendo a quotes...")
        quotes = self._klines_to_quotes(candles)
        debug_logger.debug(f"_get_rsi({timeframe}): calculando stoch_rsi...")
        stoch_rsi = indicators.get_stoch_rsi(quotes, 14, 14, 3, 3)
        rsi_value = stoch_rsi[-1].stoch_rsi
        debug_logger.debug(f"_get_rsi({timeframe}): RSI calculado={rsi_value}")

        # Guardar en cache
        self._rsi_cache[timeframe] = rsi_value
        debug_logger.debug(f"_get_rsi({timeframe}): guardado en cache")
        return rsi_value

    def _get_fractals(self, timeframe: str) -> list:
        debug_logger = get_debug_logger("strategy.debug")
        debug_logger.debug(f"_get_fractals({timeframe}): iniciando")

        # Verificar si ya tenemos los fractales calculados para este timeframe
        if timeframe in self._fractals_cache:
            fractals_count = len(self._fractals_cache[timeframe])
            debug_logger.debug(f"_get_fractals({timeframe}): usando cache, {fractals_count} fractales")
            return self._fractals_cache[timeframe]

        debug_logger.debug(f"_get_fractals({timeframe}): cache vacío, calculando fractales...")
        # Calcular fractales solo si no están en cache
        debug_logger.debug(f"_get_fractals({timeframe}): llamando _get_indicators()...")
        indicators = _get_indicators()
        debug_logger.debug(f"_get_fractals({timeframe}): _get_indicators() retornó exitosamente")
        debug_logger.debug(f"_get_fractals({timeframe}): obteniendo 100 velas para {self.symbol}")
        candles = self.market_data.get_candles(self.symbol, timeframe, 100)
        debug_logger.debug(f"_get_fractals({timeframe}): obtenidas {len(candles)} velas, convirtiendo a quotes...")
        quotes = self._klines_to_quotes(candles)
        debug_logger.debug(f"_get_fractals({timeframe}): calculando fractales...")
        fractals = indicators.get_fractal(quotes, 2, 2)  # left_span=2, right_span=2
        debug_logger.debug(f"_get_fractals({timeframe}): calculados {len(fractals)} fractales")

        # Guardar en cache
        self._fractals_cache[timeframe] = fractals
        debug_logger.debug(f"_get_fractals({timeframe}): guardado en cache")
        return fractals

    def _klines_to_quotes(self, klines: list[Candle]) -> list:
        """parsear las klines a quotes

        Args:
            klines (list[Candle]): klines
        """
        quote = _get_quote()
        quotes = []
        for kline in klines:
            quotes.append(
                quote(
                    datetime.datetime.fromtimestamp(kline.timestamp / 1000),
                    kline.open_price,
                    kline.high_price,
                    kline.low_price,
                    kline.close_price,
                    kline.volume,
                )
            )
        return quotes

    def round_up(self, num, decimals):
        getcontext().prec = decimals + 10  # Precisión suficiente para evitar errores
        factor = Decimal("1." + "0" * decimals)
        return Decimal(num).quantize(factor, rounding=ROUND_UP).normalize()

    def round_down(self, num, decimals):
        getcontext().prec = decimals + 10  # Precisión suficiente para evitar errores
        factor = Decimal("1." + "0" * decimals)
        return Decimal(num).quantize(factor, rounding=ROUND_DOWN).normalize()

    def _get_symbol_info(self):
        """Obtener symbol_info con cache"""
        debug_logger = get_debug_logger("strategy.debug")
        if self._symbol_info_cache is None:
            debug_logger.debug(f"_get_symbol_info(): cache vacío, llamando market_data.get_symbol_info({self.symbol})")
            self._symbol_info_cache = self.market_data.get_symbol_info(self.symbol)
            debug_logger.debug(f"_get_symbol_info(): cache poblado exitosamente para {self.symbol}")
        else:
            debug_logger.debug(f"_get_symbol_info(): usando cache para {self.symbol}")
        return self._symbol_info_cache

    def _get_qty_decimals(self):
        """Obtener decimales de cantidad con cache"""
        if self._qty_decimals_cache is None:
            info = self._get_symbol_info()
            self._qty_decimals_cache = self.check_decimals(info.min_qty)
        return self._qty_decimals_cache

    def _get_price_decimals(self):
        """Obtener decimales de precio con cache"""
        if self._price_decimals_cache is None:
            info = self._get_symbol_info()
            self._price_decimals_cache = self.check_decimals(info.tick_size)
        return self._price_decimals_cache

    def check_qty_decimals(self):
        info = self.market_data.get_symbol_info(self.symbol)
        return self.check_decimals(info.min_qty)

    def check_price_decimals(self):
        info = self.market_data.get_symbol_info(self.symbol)
        return self.check_decimals(info.tick_size)

    def check_decimals(self, ref):
        decimal = 0
        is_dec = False
        ref = str(ref)
        for c in ref:
            if is_dec is True:
                decimal += 1
            if c == "1":
                break
            if c == ".":
                is_dec = True
        return decimal

    def get_posible_prices(self, price: Decimal):
        """obtener los precios posibles

        Args:
            price (Decimal): Precio base
        """
        debug_logger = get_debug_logger("strategy.debug")
        debug_logger.debug(f"get_posible_prices({price}): iniciando")

        prices = {"up": [], "down": []}
        last_up = price
        last_down = price
        for i in range(len(self.timeframes)):
            timeframe = self.timeframes[i]
            timeframe_info = f"timeframe {i + 1}/{len(self.timeframes)}: {timeframe}"
            debug_logger.debug(f"get_posible_prices({price}): obteniendo fractales para {timeframe_info}")
            fractals = self._get_fractals(timeframe)
            debug_logger.debug(f"get_posible_prices({price}): obtenidos {len(fractals)} fractales para {timeframe}")
            for fractal in reversed(fractals):
                if fractal.fractal_bear is not None and len(prices["up"]) < 4:
                    if fractal.fractal_bear > last_up:
                        prices["up"].append(((fractal.fractal_bear - last_up) / 2) + last_up)
                        last_up = fractal.fractal_bear
                elif fractal.fractal_bull is not None and len(prices["down"]) < 4:
                    if fractal.fractal_bull < last_down:
                        prices["down"].append(((last_down - fractal.fractal_bull) / 2) + fractal.fractal_bull)
                        last_down = fractal.fractal_bull
                if len(prices["up"]) == 4 and len(prices["down"]) == 4:
                    up_count = len(prices["up"])
                    down_count = len(prices["down"])
                    debug_logger.debug(f"get_posible_prices({price}): completado - up={up_count}, down={down_count}")
                    break
            if len(prices["up"]) == 4 and len(prices["down"]) == 4:
                up_count = len(prices["up"])
                down_count = len(prices["down"])
                debug_logger.debug(f"get_posible_prices({price}): completado - up={up_count}, down={down_count}")
                break

        up_count = len(prices["up"])
        down_count = len(prices["down"])
        debug_logger.debug(f"get_posible_prices({price}): después de loops - up={up_count}, down={down_count}")
        if len(prices["up"]) == 0:
            prices["up"].append(price * Decimal("1.02"))
        if len(prices["down"]) == 0:
            prices["down"].append(price * Decimal("0.98"))
        for i in range(4 - len(prices["up"])):
            prices["up"].append(prices["up"][-1] * Decimal("1.02"))
        for i in range(4 - len(prices["down"])):
            prices["down"].append(prices["down"][-1] * Decimal("0.98"))
        up_count = len(prices["up"])
        down_count = len(prices["down"])
        debug_logger.debug(f"get_posible_prices({price}): retornando - up={up_count}, down={down_count}")
        return prices

    @method_logger()
    def cancel_orders(self, position_side: str, side: str):
        debug_logger = get_debug_logger("strategy.debug")
        debug_logger.debug(f"cancel_orders({position_side}, {side}): iniciando para {self.symbol}")

        orders = self.exchange.get_orders(self.symbol)
        debug_logger.debug(f"cancel_orders({position_side}, {side}): obtenidas {len(orders)} órdenes totales")

        canceled_count = 0
        for order in orders:
            if order.position_side == position_side and order.side == side:
                debug_logger.debug(f"cancel_orders({position_side}, {side}): cancelando orden {order.order_id}")
                self.exchange.cancel_order(self.symbol, order.order_id)
                canceled_count += 1
                order_info = (
                    f"{order.order_id} {order.symbol} {order.position_side} "
                    f"{order.side} {order.type} {order.price} {order.quantity}"
                )
                self.logger.info(f"Canceled order: {order_info}")

        debug_logger.debug(f"cancel_orders({position_side}, {side}): completado - {canceled_count} órdenes canceladas")

    def new_order(
        self,
        symbol: str,
        position_side: SIDE_TYPE,
        side: ORDER_SIDE_TYPE,
        type: ORDER_TYPE_TYPE,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> Order | None:
        try:
            order = self.exchange.new_order(symbol, position_side, side, type, quantity, price)
            price_str = f"{price}" if price is not None else "market"
            self.logger.info(f"New order: {symbol} {position_side} {side} {type} {price_str} {quantity}")
            return order
        except Exception as e:
            self.logger.error(f"Error creating order: {e}")
            return None

    def modify_order(self, order: Order) -> Order | None:
        try:
            order = self.exchange.modify_order(order)
            order_info = (
                f"{order.order_id} {order.symbol} {order.position_side} "
                f"{order.side} {order.type} {order.price} {order.quantity}"
            )
            self.logger.info(f"Modify order: {order_info}")
            return order
        except Exception as e:
            self.logger.error(f"Error modifying order: {e}")
            return None

    def render(self):
        """renderizar la consola"""
        columns_cls, console_cls, panel_cls = _get_rich()
        console = console_cls()
        # console.clear()

        loads_content = ""
        for side in ["long", "short"]:
            loads_content += f"{side.upper()}:\n"
            if side == "long":
                loads = self.render_data["long_position"].get_load_count()
            else:
                loads = self.render_data["short_position"].get_load_count()
            loads_content += f"{loads}\n"

        panel_loads = panel_cls(
            f"{loads_content}",
            title="Loads",
            subtitle="Contenido de loads",
            style="cyan",
        )

        orders_content = ""
        for position_side in ["long", "short"]:
            orders_content += f"{position_side.upper()}:\n"

            for side in ["buy", "sell"]:
                for order in self.render_data["orders"]:
                    if order.position_side == position_side and order.side == side:
                        orders_content += f"\t{side}: qty:{order.quantity} price:{order.price}\n"
                        break
            orders_content += "\n"
        panel_orders = panel_cls(
            f"{orders_content}",
            title="Orders",
            subtitle="Contenido de orders",
            style="blue",
        )

        done_sides_content = ""
        for side, items in self.render_data["operations_status"].items():
            done_sides_content += f"{side.upper()}:\n"
            for key, value in items.items():
                done_sides_content += f"\t{key}: {value}"
            done_sides_content += "\n"
        panel_done_sides = panel_cls(
            f"{done_sides_content}",
            title="Done Sides",
            subtitle="Contenido de done_sides",
            style="green",
        )

        rsi_levels_content = ""
        for level in self.render_data["rsi_levels"]:
            rsi_levels_content += f"{level}\n"
        panel_rsi_levels = panel_cls(
            f"{rsi_levels_content}",
            title="RSI Levels",
            subtitle="Contenido de rsi_levels",
            style="green",
        )

        columns = columns_cls([panel_loads, panel_done_sides, panel_orders, panel_rsi_levels], expand=True)
        console.print(columns)

    def _track_cycle_state(self, trade: Trade):
        """Track cycle state and detect cycle completion"""
        # Get current positions
        long_position = self.exchange.get_position(self.symbol, "long")
        short_position = self.exchange.get_position(self.symbol, "short")

        current_long_amount = long_position.amount
        current_short_amount = short_position.amount

        # Get trade timestamp (convert if string)
        try:
            trade_timestamp = int(trade.timestamp) if isinstance(trade.timestamp, str) else trade.timestamp
        except (ValueError, TypeError):
            self.logger.warning(f"Invalid trade timestamp: {trade.timestamp}, using current time")
            trade_timestamp = int(time.time() * 1000)

        # Start new cycle if both positions are zero and we weren't in a cycle
        if current_long_amount == 0 and current_short_amount == 0 and self._current_cycle_start is None:
            self._start_new_cycle(trade_timestamp)
            return

        # If we're in a cycle, track metrics
        if self._current_cycle_start is not None:
            # Count trades per position
            if trade.position_side == "long":
                self._current_cycle_long_trades += 1
            else:
                self._current_cycle_short_trades += 1

            # Track max loads reached
            if current_long_amount > 0:
                long_loads = long_position.get_load_count()
                self._current_cycle_long_max_loads = max(self._current_cycle_long_max_loads, long_loads)

            if current_short_amount < 0:
                short_loads = short_position.get_load_count()
                self._current_cycle_short_max_loads = max(self._current_cycle_short_max_loads, short_loads)

            # Check if cycle is complete (both positions are zero)
            if current_long_amount == 0 and current_short_amount == 0:
                self._complete_cycle(trade_timestamp)

        # Update previous amounts for next comparison
        self._previous_long_amount = current_long_amount
        self._previous_short_amount = current_short_amount

    def _start_new_cycle(self, candle_timestamp: int):
        """Start tracking a new cycle"""
        self._current_cycle_start = candle_timestamp
        self._current_cycle_long_max_loads = 0
        self._current_cycle_short_max_loads = 0
        self._current_cycle_long_trades = 0
        self._current_cycle_short_trades = 0
        self.logger.info(f"New cycle started at {candle_timestamp}")

    def _complete_cycle(self, candle_timestamp: int):
        """Complete the current cycle and dispatch event"""
        if self._current_cycle_start is None:
            return

        end_timestamp = candle_timestamp

        # Get all trades for this symbol to calculate P&L
        all_trades = self.exchange.get_trades(self.symbol)

        # Filter trades that occurred during this cycle
        cycle_trades = []
        for t in all_trades:
            try:
                # Handle both string and int timestamps
                trade_ts = int(t.timestamp) if isinstance(t.timestamp, str) else t.timestamp
                if self._current_cycle_start <= trade_ts <= end_timestamp:
                    cycle_trades.append(t)
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid trade timestamp: {t.timestamp}")
                continue

        # Calculate total P&L from realized P&L of trades
        total_pnl = sum(t.realized_pnl for t in cycle_trades)

        self.logger.info(f"Cycle P&L calculation: {len(cycle_trades)} trades, total_pnl={total_pnl}")

        # Create cycle entity
        cycle = Cycle(
            symbol=self.symbol,
            strategy_name=self.strategy_name,
            start_timestamp=self._current_cycle_start,
            end_timestamp=end_timestamp,
            total_pnl=total_pnl,
            long_trades_count=self._current_cycle_long_trades,
            short_trades_count=self._current_cycle_short_trades,
            long_max_loads=self._current_cycle_long_max_loads,
            short_max_loads=self._current_cycle_short_max_loads,
        )

        # Dispatch cycle completion event
        if self.cycle_dispatcher:
            self.cycle_dispatcher.dispatch_cycle_completion(cycle)
        else:
            self.logger.warning("Cycle dispatcher is None - cycle not dispatched")

        self.logger.info(f"Cycle completed: {cycle}")

        # Reset cycle state
        self._current_cycle_start = None
        self._current_cycle_long_max_loads = 0
        self._current_cycle_short_max_loads = 0
        self._current_cycle_long_trades = 0
        self._current_cycle_short_trades = 0
