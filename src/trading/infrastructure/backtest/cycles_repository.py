"""Repository for storing and retrieving trading cycles"""
import sqlite3

from trading.domain.entities import Cycle
from trading.infrastructure.logging import get_logger


class CyclesRepository:
    """Repository for storing and retrieving trading cycles from SQLite database"""

    def __init__(self, db_path: str = "backtest_results.db"):
        self.db_path = db_path
        self.logger = get_logger(self.__class__.__name__)
        self._init_database()

    def _init_database(self):
        """Initialize database and create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create cycles table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cycles (
                    cycle_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    start_timestamp INTEGER NOT NULL,
                    end_timestamp INTEGER NOT NULL,
                    duration_minutes REAL NOT NULL,
                    total_pnl TEXT NOT NULL,
                    long_trades_count INTEGER NOT NULL,
                    short_trades_count INTEGER NOT NULL,
                    long_max_loads INTEGER NOT NULL,
                    short_max_loads INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """
            )

            # Create indexes for better query performance
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cycles_symbol_strategy
                ON cycles(symbol, strategy_name)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cycles_timestamp
                ON cycles(start_timestamp, end_timestamp)
            """
            )

            conn.commit()
            self.logger.debug("Database initialized successfully")

    def save_cycle(self, cycle: Cycle) -> bool:
        """Save a cycle to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cycle_data = cycle.to_dict()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO cycles
                    (cycle_id, symbol, strategy_name, start_timestamp, end_timestamp,
                     duration_minutes, total_pnl, long_trades_count, short_trades_count,
                     long_max_loads, short_max_loads, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cycle_data["cycle_id"],
                        cycle_data["symbol"],
                        cycle_data["strategy_name"],
                        cycle_data["start_timestamp"],
                        cycle_data["end_timestamp"],
                        cycle_data["duration_minutes"],
                        cycle_data["total_pnl"],
                        cycle_data["long_trades_count"],
                        cycle_data["short_trades_count"],
                        cycle_data["long_max_loads"],
                        cycle_data["short_max_loads"],
                        cycle_data["created_at"],
                    ),
                )

                conn.commit()
                self.logger.debug(f"Cycle {cycle.cycle_id[:8]}... saved successfully")
                return True

        except Exception as e:
            self.logger.error(f"Error saving cycle: {e}")
            return False

    def get_cycles(self, symbol: str, strategy_name:[str] = None) ->[Cycle]:
        """Get cycles for a symbol, optionally filtered by strategy name"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if strategy_name:
                    cursor.execute(
                        """
                        SELECT * FROM cycles
                        WHERE symbol = ? AND strategy_name = ?
                        ORDER BY start_timestamp ASC
                    """,
                        (symbol, strategy_name),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM cycles
                        WHERE symbol = ?
                        ORDER BY start_timestamp ASC
                    """,
                        (symbol,),
                    )

                rows = cursor.fetchall()
                cycles = []

                for row in rows:
                    cycle_data = {
                        "cycle_id": row[0],
                        "symbol": row[1],
                        "strategy_name": row[2],
                        "start_timestamp": row[3],
                        "end_timestamp": row[4],
                        "duration_minutes": row[5],
                        "total_pnl": row[6],
                        "long_trades_count": row[7],
                        "short_trades_count": row[8],
                        "long_max_loads": row[9],
                        "short_max_loads": row[10],
                        "created_at": row[11],
                    }
                    cycles.append(Cycle.from_dict(cycle_data))

                self.logger.debug(f"Retrieved {len(cycles)} cycles for {symbol}")
                return cycles

        except Exception as e:
            self.logger.error(f"Error retrieving cycles: {e}")
            return []

