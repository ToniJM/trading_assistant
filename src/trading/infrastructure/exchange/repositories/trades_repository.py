"""Trades repository for exchange simulator"""


from trading.domain.entities import Trade
from trading.domain.types import SIDE_TYPE


class TradesRepository:
    """Repository for storing and retrieving trades"""

    def __init__(self):
        self.trades:[str[SIDE_TYPE[Trade]]] = {}

    def add_trade(self, trade: Trade):
        """Add trade to repository"""
        symbol = trade.symbol.lower()
        if symbol not in self.trades:
            self.trades[symbol] = {}
        if trade.position_side not in self.trades[symbol]:
            self.trades[symbol][trade.position_side] = []
        self.trades[symbol][trade.position_side].append(trade)

    def get_symbol_trades(self, symbol: str) ->[SIDE_TYPE[Trade]]:
        """Get all trades for symbol grouped by position side"""
        return self.trades.get(symbol.lower(), {})

    def get_position_trades(self, symbol: str, position_side: SIDE_TYPE) ->[Trade]:
        """Get trades for symbol and position side"""
        symbol = symbol.lower()
        return self.trades.get(symbol, {}).get(position_side, [])

