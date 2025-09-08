"""
Trade History page for displaying and managing trade records.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from app.models.trade import Trade, TradeSide, TradeStatus, WinLoss
from app.services.config_service import ConfigService
from app.services.data_service import DataService
from app.utils.notifications import get_notification_manager
from app.utils.state_management import get_state_manager

logger = logging.getLogger(__name__)


def _get_services() -> Dict[str, Any]:
    """Fetch initialized services, initializing via main.get_app_state() if needed."""
    app_state = st.session_state.get("app_state")
    if not app_state:
        try:
            # Ensure services are initialized when this page is run directly
            from app.main import get_app_state  # lazy import to avoid circulars

            app_state = get_app_state()
        except Exception:
            app_state = None
    if not app_state or not getattr(app_state, "data_service", None):
        st.error("Services not initialized. Please refresh the page.")
        st.stop()
    return {"data_service": app_state.data_service, "config_service": app_state.config_service}


def render_trade_history_page():
    """Render the main trade history page."""
    st.title("📊 Trade History")

    # Get services (robust to direct page execution)
    services = _get_services()
    data_service: DataService = services["data_service"]
    config_service: ConfigService = services["config_service"]

    # Load trades
    try:
        trades = data_service.load_trades()
    except Exception as e:
        st.error(f"Failed to load trades: {e}")
        return

    if not trades:
        st.info("No trades found. Import data from exchanges to get started.")
        return

    # Render filters
    filtered_trades = render_trade_filters(trades)

    # Render trade statistics
    render_trade_statistics(filtered_trades)

    # Render trade table
    render_trade_table(filtered_trades, data_service, config_service)


def render_trade_filters(trades: List[Trade]) -> List[Trade]:
    """Render filter controls and return filtered trades."""
    st.subheader("Filters")

    # Create filter columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Exchange filter
        exchanges = sorted(list(set(trade.exchange for trade in trades)))
        selected_exchanges = st.multiselect(
            "Exchanges", options=exchanges, default=exchanges, key="exchange_filter"
        )

    with col2:
        # Symbol filter
        symbols = sorted(list(set(trade.symbol for trade in trades)))
        selected_symbols = st.multiselect(
            "Symbols", options=symbols, default=symbols, key="symbol_filter"
        )

    with col3:
        # Status filter
        statuses = [status.value for status in TradeStatus]
        selected_statuses = st.multiselect(
            "Status", options=statuses, default=statuses, key="status_filter"
        )

    with col4:
        # Side filter
        sides = [side.value for side in TradeSide]
        selected_sides = st.multiselect(
            "Side", options=sides, default=sides, key="side_filter"
        )

    # Date range filter
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now().date() - timedelta(days=30),
            key="start_date_filter",
        )

    with col2:
        end_date = st.date_input(
            "End Date", value=datetime.now().date(), key="end_date_filter"
        )

    # Apply filters
    filtered_trades = []
    for trade in trades:
        # Exchange filter
        if trade.exchange not in selected_exchanges:
            continue

        # Symbol filter
        if trade.symbol not in selected_symbols:
            continue

        # Status filter
        if trade.status.value not in selected_statuses:
            continue

        # Side filter
        if trade.side.value not in selected_sides:
            continue

        # Date filter
        trade_date = trade.entry_time.date()
        if not (start_date <= trade_date <= end_date):
            continue

        filtered_trades.append(trade)

    return filtered_trades


def render_trade_statistics(trades: List[Trade]) -> None:
    """Render trade statistics summary."""
    if not trades:
        return

    # Calculate statistics
    total_trades = len(trades)
    open_trades = len([t for t in trades if t.status == TradeStatus.OPEN])
    closed_trades = len([t for t in trades if t.status == TradeStatus.CLOSED])
    partially_closed = len(
        [t for t in trades if t.status == TradeStatus.PARTIALLY_CLOSED]
    )

    # PnL statistics
    trades_with_pnl = [t for t in trades if t.pnl is not None]
    total_pnl = sum(t.pnl for t in trades_with_pnl) if trades_with_pnl else 0
    profitable_trades = len([t for t in trades_with_pnl if t.pnl > 0])

    # Display statistics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trades", total_trades)

    with col2:
        st.metric("Open", open_trades, delta=f"{partially_closed} partial")

    with col3:
        st.metric("Closed", closed_trades)

    with col4:
        if trades_with_pnl:
            win_rate = (profitable_trades / len(trades_with_pnl)) * 100
            st.metric("Win Rate (PnL)", f"{win_rate:.1f}%")
        else:
            st.metric("Win Rate (PnL)", "N/A")


    # Total PnL
    if trades_with_pnl:
        pnl_color = "normal" if total_pnl >= 0 else "inverse"
        st.metric("Total PnL", f"${total_pnl:.2f}", delta_color=pnl_color)


def render_trade_table(
    trades: List[Trade], data_service: DataService, config_service: ConfigService
) -> None:
    """Render the main trade table with sorting and details."""
    if not trades:
        st.info("No trades match the current filters.")
        return

    # Table header with actions
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.subheader(f"Trade Records ({len(trades)} trades)")

    with col2:
        # Bulk edit toggle
        bulk_edit_mode = st.toggle("Bulk Edit Mode", key="bulk_edit_toggle")

    with col3:
        # Export button (placeholder for future implementation)
        if st.button("📊 Export Data", help="Export filtered trades to CSV"):
            st.info("Export functionality coming soon!")

    # Convert trades to DataFrame for display
    trade_data = []
    for i, trade in enumerate(trades):
        # Format status with indicator
        status_indicator = get_status_indicator(trade.status)
        status_display = f"{status_indicator} {trade.status.value.title()}"

        # Format PnL
        pnl_display = f"${trade.pnl:.2f}" if trade.pnl is not None else "N/A"
        pnl_color = (
            "🟢"
            if trade.pnl and trade.pnl > 0
            else "🔴"
            if trade.pnl and trade.pnl < 0
            else "⚪"
        )

        # Format confluences
        confluences_display = (
            ", ".join(trade.confluences) if trade.confluences else "None"
        )
        if len(confluences_display) > 30:
            confluences_display = confluences_display[:27] + "..."

        # Pull PnL source and fees if available
        pnl_source = trade.custom_fields.get("pnl_source") if isinstance(trade.custom_fields, dict) else None
        fees_val = trade.custom_fields.get("fees") if isinstance(trade.custom_fields, dict) else None

        trade_data.append(
            {
                "Select": False
                if not bulk_edit_mode
                else False,  # Checkbox for bulk operations
                "ID": trade.id[:8] + "...",  # Shortened ID
                "Exchange": trade.exchange.title(),
                "Symbol": trade.symbol,
                "Side": trade.side.value.title(),
                "Status": status_display,
                "Entry Price": f"${trade.entry_price:.4f}",
                "Exit Price": f"${trade.exit_price:.4f}" if trade.exit_price else "N/A",
                "Quantity": f"{trade.quantity:.4f}",
                "PnL": f"{pnl_color} {pnl_display}",
                "PnL Source": pnl_source or "",
                "Fees": (f"${float(fees_val):.2f}" if fees_val not in (None, "") else ""),
                "Confluences": confluences_display,
                "Entry Time": trade.entry_time.strftime("%Y-%m-%d %H:%M"),
                "Exit Time": trade.exit_time.strftime("%Y-%m-%d %H:%M")
                if trade.exit_time
                else "N/A",
                "_trade_obj": trade,  # Store original trade object for editing
                "_index": i,  # Store index for bulk operations
            }
        )

    # Create DataFrame
    df = pd.DataFrame(trade_data)

    # Handle bulk edit mode
    if bulk_edit_mode:
        render_bulk_edit_interface(trades, data_service, config_service)
        return

    # Inline confluences edit toggle
    inline_edit = st.toggle("Inline Edit Confluences", key="inline_edit_confluences")
    if inline_edit:
        try:
            confluence_options = config_service.get_confluence_options()
        except Exception:
            confluence_options = []

        # Ensure options include any existing values so the editor can render them
        existing_values: List[str] = []
        try:
            for t in trades:
                if t.confluences:
                    for c in t.confluences:
                        s = str(c).strip()
                        if s:
                            existing_values.append(s)
        except Exception:
            pass
        # Deduplicate and merge
        merged_options = sorted(list({*confluence_options, *existing_values}))
        # Fallback to a benign placeholder if still empty
        if not merged_options:
            merged_options = ["(none)"]

        # Allow choosing strict editing (restrict to configured options) vs freeform ListColumn
        strict_mode = st.toggle(
            "Restrict to configured options",
            help=(
                "When on, uses per-row multiselects limited to the configured option list.\n"
                "When off, uses a spreadsheet-style editor (freeform lists) with validation on save."
            ),
        )

        edit_rows = []
        for t in trades:
            edit_rows.append(
                {
                    "ID": t.id,
                    "Exchange": t.exchange.title(),
                    "Symbol": t.symbol,
                    "Side": t.side.value.title(),
                    "Status": t.status.value.title(),
                    "Confluences": t.confluences or [],
                }
            )

        editor_df = None
        # Prefer Data Editor ListColumn when available and not in strict mode
        if not strict_mode and hasattr(st.column_config, "ListColumn"):
            try:
                editor_df = st.data_editor(
                    pd.DataFrame(edit_rows),
                    column_config={
                        # Some Streamlit versions don't support an 'options' arg on ListColumn.
                        # We will validate against merged_options on save instead.
                        "Confluences": st.column_config.ListColumn(
                            "Confluences", help="Select one or more confluences. Unknown entries will be ignored on save."
                        ),
                    },
                    disabled=["ID", "Exchange", "Symbol", "Side", "Status"],
                    width="stretch",
                    key="confluence_editor",
                )
            except Exception as e:
                st.error(f"Failed to render inline editor: {e}")
                st.stop()
        else:
            st.info(
                "Using compatibility editor for current Streamlit version. "
                "Edit confluences per row below and click Save."
            )
            # Manual per-row multiselects with PnL context
            for t in trades:
                # PnL snippet
                pnl_str = ""
                try:
                    if t.pnl is not None:
                        sign = "+" if t.pnl >= 0 else "-"
                        pnl_str = f" | PnL: {sign}${abs(float(t.pnl)):.2f}"
                except Exception:
                    pnl_str = ""

                # Exit time snippet
                exit_str = f" → {t.exit_time.strftime('%Y-%m-%d %H:%M')}" if t.exit_time else ""

                # Win/Loss badge (prefer explicit win_loss, fall back to pnl sign)
                try:
                    if t.win_loss == WinLoss.WIN or (t.win_loss is None and t.pnl is not None and t.pnl > 0):
                        wl_badge = "🏆 Win"
                    elif t.win_loss == WinLoss.LOSS or (t.win_loss is None and t.pnl is not None and t.pnl < 0):
                        wl_badge = "🔻 Loss"
                    else:
                        wl_badge = "•"
                except Exception:
                    wl_badge = "•"

                label = (
                    f"{t.symbol} ({t.side.value.title()}) @ {t.entry_time.strftime('%Y-%m-%d %H:%M')}"
                    f"{exit_str}{pnl_str} [{wl_badge}]"
                )
                st.multiselect(
                    label,
                    options=merged_options,
                    default=t.confluences or [],
                    key=f"conf_edit_{t.id}",
                    help="Confluences for this trade",
                )

        if st.button("Save Confluence Changes", type="primary"):
            try:
                if editor_df is not None:
                    id_to_confluences = {}
                    dropped_count = 0
                    for _, row in editor_df.iterrows():
                        vals = row.get("Confluences", [])
                        if not isinstance(vals, list):
                            vals = [str(vals)] if vals else []
                        # Validate against allowed options since ListColumn may not enforce options
                        clean = []
                        for v in vals:
                            s = str(v).strip()
                            if s in merged_options:
                                clean.append(s)
                            else:
                                dropped_count += 1
                        id_to_confluences[row["ID"]] = clean
                else:
                    # Gather from session_state for manual editor
                    id_to_confluences = {}
                    for t in trades:
                        vals = st.session_state.get(f"conf_edit_{t.id}", [])
                        # Ensure list[str]
                        if not isinstance(vals, list):
                            vals = [str(vals)] if vals else []
                        # Validate selections against options
                        id_to_confluences[t.id] = [str(v) for v in vals if str(v) in merged_options]
                updated = 0
                for t in trades:
                    new_vals = id_to_confluences.get(t.id, t.confluences)
                    if new_vals != t.confluences:
                        data_service.update_trade(t.id, {"confluences": new_vals})
                        updated += 1
                if updated:
                    get_notification_manager().success(f"Updated confluences for {updated} trades")
                    if 'dropped_count' in locals() and dropped_count:
                        st.warning(f"Ignored {dropped_count} unknown confluence value(s) not in configured options.")
                    st.rerun()
                else:
                    st.info("No changes detected")
            except Exception as e:
                st.error(f"Failed to save changes: {e}")
        return

    # Display table with selection (view-only)
    display_df = df.drop(columns=["_trade_obj", "_index", "Select"])

    selected_indices = st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="trade_table",
    )

    # Handle row selection for trade details
    if (
        selected_indices
        and "selection" in selected_indices
        and selected_indices["selection"]["rows"]
    ):
        selected_row = selected_indices["selection"]["rows"][0]
        selected_trade = trade_data[selected_row]["_trade_obj"]

        # Show trade details
        render_trade_details(selected_trade, data_service, config_service)


def render_bulk_edit_interface(
    trades: List[Trade], data_service: DataService, config_service: ConfigService
) -> None:
    """Render bulk edit interface for multiple trades."""
    st.subheader("🔧 Bulk Edit Mode")
    st.info(
        "Select trades to edit multiple records at once. Changes will be applied to all selected trades."
    )

    # Trade selection
    selected_trades = []

    # Create a more compact table for selection
    col1, col2 = st.columns([1, 3])

    with col1:
        st.write("**Select Trades:**")
        select_all = st.checkbox("Select All", key="select_all_trades")

        if select_all:
            selected_trades = trades.copy()
        else:
            # Individual selection checkboxes
            for i, trade in enumerate(trades[:20]):  # Limit to first 20 for performance
                if st.checkbox(
                    f"{trade.symbol} - {trade.entry_time.strftime('%m/%d')} - {trade.side.value}",
                    key=f"select_trade_{i}",
                ):
                    selected_trades.append(trade)

            if len(trades) > 20:
                st.caption(
                    f"Showing first 20 trades. Use filters to narrow down selection."
                )

    with col2:
        if selected_trades:
            st.write(f"**Selected {len(selected_trades)} trades for bulk edit:**")

            # Get confluence options
            try:
                confluence_options = config_service.get_confluence_options()
            except Exception as e:
                st.error(f"Failed to load confluence options: {e}")
                confluence_options = []

            # Bulk edit form
            with st.form("bulk_edit_form"):
                st.write("**Bulk Operations:**")

                # Confluence operations
                confluence_action = st.selectbox(
                    "Confluence Action",
                    options=[
                        "No Change",
                        "Add Confluences",
                        "Replace Confluences",
                        "Remove Confluences",
                    ],
                    help="Choose how to modify confluences for selected trades",
                )

                confluence_values = []
                if confluence_action != "No Change":
                    confluence_values = st.multiselect(
                        "Select Confluences",
                        options=confluence_options,
                        help="Confluences to add, replace, or remove",
                    )

                # Submit bulk changes
                col1, col2 = st.columns(2)

                with col1:
                    submitted = st.form_submit_button(
                        "Apply to Selected Trades", type="primary"
                    )

                with col2:
                    preview = st.form_submit_button("Preview Changes")

                if preview:
                    st.write("**Preview of changes:**")
                    preview_changes(selected_trades, confluence_action, confluence_values)

                if submitted:
                    apply_bulk_changes(selected_trades, data_service, confluence_action, confluence_values)
        else:
            st.info("Select trades to enable bulk editing options.")


def preview_changes(
    trades: List[Trade], confluence_action: str, confluence_values: List[str]
) -> None:
    """Preview bulk changes before applying."""
    changes_summary = []

    if confluence_action != "No Change":
        changes_summary.append(
            f"**Confluences:** {confluence_action} - {', '.join(confluence_values) if confluence_values else 'None'}"
        )


    if changes_summary:
        st.write(f"Will apply the following changes to {len(trades)} trades:")
        for change in changes_summary:
            st.write(f"• {change}")
    else:
        st.warning("No changes selected.")


def apply_bulk_changes(
    trades: List[Trade],
    data_service: DataService,
    confluence_action: str,
    confluence_values: List[str],
) -> None:
    """Apply bulk changes to selected trades."""
    try:
        success_count = 0
        error_count = 0

        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, trade in enumerate(trades):
            try:
                updates = {}

                # Handle confluence changes
                if confluence_action == "Add Confluences":
                    new_confluences = list(set(trade.confluences + confluence_values))
                    updates["confluences"] = new_confluences
                elif confluence_action == "Replace Confluences":
                    updates["confluences"] = confluence_values
                elif confluence_action == "Remove Confluences":
                    new_confluences = [
                        c for c in trade.confluences if c not in confluence_values
                    ]
                    updates["confluences"] = new_confluences

                # Apply updates if any
                if updates:
                    data_service.update_trade(trade.id, updates)
                    success_count += 1

                # Update progress
                progress = (i + 1) / len(trades)
                progress_bar.progress(progress)
                status_text.text(
                    f"Processing trade {i + 1} of {len(trades)}: {trade.symbol}"
                )

            except Exception as e:
                logger.error(f"Failed to update trade {trade.id}: {e}")
                error_count += 1

        # Show results
        progress_bar.empty()
        status_text.empty()

        if success_count > 0:
            st.success(f"✅ Successfully updated {success_count} trades!")

        if error_count > 0:
            st.error(
                f"❌ Failed to update {error_count} trades. Check logs for details."
            )

        # Refresh the page to show updated data
        st.rerun()

    except Exception as e:
        st.error(f"Bulk update failed: {e}")
        logger.error(f"Bulk update error: {e}")


def get_status_indicator(status: TradeStatus) -> str:
    """Get status indicator emoji."""
    indicators = {
        TradeStatus.OPEN: "🟡",
        TradeStatus.PARTIALLY_CLOSED: "🟠",
        TradeStatus.CLOSED: "🟢",
    }
    return indicators.get(status, "⚪")


def render_trade_details(
    trade: Trade, data_service: DataService, config_service: ConfigService
) -> None:
    """Render detailed view of a selected trade."""
    st.subheader("Trade Details")

    # Create tabs for different views
    tab1, tab2 = st.tabs(["📋 Details", "✏️ Edit"])

    with tab1:
        render_trade_detail_view(trade)

    with tab2:
        render_trade_edit_form(trade, data_service, config_service)


def render_trade_detail_view(trade: Trade) -> None:
    """Render read-only trade details."""
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Basic Information**")
        st.write(f"**ID:** {trade.id}")
        st.write(f"**Exchange:** {trade.exchange.title()}")
        st.write(f"**Symbol:** {trade.symbol}")
        st.write(f"**Side:** {trade.side.value.title()}")
        st.write(
            f"**Status:** {get_status_indicator(trade.status)} {trade.status.value.title()}"
        )

        st.write("**Pricing**")
        st.write(f"**Entry Price:** ${trade.entry_price:.4f}")
        if trade.exit_price:
            st.write(f"**Exit Price:** ${trade.exit_price:.4f}")
        st.write(f"**Quantity:** {trade.quantity:.4f}")
        if trade.pnl is not None:
            pnl_color = "🟢" if trade.pnl > 0 else "🔴"
            st.write(f"**PnL:** {pnl_color} ${trade.pnl:.2f}")

    with col2:
        st.write("**Timing**")
        st.write(f"**Entry Time:** {trade.entry_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if trade.exit_time:
            st.write(f"**Exit Time:** {trade.exit_time.strftime('%Y-%m-%d %H:%M:%S')}")

        st.write("**Analysis**")

        if trade.confluences:
            st.write("**Confluences:**")
            for confluence in trade.confluences:
                st.write(f"• {confluence}")
        else:
            st.write("**Confluences:** None")

        if trade.custom_fields:
            st.write("**Custom Fields:**")
            for field, value in trade.custom_fields.items():
                st.write(f"• **{field.title()}:** {value}")

    # Timestamps
    st.write("**System Information**")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Created:** {trade.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    with col2:
        st.write(f"**Updated:** {trade.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")


def render_trade_edit_form(
    trade: Trade, data_service: DataService, config_service: ConfigService
) -> None:
    """Render comprehensive trade editing form."""
    st.write("Edit trade analysis and custom data:")
    st.info(
        "Confluence editing is centralized in the Inline Editor above. "
        "Use the toggle ‘Inline Edit Confluences’ to modify confluences across trades."
    )
    if st.button("Open Inline Confluence Editor"):
        st.session_state["inline_edit_confluences"] = True
        st.rerun()

    # Create form with validation
    with st.form(f"edit_trade_{trade.id}", clear_on_submit=False):
        st.subheader("Trading Analysis")

        # No manual win/loss selection in MVP; outcome derived from PnL

        # Custom fields section
        st.subheader("Custom Fields")

        # Get all custom field configurations
        try:
            custom_field_configs = config_service.get_all_custom_field_configs()
        except Exception as e:
            st.error(f"Failed to load custom field configurations: {e}")
            custom_field_configs = {}

        custom_field_updates = {}

        # Render custom fields based on configuration
        for field_name, field_config in custom_field_configs.items():
            if field_name in ["confluences", "win_loss"]:
                continue  # Skip these as they're handled above

            current_value = trade.get_custom_field(field_name, "")

            if field_config.field_type.value == "text":
                custom_field_updates[field_name] = st.text_input(
                    field_config.display_name or field_name.title(),
                    value=str(current_value),
                    help=field_config.description,
                )

            elif field_config.field_type.value == "number":
                try:
                    numeric_value = float(current_value) if current_value else 0.0
                except (ValueError, TypeError):
                    numeric_value = 0.0

                custom_field_updates[field_name] = st.number_input(
                    field_config.display_name or field_name.title(),
                    value=numeric_value,
                    help=field_config.description,
                )

            elif field_config.field_type.value == "select":
                options = [""] + field_config.options
                current_index = 0
                if current_value and str(current_value) in options:
                    current_index = options.index(str(current_value))

                custom_field_updates[field_name] = st.selectbox(
                    field_config.display_name or field_name.title(),
                    options=options,
                    index=current_index,
                    help=field_config.description,
                )

            elif field_config.field_type.value == "multiselect":
                current_selections = []
                if current_value:
                    if isinstance(current_value, list):
                        current_selections = current_value
                    else:
                        current_selections = [str(current_value)]

                custom_field_updates[field_name] = st.multiselect(
                    field_config.display_name or field_name.title(),
                    options=field_config.options,
                    default=current_selections,
                    help=field_config.description,
                )

        # Show existing custom fields that don't have configurations
        existing_custom_fields = set(trade.custom_fields.keys())
        configured_fields = set(custom_field_configs.keys())
        unconfigured_fields = existing_custom_fields - configured_fields

        if unconfigured_fields:
            st.write("**Legacy Custom Fields**")
            st.caption(
                "These fields exist in the trade data but don't have current configurations:"
            )

            for field_name in sorted(unconfigured_fields):
                value = trade.custom_fields[field_name]
                custom_field_updates[field_name] = st.text_input(
                    f"{field_name.title()} (Legacy)",
                    value=str(value),
                    help="This field doesn't have a current configuration. Consider updating field configurations.",
                )

        # Validation and submission
        st.subheader("Save Changes")

        # Show validation warnings
        validation_warnings = []

        # No confluence selection here; handled by Inline Editor

        if validation_warnings:
            st.warning("Validation Notes:")
            for warning in validation_warnings:
                st.write(warning)

        # Submit buttons
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            submitted = st.form_submit_button("💾 Save Changes", type="primary")

        with col2:
            reset_clicked = st.form_submit_button("🔄 Reset Form")

        with col3:
            st.write("")  # Spacer

        # Handle form submission
        if reset_clicked:
            st.rerun()

        if submitted:
            try:
                # Prepare updates dictionary (no confluence updates here)
                updates = {}

                # Add custom field updates
                if custom_field_updates:
                    # Get current custom fields and update them
                    current_custom_fields = trade.custom_fields.copy()

                    for field_name, value in custom_field_updates.items():
                        if (
                            value or value == 0
                        ):  # Include zero values but exclude empty strings
                            current_custom_fields[field_name] = value
                        elif field_name in current_custom_fields:
                            # Remove field if value is empty
                            del current_custom_fields[field_name]

                    updates["custom_fields"] = current_custom_fields

                # Validate updates before saving
                if not validate_trade_updates(updates):
                    st.error("Validation failed. Please check your inputs.")
                    return

                # Update trade
                updated_trade = data_service.update_trade(trade.id, updates)

                # Show success message with details
                st.success("✅ Trade updated successfully!")

                # Show what was updated
                changes_made = []
                if updates.get("confluences") != trade.confluences:
                    changes_made.append(
                        f"Confluences: {len(updates.get('confluences', []))} selected"
                    )

                # No win/loss change tracking

                if "custom_fields" in updates:
                    field_count = len(updates["custom_fields"])
                    changes_made.append(f"Custom fields: {field_count} fields updated")

                if changes_made:
                    st.info("Changes made: " + " | ".join(changes_made))

                # Auto-refresh after a short delay
                st.balloons()
                st.rerun()

            except Exception as e:
                st.error(f"❌ Failed to update trade: {e}")
                logger.error(f"Failed to update trade {trade.id}: {e}")

                # Show detailed error for debugging
                with st.expander("Error Details"):
                    st.code(str(e))


def validate_trade_updates(updates: Dict[str, Any]) -> bool:
    """Validate trade updates before saving."""
    try:
        # Validate confluences
        if "confluences" in updates:
            confluences = updates["confluences"]
            if not isinstance(confluences, list):
                return False

            # Check that all confluences are strings
            if not all(isinstance(c, str) for c in confluences):
                return False

        # No manual win/loss validation in MVP

        # Validate custom_fields
        if "custom_fields" in updates:
            custom_fields = updates["custom_fields"]
            if not isinstance(custom_fields, dict):
                return False

        return True

    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False


# Main page function to be called from main.py
def show_trade_history_page():
    """Main function to display the trade history page."""
    render_trade_history_page()


# Execute the main page function directly (Streamlit multipage approach)
show_trade_history_page()
