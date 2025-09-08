from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from app.utils.validators import ValidationError


@dataclass
class Fill:
    exchange: str
    symbol: str
    time: Any  # datetime
    action: str  # "open" | "close"
    side: str  # "long" | "short"
    price: Decimal
    quantity: Decimal
    fee: Decimal
    pnl: Optional[Decimal] = None
    margin_mode: Optional[str] = None
    leverage: Optional[str] = None
    reduce_only: Optional[bool] = None
    status: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        d = {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "time": self.time,
            "action": self.action,
            "side": self.side,
            "price": self.price,
            "quantity": self.quantity,
            "fee": self.fee,
            "status": self.status,
        }
        if self.pnl is not None:
            d["pnl"] = self.pnl
        if self.margin_mode is not None:
            d["margin_mode"] = self.margin_mode
        if self.leverage is not None:
            d["leverage"] = self.leverage
        if self.reduce_only is not None:
            d["reduce_only"] = self.reduce_only
        return d


def _to_decimal(value: Any, required: bool = True) -> Optional[Decimal]:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if required:
            raise ValidationError("Missing required numeric value")
        return None
    s = str(value).strip()
    # Remove thousands separators if present
    s = s.replace(",", "")
    # Extract leading signed number
    import re

    m = re.match(r"\s*([-+]?\d+(?:\.\d+)?)", s)
    if not m:
        if required:
            raise ValidationError(f"Invalid decimal: {value}")
        return None
    try:
        return Decimal(m.group(1))
    except (InvalidOperation, ValueError):
        if required:
            raise ValidationError(f"Invalid decimal: {value}")
        return None


def _parse_time(val: Any) -> Any:
    if val is None or (isinstance(val, str) and val.strip() == ""):
        raise ValidationError("Missing required timestamp")
    ts = pd.to_datetime(val, errors="coerce", utc=True, infer_datetime_format=True)
    if pd.isna(ts):
        # Try common formats explicitly
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
                ts2 = pd.to_datetime(val, format=fmt, errors="coerce", utc=True)
                if not pd.isna(ts2):
                    ts = ts2
                    break
            except Exception:
                continue
    if pd.isna(ts):
        raise ValidationError(f"Unparseable timestamp: {val}")
    dt = ts.to_pydatetime()
    if getattr(dt, "tzinfo", None) is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _norm_str(x: Any) -> str:
    return str(x).strip()


def _lower_headers(df: pd.DataFrame) -> Dict[str, str]:
    return {str(c).strip().lower(): c for c in df.columns}


def _bitunix_action_side(text: str) -> (str, str):
    """Derive (action, position_side) from Bitunix side text.

    Bitunix exports label the order direction on close fills (e.g., "Close Short"
    when closing a long). For reconstruction we need the position direction.

    Rules:
    - action: 'open' if text contains 'open', else 'close' if contains 'close'.
    - token_side: 'long' if the string contains 'long', 'short' if contains 'short'.
    - position_side: if action == 'open' then token_side; if action == 'close'
      then invert (close short -> long position, close long -> short position).
    """
    s = str(text).strip().lower()
    action = "open" if "open" in s else ("close" if "close" in s else "")
    token_side = "long" if "long" in s else ("short" if "short" in s else "")
    if not action or not token_side:
        raise ValidationError(f"Unrecognized Bitunix side value: {text}")
    if action == "close":
        side = "long" if token_side == "short" else "short"
    else:
        side = token_side
    return action, side


def _blofin_action_side(side_text: str, reduce_only_val: Any) -> (str, str, Optional[bool]):
    s = str(side_text).strip().lower()
    # Normalize e.g., "close long(sl)"
    if s.startswith("open"):
        action = "open"
    elif s.startswith("close"):
        action = "close"
    else:
        action = "open" if "open" in s else ("close" if "close" in s else "")
    side = "long" if "long" in s else ("short" if "short" in s else "")
    if not action or not side:
        raise ValidationError(f"Unrecognized Blofin side value: {side_text}")

    ro: Optional[bool] = None
    if reduce_only_val is not None:
        rv = str(reduce_only_val).strip().lower()
        if rv in ("y", "yes", "true", "1"):
            ro = True
            action = "close"
        elif rv in ("n", "no", "false", "0", ""):
            ro = False
    return action, side, ro


def normalize(df: pd.DataFrame, exchange: str) -> List[Dict[str, Any]]:
    """Normalize raw CSV rows into fills dicts.

    Returns list of dicts with Decimal numeric fields and UTC-naive datetimes.
    Filters to Filled/FILLED and quantity > 0.
    """
    exch = str(exchange).strip().lower()
    headers = _lower_headers(df)
    fills: List[Fill] = []

    if exch == "bitunix":
        # Required columns
        req = ["date", "side", "futures", "average price", "executed", "status"]
        for r in req:
            if r not in headers:
                raise ValidationError(f"Missing required Bitunix column: {r}")

        for _, row in df.iterrows():
            status_raw = row.get(headers["status"]) if "status" in headers else None
            if status_raw is None:
                continue
            if str(status_raw).strip().lower() != "filled":
                continue

            qty = _to_decimal(row.get(headers["executed"]))
            if qty is None or qty <= Decimal("0"):
                continue

            action, side = _bitunix_action_side(row.get(headers["side"]))
            symbol = _norm_str(row.get(headers["futures"])) .upper()
            price = _to_decimal(row.get(headers["average price"]))
            time = _parse_time(row.get(headers["date"]))

            fee = Decimal("0")
            if "fee" in headers:
                try:
                    fv = _to_decimal(row.get(headers["fee"]), required=False)
                    if fv is not None:
                        fee += fv
                except ValidationError:
                    pass
            pnl = None
            if "realized p/l" in headers:
                try:
                    pnl = _to_decimal(row.get(headers["realized p/l"]), required=False)
                except ValidationError:
                    pnl = None

            f = Fill(
                exchange="Bitunix",
                symbol=symbol,
                time=time,
                action=action,
                side=side,
                price=price,
                quantity=qty,
                fee=fee,
                pnl=pnl,
                status=str(status_raw).strip(),
            )
            fills.append(f)

    elif exch == "blofin":
        req = [
            "underlying asset",
            "order time",
            "side",
            "avg fill",
            "filled",
            "status",
        ]
        for r in req:
            if r not in headers:
                raise ValidationError(f"Missing required Blofin column: {r}")

        for _, row in df.iterrows():
            status_raw = row.get(headers["status"]) if "status" in headers else None
            if status_raw is None:
                continue
            if str(status_raw).strip().lower() != "filled":
                continue

            qty = _to_decimal(row.get(headers["filled"]))
            if qty is None or qty <= Decimal("0"):
                continue

            reduce_only_val = row.get(headers["reduce-only"]) if "reduce-only" in headers else None
            action, side, ro = _blofin_action_side(row.get(headers["side"]), reduce_only_val)

            symbol = _norm_str(row.get(headers["underlying asset"])) .upper()
            price = _to_decimal(row.get(headers["avg fill"]))
            time = _parse_time(row.get(headers["order time"]))

            fee = Decimal("0")
            if "fee" in headers:
                try:
                    fv = _to_decimal(row.get(headers["fee"]), required=False)
                    if fv is not None:
                        fee += fv
                except ValidationError:
                    pass

            pnl = None
            if "pnl" in headers:
                try:
                    pnl = _to_decimal(row.get(headers["pnl"]), required=False)
                except ValidationError:
                    pnl = None

            margin_mode = row.get(headers["margin mode"]) if "margin mode" in headers else None
            leverage = row.get(headers["leverage"]) if "leverage" in headers else None

            f = Fill(
                exchange="Blofin",
                symbol=symbol,
                time=time,
                action=action,
                side=side,
                price=price,
                quantity=qty,
                fee=fee,
                pnl=pnl,
                margin_mode=str(margin_mode).strip() if margin_mode not in (None, "") else None,
                leverage=str(leverage).strip() if leverage not in (None, "") else None,
                reduce_only=ro,
                status=str(status_raw).strip(),
            )
            fills.append(f)

    else:
        raise ValidationError(f"Unsupported exchange for tx-history normalizer: {exchange}")

    return [f.as_dict() for f in fills]
