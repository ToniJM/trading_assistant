"""Advanced metrics calculation for backtest evaluation"""

import math
from decimal import Decimal
from typing import Any

from trading.domain.messages import BacktestResultsResponse


def calculate_sharpe_ratio(
    return_percentage: float,
    duration_seconds: float,
    balance_history: list[tuple[int, Decimal]] | None = None,
) -> float:
    """Calculate Sharpe Ratio for backtest results

    Args:
        return_percentage: Total return percentage
        duration_seconds: Duration of backtest in seconds
        balance_history: Optional list of (timestamp, balance) tuples for more accurate calculation

    Returns:
        Sharpe Ratio (annualized). Returns 0.0 if calculation not possible.

    Note:
        If balance_history is provided, uses periodic returns for calculation.
        Otherwise, uses simplified calculation based on total return and duration.
    """
    if duration_seconds <= 0:
        return 0.0

    # Convert duration to days
    duration_days = duration_seconds / (24 * 60 * 60)

    if balance_history and len(balance_history) > 1:
        # Calculate from periodic returns
        returns = []
        for i in range(1, len(balance_history)):
            prev_balance = float(balance_history[i - 1][1])
            curr_balance = float(balance_history[i][1])
            if prev_balance > 0:
                period_return = (curr_balance - prev_balance) / prev_balance
                returns.append(period_return)

        if len(returns) < 2:
            # Not enough data points, use simplified
            return _calculate_simplified_sharpe(return_percentage, duration_days)

        # Calculate mean and std deviation of returns
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance) if variance > 0 else 0.0

        if std_dev == 0:
            return 0.0

        # Annualize
        # Assuming daily returns (approximation)
        periods_per_year = 252  # Trading days per year
        if duration_days > 0:
            actual_periods = len(returns)
            periods_per_test = actual_periods / duration_days if duration_days > 0 else 1
            annualized_mean = mean_return * periods_per_year / periods_per_test
            annualized_std = std_dev * math.sqrt(periods_per_year / periods_per_test)
        else:
            annualized_mean = mean_return * periods_per_year
            annualized_std = std_dev * math.sqrt(periods_per_year)

        # Sharpe Ratio = (Return - Risk Free Rate) / StdDev
        # Using 0% risk-free rate for simplicity
        sharpe = annualized_mean / annualized_std if annualized_std > 0 else 0.0
        return round(sharpe, 2)

    else:
        # Simplified calculation
        return _calculate_simplified_sharpe(return_percentage, duration_days)


def _calculate_simplified_sharpe(return_percentage: float, duration_days: float) -> float:
    """Calculate simplified Sharpe Ratio when balance history is not available

    Args:
        return_percentage: Total return percentage
        duration_days: Duration in days

    Returns:
        Simplified Sharpe Ratio estimate
    """
    if duration_days <= 0:
        return 0.0

    # Annualize return
    if duration_days >= 365:
        annualized_return = return_percentage
    else:
        annualized_return = return_percentage * (365 / duration_days)

    # Estimate volatility as a fraction of return (conservative estimate)
    # This is a simplification - in practice volatility should come from actual data
    if return_percentage == 0:
        return 0.0

    # Assume volatility is proportional to return magnitude
    # For positive returns, use lower volatility estimate
    # For negative returns, use higher volatility estimate
    if return_percentage > 0:
        # Conservative: volatility ≈ 20-30% of return
        estimated_volatility = abs(annualized_return) * 0.25
    else:
        # More volatile for losses
        estimated_volatility = abs(annualized_return) * 0.4

    # Minimum volatility threshold to avoid division by very small numbers
    if estimated_volatility < 1.0:
        estimated_volatility = 1.0

    # Sharpe Ratio (with 0% risk-free rate)
    sharpe = annualized_return / estimated_volatility
    return round(sharpe, 2)


def calculate_calmar_ratio(return_percentage: float, max_drawdown: float) -> float:
    """Calculate Calmar Ratio (Return / Max Drawdown)

    Args:
        return_percentage: Annualized return percentage
        max_drawdown: Maximum drawdown percentage

    Returns:
        Calmar Ratio. Returns 0.0 if max_drawdown is 0.
    """
    if max_drawdown == 0:
        return 0.0

    calmar = abs(return_percentage) / abs(max_drawdown)
    return round(calmar, 2)


def extract_metrics_from_results(
    results: BacktestResultsResponse, calculate_advanced: bool = True
) -> dict[str, float]:
    """Extract all metrics from BacktestResultsResponse

    Args:
        results: Backtest results response
        calculate_advanced: Whether to calculate advanced metrics (Sharpe Ratio, etc.)

    Returns:
        Dictionary of metric names to values
    """
    metrics: dict[str, float] = {
        "return_percentage": results.return_percentage,
        "max_drawdown": results.max_drawdown,
        "profit_factor": results.profit_factor,
        "win_rate": results.win_rate,
        "total_trades": float(results.total_trades),
        "cycle_win_rate": results.cycle_win_rate,
    }

    if calculate_advanced:
        # Calculate Sharpe Ratio (simplified, without balance_history)
        sharpe = calculate_sharpe_ratio(
            return_percentage=results.return_percentage,
            duration_seconds=results.duration_seconds,
            balance_history=None,  # Not available in BacktestResultsResponse
        )
        metrics["sharpe_ratio"] = sharpe

        # Calculate Calmar Ratio
        calmar = calculate_calmar_ratio(
            return_percentage=results.return_percentage,
            max_drawdown=results.max_drawdown,
        )
        metrics["calmar_ratio"] = calmar

    return metrics



