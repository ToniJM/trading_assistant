"""Market data adapter for getting candles from Binance API"""
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binance.um_futures import UMFutures
else:
    # import - will fail at runtime if not installed
    try:
        from binance.um_futures import UMFutures
    except ImportError:
        UMFutures = None  # type: ignore

import sys

from trading.domain.entities import Candle, SymbolInfo
from trading.infrastructure.logging import get_debug_logger


class MarketDataAdapter:
    """Adapter to get market data from Binance API"""

    def __init__(self):
        # TODO: Create binance client factory or use direct client
        # For now, will need to be initialized externally
        self.client:[UMFutures] = None
        self._symbol_info_cache: dict[str, SymbolInfo] = {}  # Cache indexado por símbolo con solo los datos necesarios

    def _extract_symbol_data(self, symbol_info: dict) -> tuple[str, SymbolInfo]:
        """Extract only the necessary data from a symbol_info dict

        Returns:
            tuple: (symbol, SymbolInfo) with only the 5 fields we need
        """
        symbol = symbol_info["symbol"]

        # Find the filters we need
        tick_size = None
        min_qty = None
        min_step = None
        notional = None

        for filter_item in symbol_info.get("filters", []):
            filter_type = filter_item.get("filterType")
            if filter_type == "PRICE_FILTER":
                tick_size = Decimal(filter_item["tickSize"])
            elif filter_type == "LOT_SIZE":
                min_qty = Decimal(filter_item["minQty"])
                min_step = Decimal(filter_item["stepSize"])
            elif filter_type == "MIN_NOTIONAL":
                notional = Decimal(filter_item["notional"])

        # Validate we found all required fields
        if tick_size is None or min_qty is None or min_step is None or notional is None:
            raise ValueError(f"Missing required filters for symbol {symbol}")

        symbol_info_obj = SymbolInfo(
            symbol=symbol,
            min_qty=min_qty,
            min_step=min_step,
            tick_size=tick_size,
            notional=notional,
        )

        return symbol, symbol_info_obj

    def _build_symbol_cache(self, exchange_info: dict):
        """Process exchange_info and build _symbol_info_cache with only necessary data"""
        debug_logger = get_debug_logger("market_data.debug")
        debug_logger.debug("_build_symbol_cache(): iniciando procesamiento de exchange_info")

        cache_before = len(self._symbol_info_cache)

        processed = 0
        errors = 0
        for symbol_info in exchange_info.get('symbols', []):
            try:
                symbol, symbol_data = self._extract_symbol_data(symbol_info)
                self._symbol_info_cache[symbol] = symbol_data
                processed += 1
            except (KeyError, ValueError) as e:
                errors += 1
                debug_logger.debug(
                    f"_build_symbol_cache(): error procesando símbolo {symbol_info.get('symbol', 'UNKNOWN')}: {e}"
                )

        cache_after = len(self._symbol_info_cache)
        cache_size_bytes = sys.getsizeof(self._symbol_info_cache)

        debug_logger.debug(
            f"_build_symbol_cache(): procesados {processed} símbolos exitosamente, "
            f"{errors} errores. Cache: {cache_before} -> {cache_after} símbolos "
            f"({cache_size_bytes} bytes, {cache_size_bytes/1024:.2f} KB)"
        )

    def _ensure_client(self):
        """Ensure Binance client is initialized and symbol cache is built"""
        debug_logger = get_debug_logger("market_data.debug")
        debug_logger.debug(
            f"_ensure_client(): client is None={self.client is None}, "
            f"symbol_cache size={len(self._symbol_info_cache)}"
        )

        # If cache is already built, we're done
        if len(self._symbol_info_cache) > 0:
            debug_logger.debug("_ensure_client(): cache ya está construido, saltando inicialización")
            return

        if self.client is None:
            if UMFutures is None:
                raise ImportError(
                    "binance-futures-connector not installed. "
                    "Install with: pip install binance-futures-connector"
                )
            # Try to import and use binance_client_factory if available
            try:
                from binance_client_factory import binance_client_factory

                debug_logger.debug("_ensure_client(): usando binance_client_factory")
                self.client = binance_client_factory()
                debug_logger.debug("_ensure_client(): llamando client.exchange_info()...")
                exchange_info = self.client.exchange_info()
                symbols_count = len(exchange_info.get('symbols', [])) if exchange_info else 0
                size_bytes = sys.getsizeof(str(exchange_info)) if exchange_info else 0
                debug_logger.debug(
                    f"_ensure_client(): exchange_info obtenido - "
                    f"cantidad de símbolos={symbols_count}, "
                    f"tamaño aproximado={size_bytes} bytes ({size_bytes/1024/1024:.2f} MB)"
                )

                # Build cache and release exchange_info
                self._build_symbol_cache(exchange_info)
                exchange_info = None  # Release reference immediately

            except ImportError:
                # For backtests, we can create a client without credentials
                # Public endpoints (like klines) don't require authentication
                try:
                    debug_logger.debug("_ensure_client(): creando UMFutures() sin credenciales")
                    self.client = UMFutures()  # Create client without credentials for public data
                    debug_logger.debug("_ensure_client(): llamando client.exchange_info()...")
                    exchange_info = self.client.exchange_info()
                    symbols_count = len(exchange_info.get('symbols', [])) if exchange_info else 0
                    size_bytes = sys.getsizeof(str(exchange_info)) if exchange_info else 0
                    debug_logger.debug(
                        f"_ensure_client(): exchange_info obtenido - "
                        f"cantidad de símbolos={symbols_count}, "
                        f"tamaño aproximado={size_bytes} bytes ({size_bytes/1024/1024:.2f} MB)"
                    )

                    # Build cache and release exchange_info
                    self._build_symbol_cache(exchange_info)
                    exchange_info = None  # Release reference immediately

                except Exception as e:
                    raise ValueError(
                        f"Failed to create Binance client: {e}. "
                        "Either provide binance_client_factory or set client manually."
                    )

    def set_client(self, client: "UMFutures"):
        """Set Binance client manually"""
        debug_logger = get_debug_logger("market_data.debug")
        debug_logger.debug("set_client(): estableciendo cliente manualmente")
        self.client = client
        debug_logger.debug("set_client(): llamando client.exchange_info()...")
        exchange_info = client.exchange_info()
        symbols_count = len(exchange_info.get('symbols', [])) if exchange_info else 0
        size_bytes = sys.getsizeof(str(exchange_info)) if exchange_info else 0
        debug_logger.debug(
            f"set_client(): exchange_info obtenido - "
            f"cantidad de símbolos={symbols_count}, "
            f"tamaño aproximado={size_bytes} bytes ({size_bytes/1024/1024:.2f} MB)"
        )

        # Build cache and release exchange_info
        self._build_symbol_cache(exchange_info)
        exchange_info = None  # Release reference immediately

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get symbol information from Binance cache"""
        debug_logger = get_debug_logger("market_data.debug")
        debug_logger.debug(f"get_symbol_info({symbol}): iniciando")

        self._ensure_client()
        symbol = symbol.upper()

        cache_size = len(self._symbol_info_cache)
        debug_logger.debug(
            f"get_symbol_info({symbol}): buscando en cache con {cache_size} símbolos, "
            f"id(self)={id(self)}"
        )

        if symbol in self._symbol_info_cache:
            result = self._symbol_info_cache[symbol]
            debug_logger.debug(f"get_symbol_info({symbol}): símbolo encontrado en cache, notional={result.notional}")
            return result

        debug_logger.error(
            f"get_symbol_info({symbol}): símbolo NO encontrado en cache ({cache_size} símbolos disponibles)"
        )
        raise ValueError(f"Symbol {symbol} not found")

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        start_time:[int] = None,
        end_time:[int] = None,
    ) ->[Candle]:
        """Get candles from Binance API"""
        debug_logger = get_debug_logger("market_data.debug")
        debug_logger.debug(
            f"get_candles({symbol}, {timeframe}, {limit}, start_time={start_time}, end_time={end_time}): iniciando"
        )

        self._ensure_client()

        if limit > 1000:
            raise ValueError("limit must be less than 1000")

        debug_logger.debug(
            f"get_candles({symbol}, {timeframe}, {limit}): llamando client.klines() "
            f"(startTime={start_time}, endTime={end_time})"
        )

        if start_time is None:
            klines = self.client.klines(symbol=symbol, interval=timeframe, limit=limit)
        else:
            klines = self.client.klines(
                symbol=symbol, interval=timeframe, limit=limit, startTime=start_time, endTime=end_time
            )

        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): client.klines() retornó {len(klines)} klines")

        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): convirtiendo klines a Candle objects...")
        candles:[Candle] = []
        for i, kline in enumerate(klines):
            if i % 100 == 0:
                debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): procesando kline {i+1}/{len(klines)}")
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=kline[0],  # Binance returns int timestamp (milliseconds)
                    open_price=Decimal(kline[1]),
                    high_price=Decimal(kline[2]),
                    low_price=Decimal(kline[3]),
                    close_price=Decimal(kline[4]),
                    volume=Decimal(kline[5]),
                )
            )
        debug_logger.debug(
            f"get_candles({symbol}, {timeframe}, {limit}): conversión completada, retornando {len(candles)} candles"
        )
        return candles

    def close(self):
        """Close adapter and cleanup resources"""
        self.client = None
        self._symbol_info_cache.clear()

