"""Strategy factory for creating trading strategies"""
from collections.abc import Callable

from trading.domain.ports import CycleListenerPort, ExchangePort, MarketDataPort, OperationsStatusRepositoryPort
from trading.infrastructure.backtest.adapters.operations_status_repository import BacktestOperationsStatusRepository
from trading.strategies.carga_descarga.carga_descarga_strategy import CargaDescargaStrategy


def create_strategy_factory(
    strategy_name: str = "carga_descarga",
    operations_status_repository:[OperationsStatusRepositoryPort] = None,
) -> Callable:
    """Create a strategy factory function for BacktestRunner

    Args:
        strategy_name: Name of the strategy to use
        operations_status_repository: OperationsStatusRepository. If None, uses BacktestOperationsStatusRepository

    Returns:
        Factory function compatible with BacktestRunner.setup_exchange_and_strategy()
    """
    if strategy_name == "carga_descarga" or strategy_name == "default":

        def factory(
            symbol: str,
            exchange: ExchangePort,
            market_data: MarketDataPort,
            cycle_dispatcher: CycleListenerPort,
            strategy_name: str,
        ) -> CargaDescargaStrategy:
            # Use provided repository or create BacktestOperationsStatusRepository
            ops_repo = operations_status_repository or BacktestOperationsStatusRepository(symbol)

            return CargaDescargaStrategy(
                symbol=symbol,
                exchange=exchange,
                market_data=market_data,
                operation_status_repository=ops_repo,
                cycle_dispatcher=cycle_dispatcher,
                strategy_name=strategy_name,
            )

        return factory
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


def get_available_strategies() -> list[str]:
    """Get list of available strategy names"""
    return ["carga_descarga", "default"]

