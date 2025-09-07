import os
from pathlib import Path

import pandas as pd

from app.services.data_service import DataService
from app.services.csv_import.csv_import_service import CSVImportService


BITUNIX_HEADERS = [
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


def write_csv(path: Path, rows):
    import csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(BITUNIX_HEADERS)
        for r in rows:
            w.writerow(r)


def test_validate_and_import_bitunix_csv(tmp_path: Path):
    # Set up a temporary data dir for DataService
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ds = DataService(str(data_dir))
    svc = CSVImportService(ds)

    # Create a tiny Bitunix-like CSV file
    rows = [
        [
            "2025-03-22 20:06:24+00:00",
            "ETHUSDT",
            "Long",
            "0.945",
            "ETH",
            "1994.15",
            "1995.75",
            "1.512",
            "-0.7502733",
            "2.2622733",
            "CROSS",
            "2025-03-22 19:57:05+00:00",
            "1885.98375",
        ],
        [
            "2025-03-24 10:32:39+00:00",
            "SOLUSDT",
            "Short",
            "5.9",
            "SOL",
            "139.6425",
            "141.2642",
            "-9.568",
            "-10.3035753",
            "0.7827775",
            "CROSS",
            "2025-03-24 04:20:47+00:00",
            "833.45878",
        ],
    ]
    csv_path = tmp_path / "bitunix.csv"
    write_csv(csv_path, rows)

    # Validate
    vres = svc.validate_csv_file(str(csv_path), exchange_name="bitunix")
    assert vres.is_valid is True

    # Preview
    preview = svc.preview_csv_data(str(csv_path), exchange_name="bitunix", rows=2)
    assert len(preview) == 2
    assert preview[0]["symbol"] == "ETHUSDT"

    # Import
    result = svc.import_csv_file(str(csv_path), exchange_name="bitunix")
    assert result.success is True
    assert result.imported_trades == 2
    assert result.duplicate_trades == 0
    assert result.total_rows == 2

    # Import again should yield duplicates
    result2 = svc.import_csv_file(str(csv_path), exchange_name="bitunix")
    assert result2.duplicate_trades == 2
    assert result2.imported_trades == 0


def test_within_file_duplicates_are_skipped(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ds = DataService(str(data_dir))
    svc = CSVImportService(ds)

    # Duplicate the exact same row twice
    row = [
        "2025-03-22 20:06:24+00:00",
        "ETHUSDT",
        "Long",
        "0.945",
        "ETH",
        "1994.15",
        "1995.75",
        "1.512",
        "-0.7502733",
        "2.2622733",
        "CROSS",
        "2025-03-22 19:57:05+00:00",
        "1885.98375",
    ]
    csv_path = tmp_path / "dups.csv"
    write_csv(csv_path, [row, row])

    res = svc.import_csv_file(str(csv_path), exchange_name="bitunix")
    assert res.total_rows == 2
    assert res.imported_trades == 1
    assert res.duplicate_trades == 1

    # Ensure persistence has no duplicate IDs
    trades = ds.load_trades()
    ids = [t.id for t in trades]
    assert len(ids) == len(set(ids))
