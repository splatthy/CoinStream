from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from app.services.csv_import.models import ImportResult, ValidationResult
from app.services.csv_import.tx_history.router import detect_tx_history, expected_columns_summary
from app.utils.validators import ValidationError
from .normalizer import normalize as normalize_fills
from .dedupe import dedupe_fills
from .reconstructor import reconstruct


class TxHistoryService:
    """Stub service for tx-history path (normalize → dedupe → reconstruct).

    T2–T5 will implement normalization, dedupe, and reconstruction. For T1, we
    only detect and route files with a clear message.
    """

    def detect_exchange(self, headers: List[str]) -> Optional[str]:
        return detect_tx_history(headers)

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        # For T1, successful validation simply acknowledges detection.
        exch = detect_tx_history(list(df.columns))
        if exch:
            from app.services.csv_import.models import CSVValidationIssue

            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[
                    CSVValidationIssue(
                        message=f"Detected {exch} transaction/order history; routing to tx-history pipeline"
                    )
                ],
            )
        return ValidationResult(
            is_valid=False,
            errors=[ValidationError("File does not match supported tx-history formats.\n" + expected_columns_summary())],
            warnings=[],
        )

    def preview(self, df: pd.DataFrame, rows: int = 10, mode: str = "reconstructed", risk_estimate: Optional[str] = None) -> List[Dict[str, Any]]:
        exch = detect_tx_history(list(df.columns))
        if not exch:
            return [{"status": "error", "row_status": "error", "row_status_icon": "❌", "error": "Unsupported tx-history format"}]

        # Normalize → dedupe
        fills = normalize_fills(df, exch.lower())
        fills, _dups = dedupe_fills(fills)

        if mode == "raw":
            # Present normalized fills
            out: List[Dict[str, Any]] = []
            for f in fills[: max(rows, 0)]:
                out.append(
                    {
                        "status": "fill",
                        "row_status": "ok",
                        "row_status_icon": "✅",
                        "symbol": f.get("symbol"),
                        "side": f.get("side"),
                        "quantity": str(f.get("quantity")),
                        "entry_price": str(f.get("price")),
                        "exit_price": "",
                        "pnl": (str(f.get("pnl")) if f.get("pnl") is not None else ""),
                        "pnl_source": None,
                        "entry_time": f.get("time").isoformat() if f.get("time") else None,
                        "exit_time": "",
                        "notes": f"{f.get('action','')} fill",
                    }
                )
            if not out:
                return [
                    {
                        "status": "info",
                        "row_status": "info",
                        "row_status_icon": "ℹ️",
                        "message": f"{exch} tx-history detected, but no valid Filled rows with quantity > 0.",
                    }
                ]
            return out

        # Reconstructed positions
        closed, in_progress = reconstruct(fills)
        out: List[Dict[str, Any]] = []
        for t in closed[: max(rows, 0)]:
            row = {
                "status": "closed",
                "row_status": "ok",
                "row_status_icon": "✅",
                "symbol": t.symbol,
                "side": t.side,
                "quantity": str(t.quantity),
                "entry_price": str(t.entry_price),
                "exit_price": str(t.exit_price),
                "pnl": str(t.pnl),
                "pnl_source": t.pnl_source,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "notes": None,
            }
            if risk_estimate is not None:
                row["max_risk_per_trade"] = str(risk_estimate)
            out.append(row)

        for p in in_progress[: max(0, rows - len(out))]:
            row = {
                "status": "open",
                "row_status": "info",
                "row_status_icon": "🟡",
                "symbol": p.symbol,
                "side": p.side,
                "quantity": str(p.open_quantity),
                "entry_price": str(p.entry_vwap),
                "exit_price": "",
                "pnl": "",
                "pnl_source": None,
                "entry_time": p.entry_time.isoformat() if p.entry_time else None,
                "exit_time": "",
                "notes": "In-Progress (position not fully closed)",
            }
            if risk_estimate is not None:
                row["max_risk_per_trade"] = str(risk_estimate)
            out.append(row)

        if not out:
            return [
                {
                    "status": "info",
                    "row_status": "info",
                    "row_status_icon": "ℹ️",
                    "message": f"{exch} tx-history detected, but no reconstructable positions found.",
                }
            ]
        return out

    def import_df(self, df: pd.DataFrame) -> ImportResult:
        # T1 stub: fail with clear message that processing will be added later tasks.
        return ImportResult(
            success=False,
            total_rows=len(df),
            imported_trades=0,
            skipped_rows=len(df),
            duplicate_trades=0,
            errors=[
                "Tx-history pipeline detected but not implemented yet (pending T2–T5: normalizer, dedupe, reconstructor)."
            ],
            warnings=[],
            processing_time=0.0,
        )
