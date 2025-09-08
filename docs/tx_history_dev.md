# Tx-History Import — Developer Notes

This document outlines how the tx-history (fills) pipeline is structured and how to add new exchanges.

## Pipeline Overview

- Detection: `app/services/csv_import/tx_history/router.py`
  - Detects Bitunix/Blofin from headers. Add new patterns here.

- Normalization: `tx_history/normalizer.py`
  - `normalize(df, exchange)` → list[dict] fills with keys:
    - `exchange, symbol, time, action(open|close), side(long|short), price(Decimal), quantity(Decimal), fee(Decimal), pnl?(Decimal), margin_mode?, leverage?, reduce_only?, status`
  - Responsibilities: unit stripping, side/action derivation, filtering to `Filled` rows with `quantity > 0`.

- Dedupe: `tx_history/dedupe.py`
  - `dedupe_fills(fills)` rounds numerics and normalizes strings to build canonical keys.

- Reconstruction: `tx_history/reconstructor.py`
  - VWAP-based state machine per `(exchange, symbol, side[, margin_mode])`.
  - Emits `ClosedTradeDTO` and `InProgressPositionDTO`.
  - PnL: trust provided realized PnL (net); otherwise compute gross(VWAPs) − total fees.

- Service and Integration:
  - Preview: `tx_history/service.py` supports Raw vs Reconstructed modes.
  - Import: `CSVImportService.import_csv_file()` wires normalize → dedupe → reconstruct → persist.
  - Risk snapshot: attaches `max_risk_per_trade` when available.
  - Audit log: JSONL entries via `tx_history/import_log.py`.

## Adding a New Exchange

1. Detection
   - Update `router.py` to recognize the new header set.
   - Provide a concise `expected_columns_summary()` update if needed.

2. Normalizer
   - Add branch in `normalizer.normalize()` for the new `exchange`.
   - Map raw columns → normalized fields; implement unit stripping and action/side rules.
   - Filter to `Status == Filled` (or equivalent) and `quantity > 0`.

3. Dedupe Key
   - Ensure the normalized fields align with canonical key fields: time, symbol, action/side, price, quantity, status, optional fee.
   - Adjust rounding tolerances if necessary (defaults usually suffice).

4. Reconstruction
   - No changes typically required; it’s exchange-agnostic once normalized.

5. Tests
   - Add unit tests for normalization (and any parsing helpers), dedupe edge cases, and reconstructor coverage.
   - Add an integration test exercising the full flow on a small CSV.

## Testing & Validation

- Run unit tests and integration tests: `pytest -q`.
- Verify preview modes in UI (Raw vs Reconstructed).
- Confirm audit log entries and last-import time suggestion.

## Gotchas

- PnL semantics vary: confirm whether exchange “realized PnL” includes fees; if it does, do not subtract fees again.
- Reduce-only semantics: close action even if side says “Open”.
- Timezones: normalize to UTC-naive; ensure consistent parsing across formats.

