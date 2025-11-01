"""Operations status repository for backtests"""

from trading.domain.ports import OperationsStatusRepositoryPort
from trading.domain.types import ORDER_SIDE_TYPE, SIDE_TYPE


class BacktestOperationsStatusRepository(OperationsStatusRepositoryPort):
    """
    Repositorio de estado de operaciones optimizado para backtest.
    Mantiene el estado solo en memoria, sin escritura a disco.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        # Estado inicial en memoria
        self.operations = {
            "long": {"buy": False, "sell": False},
            "short": {"buy": False, "sell": False},
        }

    def get_operation_status(self, side: SIDE_TYPE, type: ORDER_SIDE_TYPE) -> bool:
        """Obtener estado de operación desde memoria"""
        return self.operations[side][type]

    def set_operation_status(self, side: SIDE_TYPE, type: ORDER_SIDE_TYPE, status: bool):
        """Establecer estado de operación en memoria (sin escritura a disco)"""
        self.operations[side][type] = status
        # No hay escritura a disco - optimización para backtest

