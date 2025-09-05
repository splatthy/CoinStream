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


def render_trade_history_page():
    """Render the main trade history page."""
    st.title("📊 Trade History")

    # Get services from session state
    data_service = st.session_state.get("app_state").data_service
    config_service = st.session_state.get("app_state").config_service

    if not data_service or not config_service:
        st.error("Services not initialized. Please refresh the page.")
        return

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

    # Win/Loss statistics
    winning_trades = len([t for t in trades if t.win_loss == WinLoss.WIN])
    losing_trades = len([t for t in trades if t.win_loss == WinLoss.LOSS])

    # Display statistics
    col1, col2, col3, col4, col5 = st.columns(5)

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

    with col5:
        if winning_trades + losing_trades > 0:
            manual_win_rate = (winning_trades / (winning_trades + losing_trades)) * 100
            st.metric("Win Rate (Manual)", f"{manual_win_rate:.1f}%")
        else:
            st.metric("Win Rate (Manual)", "N/A")

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

        # Format win/loss
        win_loss_display = ""
        if trade.win_loss == WinLoss.WIN:
            win_loss_display = "✅ Win"
        elif trade.win_loss == WinLoss.LOSS:
            win_loss_display = "❌ Loss"
        else:
            win_loss_display = "⚪ N/A"

        # Format confluences
        confluences_display = (
            ", ".join(trade.confluences) if trade.confluences else "None"
        )
        if len(confluences_display) > 30:
            confluences_display = confluences_display[:27] + "..."

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
                "Win/Loss": win_loss_display,
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

    # Display table with selection
    display_df = df.drop(columns=["_trade_obj", "_index", "Select"])

    selected_indices = st.dataframe(
        display_df,
        use_container_width=True,
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

                # Win/Loss operations
                win_loss_action = st.selectbox(
                    "Win/Loss Action",
                    options=[
                        "No Change",
                        "Set to Win",
                        "Set to Loss",
                        "Clear Win/Loss",
                    ],
                    help="Choose how to modify win/loss classification",
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
                    preview_changes(
                        selected_trades,
                        confluence_action,
                        confluence_values,
                        win_loss_action,
                    )

                if submitted:
                    apply_bulk_changes(
                        selected_trades,
                        data_service,
                        confluence_action,
                        confluence_values,
                        win_loss_action,
                    )
        else:
            st.info("Select trades to enable bulk editing options.")


def preview_changes(
    trades: List[Trade],
    confluence_action: str,
    confluence_values: List[str],
    win_loss_action: str,
) -> None:
    """Preview bulk changes before applying."""
    changes_summary = []

    if confluence_action != "No Change":
        changes_summary.append(
            f"**Confluences:** {confluence_action} - {', '.join(confluence_values) if confluence_values else 'None'}"
        )

    if win_loss_action != "No Change":
        changes_summary.append(f"**Win/Loss:** {win_loss_action}")

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
    win_loss_action: str,
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

                # Handle win/loss changes
                if win_loss_action == "Set to Win":
                    updates["win_loss"] = "win"
                elif win_loss_action == "Set to Loss":
                    updates["win_loss"] = "loss"
                elif win_loss_action == "Clear Win/Loss":
                    updates["win_loss"] = None

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
        if trade.win_loss:
            win_loss_display = "✅ Win" if trade.win_loss == WinLoss.WIN else "❌ Loss"
            st.write(f"**Outcome:** {win_loss_display}")

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

    # Get confluence options from config
    try:
        confluence_options = config_service.get_confluence_options()
        if not confluence_options:
            st.warning(
                "No confluence options configured. Go to Configuration page to set up confluence options."
            )
            confluence_options = []
    except Exception as e:
        st.error(f"Failed to load confluence options: {e}")
        confluence_options = []

    # Create form with validation
    with st.form(f"edit_trade_{trade.id}", clear_on_submit=False):
        st.subheader("Trading Analysis")

        # Confluences multi-select with validation
        col1, col2 = st.columns([2, 1])

        with col1:
            selected_confluences = st.multiselect(
                "Trading Confluences",
                options=confluence_options,
                default=trade.confluences,
                help="Select all confluences that applied to this trade. These will be used for performance analysis.",
            )

        with col2:
            # Quick add confluence option
            st.write("**Quick Actions**")
            if st.button(
                "🔄 Refresh Options",
                help="Reload confluence options from configuration",
            ):
                st.rerun()

        # Win/Loss selection with validation
        st.write("**Trade Outcome**")
        win_loss_options = [("", "Not Set"), ("win", "✅ Win"), ("loss", "❌ Loss")]

        current_win_loss = trade.win_loss.value if trade.win_loss else ""
        current_index = next(
            (
                i
                for i, (value, _) in enumerate(win_loss_options)
                if value == current_win_loss
            ),
            0,
        )

        selected_win_loss_index = st.selectbox(
            "Win/Loss Classification",
            options=range(len(win_loss_options)),
            format_func=lambda x: win_loss_options[x][1],
            index=current_index,
            help="Classify this trade as a win or loss for manual analysis. This is separate from PnL calculations.",
        )

        selected_win_loss = win_loss_options[selected_win_loss_index][0]

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

        if not selected_confluences and confluence_options:
            validation_warnings.append(
                "⚠️ No confluences selected - this trade won't appear in confluence analysis"
            )

        if not selected_win_loss:
            validation_warnings.append(
                "⚠️ Win/Loss not set - this trade won't be included in manual win rate calculations"
            )

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
                # Prepare updates dictionary
                updates = {
                    "confluences": selected_confluences,
                }

                # Handle win/loss
                if selected_win_loss:
                    updates["win_loss"] = selected_win_loss
                else:
                    updates["win_loss"] = None

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

                if updates.get("win_loss") != (
                    trade.win_loss.value if trade.win_loss else None
                ):
                    new_wl = updates.get("win_loss", "Not Set")
                    changes_made.append(f"Win/Loss: {new_wl}")

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

        # Validate win_loss
        if "win_loss" in updates:
            win_loss = updates["win_loss"]
            if win_loss is not None and win_loss not in ["win", "loss"]:
                return False

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
