from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional, Tuple

from app.utils.validators import ValidationError


getcontext().prec = 28

QTY_EPS = Decimal("0.00000001")


@dataclass
class ClosedTradeDTO:
    exchange: str
    symbol: str
    side: str  # long | short
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_time: Any  # datetime
    exit_time: Any  # datetime
    pnl: Decimal
    fees_total: Decimal
    pnl_source: str  # 'provided' | 'derived'
    margin_mode: Optional[str] = None
    leverage: Optional[str] = None


@dataclass
class InProgressPositionDTO:
    exchange: str
    symbol: str
    side: str
    open_quantity: Decimal
    entry_vwap: Decimal
    entry_time: Any
    fees_open: Decimal
    margin_mode: Optional[str] = None
    leverage: Optional[str] = None


class _State:
    def __init__(self, exchange: str, symbol: str, side: str, margin_mode: Optional[str] = None, leverage: Optional[str] = None) -> None:
        self.exchange = exchange
        self.symbol = symbol
        self.side = side
        self.margin_mode = margin_mode
        self.leverage = leverage

        # Remaining open basis for current position
        self.rem_open_qty = Decimal("0")
        self.rem_open_cost = Decimal("0")  # sum(price*qty) remaining

        # Consumed entry cost attributed to closed quantity
        self.consumed_entry_cost = Decimal("0")
        self.total_close_qty = Decimal("0")
        self.total_close_cost = Decimal("0")  # sum(close price * qty)

        # Fees and PnL
        self.open_fees = Decimal("0")
        self.close_fees = Decimal("0")
        self.close_pnl_sum = Decimal("0")
        self.close_pnl_missing = 0

        # Times
        self.entry_time = None
        self.last_close_time = None

    def entry_vwap_current(self) -> Optional[Decimal]:
        if self.rem_open_qty <= QTY_EPS:
            return None
        return self.rem_open_cost / self.rem_open_qty

    def add_open(self, qty: Decimal, price: Decimal, fee: Decimal, time: Any, margin_mode: Optional[str], leverage: Optional[str]) -> None:
        if qty <= 0:
            return
        self.rem_open_qty += qty
        self.rem_open_cost += price * qty
        self.open_fees += (fee or Decimal("0"))
        if self.entry_time is None or (time is not None and self.entry_time > time):
            self.entry_time = time
        if margin_mode and not self.margin_mode:
            self.margin_mode = str(margin_mode)
        if leverage and not self.leverage:
            self.leverage = str(leverage)

    def apply_close(self, qty: Decimal, price: Decimal, fee: Decimal, time: Any, pnl: Optional[Decimal]) -> Decimal:
        """Apply a close fill quantity against the remaining open basis.

        Returns the quantity actually applied (capped by remaining open qty).
        Allocates proportional fee and pnl when needed in caller.
        """
        if qty <= 0 or self.rem_open_qty <= QTY_EPS:
            return Decimal("0")

        use_qty = min(qty, self.rem_open_qty)

        # Attribute entry cost for the closed part at current VWAP
        vwap = self.entry_vwap_current()
        if vwap is None:
            raise ValidationError("Attempted to close without open basis")
        consumed_cost = vwap * use_qty
        self.consumed_entry_cost += consumed_cost
        self.rem_open_qty -= use_qty
        self.rem_open_cost -= consumed_cost

        # Track close cost and qty
        self.total_close_qty += use_qty
        self.total_close_cost += price * use_qty
        self.close_fees += (fee or Decimal("0")) * (use_qty / qty)

        # Track PnL if provided
        if pnl is None:
            self.close_pnl_missing += 1
        else:
            self.close_pnl_sum += pnl * (use_qty / qty)

        self.last_close_time = time
        return use_qty

    def is_closed(self) -> bool:
        return self.rem_open_qty <= QTY_EPS and self.total_close_qty > Decimal("0")

    def emit_closed(self) -> ClosedTradeDTO:
        if not self.is_closed():
            raise ValidationError("Position not closed")
        qty = self.total_close_qty
        entry_vwap = (self.consumed_entry_cost / qty) if qty > 0 else Decimal("0")
        exit_vwap = (self.total_close_cost / qty) if qty > 0 else Decimal("0")
        fees_total = self.open_fees + self.close_fees

        # Compute gross from VWAPs for comparison / fallback
        if self.side == "long":
            gross = (exit_vwap - entry_vwap) * qty
        else:  # short
            gross = (entry_vwap - exit_vwap) * qty

        if self.close_pnl_missing == 0:
            # Heuristic: some exchanges report realized PnL as gross (pre-fees), others as net.
            # Decide per-position by comparing provided vs gross within a tolerance.
            tol = Decimal("0.0000001")
            if (self.close_pnl_sum - gross).copy_abs() <= tol:
                pnl = gross - fees_total
                source = "provided_gross_adjusted"
            else:
                pnl = self.close_pnl_sum
                source = "provided"
        else:
            pnl = gross - fees_total
            source = "calculated"

        # Infer final position side from entry/exit and pnl to guard against
        # exchange-specific order-side labelling oddities.
        side_out = self.side
        try:
            if pnl is not None:
                if (exit_vwap < entry_vwap and pnl > 0) or (exit_vwap > entry_vwap and pnl < 0):
                    side_out = "short"
                elif (exit_vwap > entry_vwap and pnl > 0) or (exit_vwap < entry_vwap and pnl < 0):
                    side_out = "long"
        except Exception:
            pass

        return ClosedTradeDTO(
            exchange=self.exchange,
            symbol=self.symbol,
            side=side_out,
            quantity=qty,
            entry_price=entry_vwap,
            exit_price=exit_vwap,
            entry_time=self.entry_time,
            exit_time=self.last_close_time,
            pnl=pnl,
            fees_total=fees_total,
            pnl_source=source,
            margin_mode=self.margin_mode,
            leverage=self.leverage,
        )

    def emit_in_progress(self) -> Optional[InProgressPositionDTO]:
        if self.rem_open_qty > QTY_EPS:
            vwap = self.entry_vwap_current() or Decimal("0")
            return InProgressPositionDTO(
                exchange=self.exchange,
                symbol=self.symbol,
                side=self.side,
                open_quantity=self.rem_open_qty,
                entry_vwap=vwap,
                entry_time=self.entry_time,
                fees_open=self.open_fees,
                margin_mode=self.margin_mode,
                leverage=self.leverage,
            )
        return None


def reconstruct(fills: List[Dict[str, Any]]) -> Tuple[List[ClosedTradeDTO], List[InProgressPositionDTO]]:
    """Reconstruct closed positions from normalized fills.

    Groups by (exchange, symbol, side[, margin_mode]) and walks fills by time.
    Emits Closed trades when quantity goes to ~0; returns remaining in-progress positions.
    """
    # Sort fills chronologically to ensure deterministic reconstruction
    fills_sorted = sorted(
        fills, key=lambda f: (f.get("exchange"), f.get("symbol"), f.get("side"), str(f.get("margin_mode") or ""), f.get("time"))
    )

    def key_static(exch: str, sym: str, side: str, mm: Optional[str]) -> tuple:
        return (str(exch), str(sym), str(side), str(mm or ""))

    states: Dict[tuple, _State] = {}
    closed: List[ClosedTradeDTO] = []

    for f in fills_sorted:
        exch = str(f.get("exchange"))
        sym = str(f.get("symbol"))
        side = str(f.get("side")).lower()
        mm = f.get("margin_mode")
        lev = f.get("leverage")
        k = key_static(exch, sym, side, mm)

        action = str(f.get("action")).lower()
        qty = f.get("quantity")
        price = f.get("price")
        fee = f.get("fee") or Decimal("0")
        time = f.get("time")
        pnl = f.get("pnl")

        if action == "open":
            st = states.get(k)
            if st is None:
                states[k] = st = _State(exch, sym, side, mm, lev)
            st.add_open(qty, price, fee, time, mm, lev)
        elif action == "close":
            # Only close an existing state; do not create a state based on a close alone.
            st = states.get(k)
            if st is None:
                # Unmatched close (no open basis in current file/window); skip
                continue
            rem = qty
            # Apply possibly across multiple positions if prior one closes and leftover remains
            while rem > QTY_EPS:
                used = st.apply_close(rem, price, fee, time, pnl)
                if used <= QTY_EPS:
                    # No open qty to close; ignore unmatched close remainder for MVP
                    break
                rem -= used
                if st.is_closed():
                    closed.append(st.emit_closed())
                    # Reset state for next potential position cycle within same group
                    states[k] = st = _State(exch, sym, side, mm, lev)
        else:
            # Unknown action; ignore
            continue

    # Collect in-progress positions
    in_progress: List[InProgressPositionDTO] = []
    for st in states.values():
        ip = st.emit_in_progress()
        if ip is not None:
            in_progress.append(ip)

    # Sort closed by entry_time for stable output
    closed.sort(key=lambda t: t.entry_time)
    in_progress.sort(key=lambda t: t.entry_time)
    return closed, in_progress
