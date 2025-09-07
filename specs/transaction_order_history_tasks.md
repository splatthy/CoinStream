# Transaction/Order History Import — Task Breakdown (MVP + Post‑MVP)

This tasks document translates `specs/transaction_order_history_definition.md` into self‑contained, actionable units. Each task includes the context needed to work independently in a fresh chat.

References:
- Definition: `specs/transaction_order_history_definition.md`
- Current CSV stack: `app/services/csv_import/*`
- UI: `app/pages/csv_import.py`
- Trade model: `app/models/trade.py`
- Config service: `app/services/config_service.py`

Conventions:
- Persist only fully closed positions (MVP).
- Fees stored as single `custom_fields['fees']` stringified Decimal; do not double‑subtract when PnL provided by exchange.
- Time parsing to UTC, timezone‑naive.

---

## T1 — Exchange Detection and File Routing

- Summary: Detect Bitunix futures‑history and Blofin order history headers and route to the tx‑history ingestion path.
- Context: We are deprecating Position History imports. Input sources are fills (Bitunix `futures-history-*.csv`, Blofin `Order_history_*.csv`).
- Inputs (headers):
  - Bitunix: `date, side, futures, average price, executed, fee, realized p/l, status`.
  - Blofin: `Underlying Asset, Margin Mode, Leverage, Order Time, Side, Avg Fill, Filled, Fee, PNL, Reduce-only, Status`.
- Implementation:
  - Update `app/services/csv_import/column_mapper.py` or a new router to positively match the above headers.
  - Route to a new tx‑history path (normalizer → dedupe → reconstructor) instead of `DataTransformer.transform_row`.
- Acceptance:
  - Given either header set, service selects tx‑history path.
  - Non‑matching files raise a clear validation error with expected columns summary.

## T2 — Fills Normalizer (Unit Stripping + Action/Side Derivation)

- Summary: Parse raw CSV rows into normalized fills.
- Context: Definition → Normalized Fill Schema. Side/action rules:
  - Bitunix `side`: `Open Long/Short` → open; `Close Long/Short` → close.
  - Blofin `Side`: `Open*` → open, `Close*`/`Close*(SL)` → close; `Reduce-only == Y` forces close.
- Inputs:
  - Bitunix fields: `date, side, futures, average price, executed, fee, realized p/l, status`.
  - Blofin fields: `Order Time, Side, Underlying Asset, Avg Fill, Filled, Fee, PNL, Reduce-only, Status, Margin Mode, Leverage`.
- Implementation:
  - New module `app/services/csv_import/tx_history/normalizer.py` with a `normalize(file_df, exchange)` API returning a list of fills dicts with keys: `exchange, symbol, time, action, side, price, quantity, fee, pnl?, margin_mode?, leverage?, reduce_only?`.
  - Unit stripping helpers for values like `"0.0312 USDT"` and `"9621 ALT"`.
  - Filter to `Status == Filled` (or `FILLED`) and `quantity > 0`.
- Acceptance:
  - Sample rows from both CSVs produce expected normalized fills; numeric fields are Decimals (or serializable strings), symbols uppercased, actions and sides correct.

## T3 — Tolerant Dedupe Hashing for Fills

- Summary: Remove duplicate fills across re‑exports with rounding.
- Context: Definition → Deduplication Policy.
- Implementation:
  - New helper `app/services/csv_import/tx_history/dedupe.py` implementing rounded canonical string keys:
    - Bitunix key: `(date, futures, side, average price, executed, status[, fee])`.
    - Blofin key: `(Order Time, Underlying Asset, Side, Avg Fill, Filled, Status[, Fee])`.
  - Rounding constants: price 1e‑6, quantity 1e‑8, fee 1e‑8, pnl 1e‑8; whitespace collapse; uppercase symbols.
- Acceptance:
  - Duplicate lines in provided samples collapse to a single fill; non‑duplicates pass through.

## T4 — Position Reconstructor (State Machine)

- Summary: Reconstruct closed positions from normalized fills per `(symbol, side[, margin_mode])`.
- Context: Definition → Reconstruction Algorithm and PnL/Fees semantics.
- Implementation:
  - New module `app/services/csv_import/tx_history/reconstructor.py` with `reconstruct(fills)` → list of Closed Trade DTOs (not the model yet).
  - Track open_qty, entry_vwap, open_fees, close_fees, realized_pnl_sum, entry_time, exit_vwap, exit_time.
  - Use provided per‑fill PnL on close fills when present; else compute gross from VWAP and subtract accumulated fees to get net.
  - Emit trade when qty → 0 within tolerance; carry remaining states as in‑progress (returned separately for preview).
- Acceptance:
  - Sequences with scale‑in/out yield correct VWAPs, fees, and net PnL; in‑progress positions identified.

## T5 — CSVImportService Integration (Tx‑History Path)

- Summary: Wire normalization → dedupe → reconstruction into the import flow.
- Implementation:
  - Extend `CSVImportService` with a branch for tx‑history flow.
  - Preview: show Raw fills or Reconstructed Positions (toggle); mark computed values with 🧮.
  - Import: persist only closed trades via `DataService`.
- Acceptance:
  - Import summary reports total rows, deduped, closed persisted, open skipped, errors/warnings.

## T6 — Fees and PnL Semantics

- Summary: Align with exchange semantics where realized PnL is net of fees.
- Context: Exchange UIs indicate realized PnL includes fees (Bitunix: Closed PnL + Funding + Trading; Blofin: Closed PnL + Trading).
- Implementation:
  - When PnL provided: treat as net; do not subtract fees again. Persist `custom_fields['fees']` separately.
  - When PnL missing: compute gross (VWAPs), then net = gross − total_fees.
- Acceptance:
  - No double counting of fees; spot checks on sample rows match expected net behavior.

## T7 — Capital, Risk, and Max Loss Snapshot

- Summary: On import, attach `max_risk_per_trade` when app config has Capital and Risk %; support UI override.
- Implementation:
  - Config: read `portfolio_size` and `risk_percent` from `ConfigService` (or placeholder keys) to compute `estimated_risk_per_trade`.
  - On emitting Closed trades, set `custom_fields['max_risk_per_trade']` and `custom_fields['risk_source']='calculated'` when available.
  - Table UI: breach notice when `pnl < 0` and `abs(pnl) > max_risk_per_trade`.
  - Inline editor: allow manual edit; if user clicks Recalculate, recompute from current config and set `risk_source='calculated'`.
- Acceptance:
  - Trades created during import carry max risk when config exists; UI correctly flags breaches; manual override persists.

## T8 — Import Audit Trail and Incremental Window

- Summary: Record imports and suggest next time window.
- Implementation:
  - Model: simple import log persisted under `data/` (JSON or Parquet), capturing `import_id, timestamp, exchange, account_label?, file_hash, counts, risk_config_snapshot`.
  - Maintain `last_import_time` per `(exchange, account_label)`; propose default filter `time > last_import_time` in UI.
  - UI: optional `Account Label` on import form; disclaimer if empty and multiple accounts suspected.
- Acceptance:
  - After an import, a new log entry exists; subsequent import proposes a start time after the last one and is overrideable.

## T9 — UI Updates (Import + Preview + Risk)

- Summary: Update Streamlit page for tx‑history path, preview toggles, account label, and risk display.
- Implementation (in `app/pages/csv_import.py`):
  - Add Account Label field (optional) and surface exchange auto‑detection.
  - Preview toggle: Raw fills vs Reconstructed Positions (badges: 🧮 Derived, In‑Progress).
  - Risk: show `max_risk_per_trade` column and breach highlighting.
- Acceptance:
  - Users can label imports, see correct previews, and breach notices render for losses exceeding max risk.

## T10 — Tests (Units + Integration)

- Summary: Validate normalization, dedupe, reconstruction, risk, and import orchestration.
- Implementation:
  - Unit: normalizer (unit stripping, action/side), dedupe (rounding), reconstructor (VWAP/PnL/fees), risk snapshot logic.
  - Integration: end‑to‑end import on sample Bitunix and Blofin files; verify counts and stored trades.
- Acceptance:
  - All tests pass; coverage for core logic; sample inputs work as expected.

## T11 — Documentation and Templates

- Summary: Document CSV formats and onboarding new exchanges.
- Implementation:
  - Update `specs/transaction_order_history_definition.md` if needed.
  - Add format notes for Bitunix/Blofin order history (headers, field meanings, examples).
  - Developer notes: how to add a new exchange to the tx‑history path.
- Acceptance:
  - Docs render in repo; clearly describe inputs and behavior.

## T12 — Migration and Cleanup

- Summary: Remove Position History importer and Aggregated Positions view, and provide fresh‑start guidance.
- Implementation:
  - Hide/remove Position History code paths and UI toggles.
  - Add a brief note in README/USER_GUIDE about clearing previous data and re‑importing using tx‑history.
- Acceptance:
  - UI no longer shows Position History paths; app functions with tx‑history only.

---

# Post‑MVP Task Batch

- P1 — Portfolio & Risk Framework Expansion
  - Persist portfolio size and risk % in config UI; analytics cards; optional bulk “Recalculate risk for selected/all trades”.
- P2 — Position Sizing Calculator
  - Given entry/stop/tick value/leverage, recommend position size to adhere to `max_risk_per_trade`; allow applying to trade(s).
- P3 — Revised Export Strategy
  - Upsert window configuration; tolerant re‑ingest policies; account profiles for multi‑account workflows.
- P4 — Performance and UX
  - Chunked/stream processing for very large files; import cancellation and rollback; expanded UI tests.
- P5 — Additional Exchanges
  - Add more exchanges following the same normalized fill schema and state machine.

