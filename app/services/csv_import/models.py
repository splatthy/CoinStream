from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from app.utils.validators import ValidationError


@dataclass
class ColumnMapping:
    """
    Defines mapping between CSV columns and Trade model fields.

    Field values represent the CSV header names for each logical field.
    """

    symbol: str
    side: str
    quantity: str
    entry_price: str
    entry_time: str
    exit_price: Optional[str] = None
    exit_time: Optional[str] = None
    pnl: Optional[str] = None
    fees: Optional[str] = None

    # Metadata
    name: str = "Default"
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def required_fields(self) -> List[str]:
        """Return the list of required logical fields that must be mapped."""
        return ["symbol", "side", "quantity", "entry_price", "entry_time"]

    def as_dict(self) -> Dict[str, Optional[str]]:
        """Return mapping as a dict of logical_field -> csv_header (or None)."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time,
            "pnl": self.pnl,
            "fees": self.fees,
        }

    def validate_against_headers(self, csv_headers: List[str]) -> None:
        """
        Validate that required mapped columns exist in the provided CSV headers.
        Raises ValidationError if any required column is missing.
        """
        header_set = {h.strip(): True for h in csv_headers}
        missing: List[str] = []
        for field_name in self.required_fields():
            csv_col = getattr(self, field_name)
            if not csv_col or csv_col.strip() not in header_set:
                missing.append(f"{field_name} -> '{csv_col}'")

        if missing:
            raise ValidationError(
                "Missing required CSV columns for mapping: " + ", ".join(missing)
            )


@dataclass
class CSVValidationIssue:
    """
    Non-blocking validation issue container (e.g., warnings/info).
    Reuse ValidationError for blocking errors.
    """

    message: str
    row: Optional[int] = None
    column: Optional[str] = None
    category: str = "warning"  # e.g., "warning" | "info"


@dataclass
class ValidationResult:
    """Aggregate validation result for CSV checks."""

    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[CSVValidationIssue] = field(default_factory=list)

    def has_blocking_errors(self) -> bool:
        return len(self.errors) > 0 or not self.is_valid


@dataclass
class ImportResult:
    """Result of CSV import operation."""

    success: bool
    total_rows: int
    imported_trades: int
    skipped_rows: int
    duplicate_trades: int
    # Tx-history specific metric: number of in-progress positions skipped
    open_positions_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time: float = 0.0

    def get_summary(self) -> str:
        parts = [
            f"Success: {self.success}",
            f"Rows: {self.total_rows}",
            f"Imported (Closed): {self.imported_trades}",
            f"Open Skipped: {self.open_positions_skipped}",
            f"Skipped (Total): {self.skipped_rows}",
            f"Duplicates: {self.duplicate_trades}",
            f"Errors: {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
            f"Time: {self.processing_time:.2f}s",
        ]
        return " | ".join(parts)
