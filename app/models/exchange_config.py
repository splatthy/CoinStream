from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ConnectionStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TESTING = "testing"
    UNKNOWN = "unknown"


@dataclass
class ExchangeConfig:
    """
    Exchange configuration model with validation for API credentials and settings.
    """

    name: str
    api_key_encrypted: str
    api_secret_encrypted: Optional[str] = None
    is_active: bool = True
    last_sync: Optional[datetime] = None
    connection_status: ConnectionStatus = ConnectionStatus.UNKNOWN
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate exchange configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """Validate exchange configuration data."""
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Exchange name must be a non-empty string")

        if not self.api_key_encrypted or not isinstance(self.api_key_encrypted, str):
            raise ValueError("Encrypted API key must be a non-empty string")

        if self.api_secret_encrypted is not None and not isinstance(
            self.api_secret_encrypted, str
        ):
            raise ValueError("Encrypted API secret must be a string when provided")

        if not isinstance(self.is_active, bool):
            raise ValueError("is_active must be a boolean")

        if self.last_sync is not None and not isinstance(self.last_sync, datetime):
            raise ValueError("Last sync must be a datetime object when provided")

        if not isinstance(self.connection_status, ConnectionStatus):
            raise ValueError(
                f"Connection status must be a ConnectionStatus enum, got {type(self.connection_status)}"
            )

    def update_connection_status(self, status: ConnectionStatus) -> None:
        """Update connection status and timestamp."""
        if not isinstance(status, ConnectionStatus):
            raise ValueError(
                f"Status must be a ConnectionStatus enum, got {type(status)}"
            )

        self.connection_status = status
        self.updated_at = datetime.now()

    def update_last_sync(self, sync_time: Optional[datetime] = None) -> None:
        """Update last sync timestamp."""
        if sync_time is None:
            sync_time = datetime.now()

        if not isinstance(sync_time, datetime):
            raise ValueError("Sync time must be a datetime object")

        self.last_sync = sync_time
        self.updated_at = datetime.now()

    def activate(self) -> None:
        """Activate the exchange configuration."""
        self.is_active = True
        self.updated_at = datetime.now()

    def deactivate(self) -> None:
        """Deactivate the exchange configuration."""
        self.is_active = False
        self.updated_at = datetime.now()

    def is_connected(self) -> bool:
        """Check if exchange is currently connected."""
        return self.connection_status == ConnectionStatus.CONNECTED

    def needs_sync(self, max_age_hours: int = 24) -> bool:
        """Check if exchange data needs synchronization."""
        if self.last_sync is None:
            return True

        age = datetime.now() - self.last_sync
        return age.total_seconds() > (max_age_hours * 3600)

    def get_display_name(self) -> str:
        """Get formatted display name for UI."""
        status_indicator = "🟢" if self.is_connected() else "🔴"
        active_indicator = "" if self.is_active else " (Inactive)"
        return f"{status_indicator} {self.name.title()}{active_indicator}"
