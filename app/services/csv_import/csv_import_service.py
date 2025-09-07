from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional

import pandas as pd

from app.services.csv_import.csv_parser import CSVParser
from app.services.csv_import.csv_validator import CSVValidator
from app.services.csv_import.column_mapper import ColumnMapper
from app.services.csv_import.data_transformer import DataTransformer
from app.services.csv_import.batch_processor import process_dataframe
from app.services.csv_import.models import ColumnMapping, ImportResult, ValidationResult
from app.services.data_service import DataService
from app.models.trade import Trade
from app.utils.validators import ValidationError


class CSVImportService:
    """Main orchestrator for CSV import: parse → validate → map → transform → persist."""

    def __init__(self, data_service: DataService):
        self.data_service = data_service
        self.validator = CSVValidator()
        self.parser = CSVParser()
        self.mapper = ColumnMapper()
        self.transformer = DataTransformer()

    # ---------------------- Public API ----------------------
    def validate_csv_file(self, file_path: str, exchange_name: str) -> ValidationResult:
        """Validate CSV file structure and data quality for the selected exchange template."""
        # Basic format checks
        fmt = self.validator.validate_file_format(file_path)
        if fmt.has_blocking_errors():
            return fmt

        # Parse
        try:
            df = self.parser.parse_csv_file(file_path)
        except ValidationError as e:
            return ValidationResult(is_valid=False, errors=[e])

        # Load mapping and validate headers
        try:
            mapping = self.mapper.create_mapping(list(df.columns), exchange_name=exchange_name)
        except ValidationError as e:
            return ValidationResult(is_valid=False, errors=[e])

        # Data validation
        required_res = self.validator.validate_required_fields(df, mapping)
        if required_res.has_blocking_errors():
            return required_res

        types_res = self.validator.validate_data_types(df, mapping)
        if types_res.has_blocking_errors():
            return types_res

        # Duplicates within file (warn only)
        dup_indices = self.validator.detect_duplicates(df, mapping)
        warnings = []
        if dup_indices:
            from app.services.csv_import.models import CSVValidationIssue

            warnings.append(
                CSVValidationIssue(
                    message=f"Detected {len(dup_indices)} potential duplicate rows in CSV (symbol + entry_time)",
                    category="warning",
                )
            )

        return ValidationResult(is_valid=True, warnings=warnings)

    def preview_csv_data(
        self, file_path: str, exchange_name: str, rows: int = 10
    ) -> List[Dict]:
        """Generate preview of mapped and transformed data before import."""
        df = self.parser.parse_csv_file(file_path)
        mapping = self.mapper.create_mapping(list(df.columns), exchange_name=exchange_name)

        preview_rows: List[Dict] = []
        for i in range(min(rows, len(df))):
            row = df.iloc[i]
            try:
                trade = self.transformer.transform_row(row, mapping, exchange=exchange_name)
                # Determine if PnL was provided in CSV or calculated
                pnl_provided = False
                if mapping.pnl and mapping.pnl in df.columns:
                    raw_pnl = row.get(mapping.pnl)
                    pnl_provided = raw_pnl is not None and str(raw_pnl).strip() != ""

                # Row-level status indicator for preview
                row_status = "ok"
                row_status_icon = "✅"
                notes = []
                if not pnl_provided and trade.pnl is not None:
                    notes.append("PnL calculated")
                if trade.exit_price is None or trade.exit_time is None:
                    notes.append("Open trade (no exit)")

                preview_rows.append(
                    {
                        "symbol": trade.symbol,
                        "side": trade.side.value,
                        "quantity": str(trade.quantity),
                        "entry_price": str(trade.entry_price),
                        "exit_price": str(trade.exit_price) if trade.exit_price else None,
                        "pnl": str(trade.pnl) if trade.pnl is not None else None,
                        "pnl_source": "provided" if pnl_provided else ("calculated" if trade.pnl is not None else None),
                        "entry_time": trade.entry_time.isoformat(),
                        "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                        "status": trade.status.value,
                        "row_status": row_status,
                        "row_status_icon": row_status_icon,
                        "notes": ", ".join(notes) if notes else None,
                    }
                )
            except Exception as e:
                preview_rows.append({
                    "status": "error",
                    "row_status": "error",
                    "row_status_icon": "❌",
                    "error": str(e)
                })

        return preview_rows

    def import_csv_file(
        self,
        file_path: str,
        exchange_name: str,
        on_progress: Optional[Callable[[int, int], bool]] = None,
    ) -> ImportResult:
        """Import trades from CSV file with full validation and persistence."""
        start = time.perf_counter()
        errors: List[str] = []
        warnings: List[str] = []

        # Parse
        try:
            df = self.parser.parse_csv_file(file_path)
        except ValidationError as e:
            return ImportResult(
                success=False,
                total_rows=0,
                imported_trades=0,
                skipped_rows=0,
                duplicate_trades=0,
                errors=[str(e)],
                warnings=[],
                processing_time=0.0,
            )

        total_rows = len(df)
        if total_rows == 0:
            return ImportResult(
                success=True,
                total_rows=0,
                imported_trades=0,
                skipped_rows=0,
                duplicate_trades=0,
                errors=[],
                warnings=["CSV contains no rows"],
                processing_time=0.0,
            )

        # Mapping
        mapping = self.mapper.create_mapping(list(df.columns), exchange_name=exchange_name)

        # Validate data before attempting import
        required_res = self.validator.validate_required_fields(df, mapping)
        if required_res.has_blocking_errors():
            return ImportResult(
                success=False,
                total_rows=total_rows,
                imported_trades=0,
                skipped_rows=total_rows,
                duplicate_trades=0,
                errors=[str(e) for e in required_res.errors],
                warnings=[w.message for w in required_res.warnings],
                processing_time=time.perf_counter() - start,
            )

        types_res = self.validator.validate_data_types(df, mapping)
        if types_res.has_blocking_errors():
            return ImportResult(
                success=False,
                total_rows=total_rows,
                imported_trades=0,
                skipped_rows=total_rows,
                duplicate_trades=0,
                errors=[str(e) for e in types_res.errors],
                warnings=[w.message for w in types_res.warnings],
                processing_time=time.perf_counter() - start,
            )

        # Transform rows using batch processor; capture per-row errors without raising
        def worker(row: pd.Series) -> Dict[str, Optional[Trade]]:
            try:
                trade = self.transformer.transform_row(row, mapping, exchange=exchange_name)
                return {"trade": trade, "error": None}
            except Exception as e:
                return {"trade": None, "error": str(e)}

        results, processed, _, cancelled = process_dataframe(
            df, worker, on_progress=on_progress
        )

        # Load existing trades and index by ID for duplicate detection
        existing_trades = self.data_service.load_trades()
        existing_ids = {t.id for t in existing_trades}

        new_trades: List[Trade] = []
        duplicate_trades = 0
        skipped_rows = 0

        seen_ids = set(existing_ids)
        for res in results:
            err = res.get("error")
            trade = res.get("trade")
            if err:
                errors.append(err)
                skipped_rows += 1
                continue
            if not trade:
                skipped_rows += 1
                continue
            # Treat duplicates against existing data and within the same file
            if trade.id in seen_ids:
                duplicate_trades += 1
                continue
            new_trades.append(trade)
            seen_ids.add(trade.id)

        # Persist
        if new_trades:
            all_trades = existing_trades + new_trades
            # Basic data integrity: ensure unique IDs before save
            if len({t.id for t in all_trades}) != len(all_trades):
                errors.append("Integrity check failed: duplicate trade IDs after merge")
            else:
                self.data_service.save_trades(all_trades)

        processing_time = time.perf_counter() - start
        return ImportResult(
            success=len(errors) == 0,
            total_rows=total_rows,
            imported_trades=len(new_trades),
            skipped_rows=skipped_rows,
            duplicate_trades=duplicate_trades,
            errors=errors,
            warnings=warnings,
            processing_time=processing_time,
        )

    def get_suggested_mapping(self, csv_headers: List[str]) -> ColumnMapping:
        return self.mapper.suggest_mapping(csv_headers)
