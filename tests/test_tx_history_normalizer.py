from decimal import Decimal

import pandas as pd

from app.services.csv_import.tx_history.normalizer import normalize


def test_normalize_bitunix_basic():
    df = pd.DataFrame(
        [
            {
                "date": "2024-01-01 10:00:00",
                "side": "Open Long",
                "futures": "ETHUSDT",
                "average price": "2300.5",
                "executed": "2",
                "fee": "0.001",
                "realized p/l": "",
                "status": "FILLED",
            },
            {
                "date": "2024-01-01 11:00:00",
                "side": "Close Long",
                "futures": "ETHUSDT",
                "average price": "2310.5",
                "executed": "2",
                "fee": "0.002",
                "realized p/l": "20.0",
                "status": "FILLED",
            },
            # Not filled row should be ignored
            {
                "date": "2024-01-01 12:00:00",
                "side": "Open Long",
                "futures": "ETHUSDT",
                "average price": "2320",
                "executed": "1",
                "fee": "0.001",
                "realized p/l": "",
                "status": "CANCELLED",
            },
        ]
    )

    fills = normalize(df, "bitunix")
    assert len(fills) == 2
    f0, f1 = fills
    assert f0["exchange"] == "Bitunix"
    assert f0["symbol"] == "ETHUSDT"
    assert f0["action"] == "open"
    assert f0["side"] == "long"
    assert isinstance(f0["price"], Decimal)
    assert isinstance(f0["quantity"], Decimal)
    assert isinstance(f0["fee"], Decimal)
    assert f1["action"] == "close"
    assert f1.get("pnl") == Decimal("20.0")


def test_normalize_blofin_unit_stripping_and_reduce_only():
    df = pd.DataFrame(
        [
            {
                "Underlying Asset": "TIAUSDT",
                "Margin Mode": "Cross",
                "Leverage": "5",
                "Order Time": "01/02/2024 08:00:00",
                "Side": "Open Long",
                "Avg Fill": "0.0312 USDT",
                "Filled": "9621 ALT",
                "Fee": "1.23 USDT",
                "PNL": "",
                "Reduce-only": "N",
                "Status": "Filled",
            },
            {
                "Underlying Asset": "TIAUSDT",
                "Margin Mode": "Cross",
                "Leverage": "5",
                "Order Time": "01/02/2024 09:00:00",
                "Side": "Close Long(SL)",
                "Avg Fill": "0.0320 USDT",
                "Filled": "9621 ALT",
                "Fee": "0.77 USDT",
                "PNL": "-5.55 USDT",
                "Reduce-only": "Y",
                "Status": "Filled",
            },
        ]
    )

    fills = normalize(df, "blofin")
    assert len(fills) == 2
    f0, f1 = fills
    assert f0["exchange"] == "Blofin"
    assert f0["symbol"] == "TIAUSDT"
    assert f0["action"] == "open"
    assert f0["side"] == "long"
    assert f0["margin_mode"] == "Cross"
    assert f0["leverage"] == "5"
    assert f0["price"] == Decimal("0.0312")
    assert f0["quantity"] == Decimal("9621")
    # Reduce-only forces action=close
    assert f1["action"] == "close"
    assert f1["pnl"] == Decimal("-5.55")

