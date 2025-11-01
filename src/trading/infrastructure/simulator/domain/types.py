"""Types for market data simulator"""
from typing import Literal

# TypeAlias is available in Python 3.10+, fallback for 3.9
try:
    from typing import TypeAlias
except ImportError:
    TypeAlias = None

if TypeAlias:
    TIMEFRAME_TYPE: TypeAlias = Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "1d", "1w", "1M"]
else:
    TIMEFRAME_TYPE = Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "1d", "1w", "1M"]

