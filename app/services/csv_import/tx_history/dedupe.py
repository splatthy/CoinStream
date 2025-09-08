from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Iterable, List, Optional, Tuple


# Rounding tolerances
ROUND_PRICE = Decimal("0.000001")   # 1e-6
ROUND_QTY = Decimal("0.00000001")   # 1e-8
ROUND_FEE = Decimal("0.00000001")   # 1e-8
ROUND_PNL = Decimal("0.00000001")   # 1e-8


def _q(v: Optional[Decimal], quantum: Decimal) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return v.quantize(quantum, rounding=ROUND_HALF_UP)
    except Exception:
        # In case non-Decimal slips through
        return Decimal(str(v)).quantize(quantum, rounding=ROUND_HALF_UP)


def _canon_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    return " ".join(str(s).strip().split())


def _canon_symbol(s: Optional[str]) -> str:
    return _canon_text(s).upper()


def _canon_action_side(action: Optional[str], side: Optional[str]) -> str:
    a = _canon_text(action).lower()
    sd = _canon_text(side).lower()
    if a and sd:
        return f"{a} {sd}".upper()  # e.g., OPEN LONG
    # Fallback if action missing
    return sd.upper()


def key_for_fill(fill: Dict) -> str:
    """Build a canonical dedupe key for a normalized fill.

    Key structure (exchange-specific fields mapped to normalized schema):
    - time (original date/order time)
    - symbol (futures/underlying)
    - side token capturing open/close semantics (OPEN LONG/CLOSE SHORT)
    - price (rounded 1e-6)
    - quantity (rounded 1e-8)
    - status (FILLED)
    - optional fee (rounded 1e-8) when nonzero
    """
    exch = _canon_text(fill.get("exchange"))
    symbol = _canon_symbol(fill.get("symbol"))
    action_side = _canon_action_side(fill.get("action"), fill.get("side"))

    t = fill.get("time")
    tkey = t.isoformat() if t is not None else ""

    price = _q(fill.get("price"), ROUND_PRICE)
    qty = _q(fill.get("quantity"), ROUND_QTY)
    status = _canon_text(fill.get("status")).upper()
    fee_val = fill.get("fee")
    fee = _q(fee_val, ROUND_FEE) if fee_val is not None else None

    base = [exch, symbol, tkey, action_side, str(price), str(qty), status]
    if fee is not None and fee != Decimal("0"):
        base.append(str(fee))

    return "|".join(base)


def dedupe_fills(fills: List[Dict]) -> Tuple[List[Dict], int]:
    """Collapse duplicates using canonical keys with rounding.

    Returns (unique_fills, duplicates_removed)
    """
    seen = set()
    out: List[Dict] = []
    dup = 0
    for f in fills:
        k = key_for_fill(f)
        if k in seen:
            dup += 1
            continue
        seen.add(k)
        out.append(f)
    return out, dup

