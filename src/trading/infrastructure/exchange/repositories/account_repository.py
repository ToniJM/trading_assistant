"""Account repository for exchange simulator"""
from decimal import Decimal

from trading.domain.entities import Position
from trading.domain.types import SIDE_TYPE


class AccountRepository:
    """Repository for account state (balance, positions, leverage)"""

    def __init__(self):
        self.balance: Decimal = Decimal(0)
        self.positions:[str[SIDE_TYPE, Position]] = {}
        self.leverages:[str, Decimal] = {}

    def set_balance(self, balance: Decimal):
        """Set account balance"""
        self.balance = balance

    def update_balance(self, amount: Decimal):
        """Update account balance"""
        self.balance += amount

    def get_balance(self) -> Decimal:
        """Get current account balance"""
        return self.balance

    def set_position(self, position: Position):
        """Set position for symbol and side"""
        symbol = position.symbol.lower()
        if symbol not in self.positions:
            self.positions[symbol] = {}
        self.positions[symbol][position.side] = position

    def get_position(self, symbol: str, side: SIDE_TYPE) -> Position:
        """Get position for symbol and side"""
        symbol = symbol.lower()
        if symbol not in self.positions:
            self.positions[symbol] = {}
        if side not in self.positions[symbol]:
            self.positions[symbol][side] = Position(
                symbol=symbol,
                side=side,
                amount=Decimal(0),
                entry_price=Decimal(0),
                break_even=Decimal(0),
            )
        return self.positions[symbol][side]

    def set_leverage(self, symbol: str, leverage: Decimal):
        """Set leverage for symbol"""
        self.leverages[symbol.lower()] = leverage

    def get_leverage(self, symbol: str) -> Decimal:
        """Get leverage for symbol"""
        symbol = symbol.lower()
        if symbol not in self.leverages:
            raise ValueError(f"No leverage set for {symbol}")
        return self.leverages[symbol]

