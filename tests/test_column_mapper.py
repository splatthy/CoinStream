from app.services.csv_import.column_mapper import ColumnMapper, COMMON_COLUMN_PATTERNS
from app.services.csv_import.models import ColumnMapping
from app.utils.validators import ValidationError


def test_load_bitunix_template_and_validate():
    mapper = ColumnMapper()
    mapping = mapper.load_template("bitunix")
    assert isinstance(mapping, ColumnMapping)

    headers = [
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

    # Should validate against headers without error
    mapping.validate_against_headers(headers)

    # create_mapping with exchange enforces strict header presence (MVP policy)
    out = mapper.create_mapping(headers, exchange_name="bitunix")
    assert out.symbol == "symbol"
    assert out.entry_price == "Entry Price"


def test_suggest_mapping_from_patterns():
    mapper = ColumnMapper()
    headers = [
        "Pair",
        "Direction",
        "Amount",
        "Open",
        "Close",
        "Open Time",
        "Close Time",
        "Profit_Loss",
    ]
    mapping = mapper.suggest_mapping(headers)
    assert mapping.symbol.lower() == "pair".lower()
    assert mapping.side.lower() == "direction".lower()
    assert mapping.quantity.lower() == "amount".lower()
    assert mapping.entry_price.lower() in ("open", "open price")
    assert mapping.exit_price.lower() in ("close", "close price")
    assert mapping.entry_time.lower() in ("open time", "entry time")


def test_create_mapping_template_missing_headers_raises():
    mapper = ColumnMapper()
    headers = ["symbol", "side", "quantity", "Entry Price"]  # missing Opening Date
    try:
        mapper.create_mapping(headers, exchange_name="bitunix")
        assert False, "Expected ValidationError due to missing required header"
    except ValidationError:
        pass

