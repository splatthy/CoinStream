from __future__ import annotations

from typing import Dict, List, Optional, Tuple


BITUNIX_REQUIRED = {"date", "side", "futures", "average price", "executed", "status"}
BITUNIX_OPTIONAL = {"fee", "realized p/l"}


BLOFIN_REQUIRED = {
    "underlying asset",
    "order time",
    "side",
    "avg fill",
    "filled",
    "status",
}
BLOFIN_OPTIONAL = {"reduce-only", "margin mode", "leverage", "fee", "pnl"}


def _normalize_headers(headers: List[str]) -> List[str]:
    return [str(h).strip().lower() for h in headers if h is not None]


def detect_tx_history(headers: List[str]) -> Optional[str]:
    """Detect whether headers match a known tx-history (fills) format.

    Returns the exchange name ("Bitunix" | "Blofin") when matched; None otherwise.
    """
    hset = set(_normalize_headers(headers))

    if BITUNIX_REQUIRED.issubset(hset):
        return "Bitunix"
    if BLOFIN_REQUIRED.issubset(hset):
        return "Blofin"
    return None


def expected_columns_summary() -> str:
    """Return a concise summary of the expected headers for supported tx-history sources."""
    bitunix = ", ".join(sorted(BITUNIX_REQUIRED))
    blofin = ", ".join(sorted(BLOFIN_REQUIRED))
    return (
        "Expected tx-history headers:\n"
        f"- Bitunix: {bitunix}\n"
        f"- Blofin: {blofin}"
    )

