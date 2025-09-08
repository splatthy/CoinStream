from decimal import Decimal

from app.services.csv_import.tx_history.dedupe import dedupe_fills, key_for_fill


def test_dedupe_rounding_tolerance():
    base = {
        "exchange": "Bitunix",
        "symbol": "ALTUSDT",
        "time": __import__("datetime").datetime(2024, 1, 2, 12, 0, 0),
        "action": "open",
        "side": "long",
        "price": Decimal("0.123456789"),
        "quantity": Decimal("100.000000009"),
        "fee": Decimal("0.0000000099"),
        "status": "FILLED",
    }
    slight = {
        **base,
        "price": Decimal("0.123456780"),  # within 1e-6 rounding
        "quantity": Decimal("100.000000001"),
        "fee": Decimal("0.0000000091"),
    }

    fills = [base, slight]
    unique, dup = dedupe_fills(fills)
    assert len(unique) == 1
    assert dup == 1

