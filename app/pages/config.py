"""
Configuration page for managing exchange settings and custom field definitions.
"""

import logging
from typing import Any, Dict, List, Optional

import streamlit as st

from app.models.custom_fields import CustomFieldConfig, FieldType
from app.models.exchange_config import ConnectionStatus, ExchangeConfig
from app.services.config_service import ConfigService
from app.utils.data_management_ui import render_data_management_interface
from app.utils.notifications import get_notification_manager
from app.utils.state_management import get_state_manager
from app.utils.sync_ui import (
    render_sync_controls,
    render_sync_history,
    render_sync_progress,
    render_sync_status_card,
)

logger = logging.getLogger(__name__)


def show_config_page() -> None:
    """Display the configuration page with exchange and custom field management."""
    st.title("⚙️ Configuration")

    # Get services from app state
    if "app_state" not in st.session_state:
        st.error("Application not initialized. Please refresh the page.")
        return

    app_state = st.session_state.app_state
    notification_manager = get_notification_manager()

    config_service = app_state.config_service
    if not config_service:
        st.error("Configuration service not available. Please refresh the page.")
        return

    # Create tabs for different configuration sections
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Exchange Configuration", "Custom Fields", "Data Sync", "Data Management"]
    )

    with tab1:
        show_exchange_configuration(config_service)

    with tab2:
        show_custom_field_configuration(config_service)

    with tab3:
        show_data_sync_configuration(config_service)

    with tab4:
        show_data_management_configuration()


def show_exchange_configuration(config_service: ConfigService) -> None:
    """Display exchange configuration interface."""
    st.header("Exchange Configuration")

    # Get current exchange configurations
    try:
        exchange_configs = config_service.get_all_exchange_configs()
    except Exception as e:
        st.error(f"Failed to load exchange configurations: {e}")
        return

    # Display existing exchanges
    if exchange_configs:
        st.subheader("Configured Exchanges")

        for exchange_name, config in exchange_configs.items():
            with st.expander(f"{config.get_display_name()}", expanded=False):
                show_exchange_config_details(config_service, config)
    else:
        st.info("No exchanges configured yet.")

    # Add new exchange section
    st.subheader("Add New Exchange")
    show_add_exchange_form(config_service)


def show_exchange_config_details(
    config_service: ConfigService, config: ExchangeConfig
) -> None:
    """Display details and controls for a specific exchange configuration."""
    col1, col2 = st.columns([2, 1])

    with col1:
        # Display exchange information
        st.write(f"**Exchange:** {config.name.title()}")
        st.write(f"**Status:** {config.connection_status.value.title()}")
        st.write(f"**Active:** {'Yes' if config.is_active else 'No'}")

        if config.last_sync:
            st.write(f"**Last Sync:** {config.last_sync.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.write("**Last Sync:** Never")

        # API Key management
        st.write("**API Key:** ••••••••••••••••")

        # API Secret status
        if config.api_secret_encrypted:
            st.write("**API Secret:** ••••••••••••••••")
        else:
            st.write("**API Secret:** Not configured")

        # Update credentials
        with st.form(f"update_credentials_{config.name}"):
            st.write("**Update Credentials**")

            new_api_key = st.text_input(
                "New API Key",
                type="password",
                key=f"new_api_key_{config.name}",
                help="Enter new API key for this exchange",
            )

            new_api_secret = st.text_input(
                "New API Secret",
                type="password",
                key=f"new_api_secret_{config.name}",
                help="Enter new API secret for this exchange (required for Bitunix)",
            )

            # Show credentials toggle
            show_new_credentials = st.checkbox(
                "Show new credentials", value=False, key=f"show_new_creds_{config.name}"
            )
            if show_new_credentials:
                if new_api_key:
                    st.write("**New API Key:**")
                    st.code(new_api_key)
                if new_api_secret:
                    st.write("**New API Secret:**")
                    st.code(new_api_secret)

            col_update, col_test = st.columns(2)

            with col_update:
                update_credentials = st.form_submit_button("Update Credentials")

            with col_test:
                test_only = st.form_submit_button("Test Only")

            if update_credentials and new_api_key:
                update_exchange_credentials(
                    config_service, config.name, new_api_key, new_api_secret, save=True
                )

            elif test_only and new_api_key:
                update_exchange_credentials(
                    config_service, config.name, new_api_key, new_api_secret, save=False
                )

    with col2:
        # Control buttons
        st.write("**Actions**")

        # Test connection button
        if st.button(f"🔄 Test Connection", key=f"test_{config.name}"):
            test_exchange_connection(config_service, config.name)

        # Activate/Deactivate button
        if config.is_active:
            if st.button(f"⏸️ Deactivate", key=f"deactivate_{config.name}"):
                toggle_exchange_status(config_service, config.name, False)
        else:
            if st.button(f"▶️ Activate", key=f"activate_{config.name}"):
                toggle_exchange_status(config_service, config.name, True)

        # Delete button
        if st.button(f"🗑️ Delete", key=f"delete_{config.name}", type="secondary"):
            delete_exchange_config(config_service, config.name)


def show_add_exchange_form(config_service: ConfigService) -> None:
    """Display form for adding a new exchange configuration."""
    with st.form("add_exchange_form"):
        col1, col2 = st.columns(2)

        with col1:
            exchange_name = st.selectbox(
                "Exchange",
                options=["bitunix"],  # Add more exchanges as they become available
                help="Select the exchange to configure",
            )

        with col2:
            test_connection = st.checkbox(
                "Test connection",
                value=True,
                help="Test API key before saving configuration",
            )

        api_key = st.text_input(
            "API Key",
            type="password",
            help="Enter your API key for the selected exchange",
        )

        api_secret = st.text_input(
            "API Secret",
            type="password",
            help="Enter your API secret for the selected exchange (required for Bitunix)",
        )

        # Show/hide credentials toggle
        show_credentials = st.checkbox("Show credentials", value=False)
        if show_credentials:
            if api_key:
                st.write("**API Key:**")
                st.code(api_key)
            if api_secret:
                st.write("**API Secret:**")
                st.code(api_secret)

        submitted = st.form_submit_button("Add Exchange", type="primary")

        if submitted:
            add_exchange_configuration(
                config_service, exchange_name, api_key, api_secret, test_connection
            )


def show_custom_field_configuration(config_service: ConfigService) -> None:
    """Display custom field configuration interface."""
    st.header("Custom Field Configuration")

    # Get current custom field configurations
    try:
        custom_field_configs = config_service.get_all_custom_field_configs()
    except Exception as e:
        st.error(f"Failed to load custom field configurations: {e}")
        return

    # Display existing custom fields
    if custom_field_configs:
        st.subheader("Configured Custom Fields")

        for field_name, config in custom_field_configs.items():
            with st.expander(f"{config.get_display_name()}", expanded=False):
                show_custom_field_details(config_service, config)
    else:
        st.info("No custom fields configured yet.")

    # Add new custom field section
    st.subheader("Add New Custom Field")
    show_add_custom_field_form(config_service)


def show_custom_field_details(
    config_service: ConfigService, config: CustomFieldConfig
) -> None:
    """Display details and controls for a specific custom field configuration."""
    col1, col2 = st.columns([2, 1])

    with col1:
        # Display field information
        st.write(f"**Field Name:** {config.field_name}")
        st.write(f"**Type:** {config.field_type.value.title()}")
        st.write(f"**Required:** {'Yes' if config.is_required else 'No'}")

        if config.description:
            st.write(f"**Description:** {config.description}")

        # Show options for select/multiselect fields
        if config.field_type in [FieldType.SELECT, FieldType.MULTISELECT]:
            st.write("**Options:**")

            # Display current options with individual remove buttons
            for i, option in enumerate(config.options):
                col_option, col_remove = st.columns([3, 1])
                with col_option:
                    st.write(f"• {option}")
                with col_remove:
                    if st.button(
                        "❌",
                        key=f"remove_{config.field_name}_{i}",
                        help=f"Remove '{option}'",
                    ):
                        remove_custom_field_option(
                            config_service, config.field_name, option
                        )

            # Add new option form
            with st.form(f"add_option_{config.field_name}"):
                new_option = st.text_input(
                    "Add new option",
                    key=f"new_option_{config.field_name}",
                    help="Enter a new option to add to this field",
                )

                add_option = st.form_submit_button("Add Option")

                # Handle adding new option
                if add_option and new_option:
                    add_custom_field_option(
                        config_service, config.field_name, new_option
                    )

    with col2:
        # Control buttons
        st.write("**Actions**")

        # Edit field button
        if st.button(f"✏️ Edit Field", key=f"edit_{config.field_name}"):
            show_edit_custom_field_form(config_service, config)

        # Delete button (with confirmation)
        if config.field_name not in ["confluences", "win_loss"]:  # Protect core fields
            if st.button(
                f"🗑️ Delete", key=f"delete_field_{config.field_name}", type="secondary"
            ):
                delete_custom_field_config(config_service, config.field_name)


def show_add_custom_field_form(config_service: ConfigService) -> None:
    """Display form for adding a new custom field configuration."""
    with st.form("add_custom_field_form"):
        col1, col2 = st.columns(2)

        with col1:
            field_name = st.text_input(
                "Field Name",
                help="Enter a unique name for this field (alphanumeric and underscores only)",
            )

            field_type = st.selectbox(
                "Field Type",
                options=[ft.value for ft in FieldType],
                format_func=lambda x: x.title(),
                help="Select the type of field",
            )

        with col2:
            is_required = st.checkbox(
                "Required Field", value=False, help="Whether this field must be filled"
            )

        description = st.text_area(
            "Description", help="Optional description for this field"
        )

        # Options for select/multiselect fields
        options = []
        if field_type in ["select", "multiselect"]:
            st.write("**Options** (one per line)")
            options_text = st.text_area(
                "Options",
                help="Enter each option on a separate line",
                key="new_field_options",
            )
            if options_text:
                options = [
                    opt.strip() for opt in options_text.split("\n") if opt.strip()
                ]

        submitted = st.form_submit_button("Add Custom Field", type="primary")

        if submitted:
            add_custom_field_configuration(
                config_service,
                field_name,
                field_type,
                options,
                is_required,
                description,
            )


def show_edit_custom_field_form(
    config_service: ConfigService, config: CustomFieldConfig
) -> None:
    """Display form for editing an existing custom field configuration."""
    st.subheader(f"Edit {config.get_display_name()}")

    with st.form(f"edit_custom_field_{config.field_name}"):
        col1, col2 = st.columns(2)

        with col1:
            # Field name (read-only for existing fields)
            st.text_input(
                "Field Name",
                value=config.field_name,
                disabled=True,
                help="Field name cannot be changed after creation",
            )

            # Field type (read-only for existing fields)
            st.selectbox(
                "Field Type",
                options=[config.field_type.value],
                disabled=True,
                help="Field type cannot be changed after creation",
            )

        with col2:
            is_required = st.checkbox(
                "Required Field",
                value=config.is_required,
                help="Whether this field must be filled",
            )

        description = st.text_area(
            "Description",
            value=config.description or "",
            help="Optional description for this field",
        )

        submitted = st.form_submit_button("Update Field", type="primary")

        if submitted:
            update_custom_field_configuration(
                config_service, config.field_name, is_required, description
            )


# Helper functions for handling form submissions and actions


def add_exchange_configuration(
    config_service: ConfigService,
    exchange_name: str,
    api_key: str,
    api_secret: str,
    test_connection: bool,
) -> None:
    """Add a new exchange configuration."""
    notification_manager = get_notification_manager()

    if not api_key:
        notification_manager.error("API key is required")
        return

    # For Bitunix, API secret is also required
    if exchange_name.lower() == "bitunix" and not api_secret:
        notification_manager.error("API secret is required for Bitunix")
        return

    try:
        # Check if exchange already exists
        existing_config = config_service.get_exchange_config(exchange_name)
        if existing_config:
            notification_manager.error(
                f"Exchange {exchange_name} is already configured"
            )
            return

        # Create new configuration
        config = config_service.create_exchange_config_with_validation(
            exchange_name, api_key, api_secret, test_connection
        )

        if test_connection:
            if config.is_connected():
                notification_manager.success(
                    f"Exchange {exchange_name} added and connected successfully"
                )
            else:
                notification_manager.warning(
                    f"Exchange {exchange_name} added but connection test failed"
                )
        else:
            notification_manager.success(f"Exchange {exchange_name} added successfully")

        st.rerun()

    except Exception as e:
        logger.error(f"Failed to add exchange {exchange_name}: {e}")
        notification_manager.error(f"Failed to add exchange: {e}")


def update_exchange_credentials(
    config_service: ConfigService,
    exchange_name: str,
    new_api_key: str,
    new_api_secret: str = None,
    save: bool = True,
) -> None:
    """Update API key and secret for an exchange."""
    notification_manager = get_notification_manager()

    # For Bitunix, API secret is required
    if exchange_name.lower() == "bitunix" and not new_api_secret:
        notification_manager.error("API secret is required for Bitunix")
        return

    try:
        if save:
            # Update and save the credentials
            success = config_service.update_exchange_credentials(
                exchange_name, new_api_key, new_api_secret, test_connection=True
            )
            if success:
                config = config_service.get_exchange_config(exchange_name)
                if config and config.is_connected():
                    notification_manager.success(
                        f"Credentials updated and connection test passed for {exchange_name}"
                    )
                else:
                    notification_manager.warning(
                        f"Credentials updated but connection test failed for {exchange_name}"
                    )
                st.rerun()
            else:
                notification_manager.error(
                    f"Failed to update credentials for {exchange_name}"
                )
        else:
            # Test only without saving
            is_connected = config_service.test_exchange_connection(
                exchange_name, new_api_key, new_api_secret
            )
            if is_connected:
                notification_manager.success(
                    f"Credentials test passed for {exchange_name}"
                )
            else:
                notification_manager.warning(
                    f"Credentials test failed for {exchange_name}"
                )

    except Exception as e:
        logger.error(f"Failed to update credentials for {exchange_name}: {e}")
        notification_manager.error(f"Failed to update credentials: {e}")


def update_exchange_api_key(
    config_service: ConfigService,
    exchange_name: str,
    new_api_key: str,
    save: bool = True,
) -> None:
    """Update API key for an exchange."""
    notification_manager = get_notification_manager()

    try:
        if save:
            # Update and save the API key
            success = config_service.update_exchange_api_key(
                exchange_name, new_api_key, test_connection=True
            )
            if success:
                config = config_service.get_exchange_config(exchange_name)
                if config and config.is_connected():
                    notification_manager.success(
                        f"API key updated and connection test passed for {exchange_name}"
                    )
                else:
                    notification_manager.warning(
                        f"API key updated but connection test failed for {exchange_name}"
                    )
                st.rerun()
            else:
                notification_manager.error(
                    f"Failed to update API key for {exchange_name}"
                )
        else:
            # Test only without saving
            is_valid = config_service.validate_api_key(exchange_name, new_api_key)
            if is_valid:
                is_connected = config_service.test_exchange_connection(
                    exchange_name, new_api_key
                )
                if is_connected:
                    notification_manager.success(
                        f"API key test passed for {exchange_name}"
                    )
                else:
                    notification_manager.warning(
                        f"API key format is valid but connection test failed for {exchange_name}"
                    )
            else:
                notification_manager.error(
                    f"Invalid API key format for {exchange_name}"
                )

    except Exception as e:
        logger.error(f"Failed to update API key for {exchange_name}: {e}")
        notification_manager.error(f"Failed to update API key: {e}")


def test_exchange_connection(config_service: ConfigService, exchange_name: str) -> None:
    """Test connection to an exchange."""
    notification_manager = get_notification_manager()

    try:
        # Update status to testing
        config_service.update_exchange_connection_status(
            exchange_name, ConnectionStatus.TESTING
        )

        # Test connection
        is_connected = config_service.test_exchange_connection(exchange_name)

        # Update status based on result
        new_status = (
            ConnectionStatus.CONNECTED if is_connected else ConnectionStatus.ERROR
        )
        config_service.update_exchange_connection_status(exchange_name, new_status)

        if is_connected:
            notification_manager.success(f"Connection test passed for {exchange_name}")
        else:
            notification_manager.error(f"Connection test failed for {exchange_name}")

        st.rerun()

    except Exception as e:
        logger.error(f"Failed to test connection for {exchange_name}: {e}")
        config_service.update_exchange_connection_status(
            exchange_name, ConnectionStatus.ERROR
        )
        notification_manager.error(f"Failed to test connection: {e}")


def toggle_exchange_status(
    config_service: ConfigService, exchange_name: str, is_active: bool
) -> None:
    """Toggle exchange active status."""
    notification_manager = get_notification_manager()

    try:
        config = config_service.get_exchange_config(exchange_name)
        if not config:
            notification_manager.error(f"Exchange {exchange_name} not found")
            return

        if is_active:
            config.activate()
        else:
            config.deactivate()

        config_service.save_exchange_config(config)

        status_text = "activated" if is_active else "deactivated"
        notification_manager.success(f"Exchange {exchange_name} {status_text}")

        st.rerun()

    except Exception as e:
        logger.error(f"Failed to toggle status for {exchange_name}: {e}")
        notification_manager.error(f"Failed to update exchange status: {e}")


def delete_exchange_config(config_service: ConfigService, exchange_name: str) -> None:
    """Delete an exchange configuration."""
    notification_manager = get_notification_manager()

    try:
        success = config_service.delete_exchange_config(exchange_name)
        if success:
            notification_manager.success(
                f"Exchange {exchange_name} deleted successfully"
            )
            st.rerun()
        else:
            notification_manager.error(f"Exchange {exchange_name} not found")

    except Exception as e:
        logger.error(f"Failed to delete exchange {exchange_name}: {e}")
        notification_manager.error(f"Failed to delete exchange: {e}")


def add_custom_field_configuration(
    config_service: ConfigService,
    field_name: str,
    field_type: str,
    options: List[str],
    is_required: bool,
    description: str,
) -> None:
    """Add a new custom field configuration."""
    notification_manager = get_notification_manager()

    if not field_name:
        notification_manager.error("Field name is required")
        return

    try:
        # Check if field already exists
        existing_config = config_service.get_custom_field_config(field_name)
        if existing_config:
            notification_manager.error(f"Custom field {field_name} already exists")
            return

        # Validate options for select/multiselect fields
        if field_type in ["select", "multiselect"] and not options:
            notification_manager.error(
                f"{field_type.title()} fields must have at least one option"
            )
            return

        # Create new configuration
        config = CustomFieldConfig(
            field_name=field_name,
            field_type=FieldType(field_type),
            options=options,
            is_required=is_required,
            description=description if description else None,
        )

        config_service.save_custom_field_config(config)
        notification_manager.success(f"Custom field {field_name} added successfully")

        st.rerun()

    except Exception as e:
        logger.error(f"Failed to add custom field {field_name}: {e}")
        notification_manager.error(f"Failed to add custom field: {e}")


def update_custom_field_configuration(
    config_service: ConfigService, field_name: str, is_required: bool, description: str
) -> None:
    """Update an existing custom field configuration."""
    notification_manager = get_notification_manager()

    try:
        config = config_service.get_custom_field_config(field_name)
        if not config:
            notification_manager.error(f"Custom field {field_name} not found")
            return

        # Update modifiable properties
        config.is_required = is_required
        config.description = description if description else None

        config_service.save_custom_field_config(config)
        notification_manager.success(f"Custom field {field_name} updated successfully")

        st.rerun()

    except Exception as e:
        logger.error(f"Failed to update custom field {field_name}: {e}")
        notification_manager.error(f"Failed to update custom field: {e}")


def add_custom_field_option(
    config_service: ConfigService, field_name: str, option: str
) -> None:
    """Add an option to a custom field."""
    notification_manager = get_notification_manager()

    try:
        config = config_service.get_custom_field_config(field_name)
        if not config:
            notification_manager.error(f"Custom field {field_name} not found")
            return

        config.add_option(option)
        config_service.save_custom_field_config(config)
        notification_manager.success(f"Option '{option}' added to {field_name}")

        st.rerun()

    except Exception as e:
        logger.error(f"Failed to add option to {field_name}: {e}")
        notification_manager.error(f"Failed to add option: {e}")


def remove_custom_field_option(
    config_service: ConfigService, field_name: str, option: str
) -> None:
    """Remove an option from a custom field."""
    notification_manager = get_notification_manager()

    try:
        config = config_service.get_custom_field_config(field_name)
        if not config:
            notification_manager.error(f"Custom field {field_name} not found")
            return

        config.remove_option(option)
        config_service.save_custom_field_config(config)
        notification_manager.success(f"Option '{option}' removed from {field_name}")

        st.rerun()

    except Exception as e:
        logger.error(f"Failed to remove option from {field_name}: {e}")
        notification_manager.error(f"Failed to remove option: {e}")


def delete_custom_field_config(config_service: ConfigService, field_name: str) -> None:
    """Delete a custom field configuration."""
    notification_manager = get_notification_manager()

    try:
        success = config_service.delete_custom_field_config(field_name)
        if success:
            notification_manager.success(
                f"Custom field {field_name} deleted successfully"
            )
            st.rerun()
        else:
            notification_manager.error(f"Custom field {field_name} not found")

    except Exception as e:
        logger.error(f"Failed to delete custom field {field_name}: {e}")
        notification_manager.error(f"Failed to delete custom field: {e}")


def show_data_sync_configuration(config_service: ConfigService) -> None:
    """Display data synchronization configuration and controls."""
    st.header("Data Synchronization")

    # Sync status overview
    render_sync_status_card()

    st.divider()

    # Sync controls
    render_sync_controls(show_advanced=True)

    st.divider()

    # Sync progress (if any operations are running)
    render_sync_progress()

    st.divider()

    # Sync history
    render_sync_history(limit=15)


def show_data_management_configuration() -> None:
    """Display data management interface."""
    st.header("Data Management")

    # Render the complete data management interface
    render_data_management_interface()


# Execute the main page function directly (Streamlit multipage approach)
show_config_page()
