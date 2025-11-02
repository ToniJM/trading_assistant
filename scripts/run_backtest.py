#!/usr/bin/env python3
"""Script para ejecutar backtests usando los agentes ADK"""

import os

# Configure pythonnet to use .NET Core instead of Mono (required on macOS)
# This MUST be done before any imports that might trigger pythonnet initialization
if "PYTHONNET_RUNTIME" not in os.environ:
    os.environ["PYTHONNET_RUNTIME"] = "coreclr"

import argparse
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading.agents import OrchestratorAgent
from trading.domain.messages import StartBacktestRequest
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


def run_backtest(
    symbol: str,
    start_time: int,
    end_time: int | None,
    strategy_name: str = "carga_descarga",
    initial_balance: Decimal = Decimal("2500"),
    leverage: Decimal = Decimal("100"),
    max_notional: Decimal = Decimal("50000"),
    timeframes: list[str] = None,
    rsi_limits: list[int] | None = None,
    **kwargs,
):
    """Execute backtest using OrchestratorAgent"""
    print(f"🚀 Iniciando backtest para {symbol}...")
    print(f"   Estrategia: {strategy_name}")
    print(f"   Start time: {datetime.fromtimestamp(start_time / 1000)}")
    if end_time:
        print(f"   End time: {datetime.fromtimestamp(end_time / 1000)}")
    else:
        print("   End time: current")
    if rsi_limits:
        print(f"   RSI limits: {rsi_limits}")

    # Create orchestrator
    orchestrator = OrchestratorAgent(run_id=f"backtest_{int(datetime.now().timestamp() * 1000)}")
    orchestrator.initialize()

    # Set default timeframes if not provided
    if timeframes is None:
        timeframes = ["1m", "15m", "1h"]

    # Create backtest request (use orchestrator's run_id to ensure single run log file)
    request = StartBacktestRequest(
        symbol=symbol,
        start_time=start_time,
        end_time=end_time,
        initial_balance=initial_balance,
        leverage=leverage,
        max_notional=max_notional,
        strategy_name=strategy_name,
        run_id=orchestrator.run_id,  # Use orchestrator's run_id to avoid creating separate run logs
        timeframes=timeframes,
        rsi_limits=rsi_limits,
        **kwargs,
    )

    # Create strategy factory with timeframes and rsi_limits
    strategy_factory = create_strategy_factory(
        strategy_name=strategy_name, timeframes=timeframes, rsi_limits=rsi_limits
    )

    try:
        # Execute backtest
        results = orchestrator.run_backtest(request, strategy_factory=strategy_factory)

        # Print results
        print("\n✅ Backtest completado!")
        print(f"   Duración: {results.duration_seconds:.2f} segundos")
        print(f"   Velas procesadas: {results.total_candles_processed:,}")
        print(f"   Retorno: {results.return_percentage:.2f}%")
        print(f"   Balance final: ${results.final_balance:,.2f}")
        print(f"   Total trades: {results.total_trades}")
        print(f"   Win rate: {results.win_rate:.2f}%")
        print(f"   Profit factor: {results.profit_factor:.2f}")
        if results.total_cycles > 0:
            print(f"   Total ciclos: {results.total_cycles}")
            print(f"   Cycle win rate: {results.cycle_win_rate:.2f}%")

        return results

    finally:
        orchestrator.close()


def main():
    parser = argparse.ArgumentParser(description="Ejecutar backtest usando agentes ADK")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading symbol (e.g., BTCUSDT)")
    parser.add_argument("--start-time", type=str, required=True, help="Start timestamp (ms) or ISO format")
    parser.add_argument(
        "--end-time", type=str, default=None, help="End timestamp (ms) or ISO format (default: current)"
    )
    parser.add_argument(
        "--strategy", type=str, default="carga_descarga", choices=get_available_strategies(), help="Strategy name"
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
        "--stop-on-loss", action="store_true", default=True, help="Stop backtest if loss threshold reached"
    )
    parser.add_argument(
        "--timeframes",
        nargs="+",
        default=["1m", "15m", "1h"],
        help="Timeframes to use. Example: --timeframes 1m 15m 1h. Default: 1m 15m 1h",
    )
    parser.add_argument(
        "--rsi-limits",
        type=int,
        nargs=3,
        metavar=("LOW", "MEDIUM", "HIGH"),
        help=(
            "RSI threshold values: low, medium, high. Must be 3 integers in range 0-100. "
            "Example: --rsi-limits 15 50 85. Default: 15 50 85"
        ),
    )

    args = parser.parse_args()

    # Parse timestamps
    start_time = parse_timestamp(args.start_time)
    end_time = parse_timestamp(args.end_time) if args.end_time else None

    # Run backtest
    run_backtest(
        symbol=args.symbol,
        start_time=start_time,
        end_time=end_time,
        strategy_name=args.strategy,
        initial_balance=args.initial_balance,
        leverage=args.leverage,
        max_notional=args.max_notional,
        max_loss_percentage=args.max_loss_percentage,
        stop_on_loss=args.stop_on_loss,
        timeframes=args.timeframes,
        rsi_limits=args.rsi_limits,
    )


if __name__ == "__main__":
    main()
