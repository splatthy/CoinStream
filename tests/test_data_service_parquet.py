from pathlib import Path

from app.services.data_service import DataService
from app.models.trade import Trade, TradeSide, TradeStatus
from decimal import Decimal
from datetime import datetime


def make_trade(i: int) -> Trade:
    return Trade(
        id=f"t{i}",
        exchange="bitunix",
        symbol="BTCUSDT",
        side=TradeSide.LONG,
        entry_price=Decimal("100.0"),
        quantity=Decimal("1.0"),
        entry_time=datetime(2024, 1, 1, 0, 0, 0),
        status=TradeStatus.OPEN,
    )


def test_parquet_store_roundtrip(tmp_path: Path):
    # Write config to select parquet backend
    cfg = tmp_path / "config.json"
    cfg.write_text('{"storage_backend": "parquet"}', encoding="utf-8")

    ds = DataService(str(tmp_path))

    # Save trades
    trades = [make_trade(1), make_trade(2)]
    ds.save_trades(trades)

    # Load trades
    loaded = ds.load_trades()
    assert len(loaded) == 2
    assert {t.id for t in loaded} == {"t1", "t2"}

