"""Configuration page for the trading journal application."""

import streamlit as st

from app.services.config_service import ConfigService
from app.utils.logging_config import get_logger
from app.utils.notifications import get_notification_manager

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

    # Application settings
    render_app_settings(config_service)

    # Confluence taxonomy configuration
    st.header("Confluences")
    st.write("Manage the set of confluences used across the app.")
    show_confluence_taxonomy(config_service)


def render_app_settings(config_service: ConfigService) -> None:
    """Render basic application settings (storage backend, etc.)."""
    st.header("Application Settings")

    try:
        app_cfg = config_service.get_app_config()
    except Exception as e:
        st.error(f"Failed to load app configuration: {e}")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Storage Backend")
        current_backend = app_cfg.get("storage_backend", "parquet")
        new_backend = st.selectbox(
            "Select storage backend",
            options=["parquet", "json"],
            index=0 if current_backend == "parquet" else 1,
            help="Parquet is recommended for performance. Switching requires app restart.",
        )
    with col2:
        if st.button("Save Settings"):
            try:
                config_service.update_app_config({"storage_backend": new_backend})
                get_notification_manager().success(
                    f"Saved settings. Storage backend set to '{new_backend}'."
                )
            except Exception as e:
                get_notification_manager().error(f"Failed to save settings: {e}")

def show_confluence_taxonomy(config_service: ConfigService) -> None:
    """Render the Confluences taxonomy manager."""
    try:
        options = config_service.get_confluence_options()
    except Exception as e:
        st.error(f"Failed to load confluences: {e}")
        options = []

    st.write("Edit the list of confluences (one per line):")
    text_val = "\n".join(options)
    edited = st.text_area("Confluence Options", value=text_val, height=200)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Save Confluences", type="primary"):
            try:
                new_options = [line.strip() for line in edited.split("\n") if line.strip()]
                config_service.update_confluence_options(new_options)
                get_notification_manager().success("Confluences updated")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save confluences: {e}")
    with col2:
        if st.button("Reset to Defaults"):
            defaults = [
                "Support/Resistance 1st Retest",
                "Trendline Breakout",
                "Trendline Retest",
                "1 Day EMA 12",
                "1 Day EMA 200",
                "1 Day QVWAP",
                "1 Day YVWAP",
                "AVWAP - Major Swing",
            ]
            try:
                config_service.update_confluence_options(defaults)
                get_notification_manager().info("Confluences reset to defaults")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to reset: {e}")


# Execute the page rendering when imported as a Streamlit page module
show_config_page()
