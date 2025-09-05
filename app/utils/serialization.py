"""
Data serialization and deserialization utilities for JSON persistence.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Union, Type
from enum import Enum

from app.models.trade import Trade, TradeSide, TradeStatus, WinLoss
from app.models.position import Position, PositionSide, PositionStatus
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.models.custom_fields import CustomFieldConfig, FieldType


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for application data types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        elif hasattr(obj, "__dict__"):
            # Handle dataclass objects
            return obj.__dict__
        return super().default(obj)


class DataSerializer:
    """Utility class for serializing and deserializing application data."""

    @staticmethod
    def serialize_trade(trade: Trade) -> Dict[str, Any]:
        """Serialize a Trade object to dictionary."""
        return {
            "id": trade.id,
            "exchange": trade.exchange,
            "symbol": trade.symbol,
            "side": trade.side.value,
            "entry_price": str(trade.entry_price),
            "quantity": str(trade.quantity),
            "entry_time": trade.entry_time.isoformat(),
            "status": trade.status.value,
            "confluences": trade.confluences.copy(),
            "exit_price": str(trade.exit_price) if trade.exit_price else None,
            "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
            "pnl": str(trade.pnl) if trade.pnl else None,
            "win_loss": trade.win_loss.value if trade.win_loss else None,
            "custom_fields": trade.custom_fields.copy(),
            "created_at": trade.created_at.isoformat(),
            "updated_at": trade.updated_at.isoformat(),
        }

    @staticmethod
    def deserialize_trade(data: Dict[str, Any]) -> Trade:
        """Deserialize dictionary to Trade object."""
        return Trade(
            id=data["id"],
            exchange=data["exchange"],
            symbol=data["symbol"],
            side=TradeSide(data["side"]),
            entry_price=Decimal(data["entry_price"]),
            quantity=Decimal(data["quantity"]),
            entry_time=datetime.fromisoformat(data["entry_time"]),
            status=TradeStatus(data["status"]),
            confluences=data.get("confluences", []),
            exit_price=Decimal(data["exit_price"]) if data.get("exit_price") else None,
            exit_time=datetime.fromisoformat(data["exit_time"])
            if data.get("exit_time")
            else None,
            pnl=Decimal(data["pnl"]) if data.get("pnl") else None,
            win_loss=WinLoss(data["win_loss"]) if data.get("win_loss") else None,
            custom_fields=data.get("custom_fields", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
        )

    @staticmethod
    def serialize_position(position: Position) -> Dict[str, Any]:
        """Serialize a Position object to dictionary."""
        return {
            "position_id": position.position_id,
            "symbol": position.symbol,
            "side": position.side.value,
            "size": str(position.size),
            "entry_price": str(position.entry_price),
            "mark_price": str(position.mark_price),
            "unrealized_pnl": str(position.unrealized_pnl),
            "realized_pnl": str(position.realized_pnl),
            "status": position.status.value,
            "open_time": position.open_time.isoformat(),
            "close_time": position.close_time.isoformat()
            if position.close_time
            else None,
            "raw_data": position.raw_data.copy(),
            "created_at": position.created_at.isoformat(),
            "updated_at": position.updated_at.isoformat(),
        }

    @staticmethod
    def deserialize_position(data: Dict[str, Any]) -> Position:
        """Deserialize dictionary to Position object."""
        return Position(
            position_id=data["position_id"],
            symbol=data["symbol"],
            side=PositionSide(data["side"]),
            size=Decimal(data["size"]),
            entry_price=Decimal(data["entry_price"]),
            mark_price=Decimal(data["mark_price"]),
            unrealized_pnl=Decimal(data["unrealized_pnl"]),
            realized_pnl=Decimal(data["realized_pnl"]),
            status=PositionStatus(data["status"]),
            open_time=datetime.fromisoformat(data["open_time"]),
            close_time=datetime.fromisoformat(data["close_time"])
            if data.get("close_time")
            else None,
            raw_data=data.get("raw_data", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    @staticmethod
    def serialize_exchange_config(config: ExchangeConfig) -> Dict[str, Any]:
        """Serialize an ExchangeConfig object to dictionary."""
        return {
            "name": config.name,
            "api_key_encrypted": config.api_key_encrypted,
            "is_active": config.is_active,
            "last_sync": config.last_sync.isoformat() if config.last_sync else None,
            "connection_status": config.connection_status.value,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
        }

    @staticmethod
    def deserialize_exchange_config(data: Dict[str, Any]) -> ExchangeConfig:
        """Deserialize dictionary to ExchangeConfig object."""
        return ExchangeConfig(
            name=data["name"],
            api_key_encrypted=data["api_key_encrypted"],
            is_active=data.get("is_active", True),
            last_sync=datetime.fromisoformat(data["last_sync"])
            if data.get("last_sync")
            else None,
            connection_status=ConnectionStatus(
                data.get("connection_status", "unknown")
            ),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    @staticmethod
    def serialize_custom_field_config(config: CustomFieldConfig) -> Dict[str, Any]:
        """Serialize a CustomFieldConfig object to dictionary."""
        return {
            "field_name": config.field_name,
            "field_type": config.field_type.value,
            "options": config.options.copy(),
            "is_required": config.is_required,
            "default_value": config.default_value,
            "description": config.description,
            "validation_rules": config.validation_rules.copy(),
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
        }

    @staticmethod
    def deserialize_custom_field_config(data: Dict[str, Any]) -> CustomFieldConfig:
        """Deserialize dictionary to CustomFieldConfig object."""
        return CustomFieldConfig(
            field_name=data["field_name"],
            field_type=FieldType(data["field_type"]),
            options=data.get("options", []),
            is_required=data.get("is_required", False),
            default_value=data.get("default_value"),
            description=data.get("description"),
            validation_rules=data.get("validation_rules", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    @staticmethod
    def serialize_trades_list(trades: List[Trade]) -> List[Dict[str, Any]]:
        """Serialize a list of Trade objects."""
        return [DataSerializer.serialize_trade(trade) for trade in trades]

    @staticmethod
    def deserialize_trades_list(data: List[Dict[str, Any]]) -> List[Trade]:
        """Deserialize a list of dictionaries to Trade objects."""
        return [DataSerializer.deserialize_trade(trade_data) for trade_data in data]

    @staticmethod
    def serialize_positions_list(positions: List[Position]) -> List[Dict[str, Any]]:
        """Serialize a list of Position objects."""
        return [DataSerializer.serialize_position(position) for position in positions]

    @staticmethod
    def deserialize_positions_list(data: List[Dict[str, Any]]) -> List[Position]:
        """Deserialize a list of dictionaries to Position objects."""
        return [
            DataSerializer.deserialize_position(position_data) for position_data in data
        ]

    @staticmethod
    def serialize_exchange_configs_list(
        configs: List[ExchangeConfig],
    ) -> List[Dict[str, Any]]:
        """Serialize a list of ExchangeConfig objects."""
        return [DataSerializer.serialize_exchange_config(config) for config in configs]

    @staticmethod
    def deserialize_exchange_configs_list(
        data: List[Dict[str, Any]],
    ) -> List[ExchangeConfig]:
        """Deserialize a list of dictionaries to ExchangeConfig objects."""
        return [
            DataSerializer.deserialize_exchange_config(config_data)
            for config_data in data
        ]

    @staticmethod
    def serialize_custom_field_configs_list(
        configs: List[CustomFieldConfig],
    ) -> List[Dict[str, Any]]:
        """Serialize a list of CustomFieldConfig objects."""
        return [
            DataSerializer.serialize_custom_field_config(config) for config in configs
        ]

    @staticmethod
    def deserialize_custom_field_configs_list(
        data: List[Dict[str, Any]],
    ) -> List[CustomFieldConfig]:
        """Deserialize a list of dictionaries to CustomFieldConfig objects."""
        return [
            DataSerializer.deserialize_custom_field_config(config_data)
            for config_data in data
        ]

    @staticmethod
    def to_json(obj: Any, indent: int = 2) -> str:
        """Convert object to JSON string using custom encoder."""
        return json.dumps(obj, cls=JSONEncoder, indent=indent, ensure_ascii=False)

    @staticmethod
    def from_json(json_str: str) -> Any:
        """Parse JSON string to Python object."""
        return json.loads(json_str)
