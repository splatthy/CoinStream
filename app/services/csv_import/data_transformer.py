from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from typing import Dict, Optional

import pandas as pd

from app.models.trade import Trade, TradeSide, TradeStatus
from app.services.csv_import.models import ColumnMapping
from app.utils.validators import ValidationError


class DataTransformer:
    """Transforms CSV rows into Trade model instances."""

    def normalize_trade_side(self, side_value: str) -> TradeSide:
        if side_value is None:
            raise ValidationError("Trade side is required")
        sval = str(side_value).strip().lower()
        if sval == "long":
            return TradeSide.LONG
        if sval == "short":
            return TradeSide.SHORT
        raise ValidationError(f"Unsupported trade side: {side_value}")

    def parse_decimal(self, value: Optional[str], name: str, required: bool = True) -> Optional[Decimal]:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if required:
                raise ValidationError(f"Missing required numeric '{name}'")
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValidationError(f"Invalid decimal for '{name}': {value}")

    def parse_timestamp(self, timestamp_str: Optional[str], required: bool = True) -> Optional[datetime]:
        """Parse timestamp and normalize to UTC timezone-naive datetime.

        - If input has tzinfo, convert to UTC and drop tz.
        - If input is naive, assume UTC and keep as-is.
        """
        if timestamp_str is None or (isinstance(timestamp_str, str) and timestamp_str.strip() == ""):
            if required:
                raise ValidationError("Missing required timestamp")
            return None

        # Use pandas for robust parsing
        ts = pd.to_datetime(timestamp_str, errors="coerce", utc=True, infer_datetime_format=True)
        if pd.isna(ts):
            # Retry with common explicit formats
            for fmt in (
                "%Y-%m-%d %H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y %H:%M",
                "%m/%d/%Y",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d",
            ):
                try:
                    ts2 = pd.to_datetime(timestamp_str, format=fmt, errors="coerce", utc=True)
                    if not pd.isna(ts2):
                        ts = ts2
                        break
                except Exception:
                    continue

        if pd.isna(ts):
            raise ValidationError(f"Unparseable timestamp: {timestamp_str}")

        # ts is pandas Timestamp with tz UTC; convert to naive UTC datetime
        dt = ts.to_pydatetime()
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    def calculate_missing_pnl(self, side: TradeSide, entry_price: Decimal, quantity: Decimal, exit_price: Optional[Decimal]) -> Optional[Decimal]:
        if exit_price is None:
            return None
        if side == TradeSide.LONG:
            return (exit_price - entry_price) * quantity
        else:
            return (entry_price - exit_price) * quantity

    def generate_trade_id(self, symbol: str, entry_time: datetime, quantity: Decimal, entry_price: Decimal) -> str:
        key = f"{symbol}|{entry_time.isoformat()}|{str(quantity)}|{str(entry_price)}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def transform_row(self, row: pd.Series, mapping: ColumnMapping, exchange: str) -> Trade:
        """Transform a single CSV row into a Trade object based on mapping and exchange name."""
        # Required logical fields
        symbol = str(row.get(mapping.symbol)).strip().upper()
        side = self.normalize_trade_side(row.get(mapping.side))
        quantity = self.parse_decimal(row.get(mapping.quantity), "quantity", required=True)
        entry_price = self.parse_decimal(row.get(mapping.entry_price), "entry_price", required=True)
        entry_time = self.parse_timestamp(row.get(mapping.entry_time), required=True)

        # Optional
        exit_price = self.parse_decimal(row.get(mapping.exit_price), "exit_price", required=False) if mapping.exit_price else None
        exit_time = self.parse_timestamp(row.get(mapping.exit_time), required=False) if mapping.exit_time else None

        pnl = None
        if mapping.pnl:
            pnl = self.parse_decimal(row.get(mapping.pnl), "pnl", required=False)
        if pnl is None:
            pnl = self.calculate_missing_pnl(side, entry_price, quantity, exit_price)

        # Determine status
        status = TradeStatus.CLOSED if (exit_price is not None and exit_time is not None and pnl is not None) else TradeStatus.OPEN

        # Deterministic ID
        trade_id = self.generate_trade_id(symbol, entry_time, quantity, entry_price)

        # Custom fields (fees as string to preserve JSON serialization compatibility)
        custom_fields: Dict[str, str] = {}
        if mapping.fees:
            fees_val = row.get(mapping.fees)
            if fees_val is not None and str(fees_val).strip() != "":
                custom_fields["fees"] = str(fees_val)

        # Build Trade
        trade = Trade(
            id=trade_id,
            exchange=str(exchange),
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=entry_time,
            status=status,
            exit_price=exit_price,
            exit_time=exit_time,
            pnl=pnl,
            confluences=[],
            custom_fields=custom_fields,
        )
        return trade

