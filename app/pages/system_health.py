"""
System Health and Diagnostics page for the crypto trading journal application.
Provides health monitoring, performance metrics, and diagnostic tools.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict

import streamlit as st

from app.utils.debug_utils import error_reporter
from app.utils.diagnostics import diagnostic_tool
from app.utils.error_handler import error_handler, handle_exceptions
from app.utils.health_monitor import HealthStatus, system_monitor
from app.utils.logging_config import logging_config
from app.utils.notifications import get_notification_manager
from app.utils.state_management import get_state_manager


@handle_exceptions(context="System Health Page", show_to_user=True)
def show_system_health_page():
    """Display the system health and diagnostics page."""
    st.title("🏥 System Health & Diagnostics")

    # Create tabs for different sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Health Status", "Performance", "Diagnostics", "Error Reports", "System Info"]
    )

    with tab1:
        show_health_status_tab()

    with tab2:
        show_performance_tab()

    with tab3:
        show_diagnostics_tab()

    with tab4:
        show_error_reports_tab()

    with tab5:
        show_system_info_tab()


def show_health_status_tab():
    """Display health status information."""
    st.header("System Health Status")

    # Quick status overview
    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("🔄 Refresh Health Status", key="refresh_health"):
            st.rerun()

    with col2:
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh (30s)", key="auto_refresh_health")
        if auto_refresh:
            st.rerun()

    try:
        # Get system status
        system_status = system_monitor.get_system_status()
        overall_status = system_status.get("overall_status", "unknown")

        # Display overall status
        status_colors = {
            "healthy": "🟢",
            "warning": "🟡",
            "critical": "🔴",
            "unknown": "⚪",
        }

        status_color = status_colors.get(overall_status, "⚪")
        st.subheader(f"{status_color} Overall Status: {overall_status.title()}")

        # Display individual health checks
        health_checks = system_status.get("health_checks", [])

        if health_checks:
            st.subheader("Health Check Details")

            for check in health_checks:
                check_status = check.get("status", "unknown")
                check_color = status_colors.get(check_status, "⚪")

                with st.expander(
                    f"{check_color} {check['name'].replace('_', ' ').title()}",
                    expanded=(check_status in ["warning", "critical"]),
                ):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.write(f"**Status:** {check_status.title()}")
                        st.write(f"**Message:** {check['message']}")

                    with col2:
                        st.metric("Duration", f"{check.get('duration_ms', 0):.1f}ms")

        # Monitoring status
        st.subheader("Monitoring Status")
        monitoring_active = system_status.get("monitoring_active", False)

        col1, col2, col3 = st.columns(3)

        with col1:
            if monitoring_active:
                st.success("✅ Monitoring Active")
                if st.button("Stop Monitoring", key="stop_monitoring"):
                    system_monitor.stop_monitoring()
                    get_notification_manager().success("System monitoring stopped")
                    st.rerun()
            else:
                st.warning("⏸️ Monitoring Inactive")
                if st.button("Start Monitoring", key="start_monitoring"):
                    system_monitor.start_monitoring()
                    get_notification_manager().success("System monitoring started")
                    st.rerun()

        with col2:
            st.info(
                f"Last Update: {datetime.fromisoformat(system_status['timestamp']).strftime('%H:%M:%S')}"
            )

        with col3:
            if st.button("Run Health Checks", key="run_health_checks"):
                with st.spinner("Running health checks..."):
                    results = system_monitor.health_checker.run_all_checks()
                    get_notification_manager().success(
                        f"Completed {len(results)} health checks"
                    )
                    st.rerun()

    except Exception as e:
        st.error(f"Failed to load health status: {e}")


def show_performance_tab():
    """Display performance metrics and monitoring."""
    st.header("Performance Metrics")

    # Time range selector
    col1, col2 = st.columns([1, 3])

    with col1:
        time_range = st.selectbox(
            "Time Range",
            ["Last 10 minutes", "Last hour", "Last 6 hours", "Last 24 hours"],
            key="perf_time_range",
        )

    with col2:
        if st.button("🔄 Refresh Metrics", key="refresh_metrics"):
            st.rerun()

    # Convert time range to timedelta
    time_deltas = {
        "Last 10 minutes": timedelta(minutes=10),
        "Last hour": timedelta(hours=1),
        "Last 6 hours": timedelta(hours=6),
        "Last 24 hours": timedelta(hours=24),
    }

    since = datetime.now() - time_deltas[time_range]

    try:
        # Get performance metrics
        metric_names = ["cpu_usage", "memory_usage", "process_memory", "process_cpu"]

        # Display current metrics
        st.subheader("Current System Metrics")

        col1, col2, col3, col4 = st.columns(4)

        # Get current values
        import psutil

        current_cpu = psutil.cpu_percent(interval=1)
        current_memory = psutil.virtual_memory().percent

        process = psutil.Process()
        current_process_memory = process.memory_percent()
        current_process_cpu = process.cpu_percent()

        with col1:
            st.metric("System CPU", f"{current_cpu:.1f}%")

        with col2:
            st.metric("System Memory", f"{current_memory:.1f}%")

        with col3:
            st.metric("Process Memory", f"{current_process_memory:.1f}%")

        with col4:
            st.metric("Process CPU", f"{current_process_cpu:.1f}%")

        # Display metric summaries
        st.subheader(f"Performance Summary ({time_range})")

        for metric_name in metric_names:
            summary = system_monitor.performance_monitor.get_metric_summary(
                metric_name, since=since
            )

            if summary.get("count", 0) > 0:
                with st.expander(
                    f"📊 {metric_name.replace('_', ' ').title()}", expanded=False
                ):
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        st.metric("Count", summary["count"])

                    with col2:
                        st.metric("Average", f"{summary['avg']:.1f}{summary['unit']}")

                    with col3:
                        st.metric("Minimum", f"{summary['min']:.1f}{summary['unit']}")

                    with col4:
                        st.metric("Maximum", f"{summary['max']:.1f}{summary['unit']}")

                    with col5:
                        st.metric("Latest", f"{summary['latest']:.1f}{summary['unit']}")

        # Performance recommendations
        st.subheader("Performance Recommendations")

        recommendations = []

        if current_cpu > 80:
            recommendations.append(
                "🔴 High CPU usage detected. Consider closing other applications."
            )
        elif current_cpu > 60:
            recommendations.append("🟡 Elevated CPU usage. Monitor system performance.")

        if current_memory > 85:
            recommendations.append(
                "🔴 High memory usage detected. Consider restarting the application."
            )
        elif current_memory > 70:
            recommendations.append(
                "🟡 Elevated memory usage. Monitor memory consumption."
            )

        if current_process_memory > 50:
            recommendations.append(
                "🟡 Application using significant memory. Consider data cleanup."
            )

        if recommendations:
            for rec in recommendations:
                st.warning(rec)
        else:
            st.success("✅ System performance is within normal ranges.")

    except Exception as e:
        st.error(f"Failed to load performance metrics: {e}")


def show_diagnostics_tab():
    """Display comprehensive system diagnostics."""
    st.header("System Diagnostics")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔍 Run Full Diagnostics", key="run_diagnostics"):
            with st.spinner("Running comprehensive diagnostics..."):
                try:
                    diagnostics = diagnostic_tool.run_full_diagnostics()
                    st.session_state.diagnostics_results = diagnostics
                    get_notification_manager().success(
                        "Diagnostics completed successfully"
                    )
                except Exception as e:
                    st.error(f"Diagnostics failed: {e}")
                    return

    with col2:
        if st.button("📊 Quick Status Check", key="quick_status"):
            try:
                quick_status = diagnostic_tool.get_quick_status()
                st.session_state.quick_status = quick_status
                get_notification_manager().info("Quick status check completed")
            except Exception as e:
                st.error(f"Quick status check failed: {e}")

    # Display quick status if available
    if hasattr(st.session_state, "quick_status"):
        st.subheader("Quick Status")

        quick_status = st.session_state.quick_status

        if "error" not in quick_status:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                health_color = {
                    "healthy": "🟢",
                    "warning": "🟡",
                    "critical": "🔴",
                    "unknown": "⚪",
                }.get(quick_status.get("overall_health", "unknown"), "⚪")

                st.metric(
                    "Health",
                    f"{health_color} {quick_status.get('overall_health', 'unknown').title()}",
                )

            with col2:
                st.metric("CPU Usage", f"{quick_status.get('cpu_percent', 0):.1f}%")

            with col3:
                st.metric(
                    "Memory Usage", f"{quick_status.get('memory_percent', 0):.1f}%"
                )

            with col4:
                st.metric("Disk Free", f"{quick_status.get('disk_free_gb', 0):.1f}GB")

            # Additional status info
            col1, col2 = st.columns(2)

            with col1:
                data_dir_status = (
                    "✅" if quick_status.get("data_directory_exists") else "❌"
                )
                st.write(f"**Data Directory:** {data_dir_status}")

            with col2:
                error_count = quick_status.get("recent_errors", 0)
                error_status = "✅" if error_count == 0 else f"⚠️ {error_count}"
                st.write(f"**Recent Errors:** {error_status}")
        else:
            st.error(f"Quick status error: {quick_status['error']}")

    # Display full diagnostics if available
    if hasattr(st.session_state, "diagnostics_results"):
        st.subheader("Full Diagnostic Results")

        diagnostics = st.session_state.diagnostics_results

        # Show recommendations first
        recommendations = diagnostics.get("recommendations", [])
        if recommendations:
            st.subheader("🎯 Recommendations")
            for rec in recommendations:
                if rec.startswith("CRITICAL"):
                    st.error(rec)
                elif rec.startswith("WARNING"):
                    st.warning(rec)
                else:
                    st.info(rec)

        # Detailed sections
        sections = [
            ("System Information", "system_info"),
            ("Application State", "application_state"),
            ("Data Integrity", "data_integrity"),
            ("Configuration", "configuration"),
            ("Performance Analysis", "performance"),
            ("Health Status", "health_status"),
            ("Error Analysis", "error_analysis"),
        ]

        for section_name, section_key in sections:
            if section_key in diagnostics:
                with st.expander(f"📋 {section_name}", expanded=False):
                    section_data = diagnostics[section_key]

                    if isinstance(section_data, dict):
                        # Display key metrics for each section
                        if section_key == "system_info":
                            show_system_info_summary(section_data)
                        elif section_key == "data_integrity":
                            show_data_integrity_summary(section_data)
                        elif section_key == "performance":
                            show_performance_summary(section_data)
                        else:
                            st.json(section_data)
                    else:
                        st.write(section_data)

        # Export option
        if st.button("💾 Export Diagnostics", key="export_diagnostics"):
            try:
                file_path = diagnostic_tool.export_diagnostics()
                st.success(f"Diagnostics exported to: {file_path}")
            except Exception as e:
                st.error(f"Export failed: {e}")


def show_system_info_summary(system_info: Dict[str, Any]):
    """Display system information summary."""
    if "platform" in system_info:
        platform = system_info["platform"]
        st.write(
            f"**OS:** {platform.get('system', 'Unknown')} {platform.get('release', '')}"
        )
        st.write(f"**Architecture:** {platform.get('machine', 'Unknown')}")
        st.write(f"**Python:** {platform.get('python_version', 'Unknown')}")

    if "system_resources" in system_info:
        resources = system_info["system_resources"]
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("CPU Cores", resources.get("cpu_count", "Unknown"))

        with col2:
            total_memory_gb = resources.get("memory_total", 0) / (1024**3)
            st.metric("Total Memory", f"{total_memory_gb:.1f}GB")

        with col3:
            st.metric("Memory Usage", f"{resources.get('memory_percent', 0):.1f}%")


def show_data_integrity_summary(data_integrity: Dict[str, Any]):
    """Display data integrity summary."""
    integrity_checks = data_integrity.get("integrity_checks", {})

    # Directory status
    st.write(
        f"**Data Directory Exists:** {'✅' if integrity_checks.get('data_directory_exists') else '❌'}"
    )
    st.write(
        f"**Data Directory Writable:** {'✅' if integrity_checks.get('data_directory_writable') else '❌'}"
    )

    # Critical files
    critical_files = integrity_checks.get("critical_files", {})
    if critical_files:
        st.write("**Critical Files:**")
        for file_name, file_info in critical_files.items():
            status = (
                "✅"
                if file_info.get("exists") and file_info.get("valid_json", True)
                else "❌"
            )
            size_kb = file_info.get("size_bytes", 0) / 1024
            st.write(f"  - {file_name}: {status} ({size_kb:.1f}KB)")

    # Disk space
    disk_space = integrity_checks.get("disk_space", {})
    if disk_space and "error" not in disk_space:
        status_icon = {"ok": "✅", "warning": "🟡", "critical": "🔴"}.get(
            disk_space.get("status"), "⚪"
        )
        st.write(
            f"**Disk Space:** {status_icon} {disk_space.get('free_gb', 0):.1f}GB free"
        )


def show_performance_summary(performance: Dict[str, Any]):
    """Display performance analysis summary."""
    # Recent metrics
    recent_metrics = performance.get("recent_metrics", {})
    if recent_metrics:
        st.write("**Recent Performance Metrics:**")
        for metric_name, summary in recent_metrics.items():
            if summary.get("count", 0) > 0:
                st.write(
                    f"  - {metric_name.replace('_', ' ').title()}: {summary['avg']:.1f}{summary['unit']} (avg)"
                )

    # Bottlenecks
    bottlenecks = performance.get("bottlenecks", [])
    if bottlenecks:
        st.write("**Performance Issues:**")
        for bottleneck in bottlenecks:
            st.warning(f"⚠️ {bottleneck}")


def show_error_reports_tab():
    """Display error reports and analysis."""
    st.header("Error Reports & Analysis")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔄 Refresh Error Reports", key="refresh_errors"):
            st.rerun()

    with col2:
        if st.button("🧹 Clear Error Statistics", key="clear_error_stats"):
            error_handler.clear_error_stats()
            get_notification_manager().success("Error statistics cleared")
            st.rerun()

    try:
        # Error statistics
        error_stats = error_handler.get_error_stats()

        st.subheader("Error Statistics")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Errors", error_stats.get("total_errors", 0))

        with col2:
            st.metric("Unique Error Types", len(error_stats.get("error_counts", {})))

        with col3:
            recent_count = len(
                [
                    t
                    for t in error_stats.get("last_errors", {}).values()
                    if (datetime.now() - t).total_seconds() < 3600
                ]
            )
            st.metric("Errors (Last Hour)", recent_count)

        # Error breakdown
        if error_stats.get("error_counts"):
            st.subheader("Error Breakdown")

            error_counts = error_stats["error_counts"]
            sorted_errors = sorted(
                error_counts.items(), key=lambda x: x[1], reverse=True
            )

            for error_key, count in sorted_errors[:10]:  # Show top 10
                st.write(f"**{error_key}:** {count} occurrences")

        # Recent error reports
        st.subheader("Recent Error Reports")

        recent_reports = error_reporter.get_recent_reports(limit=10)

        if recent_reports:
            for i, report in enumerate(recent_reports):
                with st.expander(
                    f"🚨 {report['error_type']} - {report['timestamp'][:19]}",
                    expanded=(i == 0),
                ):
                    st.write(f"**Error Type:** {report['error_type']}")
                    st.write(f"**Message:** {report['error_message']}")
                    st.write(f"**Context:** {report.get('context', 'N/A')}")
                    st.write(f"**File:** {report['file']}")

                    if st.button(f"View Full Report", key=f"view_report_{i}"):
                        # Load and display full report
                        try:
                            report_path = error_reporter.reports_dir / report["file"]
                            with open(report_path, "r") as f:
                                full_report = json.load(f)

                            st.json(full_report)
                        except Exception as e:
                            st.error(f"Failed to load report: {e}")
        else:
            st.info("No recent error reports found.")

        # Log analysis
        st.subheader("Log File Analysis")

        log_stats = logging_config.get_log_stats()

        if log_stats.get("log_files"):
            col1, col2 = st.columns(2)

            with col1:
                st.metric("Log Files", len(log_stats["log_files"]))

            with col2:
                total_size_mb = log_stats["total_size"] / (1024 * 1024)
                st.metric("Total Size", f"{total_size_mb:.1f}MB")

            # Log file details
            with st.expander("📄 Log File Details", expanded=False):
                for log_file in log_stats["log_files"]:
                    size_mb = log_file["size"] / (1024 * 1024)
                    st.write(
                        f"**{log_file['name']}:** {size_mb:.1f}MB (modified: {log_file['modified'].strftime('%Y-%m-%d %H:%M')})"
                    )
        else:
            st.info("No log files found.")

    except Exception as e:
        st.error(f"Failed to load error reports: {e}")


def show_system_info_tab():
    """Display detailed system information."""
    st.header("System Information")

    if st.button("🔄 Refresh System Info", key="refresh_system_info"):
        st.rerun()

    try:
        # Get system information
        from app.utils.debug_utils import get_debug_summary

        debug_summary = get_debug_summary()

        # System information
        if "system" in debug_summary:
            st.subheader("🖥️ System Information")
            show_system_info_summary(debug_summary["system"])

        # Application state
        if "application" in debug_summary:
            st.subheader("🚀 Application State")

            app_state = debug_summary["application"]

            col1, col2 = st.columns(2)

            with col1:
                st.write(
                    f"**Working Directory:** {app_state.get('working_directory', 'Unknown')}"
                )

                env_vars = app_state.get("environment_variables", {})
                if env_vars:
                    st.write("**Environment Variables:**")
                    for var, value in env_vars.items():
                        st.write(f"  - {var}: {value}")

            with col2:
                streamlit_session = app_state.get("streamlit_session", {})
                if streamlit_session:
                    st.write("**Streamlit Session State:**")
                    for key, value_type in streamlit_session.items():
                        st.write(f"  - {key}: {value_type}")

        # File system information
        if "filesystem" in debug_summary:
            st.subheader("📁 File System")

            filesystem = debug_summary["filesystem"]

            data_dir = filesystem.get("data_directory", {})
            if data_dir:
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write(f"**Path:** {data_dir.get('path', 'Unknown')}")

                with col2:
                    st.write(f"**Exists:** {'✅' if data_dir.get('exists') else '❌'}")

                with col3:
                    st.write(
                        f"**Writable:** {'✅' if data_dir.get('is_writable') else '❌'}"
                    )

            # File listing
            files = filesystem.get("files", [])
            if files:
                st.write("**Files and Directories:**")

                for file_info in files[:20]:  # Show first 20 files
                    if "error" in file_info:
                        st.write(f"❌ {file_info['name']}: {file_info['error']}")
                    else:
                        file_type = "📁" if file_info["type"] == "directory" else "📄"
                        size_info = (
                            f" ({file_info['size']} bytes)"
                            if file_info.get("size")
                            else ""
                        )
                        st.write(f"{file_type} {file_info['name']}{size_info}")

                if len(files) > 20:
                    st.write(f"... and {len(files) - 20} more files")

    except Exception as e:
        st.error(f"Failed to load system information: {e}")


# Execute the main page function directly (Streamlit multipage approach)
show_system_health_page()
