from decimal import Decimal
from datetime import datetime

from app.services.csv_import.tx_history.reconstructor import reconstruct


def test_reconstruct_simple_long_with_scale_in_and_close():
    fills = [
        {
            "exchange": "Bitunix",
            "symbol": "BTCUSDT",
            "time": datetime(2024, 1, 1, 10, 0, 0),
            "action": "open",
            "side": "long",
            "price": Decimal("10"),
            "quantity": Decimal("100"),
            "fee": Decimal("1.0"),  # open fee
            "status": "FILLED",
        },
        {
            "exchange": "Bitunix",
            "symbol": "BTCUSDT",
            "time": datetime(2024, 1, 1, 11, 0, 0),
            "action": "open",
            "side": "long",
            "price": Decimal("12"),
            "quantity": Decimal("50"),
            "fee": Decimal("0.5"),  # open fee
            "status": "FILLED",
        },
        {
            "exchange": "Bitunix",
            "symbol": "BTCUSDT",
            "time": datetime(2024, 1, 1, 12, 0, 0),
            "action": "close",
            "side": "long",
            "price": Decimal("11"),
            "quantity": Decimal("150"),
            "fee": Decimal("0.6"),  # close fee
            "status": "FILLED",
        },
    ]

    closed, in_progress = reconstruct(fills)
    assert len(closed) == 1
    t = closed[0]
    assert t.symbol == "BTCUSDT"
    assert t.side == "long"
    assert t.quantity == Decimal("150")
    # Entry VWAP = (100*10 + 50*12) / 150 = 10.6666666667
    assert t.entry_price.quantize(Decimal("0.00000001")) == Decimal("10.66666667")
    assert t.exit_price == Decimal("11")
    # Total fees = 1.0 + 0.5 + 0.6 = 2.1
    assert t.fees_total == Decimal("2.1")
    # PnL (calculated): gross = (11 - 10.6666666667) * 150 = 50; net = 50 - 2.1 = 47.9
    assert t.pnl.quantize(Decimal("0.00000001")) == Decimal("47.90000000")
    assert t.pnl_source == "calculated"
    assert not in_progress

