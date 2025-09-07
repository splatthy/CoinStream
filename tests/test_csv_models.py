import pytest
from datetime import datetime

from app.services.csv_import.models import (
    ColumnMapping,
    CSVValidationIssue,
    ValidationResult,
    ImportResult,
)
from app.utils.validators import ValidationError


def test_column_mapping_validation_success():
    mapping = ColumnMapping(
        symbol="symbol",
        side="side",
        quantity="quantity",
        entry_price="Entry Price",
        entry_time="Opening Date",
        exit_price="Exit Price",
        exit_time="Date",
        pnl="Net PnL",
        fees="Fees",
        name="Bitunix",
        description="Bitunix export mapping",
    )

    headers = [
        "Date",
        "symbol",
        "side",
        "quantity",
        "asset",
        "Entry Price",
        "Exit Price",
        "Gross PnL",
        "Net PnL",
        "Fees",
        "margin",
        "Opening Date",
        "Closed Value",
    ]

    # Should not raise
    mapping.validate_against_headers(headers)


def test_column_mapping_validation_missing_columns():
    mapping = ColumnMapping(
        symbol="symbol",
        side="side",
        quantity="quantity",
        entry_price="Entry Price",
        entry_time="Opening Date",
    )

    headers = ["symbol", "side", "quantity", "Entry Price"]  # Missing Opening Date

    with pytest.raises(ValidationError) as exc:
        mapping.validate_against_headers(headers)

    assert "Missing required CSV columns" in str(exc.value)


def test_validation_result_has_blocking_errors():
    vr = ValidationResult(is_valid=False)
    assert vr.has_blocking_errors() is True

    vr_ok = ValidationResult(is_valid=True, errors=[])
    assert vr_ok.has_blocking_errors() is False

    # With errors present
    vr_err = ValidationResult(is_valid=True, errors=[ValidationError("x")])
    assert vr_err.has_blocking_errors() is True


def test_import_result_summary_format():
    ir = ImportResult(
        success=True,
        total_rows=100,
        imported_trades=95,
        skipped_rows=5,
        duplicate_trades=3,
        errors=["e1", "e2"],
        warnings=["w1"],
        processing_time=1.234,
    )

    summary = ir.get_summary()
    assert "Success: True" in summary
    assert "Rows: 100" in summary
    assert "Imported: 95" in summary
    assert "Duplicates: 3" in summary
    assert "Errors: 2" in summary
    assert "Warnings: 1" in summary

