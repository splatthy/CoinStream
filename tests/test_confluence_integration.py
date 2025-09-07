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


def test_confluence_analysis_after_ui_update(tmp_path: Path):
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
        "0.5",
        "ETH",
        "2000",
        "2100",
        "50",
        "50",
        "2",
        "CROSS",
        "2025-03-22 19:57:05+00:00",
        "1000",
    ]
    csv_path = tmp_path / "one.csv"
    write_csv(csv_path, [row])

    # Import
    res = cis.import_csv_file(str(csv_path), exchange_name="bitunix")
    assert res.success is True
    trades = ds.load_trades()
    assert len(trades) == 1
    t = trades[0]

    # Simulate UI: user sets confluences on the imported trade
    updated = ds.update_trade(t.id, {"confluences": ["Support/Resistance", "RSI"]})
    assert "Support/Resistance" in updated.confluences

    # Analyze confluences
    metrics = analysis.analyze_confluences(ds.load_trades())
    names = [m.confluence for m in metrics]
    assert "Support/Resistance" in names

