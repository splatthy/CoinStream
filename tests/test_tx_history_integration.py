import os
from decimal import Decimal
from pathlib import Path

import pandas as pd

from app.services.csv_import.csv_import_service import CSVImportService
from app.services.data_service import DataService
from app.services.config_service import ConfigService


def write_csv(tmpdir: str, filename: str, rows):
    import csv
    path = Path(tmpdir) / filename
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "side",
                "futures",
                "average price",
                "executed",
                "fee",
                "realized p/l",
                "status",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return str(path)


def test_tx_history_end_to_end_bitunix(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Minimal CSV representing a closed long
    csv_path = write_csv(
        tmp_path,
        "futures-history-sample.csv",
        [
            {
                "date": "2024-01-01 10:00:00",
                "side": "Open Long",
                "futures": "ALTUSDT",
                "average price": "1.0000",
                "executed": "10",
                "fee": "0.01",
                "realized p/l": "",
                "status": "FILLED",
            },
            {
                "date": "2024-01-01 11:00:00",
                "side": "Close Long",
                "futures": "ALTUSDT",
                "average price": "1.2000",
                "executed": "10",
                "fee": "0.02",
                "realized p/l": "2.0",
                "status": "FILLED",
            },
        ],
    )

    data_service = DataService(str(data_dir))
    config_service = ConfigService(str(data_dir))
    config_service.update_app_config({"portfolio_size": "1000", "risk_percent": "1.0"})

    svc = CSVImportService(data_service, config_service)

    result = svc.import_csv_file(csv_path, exchange_name="bitunix")
    assert result.success is True
    assert result.imported_trades == 1

    trades = data_service.load_trades()
    assert len(trades) == 1
    t = trades[0]
    assert t.exchange.lower() == "bitunix"
    assert t.symbol == "ALTUSDT"
    assert t.status.value == "closed"
    # Check fees and risk snapshot are present
    assert t.custom_fields.get("fees") == "0.03"
    assert t.custom_fields.get("max_risk_per_trade") == "10"
    assert t.custom_fields.get("risk_source") == "calculated"

