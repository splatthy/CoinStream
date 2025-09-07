from __future__ import annotations

"""
CSV validation utilities: file format checks, required field checks,
data type validation, and duplicate detection.
"""

from typing import List, Optional

import pandas as pd

from app.services.csv_import.models import ColumnMapping, ValidationResult
from app.utils.validators import ValidationError


class CSVValidator:
    """Validate CSV files and their data based on a provided ColumnMapping."""

    def validate_file_format(self, file_path: str) -> ValidationResult:
        """Validate basic file format and structure (extension, readability)."""
        errors: List[ValidationError] = []
        try:
            if not file_path.lower().endswith(".csv"):
                errors.append(ValidationError("Only .csv files are supported"))
        except Exception as e:
            errors.append(ValidationError(f"Unexpected error validating file: {e}"))

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def validate_required_fields(
        self, df: pd.DataFrame, mapping: ColumnMapping
    ) -> ValidationResult:
        """Ensure required fields are present and non-empty per row."""
        errors: List[ValidationError] = []

        # Header presence
        try:
            mapping.validate_against_headers(list(df.columns))
        except ValidationError as e:
            errors.append(e)
            return ValidationResult(is_valid=False, errors=errors)

        # Row-level presence checks for required fields
        required_cols = [getattr(mapping, f) for f in mapping.required_fields()]
        for idx, row in df.iterrows():
            for logical, col in zip(mapping.required_fields(), required_cols):
                val = row.get(col)
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    errors.append(
                        ValidationError(
                            f"Missing required value for '{logical}' in row {idx + 1} (column '{col}')"
                        )
                    )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def validate_data_types(
        self, df: pd.DataFrame, mapping: ColumnMapping
    ) -> ValidationResult:
        """
        Validate data types and business rules for mapped columns:
        - Numeric: quantity, entry_price, exit_price (if present), pnl (if present)
        - Dates: entry_time (required), exit_time (optional)
        - Side: must be long/short (case-insensitive)
        """
        errors: List[ValidationError] = []

        # Numeric checks
        def _check_positive_decimal(series: pd.Series, name: str, required: bool) -> None:
            if series is None:
                return
            for idx, val in series.items():
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    if required:
                        errors.append(
                            ValidationError(
                                f"Missing required numeric '{name}' in row {idx + 1}"
                            )
                        )
                    continue
                try:
                    num = float(str(val))
                except Exception:
                    errors.append(
                        ValidationError(
                            f"Invalid numeric value for '{name}' in row {idx + 1}: '{val}'"
                        )
                    )
                    continue
                if num <= 0 and name in ("quantity", "entry_price", "exit_price"):
                    errors.append(
                        ValidationError(
                            f"{name} must be positive in row {idx + 1}: '{val}'"
                        )
                    )

        qty_col = getattr(mapping, "quantity", None)
        if qty_col in df.columns:
            _check_positive_decimal(df[qty_col], "quantity", required=True)

        entry_price_col = getattr(mapping, "entry_price", None)
        if entry_price_col in df.columns:
            _check_positive_decimal(df[entry_price_col], "entry_price", required=True)

        exit_price_col = getattr(mapping, "exit_price", None)
        if exit_price_col and exit_price_col in df.columns:
            _check_positive_decimal(df[exit_price_col], "exit_price", required=False)

        pnl_col = getattr(mapping, "pnl", None)
        if pnl_col and pnl_col in df.columns:
            # pnl can be negative; only type check
            for idx, val in df[pnl_col].items():
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    continue
                try:
                    float(str(val))
                except Exception:
                    errors.append(
                        ValidationError(
                            f"Invalid numeric value for 'pnl' in row {idx + 1}: '{val}'"
                        )
                    )

        # Date checks
        def _parseable_datetime(series: pd.Series, name: str, required: bool) -> None:
            if series is None:
                return
            parsed = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
            for idx, (raw, dt) in enumerate(zip(series, parsed)):
                if pd.isna(dt):
                    if required or (raw not in (None, "")):
                        errors.append(
                            ValidationError(
                                f"Invalid {name} in row {idx + 1}: '{raw}'"
                            )
                        )

        entry_time_col = getattr(mapping, "entry_time", None)
        if entry_time_col in df.columns:
            _parseable_datetime(df[entry_time_col], "entry_time", required=True)

        exit_time_col = getattr(mapping, "exit_time", None)
        if exit_time_col and exit_time_col in df.columns:
            _parseable_datetime(df[exit_time_col], "exit_time", required=False)

        # Side validation: accept long/short (any case) and common variations
        side_col = getattr(mapping, "side", None)
        if side_col in df.columns:
            valid = {"long", "short"}
            for idx, val in df[side_col].items():
                if val is None or str(val).strip() == "":
                    errors.append(
                        ValidationError(f"Missing required side in row {idx + 1}")
                    )
                    continue
                sval = str(val).strip().lower()
                if sval not in valid:
                    errors.append(
                        ValidationError(
                            f"Invalid side in row {idx + 1}: '{val}' (expected Long/Short)"
                        )
                    )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def detect_duplicates(
        self, df: pd.DataFrame, mapping: ColumnMapping
    ) -> List[int]:
        """Detect potential duplicate trades by (symbol, entry_time). Returns row indices of duplicates beyond the first occurrence."""
        symbol_col = getattr(mapping, "symbol", None)
        time_col = getattr(mapping, "entry_time", None)
        if symbol_col not in df.columns or time_col not in df.columns:
            return []

        # Normalize time for grouping
        times = pd.to_datetime(df[time_col], errors="coerce", infer_datetime_format=True)
        keys = pd.Series(zip(df[symbol_col].astype(str).str.strip().str.upper(), times))
        dup_mask = keys.duplicated(keep="first")
        return [int(i) for i, is_dup in enumerate(dup_mask) if bool(is_dup)]

