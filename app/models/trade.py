from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum


class TradeStatus(Enum):
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"


class TradeSide(Enum):
    LONG = "long"
    SHORT = "short"


class WinLoss(Enum):
    WIN = "win"
    LOSS = "loss"


@dataclass
class Trade:
    """
    Trade data model representing a trading position with validation.
    """
    id: str
    exchange: str
    symbol: str
    side: TradeSide
    entry_price: Decimal
    quantity: Decimal
    entry_time: datetime
    status: TradeStatus
    confluences: List[str] = field(default_factory=list)
    exit_price: Optional[Decimal] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[Decimal] = None
    win_loss: Optional[WinLoss] = None
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate trade data after initialization."""
        self.validate()

    def validate(self) -> None:
        """Validate trade data integrity."""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Trade ID must be a non-empty string")
        
        if not self.exchange or not isinstance(self.exchange, str):
            raise ValueError("Exchange must be a non-empty string")
        
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("Symbol must be a non-empty string")
        
        if not isinstance(self.side, TradeSide):
            raise ValueError(f"Side must be a TradeSide enum, got {type(self.side)}")
        
        if not isinstance(self.entry_price, Decimal) or self.entry_price <= 0:
            raise ValueError("Entry price must be a positive Decimal")
        
        if not isinstance(self.quantity, Decimal) or self.quantity <= 0:
            raise ValueError("Quantity must be a positive Decimal")
        
        if not isinstance(self.entry_time, datetime):
            raise ValueError("Entry time must be a datetime object")
        
        if not isinstance(self.status, TradeStatus):
            raise ValueError(f"Status must be a TradeStatus enum, got {type(self.status)}")
        
        if self.exit_price is not None:
            if not isinstance(self.exit_price, Decimal) or self.exit_price <= 0:
                raise ValueError("Exit price must be a positive Decimal when provided")
        
        if self.exit_time is not None:
            if not isinstance(self.exit_time, datetime):
                raise ValueError("Exit time must be a datetime object when provided")
            if self.exit_time < self.entry_time:
                raise ValueError("Exit time cannot be before entry time")
        
        if self.pnl is not None and not isinstance(self.pnl, Decimal):
            raise ValueError("PnL must be a Decimal when provided")
        
        if self.win_loss is not None and not isinstance(self.win_loss, WinLoss):
            raise ValueError(f"Win/Loss must be a WinLoss enum when provided, got {type(self.win_loss)}")
        
        if not isinstance(self.confluences, list):
            raise ValueError("Confluences must be a list")
        
        if not isinstance(self.custom_fields, dict):
            raise ValueError("Custom fields must be a dictionary")
        
        # Validate closed trade requirements
        if self.status == TradeStatus.CLOSED:
            if self.exit_price is None:
                raise ValueError("Closed trades must have an exit price")
            if self.exit_time is None:
                raise ValueError("Closed trades must have an exit time")
            if self.pnl is None:
                raise ValueError("Closed trades must have PnL calculated")

    def calculate_pnl(self, current_price: Optional[Decimal] = None) -> Decimal:
        """Calculate PnL for the trade."""
        if self.status == TradeStatus.CLOSED and self.exit_price is not None:
            exit_price = self.exit_price
        elif current_price is not None:
            exit_price = current_price
        else:
            raise ValueError("Cannot calculate PnL without exit price or current price")
        
        if self.side == TradeSide.LONG:
            return (exit_price - self.entry_price) * self.quantity
        else:  # SHORT
            return (self.entry_price - exit_price) * self.quantity

    def update_pnl(self, current_price: Optional[Decimal] = None) -> None:
        """Update the PnL field with calculated value."""
        self.pnl = self.calculate_pnl(current_price)
        self.updated_at = datetime.now()

    def is_profitable(self) -> Optional[bool]:
        """Check if trade is profitable. Returns None if PnL not available."""
        if self.pnl is None:
            return None
        return self.pnl > 0

    def add_confluence(self, confluence: str) -> None:
        """Add a confluence to the trade."""
        if confluence and confluence not in self.confluences:
            self.confluences.append(confluence)
            self.updated_at = datetime.now()

    def remove_confluence(self, confluence: str) -> None:
        """Remove a confluence from the trade."""
        if confluence in self.confluences:
            self.confluences.remove(confluence)
            self.updated_at = datetime.now()

    def set_custom_field(self, field_name: str, value: Any) -> None:
        """Set a custom field value."""
        self.custom_fields[field_name] = value
        self.updated_at = datetime.now()

    def get_custom_field(self, field_name: str, default: Any = None) -> Any:
        """Get a custom field value."""
        return self.custom_fields.get(field_name, default)