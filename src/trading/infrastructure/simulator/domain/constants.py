"""Constants for market data simulator"""


from .types import TIMEFRAME_TYPE

TIMEFRAME_MINUTES:[TIMEFRAME_TYPE, int] = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "8h": 480,
    "1d": 1440,
    "1w": 10080,
    "1M": 43200,
}

ONE_MINUTE = 60000  # milliseconds

