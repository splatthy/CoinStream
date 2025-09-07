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

    def _parse_futures(self, value: str):
        """Parse Bitunix futures field like 'ETHUSDT Long·CROSS' into (symbol, side, margin_mode)."""
        if value is None:
            raise ValidationError("Futures field is required")
        s = str(value).strip()
        parts = s.split(" ", 1)
        symbol = parts[0].strip().upper() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""
        side = None
        margin = None
        if rest:
            if "·" in rest:
                side_str, margin_str = rest.split("·", 1)
                side = side_str.strip()
                margin = margin_str.strip().upper()
            else:
                side = rest.strip()
        if not side:
            rl = s.lower()
            if "long" in rl:
                side = "Long"
            elif "short" in rl:
                side = "Short"
        if not symbol or not side:
            raise ValidationError(f"Unparseable futures field: {value}")
        side_enum = self.normalize_trade_side(side)
        return symbol, side_enum, margin

    def _parse_closed_amount(self, value: Optional[str]) -> (Decimal, Optional[str]):
        """Parse '351 TIA' into (Decimal('351'), 'TIA')."""
        if value is None or str(value).strip() == "":
            raise ValidationError("Missing closed amount")
        text = str(value).strip()
        import re
        m = re.match(r"\s*([-+]?\d*\.?\d+)\s*([A-Za-z0-9_-]+)?", text)
        if not m:
            raise ValidationError(f"Invalid closed amount: {value}")
        qty = Decimal(m.group(1))
        asset = m.group(2) if m.lastindex and m.group(2) else None
        return qty, asset

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
        # Required logical fields (support composite Bitunix fields)
        if mapping.symbol == mapping.side and mapping.symbol in row:
            symbol, side, margin_mode = self._parse_futures(row.get(mapping.symbol))
        else:
            symbol = str(row.get(mapping.symbol)).strip().upper()
            side = self.normalize_trade_side(row.get(mapping.side))

        # Quantity may be composite (e.g., '351 TIA')
        qval = row.get(mapping.quantity)
        try:
            quantity = self.parse_decimal(qval, "quantity", required=True)
        except ValidationError:
            quantity, asset = self._parse_closed_amount(qval)
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

        # Custom fields. Fee normalization policy:
        # Always persist a single total fee field: custom_fields['fees'] (stringified Decimal).
        # For exchanges with multiple fee components (e.g., Bitunix funding/position), we sum them.
        # Future exchange importers should adhere to this: compute total, store only 'fees'.
        custom_fields: Dict[str, str] = {}

        # 1) Start with explicit 'Fees' column if template provides it
        fees_total = Decimal("0")
        if mapping.fees and mapping.fees in row:
            fees_val = row.get(mapping.fees)
            if fees_val is not None and str(fees_val).strip() != "":
                try:
                    fees_total += Decimal(str(fees_val))
                except Exception:
                    # Ignore non-numeric fee values
                    pass

        # 2) Add Bitunix new-format components if present
        funding_fees = row.get("funding fees") if "funding fees" in row else row.get("Funding Fees")
        position_fee = row.get("position fee") if "position fee" in row else row.get("Position Fee")
        try:
            if funding_fees not in (None, ""):
                fees_total += Decimal(str(funding_fees))
        except Exception:
            pass
        try:
            if position_fee not in (None, ""):
                fees_total += Decimal(str(position_fee))
        except Exception:
            pass

        if fees_total != Decimal("0"):
            custom_fields["fees"] = str(fees_total)

        # Attach margin mode from futures if available
        if mapping.symbol == mapping.side and mapping.symbol in row:
            try:
                _, _, margin_mode = self._parse_futures(row.get(mapping.symbol))
                if margin_mode:
                    custom_fields["margin_mode"] = margin_mode
            except Exception:
                pass

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
