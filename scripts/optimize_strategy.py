#!/usr/bin/env python3
"""Script para optimizar estrategias usando OptimizerAgent con IA"""

import os

# Configure pythonnet to use .NET Core instead of Mono (required on macOS)
# This MUST be done before any imports that might trigger pythonnet initialization
if "PYTHONNET_RUNTIME" not in os.environ:
    os.environ["PYTHONNET_RUNTIME"] = "coreclr"

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading.agents import OrchestratorAgent
from trading.domain.messages import (
    BacktestResultsResponse,
    EvaluationResponse,
    OptimizationResult,
    StartBacktestRequest,
)
from trading.strategies.factory import create_strategy_factory, get_available_strategies


def parse_timestamp(timestamp_str: str) -> int:
    """Parse timestamp string to milliseconds"""
    if timestamp_str.isdigit():
        return int(timestamp_str)
    else:
        # Try parsing as ISO format
        try:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return int(dt.timestamp() * 1000)
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {timestamp_str}")


def parse_rsi_limits(rsi_str: str) -> list[int]:
    """Parse RSI limits from comma-separated string"""
    try:
        values = [int(x.strip()) for x in rsi_str.split(",")]
        if len(values) != 3:
            raise ValueError("RSI limits must have exactly 3 values")
        if not all(0 <= v <= 100 for v in values):
            raise ValueError("All RSI values must be in range 0-100")
        if not (values[0] < values[1] < values[2]):
            raise ValueError("RSI limits must be in ascending order: low < medium < high")
        return values
    except ValueError as e:
        raise ValueError(f"Invalid RSI limits format: {e}")


def print_iteration_header(iteration: int, max_iterations: int):
    """Print iteration header"""
    print("\n" + "=" * 80)
    print(f"🔄 ITERACIÓN {iteration}/{max_iterations}")
    print("=" * 80)


def print_backtest_results(results: BacktestResultsResponse, iteration: int):
    """Print backtest results in a formatted way"""
    print(f"\n📊 Resultados del Backtest (Iteración {iteration}):")
    print(f"   Duración: {results.duration_seconds:.2f} segundos")
    print(f"   Velas procesadas: {results.total_candles_processed:,}")
    print(f"   Retorno: {results.return_percentage:.2f}%")
    print(f"   Balance final: ${results.final_balance:,.2f}")
    print(f"   Total trades: {results.total_trades}")
    print(f"   Win rate: {results.win_rate:.2f}%")
    print(f"   Profit factor: {results.profit_factor:.2f}")
    print(f"   Max drawdown: {results.max_drawdown:.2f}%")
    if results.total_cycles > 0:
        print(f"   Total ciclos: {results.total_cycles}")
        print(f"   Cycle win rate: {results.cycle_win_rate:.2f}%")


def print_evaluation_results(evaluation: EvaluationResponse):
    """Print evaluation results in a formatted way"""
    print("\n📈 Evaluación de Resultados:")
    print(f"   Status: {'✅ PASÓ' if evaluation.evaluation_passed else '❌ NO PASÓ'}")
    print(f"   Recomendación: {evaluation.recommendation.upper()}")

    print("\n   Métricas calculadas:")
    for metric_name, metric_value in evaluation.metrics.items():
        print(f"   - {metric_name}: {metric_value:.4f}")

    print("\n   Cumplimiento de KPIs:")
    for kpi_name, passed in evaluation.kpi_compliance.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {kpi_name}: {'CUMPLE' if passed else 'NO CUMPLE'}")


def print_optimization_results(opt_result: OptimizationResult):
    """Print optimization results in a formatted way"""
    print("\n🤖 Resultados de Optimización con IA:")
    print(f"   Confianza: {opt_result.confidence:.2%}")
    print("   Parámetros optimizados:")
    for param_name, param_value in opt_result.optimized_parameters.items():
        print(f"      - {param_name}: {param_value}")
    print("\n   Razonamiento:")
    print(f"      {opt_result.reasoning}")
    if opt_result.expected_improvement:
        print("\n   Mejoras esperadas:")
        for metric, improvement in opt_result.expected_improvement.items():
            sign = "+" if improvement >= 0 else ""
            print(f"      - {metric}: {sign}{improvement:.4f}")


def print_comparison_table(iterations: list[dict[str, Any]]):
    """Print comparison table of all iterations"""
    print("\n" + "=" * 80)
    print("📊 TABLA COMPARATIVA DE ITERACIONES")
    print("=" * 80)

    # Header
    header = f"{'Iter':<6} {'RSI Limits':<20} {'Return %':<12} {'Win Rate %':<12} {'Profit Factor':<14} {'Drawdown %':<12} {'Status':<10}"
    print(header)
    print("-" * 80)

    # Rows
    for iter_data in iterations:
        rsi_str = str(iter_data.get("rsi_limits", "N/A"))
        return_pct = iter_data.get("return_percentage", 0)
        win_rate = iter_data.get("win_rate", 0)
        profit_factor = iter_data.get("profit_factor", 0)
        drawdown = iter_data.get("max_drawdown", 0)
        status = "✅ PASS" if iter_data.get("evaluation_passed", False) else "❌ FAIL"

        row = (
            f"{iter_data['iteration']:<6} "
            f"{rsi_str:<20} "
            f"{return_pct:>10.2f}% "
            f"{win_rate:>10.2f}% "
            f"{profit_factor:>12.2f} "
            f"{drawdown:>10.2f}% "
            f"{status:<10}"
        )
        print(row)

    print("=" * 80)


def print_summary(iterations: list[dict[str, Any]]):
    """Print final summary with best configuration"""
    print("\n" + "=" * 80)
    print("🎯 RESUMEN FINAL")
    print("=" * 80)

    if not iterations:
        print("❌ No se completaron iteraciones")
        return

    # Find best iteration (by return percentage, or by evaluation_passed)
    best_iter = max(
        iterations,
        key=lambda x: (
            x.get("evaluation_passed", False),
            x.get("return_percentage", 0),
        ),
    )

    print(f"\n✅ Mejor configuración encontrada (Iteración {best_iter['iteration']}):")
    print(f"   RSI Limits: {best_iter.get('rsi_limits', 'N/A')}")
    print(f"   Return: {best_iter.get('return_percentage', 0):.2f}%")
    print(f"   Win Rate: {best_iter.get('win_rate', 0):.2f}%")
    print(f"   Profit Factor: {best_iter.get('profit_factor', 0):.2f}")
    print(f"   Max Drawdown: {best_iter.get('max_drawdown', 0):.2f}%")
    print(f"   KPIs Cumplidos: {'✅ SÍ' if best_iter.get('evaluation_passed', False) else '❌ NO'}")

    # Show improvement from first to best
    if len(iterations) > 1:
        first = iterations[0]
        improvement = best_iter.get("return_percentage", 0) - first.get("return_percentage", 0)
        print(f"\n📈 Mejora desde iteración inicial: {improvement:+.2f}%")

    print(f"\n📝 Total de iteraciones completadas: {len(iterations)}")


def save_results_to_json(iterations: list[dict[str, Any]], output_file: str):
    """Save optimization results to JSON file

    If output_file is just a filename (no path separators), it will be saved
    in the results/ directory. If it's a relative or absolute path, it will
    be used as-is.
    """
    output_path = Path(output_file)

    # If it's just a filename (no directory separators), use results/ directory
    if "/" not in str(output_path) and "\\" not in str(output_path):
        results_dir = Path(__file__).parent.parent / "results"
        results_dir.mkdir(exist_ok=True)
        output_path = results_dir / output_file

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "iterations": iterations,
                "best_iteration": max(
                    iterations,
                    key=lambda x: (
                        x.get("evaluation_passed", False),
                        x.get("return_percentage", 0),
                    ),
                )
                if iterations
                else None,
            },
            f,
            indent=2,
            default=str,
        )
    print(f"\n💾 Resultados guardados en: {output_path.absolute()}")


def optimize_strategy(
    symbol: str,
    start_time: int,
    end_time: int | None,
    strategy_name: str = "carga_descarga",
    initial_balance: Decimal = Decimal("2500"),
    leverage: Decimal = Decimal("100"),
    max_notional: Decimal = Decimal("50000"),
    timeframes: list[str] | None = None,
    initial_rsi: list[int] | None = None,
    objective: str = "sharpe_ratio",
    max_iterations: int = 5,
    min_confidence: float = 0.5,
    kpis: dict[str, float] | None = None,
    output_file: str | None = None,
    **kwargs,
):
    """Execute iterative optimization using OptimizerAgent"""
    print("🚀 Iniciando optimización de estrategia con IA...")
    print(f"   Símbolo: {symbol}")
    print(f"   Estrategia: {strategy_name}")
    print(f"   Objetivo: {objective}")
    print(f"   Máximo de iteraciones: {max_iterations}")
    print(f"   Start time: {datetime.fromtimestamp(start_time / 1000)}")
    if end_time:
        print(f"   End time: {datetime.fromtimestamp(end_time / 1000)}")
    else:
        print("   End time: current")

    # Set defaults
    if timeframes is None:
        timeframes = ["1m", "15m", "1h"]
    if initial_rsi is None:
        initial_rsi = [15, 50, 85]

    print(f"   RSI inicial: {initial_rsi}")
    print(f"   Timeframes: {timeframes}")

    # Create orchestrator
    orchestrator = OrchestratorAgent(run_id=f"optimization_{int(datetime.now().timestamp() * 1000)}")
    orchestrator.initialize()

    iterations_data: list[dict[str, Any]] = []
    current_rsi = initial_rsi.copy()
    current_timeframes = timeframes.copy()

    try:
        for iteration in range(1, max_iterations + 1):
            print_iteration_header(iteration, max_iterations)

            # Create backtest request
            request = StartBacktestRequest(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                initial_balance=initial_balance,
                leverage=leverage,
                max_notional=max_notional,
                strategy_name=strategy_name,
                run_id=orchestrator.run_id,
                timeframes=current_timeframes,
                rsi_limits=current_rsi,
                **kwargs,
            )

            # Create strategy factory
            strategy_factory = create_strategy_factory(
                strategy_name=strategy_name,
                timeframes=current_timeframes,
                rsi_limits=current_rsi,
            )

            # Execute backtest
            print(f"\n▶️  Ejecutando backtest con RSI limits: {current_rsi}")
            results = orchestrator.run_backtest(request, strategy_factory=strategy_factory)
            print_backtest_results(results, iteration)

            # Evaluate results
            print("\n📊 Evaluando resultados...")
            evaluation = orchestrator.evaluate_backtest(backtest_results=results, kpis=kpis)
            print_evaluation_results(evaluation)

            # Store iteration data
            iter_data = {
                "iteration": iteration,
                "rsi_limits": current_rsi.copy(),
                "timeframes": current_timeframes.copy(),
                "return_percentage": results.return_percentage,
                "win_rate": results.win_rate,
                "profit_factor": results.profit_factor,
                "max_drawdown": results.max_drawdown,
                "total_trades": results.total_trades,
                "evaluation_passed": evaluation.evaluation_passed,
                "recommendation": evaluation.recommendation,
                "metrics": evaluation.metrics,
                "kpi_compliance": evaluation.kpi_compliance,
            }
            iterations_data.append(iter_data)

            # Check if KPIs are met
            if evaluation.evaluation_passed:
                print("\n✅ KPIs cumplidos! Deteniendo optimización.")
                break

            # Check recommendation
            if evaluation.recommendation == "reject":
                print("\n❌ Estrategia rechazada. Deteniendo optimización.")
                break

            if evaluation.recommendation == "optimize" and iteration < max_iterations:
                # Optimize using AI
                print("\n🤖 Optimizando parámetros con IA...")
                try:
                    opt_result = orchestrator.optimize_strategy(
                        strategy_name=strategy_name,
                        symbol=symbol,
                        objective=objective,
                        parameter_space={
                            "rsi_limits": list(range(10, 91, 5)),  # 10-90 in steps of 5
                        },
                        base_config=request,
                    )

                    print_optimization_results(opt_result)

                    # Check confidence
                    if opt_result.confidence < min_confidence:
                        print(
                            "\n⚠️  Confianza ({opt_result.confidence:.2%}) por debajo del mínimo "
                            f"({min_confidence:.2%}). Deteniendo optimización."
                        )
                        break

                    # Update parameters if optimization suggested new ones
                    if opt_result.optimized_parameters:
                        new_rsi = opt_result.optimized_parameters.get("rsi_limits")
                        if new_rsi and new_rsi != current_rsi:
                            print(f"\n✨ Aplicando nuevos parámetros: RSI {new_rsi}")
                            current_rsi = new_rsi
                            iter_data["optimization_applied"] = True
                            iter_data["optimization_confidence"] = opt_result.confidence
                            iter_data["optimization_reasoning"] = opt_result.reasoning
                        else:
                            print("\n⚠️  No se sugirieron nuevos parámetros o son iguales a los actuales.")
                            if iteration < max_iterations:
                                print("   Continuando con siguiente iteración...")
                    else:
                        print("\n⚠️  Optimización no retornó parámetros. Deteniendo.")
                        break

                except Exception as e:
                    print("\n❌ Error durante optimización: {e}")
                    print("   Continuando con siguiente iteración...")
                    iter_data["optimization_error"] = str(e)
            elif iteration >= max_iterations:
                print(f"\n⏱️  Límite de iteraciones alcanzado ({max_iterations})")

        # Print comparison table
        if len(iterations_data) > 1:
            print_comparison_table(iterations_data)

        # Print summary
        print_summary(iterations_data)

        # Save to JSON if requested
        if output_file:
            save_results_to_json(iterations_data, output_file)

        return iterations_data

    finally:
        orchestrator.close()


def main():
    parser = argparse.ArgumentParser(
        description="Optimizar estrategia de trading usando OptimizerAgent con IA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Optimización básica
  python scripts/optimize_strategy.py --start-time 2025-01-01T00:00:00Z --end-time 2025-01-31T23:59:59Z

  # Con parámetros personalizados
  python scripts/optimize_strategy.py \\
    --symbol BTCUSDT \\
    --start-time 2025-01-01T00:00:00Z \\
    --objective profit_factor \\
    --max-iterations 3 \\
    --initial-rsi 20,50,80

  # Guardar resultados en JSON
  python scripts/optimize_strategy.py \\
    --start-time 2025-01-01T00:00:00Z \\
    --output results.json
        """,
    )

    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading symbol (e.g., BTCUSDT)")
    parser.add_argument(
        "--strategy",
        type=str,
        default="carga_descarga",
        choices=get_available_strategies(),
        help="Strategy name",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        required=True,
        help="Start timestamp (ms) or ISO format (e.g., 2025-01-01T00:00:00Z)",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        default=None,
        help="End timestamp (ms) or ISO format (default: current)",
    )
    parser.add_argument(
        "--objective",
        type=str,
        default="sharpe_ratio",
        choices=["sharpe_ratio", "profit_factor", "return_percentage"],
        help="Optimization objective",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum number of optimization iterations (default: 5)",
    )
    parser.add_argument(
        "--initial-rsi",
        type=str,
        default="15,50,85",
        help="Initial RSI limits as comma-separated values: low,medium,high (default: 15,50,85)",
    )
    parser.add_argument(
        "--timeframes",
        nargs="+",
        default=["1m", "15m", "1h"],
        help="Timeframes to use. Example: --timeframes 1m 15m 1h. Default: 1m 15m 1h",
    )
    parser.add_argument("--initial-balance", type=Decimal, default=Decimal("2500"), help="Initial balance")
    parser.add_argument("--leverage", type=Decimal, default=Decimal("100"), help="Leverage")
    parser.add_argument("--max-notional", type=Decimal, default=Decimal("50000"), help="Max notional value")
    parser.add_argument(
        "--max-loss-percentage",
        type=float,
        default=0.5,
        help="Max loss percentage: 0.5 means 50 percent",
    )
    parser.add_argument(
        "--stop-on-loss",
        action="store_true",
        default=True,
        help="Stop backtest if loss threshold reached",
    )
    parser.add_argument(
        "--kpi-sharpe",
        type=float,
        default=2.0,
        help="KPI threshold for Sharpe Ratio (default: 2.0)",
    )
    parser.add_argument(
        "--kpi-drawdown",
        type=float,
        default=10.0,
        help="KPI threshold for Max Drawdown percentage (default: 10.0)",
    )
    parser.add_argument(
        "--kpi-profit-factor",
        type=float,
        default=1.5,
        help="KPI threshold for Profit Factor (default: 1.5)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.5,
        help="Minimum confidence threshold to apply optimization (default: 0.5)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save results to JSON file. If only filename is provided, saves to results/ directory. "
        "If path is provided, uses that path as-is (optional)",
    )

    args = parser.parse_args()

    # Parse timestamps
    start_time = parse_timestamp(args.start_time)
    end_time = parse_timestamp(args.end_time) if args.end_time else None

    # Parse RSI limits
    try:
        initial_rsi = parse_rsi_limits(args.initial_rsi)
    except ValueError as e:
        parser.error(f"Invalid --initial-rsi: {e}")

    # Build KPIs dict
    kpis = {
        "sharpe_ratio": args.kpi_sharpe,
        "max_drawdown": args.kpi_drawdown,
        "profit_factor": args.kpi_profit_factor,
    }

    # Run optimization
    optimize_strategy(
        symbol=args.symbol,
        start_time=start_time,
        end_time=end_time,
        strategy_name=args.strategy,
        initial_balance=args.initial_balance,
        leverage=args.leverage,
        max_notional=args.max_notional,
        timeframes=args.timeframes,
        initial_rsi=initial_rsi,
        objective=args.objective,
        max_iterations=args.max_iterations,
        min_confidence=args.min_confidence,
        kpis=kpis,
        output_file=args.output,
        max_loss_percentage=args.max_loss_percentage,
        stop_on_loss=args.stop_on_loss,
    )


if __name__ == "__main__":
    main()
