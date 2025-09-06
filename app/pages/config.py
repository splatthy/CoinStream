"""Configuration page for the trading journal application."""

from typing import List

import streamlit as st

from ..models.custom_fields import CustomField, CustomFieldType
from ..services.config_service import ConfigService
from ..utils.logging_config import get_logger
from ..utils.notifications import add_notification

# Initialize logger
logger = get_logger(__name__)


def show_config_page() -> None:
    """Main function to display the configuration page."""
    st.title("⚙️ Configuration")

    # Get services from app state
    if "app_state" not in st.session_state:
        st.error("Application not initialized. Please refresh the page.")
        return

    app_state = st.session_state.app_state
    config_service = app_state.config_service

    if not config_service:
        st.error("Configuration service not available. Please refresh the page.")
        return

    # Show only custom fields configuration
    st.header("Custom Fields Configuration")
    st.write("Configure custom fields for your trading data.")

    show_custom_fields_tab(config_service)


def show_custom_fields_tab(config_service: ConfigService) -> None:
    """Display the custom fields configuration tab."""
    st.subheader("Custom Fields")

    # Get existing custom fields
    custom_fields = config_service.get_custom_fields()

    # Display existing custom fields
    if custom_fields:
        st.write("**Configured Custom Fields:**")
        for field in custom_fields:
            with st.expander(f"{field.name} ({field.field_type.value})"):
                st.write(f"**Type:** {field.field_type.value}")
                st.write(f"**Required:** {'Yes' if field.is_required else 'No'}")
                if field.description:
                    st.write(f"**Description:** {field.description}")
                if field.options:
                    st.write(f"**Options:** {', '.join(field.options)}")

                # Delete button
                if st.button(f"Delete {field.name}", key=f"delete_{field.name}"):
                    if config_service.delete_custom_field(field.name):
                        add_notification(
                            "success", f"Custom field '{field.name}' deleted"
                        )
                        st.rerun()
                    else:
                        add_notification(
                            "error", f"Failed to delete custom field '{field.name}'"
                        )
    else:
        st.info("No custom fields configured yet.")

    st.divider()

    # Add new custom field form
    st.subheader("Add New Custom Field")
    with st.form("add_custom_field"):
        col1, col2 = st.columns(2)

        with col1:
            field_name = st.text_input(
                "Field Name", help="Unique name for the custom field"
            )
            field_type = st.selectbox(
                "Field Type",
                options=[ft.value for ft in CustomFieldType],
                help="Type of the custom field",
            )

        with col2:
            is_required = st.checkbox("Required", help="Whether this field is required")
            description = st.text_input(
                "Description", help="Optional description for the field"
            )

        # Options for select fields
        options = []
        if field_type in ["select", "multiselect"]:
            options_text = st.text_area(
                "Options (one per line)", help="Enter each option on a separate line"
            )
            if options_text:
                options = [
                    opt.strip() for opt in options_text.split("\n") if opt.strip()
                ]

        submitted = st.form_submit_button("Add Custom Field", type="primary")

        if submitted:
            if not field_name:
                st.error("Field name is required")
            elif field_type in ["select", "multiselect"] and not options:
                st.error("Options are required for select fields")
            else:
                try:
                    custom_field = CustomField(
                        name=field_name,
                        field_type=CustomFieldType(field_type),
                        is_required=is_required,
                        description=description if description else None,
                        options=options if options else None,
                    )

                    if config_service.add_custom_field(custom_field):
                        add_notification(
                            "success", f"Custom field '{field_name}' added successfully"
                        )
                        st.rerun()
                    else:
                        st.error("Failed to add custom field")

                except Exception as e:
                    st.error(f"Error adding custom field: {str(e)}")
                    logger.error(f"Error adding custom field: {e}")
