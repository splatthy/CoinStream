# Transaction/Order History Importer — MVP Definition

This document defines the MVP ingestion path that treats transaction/order history (fills) as the canonical source of truth for reconstructing positions and persisting trades in the journal. Position History and the Aggregated Positions view are removed from scope for this phase.

## Goals
- Canonicalize on fills (order/transaction history) across exchanges.
- Reconstruct true positions (open → scale-in → partial closes → full close) with accurate VWAPs, realized PnL, and total fees.
- Persist only fully closed positions as `Trade` records; show open/in-progress positions in preview but do not persist (MVP).
- Normalize fees into a single `custom_fields['fees']` stringified Decimal total.
- Provide resilient header detection, unit stripping, tolerant deduplication, and deterministic behavior for re-exports.
 - Add import-time risk sizing support to compute a per-trade maximum loss threshold when user risk settings are available; allow manual override in UI.

## Supported Inputs (MVP)
- Bitunix (Transaction/Order History): `futures-history-*.csv`
  - Headers include: `date, side, futures, average price, executed, fee, realized p/l, status`.
  - Use rows where `status == FILLED` and `executed > 0`.
- Blofin (Order History): `Order_history_*.csv`
  - Headers include: `Underlying Asset, Margin Mode, Leverage, Order Time, Side, Avg Fill, Filled, Fee, PNL, Reduce-only, Status`.
  - Use rows where `Status == Filled` and `Filled > 0`.

### Exchange-Specific Parsing Rules (Implementation)

Bitunix futures-history (fills):
- `symbol` ← `futures`
- `time` ← `date`
- Derive `(action, side)` from `side` values:
  - `Open Long` → (`open`, `long`), `Open Short` → (`open`, `short`)
  - `Close Long` → (`close`, `long`), `Close Short` → (`close`, `short`)
- `price` ← `average price` (Decimal)
- `quantity` ← `executed` (Decimal)
- `fee` ← `fee` (Decimal; 0 if blank)
- `pnl` ← `realized p/l` where present on close fills (optional)
- Filter: `status == FILLED` and `executed > 0`

Blofin order history (fills):
- `symbol` ← `Underlying Asset`
- `time` ← `Order Time`
- Derive `(action, side)` from `Side` and `Reduce-only`:
  - `Open Long`, `Open Short` → `open`
  - `Close Long`, `Close Short`, `Close Long(SL)`, `Close Short(SL)` → `close`
  - If `Reduce-only == Y`, force `action=close`
- `price` ← `Avg Fill` (strip trailing unit, e.g., `USDT`)
- `quantity` ← `Filled` (strip trailing asset unit)
- `fee` ← `Fee` (strip unit)
- `pnl` ← `PNL` where present on close fills (optional)
- Optional: `margin_mode` ← `Margin Mode`; `leverage` ← `Leverage`; `reduce_only` from column
- Filter: `Status == Filled` and parsed `quantity > 0`

## Normalized Fill Schema (internal)
For reconstruction, each fill is normalized into:
- `exchange`: source name (e.g., `Bitunix`, `Blofin`).
- `symbol`: instrument (e.g., `TIAUSDT`, `ALTUSDT`).
- `time`: parsed UTC-naive datetime (robust parser; multiple formats allowed).
- `action`: `open` | `close` (derived from `side`/`reduce-only` semantics).
- `side`: `long` | `short` (position direction, not order side).
- `price`: Decimal (unit-stripped, e.g., `0.0312`).
- `quantity`: Decimal executed amount (unit-stripped, e.g., `9621`).
- `fee`: Decimal (per-fill; accumulates into position fees).
- `pnl`: Optional Decimal (per-fill; prefer provided on close fills; otherwise compute when reconstructing).
- `margin_mode`: Optional string (e.g., `Cross`).
- `leverage`: Optional string/number for reference.
- `reduce_only`: Optional bool (Blofin `Y/N`).
- `status`: raw status for filtering (must be `Filled`/`FILLED`).

Unit stripping examples:
- Blofin `Avg Fill`: "0.0312 USDT" → `0.0312`.
- Blofin `Filled`: "9621 ALT" → `9621`.
- Fees/PNL: strip trailing currency (e.g., `USDT`) if present.

## Deduplication Policy
- Purpose: tolerate re-exports and minor formatting deltas.
- Hash keys (rounded values and canonicalized strings):
  - Bitunix: `(date, futures, side, average price, executed, status[, fee])`.
  - Blofin: `(Order Time, Underlying Asset, Side, Avg Fill, Filled, Status[, Fee])`.
- Rounding tolerances (configurable constants):
  - `price`: round to 1e-6, `quantity`: 1e-8, `fee`: 1e-8, `pnl`: 1e-8.
- String normalization: trim spaces, collapse multiple spaces, uppercase symbols, normalize side tokens.
- Optional “upsert window” (future): ignore duplicates inside the last N days when re-importing.

### Audit Trail and Incremental Imports
- Keep an immutable import log (audit trail) capturing: `import_id`, `timestamp`, `exchange`, optional `account_label`, file metadata (name, size, hash), counts (rows parsed/deduped/persisted/skipped), and config snapshot (risk settings used).
- Track `last_import_time` per `(exchange[, account_label])` to propose the next import’s default time filter: `fill.time > last_import_time`.
- UI: allow overriding the default time filter for backfills.
- Multiple accounts on the same exchange:
  - Add optional `account_label` field (user-provided during import) to namespace dedupe and incremental windows.
  - If the user imports multiple accounts without labeling, behavior may interleave and produce gaps; show a disclaimer and recommend labeling or importing accounts separately.
  - Post-MVP: persist account profiles to avoid repeated manual entry.

## Reconstruction Algorithm (State Machine)
State by key: `(symbol, side[, margin_mode])`.

- On `open` fill:
  - Increase `open_qty`.
  - Update `entry_vwap` = weighted by fill `quantity`.
  - Accumulate `open_fees`.
  - Set `entry_time` if first open fill.

- On `close` fill:
  - If `open_qty == 0`: treat as no-op for reconstruction (or log warning).
  - Reduce `open_qty` by `fill.quantity` (clamp at 0 if small rounding drift).
  - Track `close_fees` and (if provided) `fill.pnl` into `realized_pnl_sum`.
  - If `fill.pnl` missing, compute realized component for the closed size using current `entry_vwap` and `fill.price`.
  - Maintain `exit_vwap` over the sequence of close fills that contribute to full closure.
  - Update `exit_time` to the latest close fill used to reach zero.

- When `open_qty → 0` (within tolerance):
  - Emit a Closed Trade with:
    - `entry_time`: first open fill time
    - `exit_time`: last close fill time that zeroed the position
    - `entry_price`: `entry_vwap`
    - `exit_price`: `exit_vwap`
    - `quantity`: total closed amount
    - `pnl`: `realized_pnl_sum` (provided per-fill where available; otherwise computed)
    - `custom_fields['fees']`: `open_fees + close_fees` (stringified Decimal)
    - `custom_fields['margin_mode']`: if available
  - Reset state for potential subsequent cycles.

- End-of-file with `open_qty > 0`:
  - Mark as in-progress (do not persist in MVP).

### PnL and Fees Semantics
- Prefer provided realized PnL from the exchange on close fills and at the reconstructed trade level; we assume it is net of fees for both Bitunix and Blofin based on UI/tooltips.
- Still accumulate and persist total `fees` separately for transparency and analytics; do not subtract fees again from provided PnL (avoid double counting).
- When PnL is missing and we must compute:
  - Compute gross realized PnL from entry VWAP and close prices on the closed quantity.
  - If fee totals are available, compute net PnL = gross − total_fees to match exchange semantics.
  - Store the resulting net PnL in the trade and keep `fees` as a separate custom field.

Action mapping by exchange:
- Bitunix `side`: values like `Open Long`, `Open Short`, `Close Long`, `Close Short` → map to `(action, side)`.
- Blofin `Side` examples:
  - `Open Long`, `Open Short` → `open`.
  - `Close Long`, `Close Short`, `Close Long(SL)`, `Close Short(SL)` → `close` (treat SL as close).
  - `Reduce-only` column (Y/N): when `Y`, force `action=close`.

## Trade Output Schema
Persisted model is `app/models/trade.py`:
- `exchange`, `symbol`, `side` (enum), `entry_price`, `quantity`, `entry_time`.
- `status=closed` for persisted records; requires `exit_price`, `exit_time`, and `pnl`.
- `custom_fields`: include `fees` (single total) and optional `margin_mode`, `leverage`.
  - Optional: `account_label` when supplied during import to scope audit trail and incremental windows.

MVP persistence rule: Only fully closed positions are stored. Open/in-progress positions appear in preview with a banner and are skipped from persistence.

## Capital, Risk, and Max Loss (MVP + UI Override)

Purpose: compare realized losses against the user’s maximum defined risk per trade.

- User config (from Config panel):
  - `portfolio_size` (Decimal)
  - `risk_percent` (Decimal percent, e.g., 1.0 = 1%)
  - Derived helper: `estimated_risk_per_trade = portfolio_size * (risk_percent / 100)`

- Import-time behavior:
  - If `estimated_risk_per_trade` is available, set `custom_fields['max_risk_per_trade']` on emitted Closed trades to the stringified Decimal value.
  - If not configured, leave `max_risk_per_trade` absent.

- UI behavior (table rendering):
  - Compute `actual_loss = abs(pnl)` only when `pnl < 0`.
  - Breach rule: raise a notice if `actual_loss > max_risk_per_trade`.
    - Note: This clarifies breach detection as “actual exceeds allowed”.
  - Display a subtle badge when `max_risk_per_trade` is missing (no config) to encourage setup.

- Per-trade override (manual):
  - Allow editing `max_risk_per_trade` per trade from the inline editor (manual value wins).
  - Provide a “Recalculate” helper that refills the field using current app config (portfolio size × risk %). Users may accept or overwrite.
  - Track provenance in `custom_fields['risk_source']` = `calculated` | `manual`.

- User workflow clarification:
  - Config panel provides a calculator: user enters `Capital` and `Risk %`; clicking Calculate sets the app-level "Max Capital Risk" value (`estimated_risk_per_trade`).
  - The same value can be typed directly without using the calculator.
  - At import time, we snapshot the current app-level value into each new closed trade’s `max_risk_per_trade`. Existing trades are not auto-updated when settings change.
  - Post-MVP: add bulk “Recalculate risk for selected/all trades” to re-apply current settings.

- Future (Post-MVP):
  - Position sizing calculator: suggest optimal trade size to adhere to strategy risk, considering entry, stop, and tick value. Populate or update `max_risk_per_trade` accordingly.

## Fees Normalization
- Always persist a single total fee: `custom_fields['fees']`.
- Sum all per-fill `fee` components across the reconstructed position (open + close). If an exchange provides separate fee types (e.g., funding), include them when present.
- Store as stringified Decimal (consistent with current importer policy).

## File Detection & Routing
- Bitunix tx-history: detect `date, side, futures, average price, executed, status` headers → route to fills reconstructor.
- Blofin order history: detect `Underlying Asset, Order Time, Side, Avg Fill, Filled, Reduce-only, Status` → route to fills reconstructor.
- Unknown CSV: future pattern-based mapping to normalized fills (not required for MVP).

## Time & Timezone Handling
- Parse all timestamps to UTC and store as timezone-naive UTC datetimes.
- Accept common formats, including Blofin’s `MM/DD/YYYY HH:MM:SS`.

## UI/UX Notes
- CSV Import page shows:
  - Source detection (Bitunix/Blofin).
  - Preview: Raw fills vs Reconstructed Positions (toggle).
  - Badges: 🧮 “Derived” when PnL is computed; “In-Progress” for non-zero open qty.
- Import action persists only reconstructed Closed positions; summary shows counts for closed persisted vs open skipped.
- Inline editor exposes `max_risk_per_trade` with a calculator button; save writes to `custom_fields` preserving `risk_source`.
 - Import form adds optional `Account Label` field to scope dedupe/incremental windows; show disclaimers when left empty but multiple accounts are suspected.

## Error Handling & Validation
- Filter-only `Filled` rows with executed quantity > 0.
- Validate numeric fields after unit stripping; produce row-level warnings for non-blocking issues.
- Deduplicate fills using tolerant hash before reconstruction.
- Guard against negative or zero quantities; clamp tiny negative remainders due to rounding.

## Edge Cases
- Scale-in/scale-out sequences with interleaved fees and partial PnL rows.
- Stop-loss/Reduce-only closes (`Close Short(SL)`) treated as `close` events.
- Missing per-fill PnL: compute realized components from VWAP.
- Revised exports: duplicates handled by tolerant hashing; optional upsert window in future.

## Migration Plan (MVP)
- Remove Position History importer and Aggregated Positions view from UI.
- Clear existing imported data (user is fine starting fresh).
- Introduce two exchange profiles in UI: “Bitunix (Order/Tx History)” and “Blofin (Order History)”.

## Implementation Plan (MVP)
1. Detection & Normalization
   - Add exchange detection for Bitunix futures-history and Blofin order history.
   - Implement `FillsNormalizer` to parse, unit-strip, derive `(action, side)`, attach optional fields, and emit normalized fills.
   - Implement tolerant hashing for dedupe pre-reconstruction.
2. Reconstruction & Persistence
   - Implement `PositionReconstructor` state machine and emit Closed trades.
   - Compute and attach `custom_fields['fees']` and, if available, `custom_fields['max_risk_per_trade']`.
   - Persist only Closed trades; count in-progress as preview-only.
3. UI
   - Preview toggle: Raw fills vs Reconstructed Positions with badges.
   - Risk breach highlighting in table when `actual_loss > max_risk_per_trade`.
   - Inline override for `max_risk_per_trade` + “Recalculate” helper.
4. Tests
   - Normalization (Bitunix/Blofin), reconstruction (scale-in/out), fees aggregation, dedupe tolerance.
   - Risk persistence and breach logic.

## Post-MVP Tasks (Batched)
- P1.7 Portfolio Size & Risk Framework (expand)
  - Persist portfolio size and risk % in config, show analytics cards, and portfolio curve groundwork.
  - Integrate position sizing calculator (entry, stop, leverage) to suggest size and update max risk.
- P1.8 Partial-close reconciliation & revised export policy
  - Tolerant hashing windows and upsert strategy for re-exports.
- Performance/UX
  - Chunked/streaming processing for very large files; import cancellation/rollback; broader UI tests.

## Next Steps
1. Add mapping detection for Blofin and Bitunix tx-history.
2. Implement `FillsNormalizer` (unit stripping, action/side derivation, dedupe hashing).
3. Implement `PositionReconstructor` (state machine) and emit Closed `Trade`s.
4. Wire CSV import service path for tx-history.
5. Update UI preview toggle and import summaries.
6. Tests: normalization, reconstruction (scale-in/out), PnL/fees aggregation, dedupe tolerance.
