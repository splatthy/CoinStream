from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class ConnectionStatus(Enum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    TESTING = "testing"
    ERROR = "error"


@dataclass
class ExchangeConfig:
    """
    Minimal exchange configuration model used by ConfigService and tests.
    """

    name: str
    api_key_encrypted: str
    api_secret_encrypted: Optional[str] = None
    is_active: bool = True
    last_sync: Optional[datetime] = None
    connection_status: ConnectionStatus = ConnectionStatus.UNKNOWN
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_connected(self) -> bool:
        return self.connection_status == ConnectionStatus.CONNECTED

    def update_connection_status(self, status: ConnectionStatus) -> None:
        self.connection_status = status
        self.updated_at = datetime.now()

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = datetime.now()

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = datetime.now()

    def needs_sync(self, max_age_hours: int = 24) -> bool:
        if not self.last_sync:
            return True
        return datetime.now() - self.last_sync > timedelta(hours=max_age_hours)

    def get_display_name(self) -> str:
        status_icon = {
            ConnectionStatus.CONNECTED: "🟢",
            ConnectionStatus.TESTING: "🟡",
            ConnectionStatus.ERROR: "🔴",
            ConnectionStatus.UNKNOWN: "⚪",
        }.get(self.connection_status, "⚪")
        return f"{status_icon} {self.name.title()}"

