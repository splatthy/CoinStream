from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum


class PositionStatus(Enum):
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """
    Position data model representing exchange position data with validation.
    """
    position_id: str
    symbol: str
    side: PositionSide
    size: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    status: PositionStatus
    open_time: datetime
    close_time: Optional[datetime] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate position data after initialization."""
        self.validate()

    def validate(self) -> None:
        """Validate position data integrity."""
        if not self.position_id or not isinstance(self.position_id, str):
            raise ValueError("Position ID must be a non-empty string")
        
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("Symbol must be a non-empty string")
        
        if not isinstance(self.side, PositionSide):
            raise ValueError(f"Side must be a PositionSide enum, got {type(self.side)}")
        
        if not isinstance(self.size, Decimal) or self.size <= 0:
            raise ValueError("Size must be a positive Decimal")
        
        if not isinstance(self.entry_price, Decimal) or self.entry_price <= 0:
            raise ValueError("Entry price must be a positive Decimal")
        
        if not isinstance(self.mark_price, Decimal) or self.mark_price <= 0:
            raise ValueError("Mark price must be a positive Decimal")
        
        if not isinstance(self.unrealized_pnl, Decimal):
            raise ValueError("Unrealized PnL must be a Decimal")
        
        if not isinstance(self.realized_pnl, Decimal):
            raise ValueError("Realized PnL must be a Decimal")
        
        if not isinstance(self.status, PositionStatus):
            raise ValueError(f"Status must be a PositionStatus enum, got {type(self.status)}")
        
        if not isinstance(self.open_time, datetime):
            raise ValueError("Open time must be a datetime object")
        
        if self.close_time is not None:
            if not isinstance(self.close_time, datetime):
                raise ValueError("Close time must be a datetime object when provided")
            if self.close_time < self.open_time:
                raise ValueError("Close time cannot be before open time")
        
        if not isinstance(self.raw_data, dict):
            raise ValueError("Raw data must be a dictionary")
        
        # Validate closed position requirements
        if self.status == PositionStatus.CLOSED:
            if self.close_time is None:
                raise ValueError("Closed positions must have a close time")

    def get_total_pnl(self) -> Decimal:
        """Get total PnL (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl

    def is_profitable(self) -> bool:
        """Check if position is profitable based on total PnL."""
        return self.get_total_pnl() > 0

    def update_mark_price(self, new_mark_price: Decimal) -> None:
        """Update mark price and recalculate unrealized PnL."""
        if not isinstance(new_mark_price, Decimal) or new_mark_price <= 0:
            raise ValueError("Mark price must be a positive Decimal")
        
        self.mark_price = new_mark_price
        self.unrealized_pnl = self.calculate_unrealized_pnl()
        self.updated_at = datetime.now()

    def calculate_unrealized_pnl(self) -> Decimal:
        """Calculate unrealized PnL based on current mark price."""
        if self.side == PositionSide.LONG:
            return (self.mark_price - self.entry_price) * self.size
        else:  # SHORT
            return (self.entry_price - self.mark_price) * self.size

    def update_from_raw_data(self, raw_data: Dict[str, Any]) -> None:
        """Update position from raw exchange data."""
        self.raw_data.update(raw_data)
        self.updated_at = datetime.now()

    def get_raw_field(self, field_name: str, default: Any = None) -> Any:
        """Get a field from raw exchange data."""
        return self.raw_data.get(field_name, default)

    def is_open(self) -> bool:
        """Check if position is currently open."""
        return self.status == PositionStatus.OPEN

    def is_closed(self) -> bool:
        """Check if position is fully closed."""
        return self.status == PositionStatus.CLOSED

    def is_partially_closed(self) -> bool:
        """Check if position is partially closed."""
        return self.status == PositionStatus.PARTIALLY_CLOSED