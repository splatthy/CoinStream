# Transaction/Order History CSV Import (MVP)

This app ingests exchange order/transaction history (fills) as the source of truth to reconstruct positions and persist closed trades. Position History imports are removed in this MVP.

## Supported Sources

- Bitunix futures-history (fills): `futures-history-*.csv`
  - Required headers: `date, side, futures, average price, executed, status`
  - Optional: `fee, realized p/l`
- Blofin order history (fills): `Order_history_*.csv`
  - Required headers: `Underlying Asset, Order Time, Side, Avg Fill, Filled, Status`
  - Optional: `Fee, PNL, Reduce-only, Margin Mode, Leverage`

The importer auto-detects the format from headers.

## How It Works

1) Normalize fills
- Unit stripping (e.g., `0.0312 USDT` → `0.0312`, `9621 ALT` → `9621`).
- Derive action/side:
  - Bitunix `side`: `Open/Close Long|Short` → (`open|close`, `long|short`).
  - Blofin `Side` + `Reduce-only`: `Open*` → `open`; `Close*` or `Reduce-only=Y` → `close`.
- Filter to `Status == Filled` and `quantity > 0`.

2) Deduplicate
- Canonical key with rounding tolerances (price 1e-6, qty/fee/pnl 1e-8) collapses re-exports.

3) Reconstruct positions
- Group by `(exchange, symbol, side[, margin_mode])` and process chronologically.
- Track entry VWAP, open/close fees, and realized PnL.
- Persist only fully closed positions as Trades; in-progress positions are preview-only.

4) Fees and PnL semantics
- If exchange provides realized PnL on close fills: treat as net and do not subtract fees again.
- If any PnL is missing: net = gross(VWAPs) − total fees.
- Persist a single `custom_fields['fees']` total per trade.

5) Risk snapshot (optional)
- If app config includes `portfolio_size` and `risk_percent`, each new closed trade gets:
  - `custom_fields['max_risk_per_trade'] = portfolio_size * (risk_percent/100)`
  - `custom_fields['risk_source'] = 'calculated'`

6) Audit trail and incremental imports
- Each import appends a JSONL entry at `data/import_logs.jsonl` with file metadata, counts, and a risk snapshot.
- The UI proposes a default “Start after” time based on the last import for the same `(exchange, account_label)`.

## Using the Import Page

1. Upload the CSV exported from your exchange (order/transaction history).
2. The app detects Bitunix/Blofin automatically; optionally set an Account Label.
3. Validate and Preview:
   - Preview Mode: choose “Reconstructed Positions” or “Raw Fills”.
   - Risk: when configured, preview shows a Max Risk column and flags breaches (`pnl < 0` and `abs(pnl) > max_risk`).
4. Import:
   - Optionally enable the time filter (default populated from the last import).
   - Confirm to persist closed trades.

## Notes & Limitations

- Only closed positions are persisted in this MVP.
- Unmatched close fills (no open basis) are ignored.
- Time parsing is normalized to UTC-naive datetimes.
- Multiple accounts on the same exchange: use Account Label to keep logs and incrementals distinct.

