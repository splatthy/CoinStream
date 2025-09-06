"""
Main Streamlit application entry point with navigation and session state management.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st

from app.services.analysis_service import AnalysisService
from app.services.config_service import ConfigService
from app.services.data_service import DataService
from app.utils.data_refresh import get_data_refresh_manager, register_refresh_operation
from app.utils.debug_utils import error_reporter
from app.utils.error_handler import error_handler, handle_exceptions
from app.utils.logging_config import get_logger, setup_application_logging
from app.utils.notifications import get_notification_manager, render_notifications
from app.utils.state_management import (
    get_loading_manager,
    get_state_manager,
    with_loading_state,
)

# Initialize logging system
data_path = os.getenv("DATA_PATH", "/app/data")
setup_application_logging(data_path=data_path)
logger = get_logger(__name__)


class AppState:
    """Manages application state and session data."""

    def __init__(self):
        """Initialize application state."""
        self.config_service: Optional[ConfigService] = None
        self.data_service: Optional[DataService] = None
        self.analysis_service: Optional[AnalysisService] = None
        self.last_refresh: Optional[datetime] = None
        self.initialization_error: Optional[str] = None

        # Get state and notification managers
        self.state_manager = get_state_manager()
        self.loading_manager = get_loading_manager()
        self.notification_manager = get_notification_manager()
        self.data_refresh_manager = get_data_refresh_manager()

    @handle_exceptions(context="Service Initialization", show_to_user=True)
    def initialize_services(self, data_path: str = "/app/data") -> None:
        """Initialize all application services."""
        try:
            self.loading_manager.set_loading(
                "initialization", True, "Initializing application services..."
            )

            self.config_service = ConfigService(data_path)
            self.data_service = DataService(data_path)
            self.analysis_service = AnalysisService(self.data_service)

            # Initialize default configuration if needed
            self.config_service.initialize_default_config()

            # Cache services in state manager
            self.state_manager.set("config_service", self.config_service)
            self.state_manager.set("data_service", self.data_service)
            self.state_manager.set("analysis_service", self.analysis_service)

            # Register data refresh operations
            self._register_refresh_operations()

            logger.info("Application services initialized successfully")
            self.notification_manager.success("Application initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            self.initialization_error = str(e)
            self.notification_manager.error(f"Failed to initialize application: {e}")
            # Generate error report for initialization failures
            error_reporter.save_error_report(e, "Service Initialization")
            raise
        finally:
            self.loading_manager.clear_loading("initialization")

    @with_loading_state("data_refresh", "Refreshing data...")
    @handle_exceptions(context="Data Refresh", show_to_user=True)
    def refresh_data(self) -> None:
        """Refresh application data."""
        try:
            # Clear data service cache to force reload
            if self.data_service:
                self.data_service.clear_cache()

            # Clear state manager cache
            self.state_manager.clear_cache()

            # Update last refresh time
            self.last_refresh = datetime.now()
            self.state_manager.set("last_refresh", self.last_refresh)

            self.notification_manager.success("Data refreshed successfully")

        except Exception as e:
            logger.error(f"Failed to refresh data: {e}")
            self.notification_manager.error(f"Failed to refresh data: {e}")
            raise

    def has_initialization_error(self) -> bool:
        """Check if there was an initialization error."""
        return self.initialization_error is not None

    def _register_refresh_operations(self) -> None:
        """Register data refresh operations."""
        if not all([self.config_service, self.data_service, self.analysis_service]):
            return

        # Register trade data refresh
        register_refresh_operation(
            operation_name="trade_data",
            refresh_function=lambda: self.data_service.load_trades(),
            cache_key="cached_trades",
            cache_ttl=timedelta(minutes=5),
            loading_message="Loading trade data...",
            success_message="Trade data loaded successfully",
            error_message="Failed to load trade data",
        )

        # Register configuration refresh
        register_refresh_operation(
            operation_name="app_config",
            refresh_function=lambda: self.config_service.get_app_config(),
            cache_key="cached_app_config",
            cache_ttl=timedelta(minutes=10),
            loading_message="Loading configuration...",
            success_message="Configuration loaded successfully",
            error_message="Failed to load configuration",
        )


def get_app_state() -> AppState:
    """Get or create application state from session state."""
    if "app_state" not in st.session_state:
        st.session_state.app_state = AppState()
        st.session_state.app_state.initialize_services()

    return st.session_state.app_state


def setup_page_config() -> None:
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="Crypto Trading Journal",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_sidebar_navigation() -> str:
    """Render sidebar navigation and return selected page."""
    st.sidebar.title("📈 Trading Journal")

    # Navigation menu
    pages = {
        "Trade History": "trade_history",
        "Trend Analysis": "trend_analysis",
        "Confluence Analysis": "confluence_analysis",
        "Configuration": "config",
    }

    selected_page = st.sidebar.selectbox(
        "Navigate to:", options=list(pages.keys()), key="page_selector"
    )

    # Data refresh section
    render_data_controls()

    return pages[selected_page]


def render_data_controls() -> None:
    """Render data management controls in sidebar."""
    st.sidebar.subheader("📊 Data Management")

    app_state = get_app_state()

    # Main refresh button
    if st.sidebar.button(
        "Refresh Data", key="refresh_all_button", use_container_width=True
    ):
        app_state.refresh_data()
        st.rerun()

    # Display last refresh time
    if app_state.last_refresh:
        time_str = app_state.last_refresh.strftime("%H:%M:%S")
        st.sidebar.caption(f"Last refresh: {time_str}")
    else:
        st.sidebar.caption("No recent refresh")


def render_messages() -> None:
    """Render notifications and loading states."""
    app_state = get_app_state()

    # Render notifications
    render_notifications()

    # Show initialization error if present
    if app_state.has_initialization_error():
        st.error(f"Application initialization failed: {app_state.initialization_error}")
        st.info("Please check the logs and try refreshing the page.")


@handle_exceptions(context="Main Application", show_to_user=True)
def main() -> None:
    """Main application entry point."""
    try:
        # Setup page configuration
        setup_page_config()

        # Get application state
        get_app_state()

        # Render navigation and get selected page
        selected_page = render_sidebar_navigation()

        # Render messages and notifications
        render_messages()

        # Route to appropriate page
        if selected_page == "trade_history":
            from app.pages.trade_history import show_trade_history_page

            show_trade_history_page()
        elif selected_page == "trend_analysis":
            from app.pages.trend_analysis import show_trend_analysis_page

            show_trend_analysis_page()
        elif selected_page == "confluence_analysis":
            from app.pages.confluence_analysis import show_confluence_analysis_page

            show_confluence_analysis_page()
        elif selected_page == "config":
            from app.pages.config import show_config_page

            show_config_page()
        else:
            st.error(f"Unknown page: {selected_page}")

    except Exception as e:
        logger.error(f"Application error: {e}")
        error_reporter.save_error_report(e, "Main Application")
        st.error(
            "A critical application error occurred. Please check the logs for details."
        )

        # Show error statistics in sidebar for debugging
        if st.sidebar.button("Show Error Details"):
            error_stats = error_handler.get_error_stats()
            st.sidebar.json(error_stats)


if __name__ == "__main__":
    main()
