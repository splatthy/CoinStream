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


PAGE_KEY = "csv_import_state"


def _get_services() -> Dict[str, Any]:
    app_state = st.session_state.get("app_state")
    if not app_state or not app_state.data_service:
        st.error("Services not initialized. Please refresh the page.")
        st.stop()
    data_service: DataService = app_state.data_service
    import_service = CSVImportService(data_service)
    return {"data_service": data_service, "import_service": import_service}


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

    # Step 2: Select exchange
    step = 2
    st.subheader("Step 2 of 5: Select Exchange")
    _render_step_indicator(step)
    exchange = st.selectbox("Exchange", options=["bitunix"], index=0, help="Select the exchange that produced this CSV")
    if st.button("Confirm Exchange"):
        _set_state(selected_exchange=exchange, validation=None, preview=None, import_result=None)
        st.rerun()

    selected_exchange = state["selected_exchange"]
    if not selected_exchange:
        return

    # Mapping preview (read-only)
    with st.expander("Show Mapping for Selected Exchange", expanded=True):
        try:
            # Parse headers to build mapping preview
            from app.services.csv_import.csv_parser import CSVParser
            from app.services.csv_import.column_mapper import ColumnMapper
            from app.services.csv_import.models import ColumnMapping

            parser = CSVParser()
            df_headers = list(parser.parse_csv_file(file_path).columns)
            mapper = ColumnMapper()
            mapping = mapper.create_mapping(df_headers, exchange_name=selected_exchange)

            # Build a preview table of logical field -> CSV header
            mapping_rows = []
            for field, csv_col in mapping.as_dict().items():
                required = field in mapping.required_fields()
                status = ""
                notes = ""
                if csv_col and csv_col in df_headers:
                    status = "✅"
                else:
                    if field == "fees":
                        # Fees are derived (we compute a total) when not mapped
                        status = "🧮 Derived"
                        notes = "Total fees will be calculated and stored as 'fees'"
                    else:
                        status = "❌" if required else "⚠️"
                mapping_rows.append({
                    "Field": field,
                    "CSV Column": csv_col or "(not mapped)",
                    "Required": "Yes" if required else "No",
                    "Status": status,
                    "Notes": notes,
                })
            st.dataframe(
                mapping_rows,
                use_container_width=True,
                hide_index=True,
            )
        except Exception as e:
            st.error(f"Failed to load mapping preview: {e}")

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

    if st.button("Generate Preview"):
        preview_rows = import_service.preview_csv_data(file_path, selected_exchange, rows=10)
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
                table_rows.append({
                    "Row": f"{r.get('row_status_icon', '✅')}",
                    "Symbol": r.get("symbol"),
                    "Side": r.get("side"),
                    "Qty": r.get("quantity"),
                    "Entry": r.get("entry_price"),
                    "Exit": r.get("exit_price") or "",
                    "PnL": r.get("pnl") or "",
                    "PnL Source": src_disp,
                    "Entry Time": r.get("entry_time"),
                    "Exit Time": r.get("exit_time") or "",
                    "Trade Status": r.get("status"),
                    "Notes": r.get("notes") or "",
                })
            st.dataframe(table_rows, use_container_width=True, hide_index=True)

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
        st.write(f"• Estimated rows: {est_rows}")
        confirm = st.checkbox("I confirm I want to import these trades", key="confirm_import")

    if st.button("Start Import", type="primary", disabled=not st.session_state.get("confirm_import")):
        progress = st.progress(0.0)
        status = st.empty()

        def on_progress(current: int, total: int) -> bool:
            frac = current / total if total else 0
            progress.progress(frac)
            status.text(f"Processing row {current} of {total}")
            return True

        result = import_service.import_csv_file(file_path, selected_exchange, on_progress=on_progress)
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
