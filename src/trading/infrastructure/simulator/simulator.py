"""Market data simulator for backtests"""
import time
from datetime import datetime

from trading.domain.entities import Candle
from trading.infrastructure.logging import get_debug_logger, get_logger
from trading.infrastructure.simulator.adapters.candles_repository import CandlesRepository
from trading.infrastructure.simulator.adapters.event_dispatcher import EventDispatcher
from trading.infrastructure.simulator.adapters.market_data_adapter import MarketDataAdapter
from trading.infrastructure.simulator.domain.constants import ONE_MINUTE, TIMEFRAME_MINUTES
from trading.infrastructure.simulator.domain.types import TIMEFRAME_TYPE


class MarketDataSimulator:
    """Simulator for market data in backtests"""

    def __init__(self, is_backtest: bool = False):
        self.event_dispatcher = EventDispatcher()
        self.candles_repo = CandlesRepository(is_backtest=is_backtest)
        self.market_data = MarketDataAdapter()

        self.symbols_timeframes:[str[TIMEFRAME_TYPE]] = {}
        self.start_time: int = 0
        self.end_time: int = 0
        self.min_candles: int = 0
        self.current_time: int = 0

        self.cumulative_candles:[str[TIMEFRAME_TYPE, Candle]] = {}
        self.endeds:[str, bool] = {}
        self.last_candle:[str[TIMEFRAME_TYPE, Candle]] = {}

    def ended(self, symbol: str) -> bool:
        """Check if simulation has ended for symbol"""
        if symbol not in self.endeds:
            self.endeds[symbol] = False
        result = self.endeds[symbol]
        # DEBUG: solo cuando retorna True (detalle interno)
        if result:
            debug_logger = get_debug_logger("simulator.debug")
            debug_logger.debug(
                f"ended({symbol}) retornando True - "
                f"current_time={self.current_time}, end_time={self.end_time}"
            )
        return result

    def end(self, symbol: str):
        """Mark symbol simulation as ended"""
        self.endeds[symbol] = True

    def set_times(self, start: int, end:[int] = None, min_candles: int = 10):
        """Set simulation time range"""
        self.start_time = start
        self.current_time = start
        self.end_time = end if end else int(time.time() * 1000)
        self.min_candles = min_candles

        # INFO: configuración importante del simulador (sin prefijo [DEBUG])
        logger = get_logger("simulator")
        logger.info(
            f"Configurando tiempos del simulador: "
            f"start={start} ({datetime.fromtimestamp(start/1000)}), "
            f"end={self.end_time} ({datetime.fromtimestamp(self.end_time/1000)}), "
            f"duration={self.end_time - start}ms"
        )

    def next_candle(self):
        """Process next candle for all configured symbols"""
        debug_logger = get_debug_logger("simulator.debug")

        for symbol, timeframes in self.symbols_timeframes.items():
            # DEBUG: detalles internos de next_candle()
            debug_logger.debug(
                f"next_candle() para {symbol}: "
                f"current_time={self.current_time} ({datetime.fromtimestamp(self.current_time/1000)}), "
                f"start_time={self.start_time} ({datetime.fromtimestamp(self.start_time/1000)}), "
                f"end_time={self.end_time} ({datetime.fromtimestamp(self.end_time/1000)}), "
                f"ended={self.ended(symbol)}"
            )

            if self.current_time < self.start_time:
                debug_logger.debug("current_time < start_time, ajustando...")
                while self.current_time < self.start_time:
                    candle = self._next_candle(symbol, timeframes, False)
                    self.current_time = candle.timestamp
                self.start_time = candle.timestamp
                self.event_dispatcher.dispatch_complete_candle(candle)
            else:
                candle = self._next_candle(symbol, timeframes)
                self.current_time = candle.timestamp

            # DEBUG: estado después de _next_candle()
            debug_logger.debug(
                f"Después de _next_candle: current_time={self.current_time}, "
                f"candle.timestamp={candle.timestamp if candle else None}"
            )

            # WARNING: situación anómala pero manejable
            if self.current_time >= self.end_time:
                logger = get_logger("simulator")
                logger.warning(
                    f"current_time >= end_time, terminando simulación para {symbol}. "
                    f"current_time={self.current_time}, end_time={self.end_time}"
                )
                self.end(symbol)

    def _next_candle(self, symbol: str, timeframes:[TIMEFRAME_TYPE], dispatch: bool = True) -> Candle:
        """Get next candle for symbol"""
        debug_logger = get_debug_logger("simulator.debug")
        logger = get_logger("simulator")

        if self.ended(symbol):
            raise ValueError("Symbol ended")

        # DEBUG: valores internos de _next_candle()
        debug_logger.debug(
            f"_next_candle({symbol}): "
            f"current_time={self.current_time} ({datetime.fromtimestamp(self.current_time/1000)}), "
            f"ended={self.ended(symbol)}"
        )

        candle = self.candles_repo.get_next_candle(symbol, self.current_time)
        # DEBUG: resultado de get_next_candle()
        debug_logger.debug(
            f"get_next_candle retornó: {candle is not None}, "
            f"timestamp={candle.timestamp if candle else None}"
        )

        if candle is None:
            # INFO: operación importante - obtener velas de market_data
            logger.info(f"No hay velas en repo para {symbol}, obteniendo de market_data...")
            candles = self.market_data.get_candles(symbol, "1m", 1000, self.current_time)
            logger.info(f"market_data.get_candles retornó {len(candles)} velas")
            logger.info(f"Agregando {len(candles)} velas al repositorio...")
            self.candles_repo.add_candles(candles)
            logger.info("Velas agregadas al repositorio exitosamente")
            candle = candles[0] if candles else None
            if candle is None:
                # ERROR: error crítico - no hay velas disponibles
                logger.error(
                    f"No se encontraron velas para {symbol} en {self.current_time} "
                    f"({datetime.fromtimestamp(self.current_time/1000)})"
                )
                raise ValueError(f"No candles available for {symbol} at {self.current_time}")
        elif candle.timestamp > self.current_time + ONE_MINUTE:
            # INFO: operación importante - obtener más velas
            logger.info("Siguiente vela está muy adelante, obteniendo más velas de market_data...")
            candles = self.market_data.get_candles(symbol, "1m", 1000, self.current_time)
            logger.info(f"Agregando {len(candles)} velas al repositorio...")
            self.candles_repo.add_candles(candles)
            logger.info("Velas agregadas al repositorio exitosamente")
            candle = candles[0] if candles else candle

        # DEBUG: antes de dispatch
        debug_logger.debug(
            f"Antes de dispatch: candle={candle.timestamp if candle else None}, dispatch={dispatch}"
        )

        if dispatch:
            debug_logger.debug(f"Dispatching candle para {symbol}, timestamp={candle.timestamp}")
            self.event_dispatcher.dispatch_complete_candle(candle)
            debug_logger.debug(f"Candle dispatched exitosamente para {symbol}")

        # DEBUG: después de dispatch, antes de procesar otros timeframes
        debug_logger.debug(f"Procesando otros timeframes: {[tf for tf in timeframes if tf != '1m']}")

        # Process other timeframes
        for timeframe in timeframes:
            if timeframe != "1m":
                debug_logger.debug(f"Procesando timeframe {timeframe} para {symbol}")
                timeframe_candles = self.get_candles(symbol, timeframe, 1)
                candles_count = len(timeframe_candles) if timeframe_candles else 0
                debug_logger.debug(f"get_candles({symbol}, {timeframe}, 1) retornó {candles_count} velas")
                if timeframe_candles:
                    timeframe_candle = timeframe_candles[0]
                    if self.last_candle.get(symbol) is None:
                        self.last_candle[symbol] = {}
                    if self.last_candle[symbol].get(timeframe) is None:
                        self.last_candle[symbol][timeframe] = None
                    if (
                        self.last_candle[symbol][timeframe] is None
                        or timeframe_candle.timestamp > self.last_candle[symbol][timeframe].timestamp
                    ):
                            self.last_candle[symbol][timeframe] = timeframe_candle
                            debug_logger.debug(f"Dispatching candle {timeframe} para {symbol}")
                            self.event_dispatcher.dispatch_complete_candle(timeframe_candle)
                            debug_logger.debug(f"Candle {timeframe} dispatched exitosamente")

        # DEBUG: retorno de _next_candle()
        debug_logger.debug(f"_next_candle retornando: timestamp={candle.timestamp if candle else None}")
        return candle

    def get_symbol_info(self, symbol: str):
        """Get symbol information"""
        return self.market_data.get_symbol_info(symbol)

    def get_candles(self, symbol: str, timeframe: TIMEFRAME_TYPE, limit: int) ->[Candle]:
        """Get historical candles for symbol and timeframe"""
        debug_logger = get_debug_logger("simulator.debug")
        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): iniciando")

        end_time = self.current_time - (TIMEFRAME_MINUTES[timeframe] * ONE_MINUTE)
        if self.current_time < self.start_time:
            end_time = self.start_time - (TIMEFRAME_MINUTES[timeframe] * ONE_MINUTE)
        start_time = end_time - (TIMEFRAME_MINUTES[timeframe] * ONE_MINUTE * limit)

        debug_logger.debug(
            f"get_candles({symbol}, {timeframe}, {limit}): "
            f"start_time={start_time}, end_time={end_time}, current_time={self.current_time}"
        )

        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): buscando en repositorio...")
        candles = self.candles_repo.get_candles(symbol, timeframe, limit, start_time)
        debug_logger.debug(
            f"get_candles({symbol}, {timeframe}, {limit}): "
            f"repositorio retornó {len(candles)} velas (necesitamos {limit})"
        )

        if len(candles) < limit:
            debug_logger.debug(
                f"get_candles({symbol}, {timeframe}, {limit}): "
                f"no hay suficientes velas en repo, llamando market_data.get_candles(1000)..."
            )
            candles_from_api = self.market_data.get_candles(symbol, timeframe, 1000, start_time)
            debug_logger.debug(
                f"get_candles({symbol}, {timeframe}, {limit}): "
                f"market_data.get_candles() retornó {len(candles_from_api)} velas"
            )
            debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): agregando velas al repositorio...")
            self.candles_repo.add_candles(candles_from_api)
            debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): velas agregadas al repositorio")
            candles = candles_from_api[:limit]
            debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): tomando primeras {limit} velas")

        if candles and candles[-1].timestamp > end_time + ONE_MINUTE:
            debug_logger.debug(
                f"get_candles({symbol}, {timeframe}, {limit}): "
                f"última vela fuera de rango, reobteniendo desde API..."
            )
            candles_from_api = self.market_data.get_candles(symbol, timeframe, 1000, start_time)
            debug_logger.debug(
                f"get_candles({symbol}, {timeframe}, {limit}): "
                f"market_data.get_candles() (segunda llamada) retornó {len(candles_from_api)} velas"
            )
            self.candles_repo.add_candles(candles_from_api)
            candles = candles_from_api[:limit]

        result = candles[:limit] if candles else []
        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): retornando {len(result)} velas")
        return result

    def add_complete_candle_listener(self, symbol: str, timeframe: TIMEFRAME_TYPE, listener: callable):
        """Add listener for complete candle events"""
        if self.start_time == 0:
            raise ValueError("No configuration found")
        if symbol not in self.symbols_timeframes:
            self.symbols_timeframes[symbol] = []
        if timeframe not in self.symbols_timeframes[symbol]:
            self.symbols_timeframes[symbol].append(timeframe)
            timeframe_time = TIMEFRAME_MINUTES[timeframe] * ONE_MINUTE
            new_current_time = self.start_time - (timeframe_time * self.min_candles)
            if new_current_time < self.current_time:
                self.current_time = new_current_time

        self.event_dispatcher.add_complete_candle_listener(symbol, timeframe, listener)

    def remove_complete_candle_listener(self, symbol: str, timeframe: TIMEFRAME_TYPE, listener: callable):
        """Remove listener for complete candle events"""
        return self.event_dispatcher.remove_complete_candle_listener(symbol, timeframe, listener)

    def close(self):
        """Close adapters and cleanup resources"""
        import io
        import sys

        if hasattr(self, "market_data") and self.market_data:
            # Suppress stdout during WebSocket close
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                self.market_data.close()
            finally:
                sys.stdout = old_stdout
            self.market_data = None

        if hasattr(self, "candles_repo") and self.candles_repo:
            self.candles_repo.close()

