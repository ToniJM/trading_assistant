#!/usr/bin/env python3
"""Script para ejecutar el scheduler en modo continuo"""

import argparse
import json
import os
import signal
import sys
from pathlib import Path

# Configure pythonnet to use .NET Core instead of Mono (required on macOS)
if "PYTHONNET_RUNTIME" not in os.environ:
    os.environ["PYTHONNET_RUNTIME"] = "coreclr"

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading.agents import SchedulerAgent
from trading.infrastructure.scheduler.scheduler_config import SchedulerConfig


def load_config_from_file(config_path: str) -> SchedulerConfig:
    """Load configuration from JSON file"""
    with open(config_path, "r") as f:
        config_dict = json.load(f)
    return SchedulerConfig(**config_dict)


def main():
    parser = argparse.ArgumentParser(
        description="Ejecutar scheduler en modo continuo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Scheduler básico
  python scripts/run_scheduler.py --symbol BTCUSDT --strategy carga_descarga

  # Con configuración personalizada
  python scripts/run_scheduler.py \\
    --symbol BTCUSDT \\
    --strategy carga_descarga \\
    --interval 1800 \\
    --duration 30 \\
    --max-iterations 3

  # Desde archivo de configuración
  python scripts/run_scheduler.py --config scheduler_config.json
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Archivo de configuración JSON (opcional, sobrescribe otros argumentos)",
    )
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Símbolo a tradear (e.g., BTCUSDT)")
    parser.add_argument("--strategy", type=str, default="carga_descarga", help="Nombre de estrategia")
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Intervalo entre ejecuciones en segundos (default: 3600 = 1 hora)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duración de cada backtest en días (default: 30)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Máximo de iteraciones de optimización por ciclo (default: 5)",
    )
    parser.add_argument(
        "--kpi-sharpe",
        type=float,
        default=2.0,
        help="KPI threshold para Sharpe Ratio (default: 2.0)",
    )
    parser.add_argument(
        "--kpi-drawdown",
        type=float,
        default=10.0,
        help="KPI threshold para Max Drawdown porcentaje (default: 10.0)",
    )
    parser.add_argument(
        "--kpi-profit-factor",
        type=float,
        default=1.5,
        help="KPI threshold para Profit Factor (default: 1.5)",
    )
    parser.add_argument(
        "--no-reset-memory",
        action="store_true",
        help="Desactivar reset diario de memoria episódica",
    )
    parser.add_argument(
        "--initial-balance",
        type=float,
        default=2500.0,
        help="Balance inicial para backtests (default: 2500.0)",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=100.0,
        help="Leverage para backtests (default: 100.0)",
    )
    parser.add_argument(
        "--backtests-per-period",
        type=int,
        default=10,
        help="Cantidad de backtests por periodo (default: 10)",
    )
    parser.add_argument(
        "--min-passed-backtests",
        type=int,
        default=10,
        help="Mínimo de backtests que deben pasar KPIs para avanzar al siguiente periodo (default: 10)",
    )

    args = parser.parse_args()

    # Load config from file or create from args
    if args.config:
        config = load_config_from_file(args.config)
    else:
        config = SchedulerConfig(
            symbol=args.symbol,
            strategy_name=args.strategy,
            schedule_interval_seconds=args.interval,
            backtest_duration_days=args.duration,
            max_iterations_per_cycle=args.max_iterations,
            kpis={
                "sharpe_ratio": args.kpi_sharpe,
                "max_drawdown": args.kpi_drawdown,
                "profit_factor": args.kpi_profit_factor,
            },
            auto_reset_memory=not args.no_reset_memory,
            initial_balance=args.initial_balance,
            leverage=args.leverage,
            backtests_per_period=args.backtests_per_period,
            min_passed_backtests_per_period=args.min_passed_backtests,
        )

    # Create scheduler
    scheduler = SchedulerAgent(config=config)
    scheduler.initialize()

    # Handle SIGINT (Ctrl+C) gracefully
    def signal_handler(sig, frame):
        print("\n🛑 Deteniendo scheduler...")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Start scheduler
    print("🚀 Iniciando scheduler...")
    print(f"   Símbolo: {config.symbol}")
    print(f"   Estrategia: {config.strategy_name}")
    print(f"   Intervalo: {config.schedule_interval_seconds} segundos")
    print(f"   Duración backtest: {config.backtest_duration_days} días")
    print(f"   Máximo iteraciones: {config.max_iterations_per_cycle}")
    print(f"   Reset diario memoria: {'Sí' if config.auto_reset_memory else 'No'}")
    print(f"   Periodos incrementales: {config.incremental_periods} días")
    print(f"   Backtests por periodo: {config.backtests_per_period}")
    print(f"   Mínimo pasados por periodo: {config.min_passed_backtests_per_period}")
    print("\n💡 Presiona Ctrl+C para detener el scheduler\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n🛑 Scheduler detenido por el usuario")
    finally:
        scheduler.close()


if __name__ == "__main__":
    main()

