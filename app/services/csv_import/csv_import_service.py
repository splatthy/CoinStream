from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional
from decimal import Decimal, InvalidOperation

import pandas as pd

from app.services.csv_import.csv_parser import CSVParser
from app.services.csv_import.csv_validator import CSVValidator
from app.services.csv_import.column_mapper import ColumnMapper
from app.services.csv_import.data_transformer import DataTransformer
from app.services.csv_import.batch_processor import process_dataframe
from app.services.csv_import.models import ColumnMapping, ImportResult, ValidationResult
from app.services.csv_import.tx_history.service import TxHistoryService
from app.services.csv_import.tx_history.router import expected_columns_summary
from app.services.data_service import DataService
from app.services.config_service import ConfigService
from app.models.trade import Trade
from app.models.trade import TradeStatus, TradeSide
from app.services.csv_import.tx_history.normalizer import normalize as normalize_fills
from app.services.csv_import.tx_history.dedupe import dedupe_fills
from app.services.csv_import.tx_history.reconstructor import reconstruct
from app.services.csv_import.tx_history.import_log import ImportLogStore
from app.utils.validators import ValidationError


class CSVImportService:
    """Main orchestrator for CSV import: parse → validate → map → transform → persist."""

    def __init__(self, data_service: DataService, config_service: Optional[ConfigService] = None):
        self.data_service = data_service
        self.config_service = config_service
        self.validator = CSVValidator()
        self.parser = CSVParser()
        self.mapper = ColumnMapper()
        self.transformer = DataTransformer()
        self.tx_history = TxHistoryService()

    # ---------------------- Helpers ----------------------
    def _get_estimated_risk_per_trade(self) -> Optional[Decimal]:
        """Compute portfolio_size * (risk_percent/100) from app config if available."""
        try:
            if not self.config_service:
                return None
            cfg = self.config_service.get_app_config() or {}
            ps = cfg.get("portfolio_size")
            rp = cfg.get("risk_percent")
            if ps is None or rp is None:
                return None
            ps_d = Decimal(str(ps))
            rp_d = Decimal(str(rp))
            if ps_d <= 0 or rp_d <= 0:
                return None
            est = ps_d * (rp_d / Decimal("100"))
            # Normalize scale minimally
            return est
        except Exception:
            return None

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

        # T1: Detect tx-history headers and short-circuit to tx-history validation
        detected = self.tx_history.detect_exchange(list(df.columns))
        if detected:
            return self.tx_history.validate(df)

        # Heuristic: if looks like tx-history but missing required columns, raise clear error
        lower = {str(h).strip().lower() for h in list(df.columns)}
        bitunix_anchors = {"futures", "executed", "average price", "side"}
        blofin_anchors = {"underlying asset", "order time", "avg fill", "filled", "side"}
        if (len(lower.intersection(bitunix_anchors)) >= 3) or (len(lower.intersection(blofin_anchors)) >= 3):
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError("CSV resembles tx-history but is missing required headers.\n" + expected_columns_summary())],
                warnings=[],
            )

        # Load mapping and validate headers (legacy per-trade path)
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
        self,
        file_path: str,
        exchange_name: str,
        rows: int = 10,
        preview_mode: str = "reconstructed",
        risk_estimate: Optional[Decimal] = None,
    ) -> List[Dict]:
        """Generate preview of mapped and transformed data before import."""
        df = self.parser.parse_csv_file(file_path)

        # T1/T9: tx-history path detection
        detected = self.tx_history.detect_exchange(list(df.columns))
        if detected:
            risk_str = str(risk_estimate) if risk_estimate is not None else None
            return self.tx_history.preview(df, rows=rows, mode=preview_mode, risk_estimate=risk_str)

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
        account_label: Optional[str] = None,
        start_time_after: Optional[str] = None,
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
                open_positions_skipped=0,
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
                open_positions_skipped=0,
                errors=[],
                warnings=["CSV contains no rows"],
                processing_time=0.0,
            )

        # Tx-history path: normalize → optional time filter → dedupe → reconstruct → persist (closed only)
        detected = self.tx_history.detect_exchange(list(df.columns))
        if detected:
            fills = normalize_fills(df, detected.lower())
            # Optional incremental filter
            if start_time_after:
                try:
                    # Parse naive ISO datetime
                    import pandas as pd
                    st = pd.to_datetime(start_time_after, errors="coerce", utc=False)
                    if st is not None and not pd.isna(st):
                        st_py = st.to_pydatetime()
                        fills = [f for f in fills if f.get('time') and f['time'] > st_py]
                except Exception:
                    pass
            fills, dedup_removed = dedupe_fills(fills)
            closed, in_progress = reconstruct(fills)

            # Persist closed trades only
            existing_trades = self.data_service.load_trades()
            existing_ids = {t.id for t in existing_trades}
            seen_ids = set(existing_ids)

            new_trades: List[Trade] = []
            duplicate_trades = 0
            est_risk = self._get_estimated_risk_per_trade()
            for t in closed:
                trade_id = self.transformer.generate_trade_id(t.symbol, t.entry_time, t.quantity, t.entry_price)
                if trade_id in seen_ids:
                    duplicate_trades += 1
                    continue

                side_enum = TradeSide.LONG if str(t.side).lower() == "long" else TradeSide.SHORT
                trade = Trade(
                    id=trade_id,
                    exchange=t.exchange,
                    symbol=t.symbol,
                    side=side_enum,
                    entry_price=t.entry_price,
                    quantity=t.quantity,
                    entry_time=t.entry_time,
                    status=TradeStatus.CLOSED,
                    exit_price=t.exit_price,
                    exit_time=t.exit_time,
                    pnl=t.pnl,
                    confluences=[],
                    custom_fields={},
                )
                if getattr(t, 'fees_total', None) is not None:
                    trade.custom_fields['fees'] = str(t.fees_total)
                if getattr(t, 'pnl_source', None):
                    trade.custom_fields['pnl_source'] = t.pnl_source
                if getattr(t, 'margin_mode', None):
                    trade.custom_fields['margin_mode'] = t.margin_mode
                if getattr(t, 'leverage', None):
                    trade.custom_fields['leverage'] = t.leverage
                # T7: attach risk snapshot if available
                if est_risk is not None:
                    trade.custom_fields['max_risk_per_trade'] = str(est_risk)
                    trade.custom_fields['risk_source'] = 'calculated'

                new_trades.append(trade)
                seen_ids.add(trade_id)

            if new_trades:
                all_trades = existing_trades + new_trades
                if len({t.id for t in all_trades}) != len(all_trades):
                    return ImportResult(
                        success=False,
                        total_rows=total_rows,
                        imported_trades=0,
                        skipped_rows=total_rows,
                        duplicate_trades=0,
                        open_positions_skipped=0,
                        errors=["Integrity check failed: duplicate trade IDs after merge"],
                        warnings=[],
                        processing_time=time.perf_counter() - start,
                    )
                self.data_service.save_trades(all_trades)

            processing_time = time.perf_counter() - start
            warn = []
            if dedup_removed:
                warn.append(f"Deduplicated fills removed: {dedup_removed}")
            if in_progress:
                warn.append(f"Open positions skipped: {len(in_progress)}")

            # Write audit log entry
            try:
                log = ImportLogStore(str(self.data_service.data_path))
                # Risk snapshot for logging
                snap = None
                if self.config_service:
                    cfg = self.config_service.get_app_config() or {}
                    est = self._get_estimated_risk_per_trade()
                    snap = {
                        'portfolio_size': str(cfg.get('portfolio_size')) if cfg.get('portfolio_size') is not None else None,
                        'risk_percent': str(cfg.get('risk_percent')) if cfg.get('risk_percent') is not None else None,
                        'estimated_risk_per_trade': str(est) if est is not None else None,
                    }
                max_fill_time = None
                try:
                    max_fill_time = max((f.get('time') for f in fills if f.get('time')), default=None)
                except Exception:
                    max_fill_time = None
                counts = {
                    'total_rows': total_rows,
                    'dedup_removed': dedup_removed,
                    'closed_persisted': len(new_trades),
                    'open_skipped': len(in_progress),
                    'duplicate_trades': duplicate_trades,
                    'errors': len(errors),
                    'warnings': len(warn),
                }
                entry = ImportLogStore.new_entry(
                    exchange=detected,
                    account_label=account_label,
                    file_path=file_path,
                    counts=counts,
                    risk_config_snapshot=snap,
                    max_fill_time=max_fill_time,
                )
                log.append(entry)
            except Exception:
                # Do not fail import on logging errors
                pass

            return ImportResult(
                success=True,
                total_rows=total_rows,
                imported_trades=len(new_trades),
                skipped_rows=(len(in_progress) + duplicate_trades),
                duplicate_trades=duplicate_trades,
                open_positions_skipped=len(in_progress),
                errors=[],
                warnings=warn,
                processing_time=processing_time,
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
                open_positions_skipped=0,
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
                open_positions_skipped=0,
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
             open_positions_skipped=0,
            errors=errors,
            warnings=warnings,
            processing_time=processing_time,
        )

    def get_suggested_mapping(self, csv_headers: List[str]) -> ColumnMapping:
        return self.mapper.suggest_mapping(csv_headers)
