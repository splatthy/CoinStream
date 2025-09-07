import pandas as pd
import pytest

from app.services.csv_import.models import ColumnMapping
from app.services.csv_import.csv_validator import CSVValidator
from app.utils.validators import ValidationError


def bitunix_mapping() -> ColumnMapping:
    return ColumnMapping(
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
    )


def test_validate_required_fields_success():
    validator = CSVValidator()
    mapping = bitunix_mapping()
    df = pd.DataFrame(
        {
            "Date": ["2024-01-02 03:04:05"],
            "symbol": ["BTCUSDT"],
            "side": ["Long"],
            "quantity": ["1.5"],
            "Entry Price": ["45000"],
            "Exit Price": ["46000"],
            "Net PnL": ["1500"],
            "Fees": ["5"],
            "Opening Date": ["2024-01-01 10:00:00"],
        }
    )

    res = validator.validate_required_fields(df, mapping)
    assert res.is_valid is True


def test_validate_required_fields_missing_values():
    validator = CSVValidator()
    mapping = bitunix_mapping()
    df = pd.DataFrame(
        {
            "Date": ["2024-01-02 03:04:05"],
            "symbol": ["BTCUSDT"],
            "side": ["Long"],
            "quantity": [""],  # missing
            "Entry Price": ["45000"],
            "Opening Date": ["2024-01-01 10:00:00"],
        }
    )

    res = validator.validate_required_fields(df, mapping)
    assert res.is_valid is False
    assert any("quantity" in str(e) for e in res.errors)


def test_validate_data_types_invalid_values():
    validator = CSVValidator()
    mapping = bitunix_mapping()
    df = pd.DataFrame(
        {
            "Date": ["2024-01-02 03:04:05"],
            "symbol": ["BTCUSDT"],
            "side": ["Hold"],  # invalid side
            "quantity": ["-2"],  # negative
            "Entry Price": ["abc"],  # not numeric
            "Opening Date": ["not-a-date"],  # invalid date
        }
    )

    res = validator.validate_data_types(df, mapping)
    assert res.is_valid is False
    msgs = [str(e) for e in res.errors]
    assert any("Invalid side" in m for m in msgs)
    assert any("must be positive" in m for m in msgs)
    assert any("Invalid numeric value for 'entry_price'" in m for m in msgs)
    assert any("Invalid entry_time" in m for m in msgs)


def test_detect_duplicates_by_symbol_and_entry_time():
    validator = CSVValidator()
    mapping = bitunix_mapping()
    df = pd.DataFrame(
        {
            "symbol": ["BTCUSDT", "BTCUSDT", "ETHUSDT"],
            "side": ["Long", "Short", "Long"],
            "quantity": ["1", "1", "2"],
            "Entry Price": ["45000", "44000", "2000"],
            "Opening Date": [
                "2024-01-01 10:00:00",
                "2024-01-01 10:00:00",  # duplicate with row 0 by (symbol, time)
                "2024-01-02 10:00:00",
            ],
        }
    )

    dups = validator.detect_duplicates(df, mapping)
    assert dups == [1]

