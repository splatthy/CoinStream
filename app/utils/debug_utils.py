"""
Debugging and error reporting utilities for the crypto trading journal application.
Provides tools for troubleshooting and system diagnostics.
"""

import logging
import traceback
import sys
import os
import psutil
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import streamlit as st

from .logging_config import get_logger


logger = get_logger(__name__)


class DebugInfo:
    """Collects and formats debugging information."""
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Get system information for debugging."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "platform": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                    "python_version": sys.version
                },
                "process": {
                    "pid": os.getpid(),
                    "memory_rss": memory_info.rss,
                    "memory_vms": memory_info.vms,
                    "memory_percent": process.memory_percent(),
                    "cpu_percent": process.cpu_percent(),
                    "num_threads": process.num_threads(),
                    "create_time": datetime.fromtimestamp(process.create_time())
                },
                "system_resources": {
                    "cpu_count": psutil.cpu_count(),
                    "memory_total": psutil.virtual_memory().total,
                    "memory_available": psutil.virtual_memory().available,
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_usage": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent
                }
            }
        except Exception as e:
            logger.warning(f"Failed to collect system info: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def get_application_state() -> Dict[str, Any]:
        """Get current application state information."""
        try:
            state_info = {
                "streamlit_session": {},
                "environment_variables": {},
                "working_directory": os.getcwd(),
                "python_path": sys.path[:5]  # First 5 entries
            }
            
            # Streamlit session state (if available)
            if hasattr(st, 'session_state'):
                # Only include non-sensitive session state keys
                safe_keys = [k for k in st.session_state.keys() 
                           if not any(sensitive in k.lower() 
                                    for sensitive in ['key', 'secret', 'password', 'token'])]
                state_info["streamlit_session"] = {
                    k: type(st.session_state[k]).__name__ for k in safe_keys
                }
            
            # Environment variables (non-sensitive)
            safe_env_vars = ['LOG_LEVEL', 'DATA_PATH', 'PYTHONPATH']
            state_info["environment_variables"] = {
                var: os.getenv(var) for var in safe_env_vars if os.getenv(var)
            }
            
            return state_info
        except Exception as e:
            logger.warning(f"Failed to collect application state: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def get_file_system_info(data_path: str = "data") -> Dict[str, Any]:
        """Get file system information for debugging."""
        try:
            data_dir = Path(data_path)
            info = {
                "data_directory": {
                    "path": str(data_dir.absolute()),
                    "exists": data_dir.exists(),
                    "is_writable": os.access(data_dir, os.W_OK) if data_dir.exists() else False
                },
                "files": []
            }
            
            if data_dir.exists():
                for item in data_dir.iterdir():
                    try:
                        stat = item.stat()
                        info["files"].append({
                            "name": item.name,
                            "type": "directory" if item.is_dir() else "file",
                            "size": stat.st_size if item.is_file() else None,
                            "modified": datetime.fromtimestamp(stat.st_mtime),
                            "permissions": oct(stat.st_mode)[-3:]
                        })
                    except Exception as e:
                        info["files"].append({
                            "name": item.name,
                            "error": str(e)
                        })
            
            return info
        except Exception as e:
            logger.warning(f"Failed to collect file system info: {e}")
            return {"error": str(e)}


class ErrorReporter:
    """Handles error reporting and debugging information collection."""
    
    def __init__(self, data_path: str = "data"):
        self.data_path = Path(data_path)
        self.reports_dir = self.data_path / "error_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_error_report(
        self,
        error: Exception,
        context: str = None,
        include_system_info: bool = True,
        include_traceback: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive error report.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            include_system_info: Whether to include system information
            include_traceback: Whether to include full traceback
        
        Returns:
            Dictionary containing error report data
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "error": {
                "type": type(error).__name__,
                "message": str(error),
                "context": context
            }
        }
        
        if include_traceback:
            report["traceback"] = traceback.format_exc()
        
        if include_system_info:
            report["system_info"] = DebugInfo.get_system_info()
            report["application_state"] = DebugInfo.get_application_state()
            report["file_system"] = DebugInfo.get_file_system_info(str(self.data_path))
        
        return report
    
    def save_error_report(
        self,
        error: Exception,
        context: str = None,
        report_id: str = None
    ) -> str:
        """
        Save an error report to disk.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            report_id: Optional custom report ID
        
        Returns:
            Path to the saved report file
        """
        if not report_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_id = f"error_report_{timestamp}"
        
        report = self.generate_error_report(error, context)
        report_file = self.reports_dir / f"{report_id}.json"
        
        try:
            import json
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Error report saved: {report_file}")
            return str(report_file)
        except Exception as e:
            logger.error(f"Failed to save error report: {e}")
            return None
    
    def get_recent_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent error reports.
        
        Args:
            limit: Maximum number of reports to return
        
        Returns:
            List of recent error reports
        """
        reports = []
        
        try:
            report_files = sorted(
                self.reports_dir.glob("*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )[:limit]
            
            import json
            for report_file in report_files:
                try:
                    with open(report_file, 'r') as f:
                        report_data = json.load(f)
                        reports.append({
                            "file": report_file.name,
                            "timestamp": report_data.get("timestamp"),
                            "error_type": report_data.get("error", {}).get("type"),
                            "error_message": report_data.get("error", {}).get("message"),
                            "context": report_data.get("error", {}).get("context")
                        })
                except Exception as e:
                    logger.warning(f"Failed to read report {report_file}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to get recent reports: {e}")
        
        return reports
    
    def cleanup_old_reports(self, days_to_keep: int = 30) -> int:
        """
        Clean up old error reports.
        
        Args:
            days_to_keep: Number of days of reports to keep
        
        Returns:
            Number of reports deleted
        """
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0
        
        try:
            for report_file in self.reports_dir.glob("*.json"):
                if report_file.stat().st_mtime < cutoff_time:
                    try:
                        report_file.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete old report {report_file}: {e}")
        except Exception as e:
            logger.error(f"Failed to cleanup old reports: {e}")
        
        return deleted_count


def format_exception_for_display(error: Exception, context: str = None) -> str:
    """
    Format an exception for user-friendly display.
    
    Args:
        error: The exception to format
        context: Additional context
    
    Returns:
        Formatted error message
    """
    error_type = type(error).__name__
    error_message = str(error)
    
    if context:
        return f"**{context}**\n\n{error_type}: {error_message}"
    else:
        return f"{error_type}: {error_message}"


def get_debug_summary() -> Dict[str, Any]:
    """Get a summary of debugging information."""
    return {
        "system": DebugInfo.get_system_info(),
        "application": DebugInfo.get_application_state(),
        "filesystem": DebugInfo.get_file_system_info()
    }


# Global error reporter instance
error_reporter = ErrorReporter()