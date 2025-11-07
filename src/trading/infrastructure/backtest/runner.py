import logging
import time
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from trading.domain.entities import Cycle, Trade
from trading.domain.ports import ExchangePort, MarketDataPort, StrategyPort
from trading.infrastructure.backtest.adapters.exchange_adapter import BacktestExchangeAdapter
from trading.infrastructure.backtest.adapters.market_data_adapter import BacktestMarketDataAdapter
from trading.infrastructure.backtest.config import (
    LOG_LEVEL,
    BacktestConfig,
    BacktestResults,
    disable_logging_for_backtest,
    enable_logging_after_backtest,
)
from trading.infrastructure.backtest.cycles_repository import CyclesRepository
from trading.infrastructure.backtest.event_dispatcher import EventDispatcher
from trading.infrastructure.logging import (
    get_backtest_logger,
    get_debug_logger,
    get_logger,
    logging_context,
)
from trading.infrastructure.simulator.simulator import MarketDataSimulator, get_base_timeframe


class BacktestRunner:
    """Runner principal para ejecutar backtests de forma independiente"""

    def __init__(self, config: BacktestConfig, simulator=None):
        self.logger = get_logger(self.__class__.__name__)
        self.config = config
        self.run_id = config.run_id

        # Generar nombre de log si no se especificó
        if config.log_filename is None:
            start_date = datetime.fromtimestamp(config.start_time / 1000).strftime("%Y%m%d")
            end_date = (
                datetime.fromtimestamp(config.end_time / 1000).strftime("%Y%m%d") if config.end_time else "current"
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            config.log_filename = (
                f"{config.strategy_name}/backtest_{config.symbol}_{start_date}_to_{end_date}_{timestamp}"
            )

        # Crear logger específico para este backtest
        self.backtest_logger, self.backtest_handler = get_backtest_logger(config.log_filename)

        # Deshabilitar logging verboso para mejorar rendimiento
        disable_logging_for_backtest()

        # Inicializar simulador en modo backtest
        if simulator is None:
            self.simulator = MarketDataSimulator(is_backtest=True)
        else:
            self.simulator = simulator

        self.simulator.set_times(start=config.start_time, end=config.end_time, min_candles=10)
        self.simulator.symbols_timeframes[config.symbol] = config.timeframes

        # Inicializar exchange y market data
        self.exchange: [ExchangePort] = None
        self.market_data: [MarketDataPort] = None
        self.strategy: [StrategyPort] = None
        self.front = None

        # Métricas de rendimiento
        self.start_execution_time = None
        self.candles_processed = 0
        self.last_progress_update = 0
        self.progress_update_interval = 1000

        # Tracking de max drawdown basado en unrealized PnL
        self.max_unrealized_pnl_loss = Decimal(0)
        self.last_base_candle = None  # Último candle del timeframe base procesado

        # Cycle tracking
        self.cycles_repository = CyclesRepository() if config.track_cycles else None
        self.cycle_dispatcher = EventDispatcher() if config.track_cycles else None
        self.cycles: [Cycle] = []

    def _configure_component_loggers(self):
        """Configurar loggers de componentes para que escriban al backtest"""
        component_loggers = [
            "CargaDescargaStrategy",
            "UserData",
            "OperationsStatusRepository",
            "BacktestExchangeAdapter",
            "BacktestMarketDataAdapter",
        ]

        for component_name in component_loggers:
            component_logger = logging.getLogger(component_name)
            component_logger.handlers.clear()
            component_logger.addHandler(self.backtest_handler)
            component_logger.setLevel(getattr(logging, LOG_LEVEL))
            component_logger.propagate = False

    def setup_exchange_and_strategy(
        self,
        exchange_factory: [Callable] = None,
        market_data_factory: [Callable] = None,
        strategy_factory: Callable = None,
        frontend_factory: [Callable] = None,
    ):
        """Configurar exchange, market data y estrategia

        Args:
            exchange_factory: factory function for exchange adapter.
                            If None, uses BacktestExchangeAdapter by default.
            market_data_factory: factory function for market data adapter.
                               If None, uses BacktestMarketDataAdapter by default.
            strategy_factory: Required factory function for strategy
            frontend_factory: factory function for frontend
        """
        self.logger.info("Configurando exchange y estrategia...")

        # Crear adaptadores (use defaults if factories not provided)
        if market_data_factory is None:
            self.market_data = BacktestMarketDataAdapter(self.simulator)
        else:
            self.market_data = market_data_factory(self.simulator)

        if exchange_factory is None:
            self.exchange = BacktestExchangeAdapter(market_data_adapter=self.market_data)
        else:
            self.exchange = exchange_factory(market_data=self.market_data)

        # Configurar exchange
        self.exchange.set_balance(self.config.initial_balance)
        self.exchange.set_leverage(self.config.symbol, self.config.leverage)
        self.exchange.set_fees(self.config.maker_fee, self.config.taker_fee)
        self.exchange.set_max_notional(self.config.max_notional)
        # Configurar timeframe base para order execution
        base_timeframe = get_base_timeframe(self.config.timeframes)
        self.exchange.set_base_timeframe(base_timeframe)

        # Crear estrategia
        self.strategy = strategy_factory(
            symbol=self.config.symbol,
            exchange=self.exchange,
            market_data=self.market_data,
            cycle_dispatcher=self.cycle_dispatcher,
            strategy_name=self.config.strategy_name,
        )

        # Configurar loggers de componentes
        self._configure_component_loggers()

        # Set up cycle tracking if enabled
        if self.config.track_cycles and self.cycle_dispatcher:
            self.cycle_dispatcher.add_cycle_listener(self.config.symbol, self._on_cycle_completed)

        # Agregar listener para capturar el último candle del timeframe base
        base_timeframe = get_base_timeframe(self.config.timeframes)
        self.market_data.add_complete_candle_listener(self.config.symbol, base_timeframe, self._on_base_candle_update)

        # Frontend initialization (if needed) would go here
        self.logger.info("Configuración completada")

    def _on_cycle_completed(self, cycle: Cycle):
        """Handle cycle completion event"""
        self.cycles.append(cycle)
        if self.cycles_repository:
            self.cycles_repository.save_cycle(cycle)
        self.logger.info(f"Cycle completed and saved: {cycle}")

    def _on_base_candle_update(self, candle):
        """Handle base timeframe candle update - guardar el último candle para drawdown calculation"""
        self.last_base_candle = candle

    def _update_drawdown(self):
        """Actualizar max drawdown basado en unrealized PnL actual"""
        debug_logger = get_debug_logger("backtest.debug")
        
        # Usar el último candle del timeframe base que fue procesado por el exchange
        last_candle = self.last_base_candle

        if last_candle:
            balance = self.exchange.get_balance()
            # Acceder al exchange real desde el adapter
            exchange_real = self.exchange.exchange if hasattr(self.exchange, 'exchange') else self.exchange
            real_balance = exchange_real.get_real_balance(self.config.symbol, last_candle)
            # Calcular unrealized PnL: real_balance - balance_efectivo
            unrealized_pnl = real_balance - balance

            debug_logger.debug(
                f"_update_drawdown: candle_timestamp={last_candle.timestamp}, balance=${balance:,.2f}, "
                f"real_balance=${real_balance:,.2f}, unrealized_pnl=${unrealized_pnl:,.2f}, "
                f"current_max_unrealized_pnl_loss=${self.max_unrealized_pnl_loss:,.2f}"
            )

            # Si el unrealized PnL es negativo, actualizar el máximo
            if unrealized_pnl < 0:
                if unrealized_pnl < self.max_unrealized_pnl_loss:
                    old_max = self.max_unrealized_pnl_loss
                    self.max_unrealized_pnl_loss = unrealized_pnl
                    debug_logger.info(
                        f"_update_drawdown: UPDATED max_unrealized_pnl_loss from ${old_max:,.2f} to ${unrealized_pnl:,.2f}"
                    )
                else:
                    debug_logger.debug(
                        f"_update_drawdown: unrealized_pnl=${unrealized_pnl:,.2f} is negative but not less than current max=${self.max_unrealized_pnl_loss:,.2f}"
                    )
            else:
                debug_logger.debug(f"_update_drawdown: unrealized_pnl=${unrealized_pnl:,.2f} is not negative")
        else:
            debug_logger.debug("_update_drawdown: last_base_candle is None, skipping update")

    def run(self) -> BacktestResults:
        """Ejecutar el backtest completo"""
        if not self.exchange or not self.market_data or not self.strategy:
            raise ValueError("Debe configurar exchange y estrategia antes de ejecutar")

        # Extract backtest_id from log_filename (format: "backtest_{id}")
        backtest_id = None
        if self.config.log_filename:
            # Remove "backtest_" prefix if present
            backtest_id = (
                self.config.log_filename.replace("backtest_", "")
                if self.config.log_filename.startswith("backtest_")
                else self.config.log_filename
            )

        # Logging inicial - detallado solo en backtest logger
        self.backtest_logger.info("=" * 80)
        self.backtest_logger.info(f"BACKTEST INICIADO: {self.config.symbol}")
        self.backtest_logger.info(f"Estrategia: {self.config.strategy_name}")
        self.backtest_logger.info(f"Fecha inicio: {datetime.fromtimestamp(self.config.start_time / 1000)}")
        if self.config.end_time:
            self.backtest_logger.info(f"Fecha fin: {datetime.fromtimestamp(self.config.end_time / 1000)}")
        else:
            self.backtest_logger.info("Fecha fin: Actualidad")
        self.backtest_logger.info(f"Balance inicial: ${self.config.initial_balance}")
        self.backtest_logger.info(f"Leverage: {self.config.leverage}x")
        self.backtest_logger.info("=" * 80)

        # Log inicio: usar logger principal con contexto del run_id del orchestrator
        # NO crear run logger específico aquí, usar el contexto para que se capture en el run logger principal
        if self.run_id:
            # El run_id aquí es el del orchestrator, así que los logs irán al archivo run principal
            with logging_context(run_id=self.run_id, agent="backtest", flow="execute_backtest"):
                self.logger.info(
                    f"Backtest started: id={backtest_id} symbol={self.config.symbol} "
                    f"strategy={self.config.strategy_name}"
                )
        else:
            self.logger.info(f"Iniciando backtest para {self.config.symbol}")
            self.logger.info(
                f"Período: {datetime.fromtimestamp(self.config.start_time / 1000)} - "
                f"{datetime.fromtimestamp(self.config.end_time / 1000) if self.config.end_time else 'Actualidad'}"
            )

        self.start_execution_time = time.time()
        self.candles_processed = 0
        self._update_drawdown()

        try:
            if self.config.enable_frontend:
                self._run_with_frontend()
            else:
                self._run_headless()
        except KeyboardInterrupt:
            self.logger.info("Backtest interrumpido por el usuario")
        except Exception as e:
            self.logger.error(f"Error durante el backtest: {e}")
            raise

        # Calcular resultados
        results = self._calculate_results()
        self._log_results(results)
        self._print_results_to_console(results)

        # Log fin: usar logger principal con contexto del run_id del orchestrator
        if self.run_id:
            # El run_id aquí es el del orchestrator, así que los logs irán al archivo run principal
            with logging_context(run_id=self.run_id, agent="backtest", flow="execute_backtest"):
                self.logger.info(
                    f"Backtest completed: id={backtest_id} symbol={self.config.symbol} "
                    f"return={results.return_percentage:.2f}% trades={results.total_trades}"
                )

        return results

    def _run_with_frontend(self):
        """Ejecutar backtest en modo frontend"""
        if not self.front:
            raise ValueError("Frontend no inicializado")

        self.logger.info("Esperando control desde la interfaz web...")
        try:
            while not self.simulator.ended(self.config.symbol):
                time.sleep(0.1)
                if self._should_stop():
                    self.logger.info("Condición de parada alcanzada")
                    break
        except KeyboardInterrupt:
            self.logger.info("Backtest interrumpido por el usuario")

    def _run_headless(self):
        """Ejecutar backtest en modo headless - avance automático"""
        debug_logger = get_debug_logger("backtest.debug")
        # Conectar el debug_logger al handler del backtest para que sus logs aparezcan en el archivo
        debug_logger.addHandler(self.backtest_handler)

        # Log de depuración: verificar estado inicial (DEBUG)
        ended = self.simulator.ended(self.config.symbol)
        current_time = self.simulator.current_time
        start_time = self.simulator.start_time
        end_time = self.simulator.end_time

        debug_logger.debug(
            f"Iniciando loop headless - Estado inicial: "
            f"ended={ended}, current_time={current_time}, "
            f"start_time={start_time}, end_time={end_time}, "
            f"duration={end_time - start_time}ms"
        )

        # INFO: inicio de loop (sin detalles internos)
        self.logger.info("Iniciando loop headless del backtest")

        if ended:
            self.logger.warning(
                f"El simulador ya está marcado como terminado para {self.config.symbol} antes de iniciar el loop!"
            )
            return

        loop_iteration = 0
        while not self.simulator.ended(self.config.symbol):
            loop_iteration += 1
            try:
                # DEBUG: primera iteración (detalle interno)
                if loop_iteration == 1:
                    debug_logger.debug("Primera iteración del loop - llamando next_candle()")

                self.simulator.next_candle()
                self.candles_processed += 1

                # Actualizar drawdown en cada vela para capturar el máximo unrealized PnL negativo
                self._update_drawdown()

                if self.candles_processed % 100 == 0:
                    self.logger.info(
                        f"Procesadas {self.candles_processed:,} velas | Balance: ${self.exchange.get_balance():,.2f}"
                    )

                if self._should_stop():
                    self.logger.info("Condición de parada alcanzada")
                    break

                self._update_progress()
            except Exception as e:
                self.logger.error(f"Error procesando vela {self.candles_processed}: {e}", exc_info=True)
                raise

        # DEBUG: estado final detallado
        debug_logger.debug(
            f"Loop terminado - Estado final: "
            f"iteraciones={loop_iteration}, "
            f"ended={self.simulator.ended(self.config.symbol)}, "
            f"candles_processed={self.candles_processed}"
        )

        # INFO: loop terminado (sin detalles internos)
        self.logger.info("Loop headless del backtest terminado")

    def _should_stop(self) -> bool:
        """Verificar si se debe detener el backtest"""
        if not self.config.stop_on_loss:
            return False

        current_balance = self.exchange.get_balance()
        initial_balance = self.config.initial_balance
        loss_percentage = float((initial_balance - current_balance) / initial_balance)

        if loss_percentage >= self.config.max_loss_percentage:
            self.logger.warning(f"Pérdida máxima alcanzada: {loss_percentage:.2%}")
            return True

        return False

    def _update_progress(self):
        """Actualizar progreso del backtest"""
        if not self.config.progress_callback:
            return

        current_time = time.time()
        if (current_time - self.last_progress_update) > 1.0:
            progress_data = {
                "candles_processed": self.candles_processed,
                "current_balance": float(self.exchange.get_balance()),
                "execution_time": current_time - self.start_execution_time,
                "candles_per_second": self.candles_processed / (current_time - self.start_execution_time),
            }
            self.config.progress_callback(progress_data)
            self.last_progress_update = current_time

    def _analyze_closed_positions(self, trades: list[Trade]) -> dict:
        """Analizar posiciones cerradas usando P&L ya calculado en trades"""
        closed_positions = []
        closing_trades = []

        for trade in trades:
            if trade.realized_pnl != 0:
                is_partial = not trade.closes_position_completely
                position_data = {
                    "profit": trade.realized_pnl,
                    "side": trade.position_side,
                    "trade": trade,
                    "is_partial": is_partial,
                    "is_winner": trade.realized_pnl > 0,
                }

                if trade.closes_position_completely:
                    closed_positions.append(position_data)

                closing_trades.append(trade)

        total_closing = len(closing_trades)
        partial_closing = len([t for t in closing_trades if not t.closes_position_completely])
        full_closing = len([t for t in closing_trades if t.closes_position_completely])

        winning_closing = len([p for p in closed_positions if p["is_winner"]])
        losing_closing = len([p for p in closed_positions if not p["is_winner"]])

        partial_winning = len([t for t in closing_trades if not t.closes_position_completely and t.realized_pnl > 0])
        partial_losing = len([t for t in closing_trades if not t.closes_position_completely and t.realized_pnl <= 0])
        full_winning = len([t for t in closing_trades if t.closes_position_completely and t.realized_pnl > 0])
        full_losing = len([t for t in closing_trades if t.closes_position_completely and t.realized_pnl <= 0])

        return {
            "positions": closed_positions,
            "stats": {
                "total_closing_trades": total_closing,
                "partial_closing_trades": partial_closing,
                "full_closing_trades": full_closing,
                "winning_closing_trades": winning_closing,
                "losing_closing_trades": losing_closing,
                "partial_winning_trades": partial_winning,
                "partial_losing_trades": partial_losing,
                "full_winning_trades": full_winning,
                "full_losing_trades": full_losing,
            },
        }

    def _validate_metrics_consistency(self, results: BacktestResults, trades: list[Trade]) -> list[str]:
        """Validar consistencia de métricas calculadas"""
        warnings = []

        initial = results.final_balance - results.total_return
        if abs(float(initial - self.config.initial_balance)) > 0.01:
            warnings.append(
                f"Balance inconsistency: initial calculated {initial} != config {self.config.initial_balance}"
            )

        sum_realized = sum(t.realized_pnl for t in trades)
        # total_return ya incluye todo: profits de cierres - todas las comisiones (apertura + cierre)
        # sum_realized solo incluye: profits de cierres - comisiones de cierres
        # Las comisiones de apertura se restan del balance pero no están en realized_pnl
        # Por lo tanto: sum_realized = total_return + opening_commissions
        opening_commissions = sum(abs(t.commission) for t in trades if t.realized_pnl == 0)
        expected_return = results.total_return + opening_commissions
        if abs(float(sum_realized - expected_return)) > 0.01:
            warnings.append(
                f"P&L inconsistency: sum realized_pnl {sum_realized} != "
                f"total_return {results.total_return} + opening_commissions {opening_commissions} = {expected_return}"
            )

        expected_wr = (
            (results.winning_positions / results.total_closed_positions * 100)
            if results.total_closed_positions > 0
            else 0
        )
        if abs(expected_wr - results.win_rate) > 0.01:
            warnings.append(f"Win rate inconsistency: {expected_wr}% != {results.win_rate}%")

        if results.profit_factor > 1 and results.total_return <= 0:
            warnings.append("Profit factor > 1 but return is negative")
        if results.profit_factor < 1 and results.total_return > 0:
            warnings.append("Profit factor < 1 but return is positive")

        return warnings

    def _calculate_cycle_statistics(self) -> dict:
        """Calculate cycle statistics from completed cycles"""
        if not self.cycles:
            return {
                "total_cycles": 0,
                "avg_cycle_duration": 0.0,
                "avg_cycle_pnl": 0.0,
                "winning_cycles": 0,
                "losing_cycles": 0,
                "cycle_win_rate": 0.0,
            }

        total_cycles = len(self.cycles)
        winning_cycles = len([c for c in self.cycles if c.total_pnl > 0])
        losing_cycles = total_cycles - winning_cycles

        avg_duration = sum(c.duration_minutes for c in self.cycles) / total_cycles
        avg_pnl = sum(float(c.total_pnl) for c in self.cycles) / total_cycles
        win_rate = (winning_cycles / total_cycles * 100) if total_cycles > 0 else 0.0

        return {
            "total_cycles": total_cycles,
            "avg_cycle_duration": round(avg_duration, 2),
            "avg_cycle_pnl": round(avg_pnl, 2),
            "winning_cycles": winning_cycles,
            "losing_cycles": losing_cycles,
            "cycle_win_rate": round(win_rate, 2),
        }

    def _calculate_results(self) -> BacktestResults:
        """Calcular resultados finales del backtest"""
        end_time = int(time.time() * 1000)
        duration = time.time() - self.start_execution_time

        final_balance = self.exchange.get_balance()
        initial_balance = self.config.initial_balance
        total_return = final_balance - initial_balance
        return_percentage = float(total_return / initial_balance) * 100

        trades = self.exchange.get_trades(self.config.symbol)
        total_trades = len(trades)

        position_analysis = self._analyze_closed_positions(trades)
        closed_positions = position_analysis["positions"]
        stats = position_analysis["stats"]

        total_closed = len(closed_positions)
        winning_positions = [p for p in closed_positions if p["profit"] > 0]
        losing_positions = [p for p in closed_positions if p["profit"] < 0]

        win_rate = (len(winning_positions) / total_closed * 100) if total_closed > 0 else 0

        gross_profit = sum(p["profit"] for p in winning_positions)
        gross_loss = abs(sum(p["profit"] for p in losing_positions))
        profit_factor = (
            float(gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0)
        )

        # Calcular max_drawdown desde max_unrealized_pnl_loss
        max_drawdown = 0.0
        if self.max_unrealized_pnl_loss < 0:
            # Drawdown en porcentaje del balance efectivo
            balance_efectivo = float(final_balance)
            if balance_efectivo > 0:
                max_drawdown = (abs(float(self.max_unrealized_pnl_loss)) / balance_efectivo) * 100
            else:
                max_drawdown = 0.0
            
            self.logger.info(
                f"Max drawdown calculation (basado en unrealized PnL): "
                f"max_unrealized_pnl_loss=${self.max_unrealized_pnl_loss:,.2f}, "
                f"balance_efectivo=${balance_efectivo:,.2f}, "
                f"max_drawdown={max_drawdown:.4f}%"
            )
        else:
            self.logger.info("No unrealized PnL negativo registrado durante el backtest")

        total_trade_value = sum(abs(t.quantity * t.price) for t in trades)
        avg_trade_size = total_trade_value / len(trades) if trades else Decimal(0)
        total_commission = sum(abs(t.commission) for t in trades)
        commission_pct = (float(total_commission / abs(total_return)) * 100) if total_return != 0 else 0

        cycle_stats = self._calculate_cycle_statistics()
        self._update_drawdown()

        results = BacktestResults(
            start_time=self.config.start_time,
            end_time=end_time,
            duration_seconds=duration,
            total_candles_processed=self.candles_processed,
            final_balance=final_balance,
            total_return=total_return,
            return_percentage=return_percentage,
            max_drawdown=max_drawdown,
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_closed_positions=total_closed,
            winning_positions=len(winning_positions),
            losing_positions=len(losing_positions),
            average_trade_size=avg_trade_size,
            total_commission=total_commission,
            commission_percentage=commission_pct,
            total_closing_trades=stats["total_closing_trades"],
            partial_closing_trades=stats["partial_closing_trades"],
            full_closing_trades=stats["full_closing_trades"],
            winning_closing_trades=stats["winning_closing_trades"],
            losing_closing_trades=stats["losing_closing_trades"],
            partial_winning_trades=stats["partial_winning_trades"],
            partial_losing_trades=stats["partial_losing_trades"],
            full_winning_trades=stats["full_winning_trades"],
            full_losing_trades=stats["full_losing_trades"],
            total_cycles=cycle_stats["total_cycles"],
            avg_cycle_duration=cycle_stats["avg_cycle_duration"],
            avg_cycle_pnl=cycle_stats["avg_cycle_pnl"],
            winning_cycles=cycle_stats["winning_cycles"],
            losing_cycles=cycle_stats["losing_cycles"],
            cycle_win_rate=cycle_stats["cycle_win_rate"],
            strategy_name=self.config.strategy_name,
            symbol=self.config.symbol,
        )

        warnings = self._validate_metrics_consistency(results, trades)
        if warnings:
            self.logger.warning("ADVERTENCIAS DE CONSISTENCIA:")
            for warning in warnings:
                self.logger.warning(f"  - {warning}")

        return results

    def _log_results(self, results: BacktestResults):
        """Loggear resultados del backtest"""
        self.logger.info("=" * 60)
        self.logger.info("RESULTADOS DEL BACKTEST")
        self.logger.info("=" * 60)
        self.logger.info(f"Balance inicial: ${results.final_balance - results.total_return:,.2f}")
        self.logger.info(f"Balance final: ${results.final_balance:,.2f}")
        self.logger.info(f"Retorno total: ${results.total_return:,.2f}")
        self.logger.info(f"Retorno porcentual: {results.return_percentage:.2f}%")
        self.logger.info(f"Max Drawdown: {results.max_drawdown:.2f}%")
        self.logger.info("-" * 60)
        self.logger.info(f"Total trades: {results.total_trades}")
        self.logger.info(f"Tamaño promedio trade: ${results.average_trade_size:,.2f}")
        self.logger.info(f"Posiciones cerradas: {results.total_closed_positions}")
        self.logger.info(f"Posiciones ganadoras: {results.winning_positions}")
        self.logger.info(f"Posiciones perdedoras: {results.losing_positions}")
        self.logger.info(f"Win rate: {results.win_rate:.2f}%")
        self.logger.info(f"Profit factor: {results.profit_factor:.2f}")
        self.logger.info("=" * 60)
        enable_logging_after_backtest()

    def _print_results_to_console(self, results: BacktestResults):
        """Mostrar resultados del backtest"""
        output_lines = []
        output_lines.append("\n" + "=" * 80)
        output_lines.append("📊 RESULTADOS DEL BACKTEST")
        output_lines.append("=" * 80)
        output_lines.append(f"💰 Balance inicial: ${results.final_balance - results.total_return:,.2f}")
        output_lines.append(f"💰 Balance final: ${results.final_balance:,.2f}")
        output_lines.append(f"📈 Retorno total: ${results.total_return:,.2f}")
        output_lines.append(f"📊 Retorno porcentual: {results.return_percentage:.2f}%")
        output_lines.append(f"📉 Max Drawdown: {results.max_drawdown:.2f}%")
        output_lines.append("-" * 80)
        output_lines.append(f"🔄 Total trades: {results.total_trades}")
        output_lines.append(f"🎯 Posiciones cerradas: {results.total_closed_positions}")
        output_lines.append(f"🏆 Win rate: {results.win_rate:.2f}%")
        output_lines.append(f"⚖️  Profit factor: {results.profit_factor:.2f}")
        output_lines.append("=" * 80)

        for line in output_lines:
            print(line)
            self.backtest_logger.info(line)

    def cleanup(self):
        """Limpiar recursos"""
        import io
        import sys

        disable_logging_for_backtest()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            if hasattr(self, "market_data") and self.market_data:
                self.market_data.close()
                self.market_data = None

            if hasattr(self, "simulator") and self.simulator:
                self.simulator.close()
                self.simulator = None
        finally:
            sys.stdout = old_stdout

        if hasattr(self, "backtest_handler"):
            self.backtest_handler.close()
            if hasattr(self, "backtest_logger"):
                self.backtest_logger.removeHandler(self.backtest_handler)

        self.exchange = None
        self.strategy = None
        self.front = None
