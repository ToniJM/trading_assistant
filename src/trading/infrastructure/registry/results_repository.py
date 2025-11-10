"""Results repository for persistent storage of backtest, evaluation, and optimization results"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from trading.infrastructure.logging import get_logger

logger = get_logger("registry.repository")


class ResultsRepository:
    """Repository for storing and retrieving results using JSON files"""

    def __init__(self, base_path: Path | str | None = None):
        """Initialize repository with base path

        Args:
            base_path: Base directory for storage (default: data/registry)
        """
        if base_path is None:
            base_path = Path("data/registry")
        elif isinstance(base_path, str):
            base_path = Path(base_path)

        self.base_path = base_path
        self.backtests_path = self.base_path / "backtests"
        self.evaluations_path = self.base_path / "evaluations"
        self.optimizations_path = self.base_path / "optimizations"
        self.index_path = self.base_path / "index.json"

        # Create directories
        self.backtests_path.mkdir(parents=True, exist_ok=True)
        self.evaluations_path.mkdir(parents=True, exist_ok=True)
        self.optimizations_path.mkdir(parents=True, exist_ok=True)

        # Initialize index if it doesn't exist
        if not self.index_path.exists():
            self._init_index()

    def _init_index(self):
        """Initialize index file"""
        index = {
            "runs": {},
            "strategies": {},
            "symbols": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._write_index(index)

    def _read_index(self) -> dict[str, Any]:
        """Read index file"""
        if not self.index_path.exists():
            self._init_index()
        with self.index_path.open("r") as f:
            return json.load(f)

    def _write_index(self, index: dict[str, Any]):
        """Write index file"""
        index["updated_at"] = datetime.now().isoformat()
        with self.index_path.open("w") as f:
            json.dump(index, f, indent=2, default=str)

    def _update_index(
        self,
        run_id: str,
        strategy_name: str,
        symbol: str,
        stored_at: datetime,
        result_type: str,
    ):
        """Update index with new entry"""
        index = self._read_index()

        # Add to runs index
        if run_id not in index["runs"]:
            index["runs"][run_id] = {
                "strategy_name": strategy_name,
                "symbol": symbol,
                "stored_at": stored_at.isoformat(),
                "result_types": [],
            }

        if result_type not in index["runs"][run_id]["result_types"]:
            index["runs"][run_id]["result_types"].append(result_type)

        # Add to strategies index
        if strategy_name not in index["strategies"]:
            index["strategies"][strategy_name] = []
        if run_id not in index["strategies"][strategy_name]:
            index["strategies"][strategy_name].append(run_id)

        # Add to symbols index
        if symbol not in index["symbols"]:
            index["symbols"][symbol] = []
        if run_id not in index["symbols"][symbol]:
            index["symbols"][symbol].append(run_id)

        self._write_index(index)

    def store_backtest(self, run_id: str, data: dict[str, Any]) -> str:
        """Store backtest results

        Args:
            run_id: Run identifier
            data: Backtest data to store

        Returns:
            Storage ID
        """
        storage_id = f"backtest-{run_id}"
        file_path = self.backtests_path / f"{run_id}.json"

        # Add metadata
        data["_metadata"] = {
            "storage_id": storage_id,
            "stored_at": datetime.now().isoformat(),
            "result_type": "backtest",
        }

        with file_path.open("w") as f:
            json.dump(data, f, indent=2, default=str)

        # Update index
        strategy_name = data.get("strategy_name", "unknown")
        symbol = data.get("symbol", "unknown")
        self._update_index(run_id, strategy_name, symbol, datetime.now(), "backtest")

        logger.debug(f"Stored backtest results: {storage_id}")
        return storage_id

    def store_evaluation(self, run_id: str, data: dict[str, Any]) -> str:
        """Store evaluation results

        Args:
            run_id: Run identifier
            data: Evaluation data to store

        Returns:
            Storage ID
        """
        storage_id = f"evaluation-{run_id}"
        file_path = self.evaluations_path / f"{run_id}.json"

        # Add metadata
        data["_metadata"] = {
            "storage_id": storage_id,
            "stored_at": datetime.now().isoformat(),
            "result_type": "evaluation",
        }

        with file_path.open("w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.debug(f"Stored evaluation results: {storage_id}")
        return storage_id

    def store_optimization(self, run_id: str, data: dict[str, Any]) -> str:
        """Store optimization results

        Args:
            run_id: Run identifier
            data: Optimization data to store

        Returns:
            Storage ID
        """
        storage_id = f"optimization-{run_id}"
        file_path = self.optimizations_path / f"{run_id}.json"

        # Add metadata
        data["_metadata"] = {
            "storage_id": storage_id,
            "stored_at": datetime.now().isoformat(),
            "result_type": "optimization",
        }

        with file_path.open("w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.debug(f"Stored optimization results: {storage_id}")
        return storage_id

    def retrieve_by_run_id(self, run_id: str) -> dict[str, Any] | None:
        """Retrieve all results for a specific run_id

        Args:
            run_id: Run identifier

        Returns:
            Dictionary with backtest, evaluation, and optimization results, or None if not found
        """
        index = self._read_index()
        if run_id not in index["runs"]:
            return None

        results: dict[str, Any] = {}

        # Try to load backtest
        backtest_path = self.backtests_path / f"{run_id}.json"
        if backtest_path.exists():
            with backtest_path.open("r") as f:
                results["backtest"] = json.load(f)

        # Try to load evaluation
        evaluation_path = self.evaluations_path / f"{run_id}.json"
        if evaluation_path.exists():
            with evaluation_path.open("r") as f:
                results["evaluation"] = json.load(f)

        # Try to load optimization
        optimization_path = self.optimizations_path / f"{run_id}.json"
        if optimization_path.exists():
            with optimization_path.open("r") as f:
                results["optimization"] = json.load(f)

        if not results:
            return None

        # Add index metadata
        results["_index"] = index["runs"][run_id]
        return results

    def retrieve_by_strategy(
        self, strategy_name: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Retrieve results by strategy name

        Args:
            strategy_name: Strategy name to filter by
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of results
        """
        index = self._read_index()
        if strategy_name not in index["strategies"]:
            return []

        run_ids = index["strategies"][strategy_name][offset : offset + limit]
        results = []

        for run_id in run_ids:
            result = self.retrieve_by_run_id(run_id)
            if result:
                results.append(result)

        return results

    def retrieve_by_symbol(
        self, symbol: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Retrieve results by symbol

        Args:
            symbol: Trading symbol to filter by
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of results
        """
        index = self._read_index()
        if symbol not in index["symbols"]:
            return []

        run_ids = index["symbols"][symbol][offset : offset + limit]
        results = []

        for run_id in run_ids:
            result = self.retrieve_by_run_id(run_id)
            if result:
                results.append(result)

        return results

    def get_total_count(
        self, strategy_name: str | None = None, symbol: str | None = None
    ) -> int:
        """Get total count of results matching filters

        Args:
            strategy_name: Optional strategy name filter
            symbol: Optional symbol filter

        Returns:
            Total count
        """
        index = self._read_index()

        if strategy_name:
            if strategy_name not in index["strategies"]:
                return 0
            return len(index["strategies"][strategy_name])

        if symbol:
            if symbol not in index["symbols"]:
                return 0
            return len(index["symbols"][symbol])

        return len(index["runs"])

