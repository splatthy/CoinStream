"""
Unit tests for debugging and error reporting utilities.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.utils.debug_utils import (
    DebugInfo, ErrorReporter, format_exception_for_display,
    get_debug_summary, error_reporter
)
from app.utils.error_handler import TradingJournalError, ConfigurationError


class TestDebugInfo:
    """Test DebugInfo class methods."""
    
    @patch('psutil.Process')
    @patch('psutil.cpu_count')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_get_system_info_success(self, mock_disk, mock_memory, mock_cpu, mock_process):
        """Test successful system info collection."""
        # Mock process info
        mock_proc = Mock()
        mock_proc.memory_info.return_value = Mock(rss=1000000, vms=2000000)
        mock_proc.memory_percent.return_value = 5.5
        mock_proc.cpu_percent.return_value = 10.2
        mock_proc.num_threads.return_value = 4
        mock_proc.create_time.return_value = 1640995200.0  # Fixed timestamp
        mock_process.return_value = mock_proc
        
        # Mock system info
        mock_cpu.return_value = 8
        mock_memory.return_value = Mock(total=8000000000, available=4000000000, percent=50.0)
        mock_disk.return_value = Mock(percent=25.0)
        
        with patch('platform.system', return_value='Linux'):
            with patch('platform.release', return_value='5.4.0'):
                with patch('platform.version', return_value='Ubuntu 20.04'):
                    with patch('platform.machine', return_value='x86_64'):
                        with patch('platform.processor', return_value='Intel'):
                            info = DebugInfo.get_system_info()
        
        assert "platform" in info
        assert "process" in info
        assert "system_resources" in info
        
        # Check platform info
        assert info["platform"]["system"] == "Linux"
        assert info["platform"]["release"] == "5.4.0"
        
        # Check process info
        assert info["process"]["memory_rss"] == 1000000
        assert info["process"]["memory_percent"] == 5.5
        assert info["process"]["cpu_percent"] == 10.2
        
        # Check system resources
        assert info["system_resources"]["cpu_count"] == 8
        assert info["system_resources"]["memory_total"] == 8000000000
        assert info["system_resources"]["memory_percent"] == 50.0
    
    @patch('psutil.Process')
    def test_get_system_info_failure(self, mock_process):
        """Test system info collection with failure."""
        mock_process.side_effect = Exception("psutil error")
        
        info = DebugInfo.get_system_info()
        
        assert "error" in info
        assert "psutil error" in info["error"]
    
    @patch('streamlit.session_state', create=True)
    def test_get_application_state_with_streamlit(self, mock_session_state):
        """Test application state collection with Streamlit session."""
        # Mock session state
        mock_session_state.keys.return_value = ['user_data', 'api_key', 'config']
        mock_session_state.__getitem__ = lambda self, key: {
            'user_data': {'name': 'test'},
            'api_key': 'secret123',
            'config': {'theme': 'dark'}
        }[key]
        
        with patch('os.getcwd', return_value='/app'):
            with patch('sys.path', ['/app', '/usr/lib/python']):
                info = DebugInfo.get_application_state()
        
        assert "streamlit_session" in info
        assert "environment_variables" in info
        assert "working_directory" in info
        assert "python_path" in info
        
        # Check that sensitive keys are filtered out
        assert 'user_data' in info["streamlit_session"]
        assert 'config' in info["streamlit_session"]
        assert 'api_key' not in info["streamlit_session"]  # Should be filtered
        
        assert info["working_directory"] == "/app"
    
    def test_get_application_state_without_streamlit(self):
        """Test application state collection without Streamlit."""
        with patch('os.getcwd', return_value='/app'):
            with patch('sys.path', ['/app']):
                info = DebugInfo.get_application_state()
        
        assert "streamlit_session" in info
        assert "working_directory" in info
        assert info["working_directory"] == "/app"
    
    def test_get_application_state_failure(self):
        """Test application state collection with failure."""
        with patch('os.getcwd', side_effect=Exception("OS error")):
            info = DebugInfo.get_application_state()
        
        assert "error" in info
        assert "OS error" in info["error"]
    
    def test_get_file_system_info_success(self):
        """Test file system info collection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")
            
            test_dir = Path(temp_dir) / "subdir"
            test_dir.mkdir()
            
            info = DebugInfo.get_file_system_info(temp_dir)
            
            assert "data_directory" in info
            assert "files" in info
            
            # Check directory info
            assert info["data_directory"]["exists"] is True
            assert info["data_directory"]["is_writable"] is True
            
            # Check files info
            assert len(info["files"]) == 2  # test.txt and subdir
            
            file_names = [f["name"] for f in info["files"]]
            assert "test.txt" in file_names
            assert "subdir" in file_names
            
            # Check file details
            txt_file_info = next(f for f in info["files"] if f["name"] == "test.txt")
            assert txt_file_info["type"] == "file"
            assert txt_file_info["size"] > 0
            assert isinstance(txt_file_info["modified"], datetime)
            
            dir_info = next(f for f in info["files"] if f["name"] == "subdir")
            assert dir_info["type"] == "directory"
    
    def test_get_file_system_info_nonexistent_path(self):
        """Test file system info with nonexistent path."""
        info = DebugInfo.get_file_system_info("/nonexistent/path")
        
        assert "data_directory" in info
        assert info["data_directory"]["exists"] is False
        assert info["data_directory"]["is_writable"] is False
    
    def test_get_file_system_info_failure(self):
        """Test file system info collection with failure."""
        with patch('pathlib.Path.exists', side_effect=Exception("Path error")):
            info = DebugInfo.get_file_system_info("test")
        
        assert "error" in info
        assert "Path error" in info["error"]


class TestErrorReporter:
    """Test ErrorReporter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.error_reporter = ErrorReporter(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test ErrorReporter initialization."""
        assert self.error_reporter.data_path == Path(self.temp_dir)
        assert self.error_reporter.reports_dir == Path(self.temp_dir) / "error_reports"
        assert self.error_reporter.reports_dir.exists()
    
    @patch.object(DebugInfo, 'get_system_info')
    @patch.object(DebugInfo, 'get_application_state')
    @patch.object(DebugInfo, 'get_file_system_info')
    def test_generate_error_report_full(self, mock_fs_info, mock_app_state, mock_sys_info):
        """Test generating complete error report."""
        # Mock debug info methods
        mock_sys_info.return_value = {"platform": "test"}
        mock_app_state.return_value = {"session": "test"}
        mock_fs_info.return_value = {"files": []}
        
        error = TradingJournalError("Test error", "TEST_001", "Try again")
        
        report = self.error_reporter.generate_error_report(
            error, 
            context="Test Context",
            include_system_info=True,
            include_traceback=True
        )
        
        assert "timestamp" in report
        assert "error" in report
        assert "traceback" in report
        assert "system_info" in report
        assert "application_state" in report
        assert "file_system" in report
        
        # Check error details
        assert report["error"]["type"] == "TradingJournalError"
        assert report["error"]["message"] == "Test error"
        assert report["error"]["context"] == "Test Context"
        
        # Verify debug info methods were called
        mock_sys_info.assert_called_once()
        mock_app_state.assert_called_once()
        mock_fs_info.assert_called_once_with(str(self.error_reporter.data_path))
    
    def test_generate_error_report_minimal(self):
        """Test generating minimal error report."""
        error = ValueError("Simple error")
        
        report = self.error_reporter.generate_error_report(
            error,
            include_system_info=False,
            include_traceback=False
        )
        
        assert "timestamp" in report
        assert "error" in report
        assert "traceback" not in report
        assert "system_info" not in report
        
        assert report["error"]["type"] == "ValueError"
        assert report["error"]["message"] == "Simple error"
    
    def test_save_error_report(self):
        """Test saving error report to file."""
        error = ConfigurationError("Config missing")
        
        report_path = self.error_reporter.save_error_report(
            error,
            context="Config Test",
            report_id="test_report"
        )
        
        assert report_path is not None
        assert "test_report.json" in report_path
        
        # Verify file exists and contains correct data
        report_file = Path(report_path)
        assert report_file.exists()
        
        with open(report_file, 'r') as f:
            saved_report = json.load(f)
        
        assert saved_report["error"]["type"] == "ConfigurationError"
        assert saved_report["error"]["message"] == "Config missing"
        assert saved_report["error"]["context"] == "Config Test"
    
    def test_save_error_report_auto_id(self):
        """Test saving error report with auto-generated ID."""
        error = ValueError("Test error")
        
        report_path = self.error_reporter.save_error_report(error)
        
        assert report_path is not None
        assert "error_report_" in report_path
        assert report_path.endswith(".json")
        
        # Verify file exists
        assert Path(report_path).exists()
    
    @patch('builtins.open', side_effect=Exception("Write error"))
    def test_save_error_report_failure(self, mock_open):
        """Test error report saving failure."""
        error = ValueError("Test error")
        
        report_path = self.error_reporter.save_error_report(error)
        
        assert report_path is None
    
    def test_get_recent_reports(self):
        """Test getting recent error reports."""
        # Create multiple reports
        errors = [
            ValueError("Error 1"),
            TypeError("Error 2"),
            RuntimeError("Error 3")
        ]
        
        for i, error in enumerate(errors):
            self.error_reporter.save_error_report(
                error,
                context=f"Context {i+1}",
                report_id=f"report_{i+1}"
            )
        
        recent_reports = self.error_reporter.get_recent_reports(limit=2)
        
        assert len(recent_reports) == 2
        
        # Check report structure
        for report in recent_reports:
            assert "file" in report
            assert "timestamp" in report
            assert "error_type" in report
            assert "error_message" in report
            assert "context" in report
        
        # Reports should be sorted by most recent first
        assert "report_3.json" in recent_reports[0]["file"]
        assert "report_2.json" in recent_reports[1]["file"]
    
    def test_get_recent_reports_empty(self):
        """Test getting recent reports when none exist."""
        recent_reports = self.error_reporter.get_recent_reports()
        
        assert len(recent_reports) == 0
    
    def test_cleanup_old_reports(self):
        """Test cleaning up old error reports."""
        # Create reports
        error = ValueError("Test error")
        
        report_path1 = self.error_reporter.save_error_report(error, report_id="old_report")
        report_path2 = self.error_reporter.save_error_report(error, report_id="new_report")
        
        # Make one report "old" by modifying timestamp
        old_file = Path(report_path1)
        old_time = datetime.now().timestamp() - (40 * 24 * 60 * 60)  # 40 days ago
        os.utime(old_file, (old_time, old_time))
        
        # Clean up reports older than 30 days
        deleted_count = self.error_reporter.cleanup_old_reports(days_to_keep=30)
        
        assert deleted_count == 1
        assert not old_file.exists()
        assert Path(report_path2).exists()
    
    def test_cleanup_old_reports_failure(self):
        """Test cleanup with file deletion failure."""
        # Create a report
        error = ValueError("Test error")
        report_path = self.error_reporter.save_error_report(error, report_id="test_report")
        
        # Make it old
        old_file = Path(report_path)
        old_time = datetime.now().timestamp() - (40 * 24 * 60 * 60)
        os.utime(old_file, (old_time, old_time))
        
        # Mock unlink to fail
        with patch.object(Path, 'unlink', side_effect=OSError("Permission denied")):
            deleted_count = self.error_reporter.cleanup_old_reports(days_to_keep=30)
        
        assert deleted_count == 0  # No files deleted due to error


class TestDebugUtilities:
    """Test debug utility functions."""
    
    def test_format_exception_for_display_with_context(self):
        """Test formatting exception with context."""
        error = ValueError("Test error message")
        
        formatted = format_exception_for_display(error, "Data Processing")
        
        assert "**Data Processing**" in formatted
        assert "ValueError: Test error message" in formatted
    
    def test_format_exception_for_display_without_context(self):
        """Test formatting exception without context."""
        error = TypeError("Type mismatch")
        
        formatted = format_exception_for_display(error)
        
        assert "TypeError: Type mismatch" in formatted
        assert "**" not in formatted  # No context formatting
    
    @patch.object(DebugInfo, 'get_system_info')
    @patch.object(DebugInfo, 'get_application_state')
    @patch.object(DebugInfo, 'get_file_system_info')
    def test_get_debug_summary(self, mock_fs_info, mock_app_state, mock_sys_info):
        """Test getting debug summary."""
        mock_sys_info.return_value = {"platform": "test"}
        mock_app_state.return_value = {"session": "test"}
        mock_fs_info.return_value = {"files": []}
        
        summary = get_debug_summary()
        
        assert "system" in summary
        assert "application" in summary
        assert "filesystem" in summary
        
        mock_sys_info.assert_called_once()
        mock_app_state.assert_called_once()
        mock_fs_info.assert_called_once()


class TestErrorReporterIntegration:
    """Integration tests for error reporting system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_error_reporting(self):
        """Test complete error reporting workflow."""
        reporter = ErrorReporter(self.temp_dir)
        
        # Create and save error report
        error = TradingJournalError(
            "Integration test error",
            "INT_001",
            "Check configuration"
        )
        
        report_path = reporter.save_error_report(
            error,
            context="Integration Test"
        )
        
        # Verify report was saved
        assert report_path is not None
        report_file = Path(report_path)
        assert report_file.exists()
        
        # Load and verify report content
        with open(report_file, 'r') as f:
            report_data = json.load(f)
        
        assert report_data["error"]["type"] == "TradingJournalError"
        assert report_data["error"]["message"] == "Integration test error"
        assert report_data["error"]["context"] == "Integration Test"
        
        # Get recent reports
        recent = reporter.get_recent_reports(limit=1)
        assert len(recent) == 1
        assert recent[0]["error_type"] == "TradingJournalError"
        
        # Test cleanup
        deleted = reporter.cleanup_old_reports(days_to_keep=0)  # Delete all
        assert deleted == 1
        assert not report_file.exists()
    
    def test_global_error_reporter_instance(self):
        """Test that global error reporter instance works."""
        # The global instance should be available
        assert error_reporter is not None
        assert isinstance(error_reporter, ErrorReporter)
        
        # Should be able to generate reports
        error = ValueError("Global test error")
        report = error_reporter.generate_error_report(error)
        
        assert "error" in report
        assert report["error"]["type"] == "ValueError"