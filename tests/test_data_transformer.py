from decimal import Decimal
from datetime import datetime

import pandas as pd

from app.services.csv_import.models import ColumnMapping
from app.services.csv_import.data_transformer import DataTransformer
from app.models.trade import TradeStatus, TradeSide


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


def test_transform_row_closed_trade_with_pnl():
    tr = DataTransformer()
    mapping = bitunix_mapping()
    row = pd.Series(
        {
            "symbol": "ETHUSDT",
            "side": "Long",
            "quantity": "0.945",
            "Entry Price": "1994.15",
            "Opening Date": "2025-03-22 19:57:05+00:00",
            "Exit Price": "1995.75",
            "Date": "2025-03-22 20:06:24+00:00",
            "Net PnL": "-0.7502733",
            "Fees": "2.2622733",
        }
    )

    trade = tr.transform_row(row, mapping, exchange="bitunix")
    assert trade.exchange == "bitunix"
    assert trade.symbol == "ETHUSDT"
    assert trade.side == TradeSide.LONG
    assert trade.quantity == Decimal("0.945")
    assert trade.entry_price == Decimal("1994.15")
    assert trade.status == TradeStatus.CLOSED
    # Datetimes should be naive UTC
    assert trade.entry_time.tzinfo is None
    assert trade.exit_time.tzinfo is None
    assert isinstance(trade.pnl, Decimal)
    assert trade.custom_fields.get("fees") == "2.2622733"
    # Deterministic ID
    trade2 = tr.transform_row(row, mapping, exchange="bitunix")
    assert trade.id == trade2.id


def test_transform_row_calculates_pnl_when_missing():
    tr = DataTransformer()
    mapping = bitunix_mapping()
    row = pd.Series(
        {
            "symbol": "BTCUSDT",
            "side": "Short",
            "quantity": "0.0229",
            "Entry Price": "87054.4",
            "Opening Date": "2025-03-25 12:35:27+00:00",
            "Exit Price": "85249.5",
            "Date": "2025-03-28 09:18:56+00:00",
            # No Net PnL provided
        }
    )

    trade = tr.transform_row(row, mapping, exchange="bitunix")
    assert trade.status == TradeStatus.CLOSED
    # For short: (entry - exit) * qty
    expected = (Decimal("87054.4") - Decimal("85249.5")) * Decimal("0.0229")
    assert trade.pnl == expected


def test_transform_row_open_trade_when_exit_missing():
    tr = DataTransformer()
    mapping = bitunix_mapping()
    row = pd.Series(
        {
            "symbol": "SUIUSDT",
            "side": "Long",
            "quantity": "100",
            "Entry Price": "2.25",
            "Opening Date": "2025-03-29 20:13:15+00:00",
            # Missing Exit Price and Date
        }
    )

    trade = tr.transform_row(row, mapping, exchange="bitunix")
    assert trade.status == TradeStatus.OPEN
    assert trade.exit_price is None
    assert trade.exit_time is None
    assert trade.pnl is None

