"""
CSV Import page: Upload → Select Exchange → Validate → Preview → Import.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List

import streamlit as st

from app.services.csv_import.csv_import_service import CSVImportService
from app.services.data_service import DataService
from app.services.config_service import ConfigService


PAGE_KEY = "csv_import_state"


def _get_services() -> Dict[str, Any]:
    app_state = st.session_state.get("app_state")
    if not app_state or not app_state.data_service:
        st.error("Services not initialized. Please refresh the page.")
        st.stop()
    data_service: DataService = app_state.data_service
    config_service: ConfigService = app_state.config_service
    import_service = CSVImportService(data_service, config_service)
    return {"data_service": data_service, "config_service": config_service, "import_service": import_service}


def _init_state() -> None:
    if PAGE_KEY not in st.session_state:
        st.session_state[PAGE_KEY] = {
            "file_path": None,
            "file_info": None,
            "selected_exchange": None,
            "validation": None,
            "preview": None,
            "import_result": None,
        }


def _set_state(**kwargs) -> None:
    st.session_state[PAGE_KEY].update(kwargs)


def _estimate_row_count(file_path: str) -> int:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            # Subtract header line
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return 0


def _save_uploaded_file(upload) -> Dict[str, Any]:
    # Persist uploaded file to a temp path (tmpfs in Docker Compose)
    suffix = os.path.splitext(upload.name)[-1] or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(upload.getbuffer())
        path = tmp.name
    info = {
        "name": upload.name,
        "size": len(upload.getbuffer()),
        "path": path,
    }
    return info


def _render_step_indicator(current_step: int) -> None:
    steps = [
        "Upload",
        "Select Exchange",
        "Validate",
        "Preview",
        "Import",
    ]
    cols = st.columns(len(steps))
    for i, (label, col) in enumerate(zip(steps, cols), start=1):
        with col:
            marker = "●" if i <= current_step else "○"
            st.markdown(f"**{marker} {label}**")


def handle_import_workflow():
    services = _get_services()
    import_service: CSVImportService = services["import_service"]

    state = st.session_state[PAGE_KEY]
    st.info(
        "This importer now uses Transaction/Order History (fills) as the source of truth. "
        "Position History imports have been removed. If you previously imported Position History, consider backing up and re-importing using fills."
    )
    step = 1

    st.subheader("Step 1 of 5: Upload CSV File")
    _render_step_indicator(step)
    upload = st.file_uploader("Select a CSV file", type=["csv"], accept_multiple_files=False)

    if upload is not None and st.button("Use This File"):
        info = _save_uploaded_file(upload)
        _set_state(file_path=info["path"], file_info=info, validation=None, preview=None, import_result=None)
        st.success(f"Loaded {info['name']} ({info['size']} bytes)")
        st.rerun()

    file_path = state["file_path"]
    if not file_path:
        return

    # Step 2: Source Detection (tx-history only)
    step = 2
    st.subheader("Step 2 of 5: Source Detection")
    _render_step_indicator(step)
    from app.services.csv_import.csv_parser import CSVParser
    from app.services.csv_import.tx_history.router import detect_tx_history

    try:
        headers = list(CSVParser().parse_csv_file(file_path).columns)
        detected = detect_tx_history(headers)
    except Exception as e:
        detected = None

    if not detected:
        st.error("Unsupported CSV format. This importer now only supports Transaction/Order History (fills) for Bitunix/Blofin.")
        st.info("Please export the appropriate order/transaction history CSV from your exchange and try again.")
        return

    st.success(f"Detected tx-history format: {detected}")
    account_label = st.text_input(
        "Account Label (optional)",
        value=state.get("account_label") or "",
        help="If you manage multiple accounts on the same exchange, label this import to keep audit and incremental windows separate.",
    )
    if st.button("Confirm Source"):
        _set_state(selected_exchange=detected.lower(), account_label=(account_label.strip() or None), validation=None, preview=None, import_result=None)
        st.rerun()

    selected_exchange = state["selected_exchange"]
    if not selected_exchange:
        return

    # Step 3: Validate
    step = 3
    st.subheader("Step 3 of 5: Validate File")
    _render_step_indicator(step)
    if st.button("Run Validation"):
        vres = import_service.validate_csv_file(file_path, selected_exchange)
        _set_state(validation=vres)
        st.rerun()

    vres = state["validation"]
    if vres is None:
        return

    if not vres.is_valid:
        st.error("Validation failed:")
        for e in vres.errors:
            st.write(f"- {e}")
        return
    else:
        st.success("Validation succeeded")
        if vres.warnings:
            for w in vres.warnings:
                st.warning(w.message)

    # Step 4: Preview
    step = 4
    st.subheader("Step 4 of 5: Preview Data")
    _render_step_indicator(step)

    # Preview mode selection (T9)
    preview_mode = st.radio(
        "Preview Mode",
        options=["Reconstructed Positions", "Raw Fills"],
        index=0,
        horizontal=True,
        help="Reconstructed Positions shows closed/open positions; Raw Fills shows the normalized fills.",
    )

    # Compute risk estimate to display in preview for breach context
    try:
        cfg = _get_services()["config_service"].get_app_config() or {}
        ps = cfg.get("portfolio_size")
        rp = cfg.get("risk_percent")
        risk_estimate = None
        if ps is not None and rp is not None:
            from decimal import Decimal
            risk_estimate = Decimal(str(ps)) * (Decimal(str(rp)) / Decimal("100"))
    except Exception:
        risk_estimate = None

    if st.button("Generate Preview"):
        preview_rows = import_service.preview_csv_data(
            file_path,
            selected_exchange,
            rows=10,
            preview_mode=("raw" if preview_mode == "Raw Fills" else "reconstructed"),
            risk_estimate=risk_estimate,
        )
        _set_state(preview=preview_rows)
        st.rerun()

    preview_rows = state["preview"]
    if preview_rows is not None:
        # Split out errors from OK rows for clearer display
        ok_rows = [r for r in preview_rows if not (isinstance(r, dict) and r.get("status") == "error")]
        err_rows = [r for r in preview_rows if isinstance(r, dict) and r.get("status") == "error"]

        if ok_rows:
            # Add friendly indicators for PnL source
            table_rows = []
            for r in ok_rows:
                src = r.get("pnl_source")
                src_disp = "📝 Provided" if src == "provided" else ("🧮 Calculated" if src == "calculated" else "—")
                # Risk display and breach logic (when available in preview or computed)
                max_risk = r.get("max_risk_per_trade") or (str(risk_estimate) if risk_estimate is not None else "")
                breach = ""
                try:
                    if r.get("status") == "closed" and r.get("pnl") not in (None, "") and max_risk:
                        from decimal import Decimal
                        pnl_val = Decimal(str(r.get("pnl")))
                        if pnl_val < 0 and abs(pnl_val) > Decimal(str(max_risk)):
                            breach = "⚠️ Breach"
                except Exception:
                    breach = ""

                table_rows.append({
                    "Row": f"{r.get('row_status_icon', '✅')}",
                    "Symbol": r.get("symbol"),
                    "Side": r.get("side"),
                    "Qty": r.get("quantity"),
                    "Entry": r.get("entry_price"),
                    "Exit": r.get("exit_price") or "",
                    "PnL": r.get("pnl") or "",
                    "PnL Source": src_disp,
                    "Max Risk": max_risk or "",
                    "Risk": breach,
                    "Entry Time": r.get("entry_time"),
                    "Exit Time": r.get("exit_time") or "",
                    "Trade Status": r.get("status"),
                    "Notes": r.get("notes") or "",
                })
            st.dataframe(table_rows, width="stretch", hide_index=True)

            with st.expander("Row details (JSON)"):
                st.json(ok_rows)

        if err_rows:
            st.error("Some preview rows could not be parsed:")
            for i, er in enumerate(err_rows, start=1):
                st.write(f"Row {i}: {er.get('error')}")

    # Step 5: Import with progress
    step = 5
    st.subheader("Step 5 of 5: Import Trades")
    _render_step_indicator(step)

    # Show confirmation summary
    file_info = state.get("file_info") or {}
    est_rows = _estimate_row_count(file_path)
    with st.expander("Import Confirmation", expanded=True):
        st.write("Review before importing:")
        st.write(f"• File: {file_info.get('name', '(unknown)')} ({file_info.get('size', 0)} bytes)")
        st.write(f"• Exchange: {selected_exchange}")
        if state.get("account_label"):
            st.write(f"• Account Label: {state.get('account_label')}")
        st.write(f"• Estimated rows: {est_rows}")
        # Incremental window suggestion
        try:
            from app.services.csv_import.tx_history.import_log import ImportLogStore
            services = _get_services()
            data_service = services["data_service"]
            log = ImportLogStore(str(data_service.data_path))
            last_time = log.get_last_import_time(
                exchange=selected_exchange.title(),
                account_label=state.get("account_label")
            )
        except Exception:
            last_time = None

        use_filter = st.checkbox("Use time filter (import fills after a date)", value=bool(last_time is not None), help="When enabled, only fills with time greater than the selected date are imported.")
        start_time_after = None
        if use_filter:
            default_dt = last_time
            # Prefer datetime_input when available, else fallback to date+time inputs
            if hasattr(st, "datetime_input"):
                dt_val = st.datetime_input(
                    "Start importing after (UTC)",
                    value=default_dt,
                    help="Default is the last import time for this exchange/account, if available.",
                    key="tx_history_start_time_after",
                )
                if dt_val is not None:
                    start_time_after = dt_val.isoformat()
            else:
                import datetime as _dt
                date_val = st.date_input(
                    "Start date (UTC)",
                    value=(default_dt.date() if default_dt else _dt.datetime.utcnow().date()),
                    key="tx_history_start_date",
                    help="Default is the last import date for this exchange/account, if available.",
                )
                time_val = st.time_input(
                    "Start time (UTC)",
                    value=(default_dt.time() if default_dt else _dt.time(0, 0, 0)),
                    key="tx_history_start_time",
                    help="Set time after which fills will be imported.",
                )
                try:
                    dt_combined = _dt.datetime.combine(date_val, time_val)
                    start_time_after = dt_combined.isoformat()
                except Exception:
                    start_time_after = None
        _set_state(start_time_after=start_time_after)
        confirm = st.checkbox("I confirm I want to import these trades", key="confirm_import")

    if st.button("Start Import", type="primary", disabled=not st.session_state.get("confirm_import")):
        progress = st.progress(0.0)
        status = st.empty()

        def on_progress(current: int, total: int) -> bool:
            frac = current / total if total else 0
            progress.progress(frac)
            status.text(f"Processing row {current} of {total}")
            return True

        result = import_service.import_csv_file(
            file_path,
            selected_exchange,
            account_label=state.get("account_label"),
            start_time_after=state.get("start_time_after"),
            on_progress=on_progress,
        )
        _set_state(import_result=result)

        # Clear cache so Trade History updates immediately
        services["data_service"].clear_cache()

        progress.empty(); status.empty()
        st.rerun()

    result = state.get("import_result")
    if result is not None:
        if result.success:
            st.success("Import complete")
        else:
            st.error("Import completed with errors")
        st.write(result.get_summary())
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Go to Trade History"):
                st.session_state["page_selector"] = "Trade History"
                st.rerun()
        with col2:
            if st.button("Import Another File"):
                # Reset state but keep services
                _set_state(file_path=None, file_info=None, selected_exchange=None, validation=None, preview=None, import_result=None)
                st.rerun()


def show_csv_import_page():
    _init_state()
    st.title("📊 Import Trade Data")
    handle_import_workflow()


# Streamlit multipage: invoke when run as page
show_csv_import_page()
