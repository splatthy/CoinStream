from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from app.services.csv_import.models import ColumnMapping, ValidationResult
from app.utils.validators import ValidationError

MAPPINGS_DIR = Path(__file__).with_suffix("").parent / "mappings"


COMMON_COLUMN_PATTERNS: Dict[str, List[str]] = {
    "symbol": ["symbol", "pair", "instrument", "market", "asset"],
    "side": ["side", "direction", "type", "position"],
    "quantity": ["quantity", "amount", "size", "volume"],
    "entry_price": ["entry price", "entry_price", "open_price", "entry", "open"],
    "exit_price": ["exit price", "exit_price", "close_price", "exit", "close"],
    "entry_time": [
        "opening date",
        "entry time",
        "entry_time",
        "open_time",
        "start_time",
        "open time",
    ],
    "exit_time": [
        "date",
        "exit time",
        "exit_time",
        "close_time",
        "end_time",
        "close time",
    ],
    "pnl": ["net pnl", "pnl", "profit_loss", "net_pnl", "realized pnl", "realized_pnl"],
    "fees": ["fees", "fee"],
}


class ColumnMapper:
    """Creates column mappings either from shipped templates or by pattern matching."""

    def load_template(self, exchange_name: str) -> ColumnMapping:
        """Load a shipped mapping template for a given exchange."""
        name = exchange_name.strip().lower()
        path = MAPPINGS_DIR / f"{name}.json"
        if not path.exists():
            raise ValidationError(
                f"No mapping template found for exchange '{exchange_name}'"
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise ValidationError(
                f"Failed to load mapping template for {exchange_name}: {e}"
            )

        fields: Dict[str, Optional[str]] = data.get("fields", {})
        mapping = ColumnMapping(
            symbol=fields.get("symbol"),
            side=fields.get("side"),
            quantity=fields.get("quantity"),
            entry_price=fields.get("entry_price"),
            entry_time=fields.get("entry_time"),
            exit_price=fields.get("exit_price"),
            exit_time=fields.get("exit_time"),
            pnl=fields.get("pnl"),
            fees=fields.get("fees"),
            name=data.get("name", exchange_name.title()),
            description=data.get("description"),
        )
        return mapping

    def create_mapping(
        self, csv_headers: List[str], exchange_name: Optional[str] = None
    ) -> ColumnMapping:
        """Create a ColumnMapping using a template if exchange_name is provided; otherwise, suggest by patterns.

        If a template is provided but required headers are missing, raises ValidationError.
        """
        headers_norm = [h.strip() for h in csv_headers]
        if exchange_name:
            mapping = self.load_template(exchange_name)
            # Validate headers against template strictly for MVP
            mapping.validate_against_headers(headers_norm)
            return mapping

        return self.suggest_mapping(headers_norm)

    def suggest_mapping(self, csv_headers: List[str]) -> ColumnMapping:
        """Suggest a mapping using common patterns and the provided headers."""
        lower_headers = {h.lower(): h for h in csv_headers}

        def find_first(patterns: List[str]) -> Optional[str]:
            for pat in patterns:
                key = pat.lower()
                if key in lower_headers:
                    return lower_headers[key]
            # fallback: contains match
            for pat in patterns:
                for k, original in lower_headers.items():
                    if pat in k:
                        return original
            return None

        fields: Dict[str, Optional[str]] = {}
        for logical, pats in COMMON_COLUMN_PATTERNS.items():
            fields[logical] = find_first(pats)

        mapping = ColumnMapping(
            symbol=fields.get("symbol"),
            side=fields.get("side"),
            quantity=fields.get("quantity"),
            entry_price=fields.get("entry_price"),
            entry_time=fields.get("entry_time"),
            exit_price=fields.get("exit_price"),
            exit_time=fields.get("exit_time"),
            pnl=fields.get("pnl"),
            fees=fields.get("fees"),
            name="Suggested",
            description="Auto-suggested mapping based on header patterns",
        )
        return mapping

    def validate_mapping(
        self, mapping: ColumnMapping, csv_headers: List[str]
    ) -> ValidationResult:
        try:
            mapping.validate_against_headers(csv_headers)
            return ValidationResult(is_valid=True)
        except ValidationError as e:
            return ValidationResult(is_valid=False, errors=[e])
