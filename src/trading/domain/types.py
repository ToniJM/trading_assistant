"""Domain type definitions"""
from typing import Literal

# TypeAlias is available in Python 3.10+, fallback to direct assignment for 3.9
try:
    from typing import TypeAlias
except ImportError:
    # Fallback for Python < 3.10
    TypeAlias = None

if TypeAlias:
    SIDE_TYPE: TypeAlias = Literal["long", "short"]
    ORDER_SIDE_TYPE: TypeAlias = Literal["buy", "sell"]
    ORDER_TYPE_TYPE: TypeAlias = Literal["market", "limit"]
    ORDER_STATUS_TYPE: TypeAlias = Literal["new", "filled"]
else:
    # For Python < 3.10
    SIDE_TYPE = Literal["long", "short"]
    ORDER_SIDE_TYPE = Literal["buy", "sell"]
    ORDER_TYPE_TYPE = Literal["market", "limit"]
    ORDER_STATUS_TYPE = Literal["new", "filled"]

