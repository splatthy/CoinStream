from pathlib import Path

from app.services.data_service import DataService
from app.services.csv_import.csv_import_service import CSVImportService


def test_import_bitunix_new_export(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ds = DataService(str(data_dir))
    svc = CSVImportService(ds)

    # Use real sample file from repo root
    csv_path = Path("Bitunix_Export_Sample.csv")
    assert csv_path.exists(), "Bitunix_Export_Sample.csv should exist in repo root"

    res = svc.import_csv_file(str(csv_path), exchange_name="bitunix")
    assert res.total_rows > 0
    assert res.imported_trades > 0

    trades = ds.load_trades()
    assert len(trades) == res.imported_trades
    t = trades[0]
    # Futures parsed correctly
    assert t.symbol.endswith("USDT")
    assert t.side.value in ("long", "short")
    # Quantity parsed from "closed amount"
    assert t.quantity is not None
    # Entry/exit prices parsed
    assert t.entry_price is not None
    # PnL present from realized pnl
    assert t.pnl is not None

