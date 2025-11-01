"""Repository for storing and retrieving candles from SQLite"""
import sqlite3
from decimal import Decimal

from trading.domain.entities import Candle
from trading.infrastructure.logging import get_debug_logger


class CandlesRepository:
    """Repository for candles storage in SQLite database"""

    def __init__(self, is_backtest: bool = False, db_path: str = "candles.db"):
        self.is_backtest = is_backtest
        self.db_path = db_path
        self.table_suffix = "_kline"

        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
        self.cursor = self.conn.cursor()

        # Optimize database for backtest or production
        self._optimize_database()

    def _optimize_database(self):
        """Optimize database with indexes and configurations"""
        try:
            if self.is_backtest:
                # Aggressive configuration for backtest (maximum performance)
                self.cursor.execute("PRAGMA synchronous=OFF")
                self.cursor.execute("PRAGMA journal_mode=MEMORY")
                self.cursor.execute("PRAGMA temp_store=MEMORY")
                # Don't use EXCLUSIVE mode to allow multiple connections if needed
                # self.cursor.execute("PRAGMA locking_mode=EXCLUSIVE")
                self.cursor.execute("PRAGMA cache_size=50000")  # 50MB cache
            else:
                # Safe configuration for production
                self.cursor.execute("PRAGMA journal_mode=WAL")
                self.cursor.execute("PRAGMA synchronous=NORMAL")
                self.cursor.execute("PRAGMA cache_size=10000")  # 10MB cache

            # Get all existing tables
            self.cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name LIKE '%_kline'
            """
            )
            tables = self.cursor.fetchall()

            for table in tables:
                table_name = table[0]

                # Create indexes if they don't exist
                self.cursor.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_timeframe_timestamp
                    ON {table_name} (timeframe, timestamp)
                """
                )

                self.cursor.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp
                    ON {table_name} (timestamp)
                """
                )

            self.conn.commit()

        except Exception:
            # Continue without optimization if error
            pass

    def add_candles(self, candles:[Candle]):
        """Add candles to repository"""
        if not candles:
            return

        symbol = candles[0].symbol.lower()
        t_name = symbol + self.table_suffix

        # Check if table exists
        self.cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name=?
        """,
            (t_name,),
        )
        table_exist = self.cursor.fetchone()

        if not table_exist:
            # Create table with transaction
            self.cursor.execute("BEGIN IMMEDIATE")
            try:
                self.cursor.execute(
                    f"""
                CREATE TABLE IF NOT EXISTS {t_name} (
                    timeframe TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    PRIMARY KEY (timestamp, timeframe)
                )
                """
                )

                # Create indexes
                self.cursor.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{t_name}_timeframe_timestamp
                    ON {t_name} (timeframe, timestamp)
                """
                )

                self.cursor.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{t_name}_timestamp
                    ON {t_name} (timestamp)
                """
                )

                self.conn.commit()
            except Exception as e:
                self.conn.rollback()
                raise e

        # Prepare data for insertion
        candles_tuple = [
            (
                candle.timeframe,
                candle.timestamp,  # Already int in our Candle
                str(candle.open_price),
                str(candle.high_price),
                str(candle.low_price),
                str(candle.close_price),
                str(candle.volume) if candle.volume else "0",
            )
            for candle in candles
        ]

        # Use transaction for batch insertion
        self.cursor.execute("BEGIN DEFERRED")
        try:
            self.cursor.executemany(
                f"""
                INSERT OR REPLACE INTO {t_name} (timeframe, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                candles_tuple,
            )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

    def get_next_candle(self, symbol: str, timestamp: int, timeframe: str = "1m") ->[Candle]:
        """Get next candle after timestamp"""
        t_name = symbol.lower() + self.table_suffix

        self.cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name=?
        """,
            (t_name,),
        )
        table_exist = self.cursor.fetchone()

        if not table_exist:
            return None

        self.cursor.execute(
            f"""
            SELECT * FROM {t_name}
            WHERE timestamp > ?
            AND timeframe = ?
            ORDER BY timestamp ASC
            LIMIT 1
        """,
            (timestamp, timeframe),
        )
        row = self.cursor.fetchone()

        if not row:
            return None

        # row: (timeframe, timestamp, open, high, low, close, volume)
        return Candle(
            symbol=symbol,
            timeframe=row[0],
            timestamp=row[1],  # Already int
            open_price=Decimal(str(row[2])),
            high_price=Decimal(str(row[3])),
            low_price=Decimal(str(row[4])),
            close_price=Decimal(str(row[5])),
            volume=Decimal(str(row[6])) if row[6] else None,
        )

    def get_candles(self, symbol: str, timeframe: str, limit: int, start_time: int) ->[Candle]:
        """Get candles for symbol, timeframe, starting from start_time"""
        debug_logger = get_debug_logger("repository.debug")
        debug_logger.debug(
            f"get_candles({symbol}, {timeframe}, {limit}, start_time={start_time}): iniciando"
        )

        t_name = symbol.lower() + self.table_suffix
        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): nombre de tabla={t_name}")

        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): verificando existencia de tabla...")
        self.cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name=?
        """,
            (t_name,),
        )
        table_exist = self.cursor.fetchone()

        if not table_exist:
            debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): tabla {t_name} no existe, retornando []")
            return []

        debug_logger.debug(
            f"get_candles({symbol}, {timeframe}, {limit}): "
            f"ejecutando query SQL (timeframe={timeframe}, start_time={start_time}, limit={limit})"
        )
        self.cursor.execute(
            f"""
            SELECT * FROM {t_name}
            WHERE timeframe = ?
            AND timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
        """,
            (timeframe, start_time, limit),
        )
        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): query ejecutada, obteniendo resultados...")
        rows = self.cursor.fetchall()
        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): obtenidas {len(rows)} filas de SQLite")

        debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): convirtiendo rows a Candle objects...")
        candles = []
        for i, row in enumerate(rows):
            if i % 100 == 0 and len(rows) > 100:
                debug_logger.debug(f"get_candles({symbol}, {timeframe}, {limit}): procesando row {i+1}/{len(rows)}")
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=row[0],
                    timestamp=row[1],  # Already int
                    open_price=Decimal(str(row[2])),
                    high_price=Decimal(str(row[3])),
                    low_price=Decimal(str(row[4])),
                    close_price=Decimal(str(row[5])),
                    volume=Decimal(str(row[6])) if row[6] else None,
                )
            )

        debug_logger.debug(
            f"get_candles({symbol}, {timeframe}, {limit}): conversión completada, retornando {len(candles)} candles"
        )
        return candles

    def close(self):
        """Close database connection"""
        if hasattr(self, "conn") and self.conn:
            self.conn.close()

