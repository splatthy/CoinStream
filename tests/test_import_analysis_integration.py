from pathlib import Path

from app.services.data_service import DataService
from app.services.csv_import.csv_import_service import CSVImportService
from app.services.analysis_service import AnalysisService


HEADERS = [
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
        w.writerow(HEADERS)
        for r in rows:
            w.writerow(r)


def test_import_then_analyze(tmp_path: Path):
    # Arrange services
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ds = DataService(str(data_dir))
    cis = CSVImportService(ds)
    analysis = AnalysisService(ds)

    # Create a small CSV with one closed trade
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
    csv_path = tmp_path / "sample.csv"
    write_csv(csv_path, [row])

    # Act: Import
    res = cis.import_csv_file(str(csv_path), exchange_name="bitunix")
    assert res.success is True
    assert res.imported_trades == 1

    # Load and analyze
    trades = ds.load_trades()
    assert len(trades) == 1
    t = trades[0]
    # Fees from CSV preserved in custom_fields
    assert t.custom_fields.get("fees") == "2.2622733"
    # PnL present
    assert t.pnl is not None

    # Trend analysis should return one data point
    trend = analysis.calculate_pnl_trend(trades, timeframe="daily")
    assert len(trend) == 1
    # Confluence analysis should work even if no confluences are set
    confl = analysis.analyze_confluences(trades)
    assert isinstance(confl, list)

