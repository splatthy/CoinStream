"""
Diagnostic tools for troubleshooting the crypto trading journal application.
Provides comprehensive system diagnostics, configuration validation, and troubleshooting utilities.
"""

import logging
import json
import traceback
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st

from .logging_config import get_logger
from .error_handler import handle_exceptions, safe_execute
from .health_monitor import system_monitor, HealthStatus
from .debug_utils import DebugInfo, error_reporter


logger = get_logger(__name__)


class DiagnosticTool:
    """Comprehensive diagnostic tool for system troubleshooting."""
    
    def __init__(self, data_path: str = "data"):
        self.data_path = Path(data_path)
        self.diagnostics: Dict[str, Any] = {}
    
    @handle_exceptions(context="System Diagnostics", show_to_user=False)
    def run_full_diagnostics(self) -> Dict[str, Any]:
        """
        Run comprehensive system diagnostics.
        
        Returns:
            Dictionary containing all diagnostic results
        """
        logger.info("Starting full system diagnostics")
        
        diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "system_info": self._diagnose_system(),
            "application_state": self._diagnose_application(),
            "data_integrity": self._diagnose_data_integrity(),
            "configuration": self._diagnose_configuration(),
            "performance": self._diagnose_performance(),
            "health_status": self._diagnose_health(),
            "error_analysis": self._diagnose_errors(),
            "recommendations": []
        }
        
        # Generate recommendations based on findings
        diagnostics["recommendations"] = self._generate_recommendations(diagnostics)
        
        self.diagnostics = diagnostics
        logger.info("Completed full system diagnostics")
        
        return diagnostics
    
    def _diagnose_system(self) -> Dict[str, Any]:
        """Diagnose system-level information."""
        return safe_execute(
            DebugInfo.get_system_info,
            default_return={"error": "Failed to get system info"},
            show_to_user=False
        )
    
    def _diagnose_application(self) -> Dict[str, Any]:
        """Diagnose application state and configuration."""
        app_state = safe_execute(
            DebugInfo.get_application_state,
            default_return={"error": "Failed to get application state"},
            show_to_user=False
        )
        
        # Add Streamlit-specific diagnostics
        streamlit_info = {}
        try:
            if hasattr(st, 'session_state'):
                streamlit_info["session_state_keys"] = len(st.session_state.keys())
                streamlit_info["has_session_state"] = True
            else:
                streamlit_info["has_session_state"] = False
            
            # Check if running in Streamlit context
            try:
                st.get_option("server.port")
                streamlit_info["in_streamlit_context"] = True
            except:
                streamlit_info["in_streamlit_context"] = False
                
        except Exception as e:
            streamlit_info["error"] = str(e)
        
        app_state["streamlit_diagnostics"] = streamlit_info
        return app_state
    
    def _diagnose_data_integrity(self) -> Dict[str, Any]:
        """Diagnose data integrity and file system status."""
        file_system_info = safe_execute(
            DebugInfo.get_file_system_info,
            str(self.data_path),
            default_return={"error": "Failed to get file system info"},
            show_to_user=False
        )
        
        # Additional data integrity checks
        integrity_checks = {
            "data_directory_exists": self.data_path.exists(),
            "data_directory_writable": self.data_path.exists() and self.data_path.is_dir(),
            "critical_files": self._check_critical_files(),
            "file_permissions": self._check_file_permissions(),
            "disk_space": self._check_disk_space_detailed()
        }
        
        return {
            "file_system": file_system_info,
            "integrity_checks": integrity_checks
        }
    
    def _check_critical_files(self) -> Dict[str, Any]:
        """Check for existence and validity of critical files."""
        critical_files = {
            "trades.json": self.data_path / "trades.json",
            "config.json": self.data_path / "config.json",
            "exchange_configs.json": self.data_path / "exchange_configs.json"
        }
        
        file_status = {}
        for name, path in critical_files.items():
            status = {
                "exists": path.exists(),
                "readable": False,
                "valid_json": False,
                "size_bytes": 0,
                "last_modified": None
            }
            
            if path.exists():
                try:
                    status["readable"] = path.is_file()
                    status["size_bytes"] = path.stat().st_size
                    status["last_modified"] = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                    
                    # Check if it's valid JSON
                    if path.suffix == ".json":
                        with open(path, 'r') as f:
                            json.load(f)
                        status["valid_json"] = True
                        
                except Exception as e:
                    status["error"] = str(e)
            
            file_status[name] = status
        
        return file_status
    
    def _check_file_permissions(self) -> Dict[str, Any]:
        """Check file and directory permissions."""
        import os
        
        permissions = {}
        
        # Check data directory permissions
        if self.data_path.exists():
            permissions["data_directory"] = {
                "readable": os.access(self.data_path, os.R_OK),
                "writable": os.access(self.data_path, os.W_OK),
                "executable": os.access(self.data_path, os.X_OK)
            }
        
        # Check subdirectories
        subdirs = ["logs", "backups", "error_reports"]
        for subdir in subdirs:
            subdir_path = self.data_path / subdir
            if subdir_path.exists():
                permissions[subdir] = {
                    "readable": os.access(subdir_path, os.R_OK),
                    "writable": os.access(subdir_path, os.W_OK),
                    "executable": os.access(subdir_path, os.X_OK)
                }
        
        return permissions
    
    def _check_disk_space_detailed(self) -> Dict[str, Any]:
        """Check detailed disk space information."""
        try:
            import psutil
            
            # Get disk usage for the data directory
            disk_usage = psutil.disk_usage(str(self.data_path))
            
            return {
                "total_gb": disk_usage.total / (1024**3),
                "used_gb": disk_usage.used / (1024**3),
                "free_gb": disk_usage.free / (1024**3),
                "used_percent": (disk_usage.used / disk_usage.total) * 100,
                "status": "critical" if disk_usage.free < (1024**3) else "warning" if disk_usage.free < (5 * 1024**3) else "ok"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _diagnose_configuration(self) -> Dict[str, Any]:
        """Diagnose application configuration."""
        config_diagnostics = {
            "config_files": {},
            "environment_variables": {},
            "streamlit_config": {}
        }
        
        # Check configuration files
        config_files = [
            "config.json",
            "exchange_configs.json",
            "custom_fields.json"
        ]
        
        for config_file in config_files:
            config_path = self.data_path / config_file
            file_info = {
                "exists": config_path.exists(),
                "valid": False,
                "content_summary": {}
            }
            
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        content = json.load(f)
                    file_info["valid"] = True
                    file_info["content_summary"] = {
                        "keys": list(content.keys()) if isinstance(content, dict) else "not_dict",
                        "size": len(str(content))
                    }
                except Exception as e:
                    file_info["error"] = str(e)
            
            config_diagnostics["config_files"][config_file] = file_info
        
        # Check environment variables
        import os
        env_vars = ["LOG_LEVEL", "DATA_PATH", "STREAMLIT_SERVER_PORT"]
        for var in env_vars:
            config_diagnostics["environment_variables"][var] = os.getenv(var)
        
        # Check Streamlit configuration
        try:
            config_diagnostics["streamlit_config"] = {
                "server_port": st.get_option("server.port"),
                "server_address": st.get_option("server.address"),
                "theme": st.get_option("theme.base") if hasattr(st, 'get_option') else "unknown"
            }
        except Exception as e:
            config_diagnostics["streamlit_config"]["error"] = str(e)
        
        return config_diagnostics
    
    def _diagnose_performance(self) -> Dict[str, Any]:
        """Diagnose performance-related issues."""
        performance_info = {
            "recent_metrics": {},
            "system_resources": {},
            "bottlenecks": []
        }
        
        # Get recent performance metrics
        try:
            metric_names = ["cpu_usage", "memory_usage", "process_memory", "process_cpu"]
            for metric_name in metric_names:
                summary = system_monitor.performance_monitor.get_metric_summary(
                    metric_name,
                    since=datetime.now() - timedelta(minutes=30)
                )
                if summary["count"] > 0:
                    performance_info["recent_metrics"][metric_name] = summary
        except Exception as e:
            performance_info["recent_metrics"]["error"] = str(e)
        
        # Get current system resources
        try:
            import psutil
            performance_info["system_resources"] = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_io": psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
                "network_io": psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {}
            }
        except Exception as e:
            performance_info["system_resources"]["error"] = str(e)
        
        # Identify potential bottlenecks
        performance_info["bottlenecks"] = self._identify_bottlenecks(performance_info)
        
        return performance_info
    
    def _identify_bottlenecks(self, performance_info: Dict[str, Any]) -> List[str]:
        """Identify potential performance bottlenecks."""
        bottlenecks = []
        
        try:
            # Check CPU usage
            cpu_metrics = performance_info["recent_metrics"].get("cpu_usage", {})
            if cpu_metrics.get("avg", 0) > 80:
                bottlenecks.append("High CPU usage detected")
            
            # Check memory usage
            memory_metrics = performance_info["recent_metrics"].get("memory_usage", {})
            if memory_metrics.get("avg", 0) > 85:
                bottlenecks.append("High memory usage detected")
            
            # Check current system resources
            resources = performance_info["system_resources"]
            if resources.get("cpu_percent", 0) > 90:
                bottlenecks.append("Critical CPU usage")
            
            if resources.get("memory_percent", 0) > 90:
                bottlenecks.append("Critical memory usage")
                
        except Exception as e:
            bottlenecks.append(f"Error analyzing bottlenecks: {e}")
        
        return bottlenecks
    
    def _diagnose_health(self) -> Dict[str, Any]:
        """Diagnose overall system health."""
        try:
            return system_monitor.get_system_status()
        except Exception as e:
            return {"error": str(e)}
    
    def _diagnose_errors(self) -> Dict[str, Any]:
        """Diagnose recent errors and issues."""
        error_analysis = {
            "recent_reports": [],
            "error_patterns": {},
            "log_analysis": {}
        }
        
        # Get recent error reports
        try:
            recent_reports = error_reporter.get_recent_reports(limit=10)
            error_analysis["recent_reports"] = recent_reports
            
            # Analyze error patterns
            error_types = {}
            for report in recent_reports:
                error_type = report.get("error_type", "unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            error_analysis["error_patterns"] = error_types
            
        except Exception as e:
            error_analysis["recent_reports_error"] = str(e)
        
        # Analyze log files
        try:
            log_dir = self.data_path / "logs"
            if log_dir.exists():
                log_files = list(log_dir.glob("*.log"))
                error_analysis["log_analysis"] = {
                    "log_files_count": len(log_files),
                    "total_size_mb": sum(f.stat().st_size for f in log_files) / (1024*1024),
                    "most_recent": max(log_files, key=lambda f: f.stat().st_mtime).name if log_files else None
                }
                
                # Check for error patterns in recent logs
                if log_files:
                    error_analysis["log_analysis"]["recent_errors"] = self._analyze_recent_log_errors(log_files[0])
            
        except Exception as e:
            error_analysis["log_analysis_error"] = str(e)
        
        return error_analysis
    
    def _analyze_recent_log_errors(self, log_file: Path, lines_to_check: int = 100) -> Dict[str, Any]:
        """Analyze recent log entries for error patterns."""
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Check last N lines
            recent_lines = lines[-lines_to_check:] if len(lines) > lines_to_check else lines
            
            error_count = 0
            warning_count = 0
            critical_count = 0
            
            for line in recent_lines:
                if "ERROR" in line:
                    error_count += 1
                elif "WARNING" in line:
                    warning_count += 1
                elif "CRITICAL" in line:
                    critical_count += 1
            
            return {
                "lines_analyzed": len(recent_lines),
                "error_count": error_count,
                "warning_count": warning_count,
                "critical_count": critical_count,
                "error_rate": error_count / len(recent_lines) if recent_lines else 0
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _generate_recommendations(self, diagnostics: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on diagnostic results."""
        recommendations = []
        
        try:
            # Check health status
            health_status = diagnostics.get("health_status", {})
            overall_status = health_status.get("overall_status", "unknown")
            
            if overall_status == "critical":
                recommendations.append("CRITICAL: System health issues detected. Check health_status section for details.")
            elif overall_status == "warning":
                recommendations.append("WARNING: System performance issues detected. Monitor system resources.")
            
            # Check disk space
            data_integrity = diagnostics.get("data_integrity", {})
            disk_info = data_integrity.get("integrity_checks", {}).get("disk_space", {})
            
            if disk_info.get("status") == "critical":
                recommendations.append("CRITICAL: Low disk space. Free up disk space immediately.")
            elif disk_info.get("status") == "warning":
                recommendations.append("WARNING: Disk space getting low. Consider cleaning up old files.")
            
            # Check configuration issues
            config_info = diagnostics.get("configuration", {})
            config_files = config_info.get("config_files", {})
            
            for file_name, file_info in config_files.items():
                if not file_info.get("exists"):
                    recommendations.append(f"Missing configuration file: {file_name}")
                elif not file_info.get("valid"):
                    recommendations.append(f"Invalid configuration file: {file_name}")
            
            # Check performance bottlenecks
            performance_info = diagnostics.get("performance", {})
            bottlenecks = performance_info.get("bottlenecks", [])
            
            for bottleneck in bottlenecks:
                recommendations.append(f"Performance issue: {bottleneck}")
            
            # Check error patterns
            error_analysis = diagnostics.get("error_analysis", {})
            error_patterns = error_analysis.get("error_patterns", {})
            
            if error_patterns:
                total_errors = sum(error_patterns.values())
                if total_errors > 10:
                    recommendations.append(f"High error rate detected: {total_errors} recent errors")
            
            # Check data integrity
            critical_files = data_integrity.get("integrity_checks", {}).get("critical_files", {})
            for file_name, file_info in critical_files.items():
                if file_info.get("exists") and not file_info.get("valid_json"):
                    recommendations.append(f"Data corruption detected in {file_name}")
            
            if not recommendations:
                recommendations.append("System appears to be functioning normally.")
                
        except Exception as e:
            recommendations.append(f"Error generating recommendations: {e}")
        
        return recommendations
    
    def export_diagnostics(self, file_path: Optional[str] = None) -> str:
        """
        Export diagnostic results to a file.
        
        Args:
            file_path: Optional custom file path
        
        Returns:
            Path to the exported file
        """
        if not self.diagnostics:
            self.run_full_diagnostics()
        
        if not file_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = str(self.data_path / f"diagnostics_{timestamp}.json")
        
        try:
            with open(file_path, 'w') as f:
                json.dump(self.diagnostics, f, indent=2, default=str)
            
            logger.info(f"Diagnostics exported to: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to export diagnostics: {e}")
            raise
    
    def get_quick_status(self) -> Dict[str, Any]:
        """Get a quick system status summary."""
        try:
            health_results = system_monitor.health_checker.run_all_checks()
            overall_status = system_monitor.health_checker.get_overall_status(health_results)
            
            # Get basic system info
            import psutil
            
            return {
                "overall_health": overall_status.value,
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_free_gb": psutil.disk_usage(str(self.data_path)).free / (1024**3),
                "data_directory_exists": self.data_path.exists(),
                "recent_errors": len(error_reporter.get_recent_reports(limit=5)),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Global diagnostic tool instance
diagnostic_tool = DiagnosticTool()