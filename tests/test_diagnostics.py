"""
Unit tests for the diagnostics system.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.utils.diagnostics import DiagnosticTool, diagnostic_tool
from app.utils.health_monitor import HealthStatus, HealthCheckResult


class TestDiagnosticTool:
    """Test DiagnosticTool class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.diagnostic_tool = DiagnosticTool(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test DiagnosticTool initialization."""
        assert self.diagnostic_tool.data_path == Path(self.temp_dir)
        assert self.diagnostic_tool.diagnostics == {}
    
    @patch('app.utils.diagnostics.system_monitor')
    @patch('app.utils.diagnostics.error_reporter')
    @patch('app.utils.diagnostics.DebugInfo')
    def test_run_full_diagnostics(self, mock_debug_info, mock_error_reporter, mock_system_monitor):
        """Test running full diagnostics."""
        # Mock debug info methods
        mock_debug_info.get_system_info.return_value = {"platform": "test"}
        mock_debug_info.get_application_state.return_value = {"session": "test"}
        mock_debug_info.get_file_system_info.return_value = {"files": []}
        
        # Mock system monitor
        mock_system_monitor.get_system_status.return_value = {
            "overall_status": "healthy",
            "health_checks": []
        }
        
        # Mock error reporter
        mock_error_reporter.get_recent_reports.return_value = []
        
        # Create test data directory
        os.makedirs(self.temp_dir, exist_ok=True)
        
        diagnostics = self.diagnostic_tool.run_full_diagnostics()
        
        # Check that all expected sections are present
        expected_sections = [
            "timestamp", "system_info", "application_state", "data_integrity",
            "configuration", "performance", "health_status", "error_analysis",
            "recommendations"
        ]
        
        for section in expected_sections:
            assert section in diagnostics
        
        # Check that diagnostics were stored
        assert self.diagnostic_tool.diagnostics == diagnostics
        
        # Check timestamp format
        assert isinstance(diagnostics["timestamp"], str)
        datetime.fromisoformat(diagnostics["timestamp"])  # Should not raise
    
    @patch('app.utils.diagnostics.DebugInfo.get_system_info')
    def test_diagnose_system(self, mock_get_system_info):
        """Test system diagnostics."""
        mock_get_system_info.return_value = {
            "platform": {"system": "Linux", "release": "5.4.0"},
            "process": {"memory_percent": 25.0}
        }
        
        result = self.diagnostic_tool._diagnose_system()
        
        assert "platform" in result
        assert "process" in result
        mock_get_system_info.assert_called_once()
    
    @patch('app.utils.diagnostics.DebugInfo.get_system_info')
    def test_diagnose_system_failure(self, mock_get_system_info):
        """Test system diagnostics with failure."""
        mock_get_system_info.side_effect = Exception("System info error")
        
        result = self.diagnostic_tool._diagnose_system()
        
        assert "error" in result
        assert "Failed to get system info" in result["error"]
    
    @patch('streamlit.session_state', create=True)
    @patch('streamlit.get_option')
    def test_diagnose_application_with_streamlit(self, mock_get_option, mock_session_state):
        """Test application diagnostics with Streamlit context."""
        # Mock session state
        mock_session_state.keys.return_value = ['user_data', 'config']
        mock_session_state.__getitem__ = lambda self, key: {"test": "data"}
        
        # Mock Streamlit options
        mock_get_option.return_value = 8501
        
        with patch('app.utils.diagnostics.DebugInfo.get_application_state') as mock_get_app_state:
            mock_get_app_state.return_value = {"working_directory": "/app"}
            
            result = self.diagnostic_tool._diagnose_application()
            
            assert "streamlit_diagnostics" in result
            streamlit_info = result["streamlit_diagnostics"]
            assert streamlit_info["has_session_state"] is True
            assert streamlit_info["in_streamlit_context"] is True
            assert streamlit_info["session_state_keys"] == 2
    
    def test_diagnose_data_integrity(self):
        """Test data integrity diagnostics."""
        # Create test data directory and files
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Create test JSON files
        test_files = {
            "trades.json": {"trades": []},
            "config.json": {"version": "1.0"},
            "invalid.json": "invalid json content"
        }
        
        for filename, content in test_files.items():
            file_path = Path(self.temp_dir) / filename
            if filename == "invalid.json":
                with open(file_path, 'w') as f:
                    f.write(content)
            else:
                with open(file_path, 'w') as f:
                    json.dump(content, f)
        
        result = self.diagnostic_tool._diagnose_data_integrity()
        
        assert "file_system" in result
        assert "integrity_checks" in result
        
        integrity_checks = result["integrity_checks"]
        assert integrity_checks["data_directory_exists"] is True
        assert integrity_checks["data_directory_writable"] is True
        
        # Check critical files
        critical_files = integrity_checks["critical_files"]
        assert "trades.json" in critical_files
        assert critical_files["trades.json"]["exists"] is True
        assert critical_files["trades.json"]["valid_json"] is True
    
    def test_check_critical_files(self):
        """Test checking critical files."""
        # Create test directory and files
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Create valid JSON file
        trades_file = Path(self.temp_dir) / "trades.json"
        with open(trades_file, 'w') as f:
            json.dump({"trades": []}, f)
        
        # Create invalid JSON file
        config_file = Path(self.temp_dir) / "config.json"
        with open(config_file, 'w') as f:
            f.write("invalid json")
        
        result = self.diagnostic_tool._check_critical_files()
        
        # Check trades.json
        trades_status = result["trades.json"]
        assert trades_status["exists"] is True
        assert trades_status["readable"] is True
        assert trades_status["valid_json"] is True
        assert trades_status["size_bytes"] > 0
        
        # Check config.json
        config_status = result["config.json"]
        assert config_status["exists"] is True
        assert config_status["readable"] is True
        assert config_status["valid_json"] is False
        assert "error" in config_status
    
    def test_check_file_permissions(self):
        """Test checking file permissions."""
        # Create test directory
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Create subdirectories
        for subdir in ["logs", "backups"]:
            os.makedirs(Path(self.temp_dir) / subdir, exist_ok=True)
        
        result = self.diagnostic_tool._check_file_permissions()
        
        assert "data_directory" in result
        data_perms = result["data_directory"]
        assert data_perms["readable"] is True
        assert data_perms["writable"] is True
        assert data_perms["executable"] is True
        
        # Check subdirectories
        assert "logs" in result
        assert "backups" in result
    
    @patch('psutil.disk_usage')
    def test_check_disk_space_detailed(self, mock_disk_usage):
        """Test detailed disk space check."""
        mock_disk_usage.return_value = Mock(
            total=1000000000000,  # 1TB
            used=500000000000,    # 500GB
            free=500000000000     # 500GB
        )
        
        result = self.diagnostic_tool._check_disk_space_detailed()
        
        assert "total_gb" in result
        assert "used_gb" in result
        assert "free_gb" in result
        assert "used_percent" in result
        assert "status" in result
        
        assert result["total_gb"] == pytest.approx(931.32, rel=1e-2)  # 1TB in GB
        assert result["used_percent"] == 50.0
        assert result["status"] == "ok"
    
    @patch('psutil.disk_usage')
    def test_check_disk_space_critical(self, mock_disk_usage):
        """Test disk space check with critical status."""
        mock_disk_usage.return_value = Mock(
            total=1000000000000,  # 1TB
            used=999000000000,    # 999GB
            free=1000000000       # 1GB
        )
        
        result = self.diagnostic_tool._check_disk_space_detailed()
        
        assert result["status"] == "critical"
        assert result["free_gb"] < 1.0
    
    def test_diagnose_configuration(self):
        """Test configuration diagnostics."""
        # Create test configuration files
        os.makedirs(self.temp_dir, exist_ok=True)
        
        config_data = {"version": "1.0", "debug": True}
        config_file = Path(self.temp_dir) / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Create invalid config file
        invalid_config = Path(self.temp_dir) / "exchange_configs.json"
        with open(invalid_config, 'w') as f:
            f.write("invalid json")
        
        with patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG', 'DATA_PATH': '/test'}):
            with patch('streamlit.get_option') as mock_get_option:
                mock_get_option.side_effect = lambda key: {
                    "server.port": 8501,
                    "server.address": "0.0.0.0",
                    "theme.base": "light"
                }.get(key, "unknown")
                
                result = self.diagnostic_tool._diagnose_configuration()
        
        assert "config_files" in result
        assert "environment_variables" in result
        assert "streamlit_config" in result
        
        # Check config files
        config_files = result["config_files"]
        assert "config.json" in config_files
        assert config_files["config.json"]["exists"] is True
        assert config_files["config.json"]["valid"] is True
        
        assert "exchange_configs.json" in config_files
        assert config_files["exchange_configs.json"]["exists"] is True
        assert config_files["exchange_configs.json"]["valid"] is False
        
        # Check environment variables
        env_vars = result["environment_variables"]
        assert env_vars["LOG_LEVEL"] == "DEBUG"
        assert env_vars["DATA_PATH"] == "/test"
        
        # Check Streamlit config
        streamlit_config = result["streamlit_config"]
        assert streamlit_config["server_port"] == 8501
        assert streamlit_config["server_address"] == "0.0.0.0"
    
    @patch('app.utils.diagnostics.system_monitor')
    def test_diagnose_performance(self, mock_system_monitor):
        """Test performance diagnostics."""
        # Mock performance monitor
        mock_performance_monitor = Mock()
        mock_performance_monitor.get_metric_summary.return_value = {
            "count": 10,
            "avg": 50.0,
            "min": 30.0,
            "max": 70.0,
            "unit": "%"
        }
        mock_system_monitor.performance_monitor = mock_performance_monitor
        
        with patch('psutil.cpu_percent', return_value=45.0):
            with patch('psutil.virtual_memory') as mock_memory:
                mock_memory.return_value = Mock(percent=60.0)
                
                with patch('psutil.Process') as mock_process:
                    mock_proc = Mock()
                    mock_proc.memory_percent.return_value = 25.0
                    mock_proc.cpu_percent.return_value = 15.0
                    mock_proc.num_threads.return_value = 8
                    mock_process.return_value = mock_proc
                    
                    with patch('psutil.disk_io_counters', return_value=Mock(_asdict=lambda: {"read_bytes": 1000})):
                        with patch('psutil.net_io_counters', return_value=Mock(_asdict=lambda: {"bytes_sent": 2000})):
                            result = self.diagnostic_tool._diagnose_performance()
        
        assert "recent_metrics" in result
        assert "system_resources" in result
        assert "bottlenecks" in result
        
        # Check system resources
        resources = result["system_resources"]
        assert resources["cpu_percent"] == 45.0
        assert resources["memory_percent"] == 60.0
    
    def test_identify_bottlenecks(self):
        """Test bottleneck identification."""
        # Test with high CPU usage
        performance_info = {
            "recent_metrics": {
                "cpu_usage": {"avg": 85.0, "count": 10},
                "memory_usage": {"avg": 50.0, "count": 10}
            },
            "system_resources": {
                "cpu_percent": 95.0,
                "memory_percent": 70.0
            }
        }
        
        bottlenecks = self.diagnostic_tool._identify_bottlenecks(performance_info)
        
        assert len(bottlenecks) >= 2
        assert any("High CPU usage" in b for b in bottlenecks)
        assert any("Critical CPU usage" in b for b in bottlenecks)
    
    @patch('app.utils.diagnostics.system_monitor')
    def test_diagnose_health(self, mock_system_monitor):
        """Test health diagnostics."""
        mock_system_monitor.get_system_status.return_value = {
            "overall_status": "healthy",
            "health_checks": [
                {"name": "memory_usage", "status": "healthy", "message": "OK"}
            ]
        }
        
        result = self.diagnostic_tool._diagnose_health()
        
        assert result["overall_status"] == "healthy"
        assert len(result["health_checks"]) == 1
    
    @patch('app.utils.diagnostics.error_reporter')
    def test_diagnose_errors(self, mock_error_reporter):
        """Test error diagnostics."""
        # Mock recent reports
        mock_error_reporter.get_recent_reports.return_value = [
            {"error_type": "ValueError", "error_message": "Test error 1"},
            {"error_type": "TypeError", "error_message": "Test error 2"},
            {"error_type": "ValueError", "error_message": "Test error 3"}
        ]
        
        # Create test log directory and file
        log_dir = Path(self.temp_dir) / "logs"
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / "test.log"
        log_content = """
        2023-01-01 10:00:00 - INFO - Application started
        2023-01-01 10:01:00 - ERROR - Test error occurred
        2023-01-01 10:02:00 - WARNING - Test warning
        2023-01-01 10:03:00 - ERROR - Another error
        2023-01-01 10:04:00 - CRITICAL - Critical issue
        """
        with open(log_file, 'w') as f:
            f.write(log_content)
        
        result = self.diagnostic_tool._diagnose_errors()
        
        assert "recent_reports" in result
        assert "error_patterns" in result
        assert "log_analysis" in result
        
        # Check error patterns
        error_patterns = result["error_patterns"]
        assert error_patterns["ValueError"] == 2
        assert error_patterns["TypeError"] == 1
        
        # Check log analysis
        log_analysis = result["log_analysis"]
        assert log_analysis["log_files_count"] == 1
        assert "recent_errors" in log_analysis
        
        recent_errors = log_analysis["recent_errors"]
        assert recent_errors["error_count"] == 2
        assert recent_errors["warning_count"] == 1
        assert recent_errors["critical_count"] == 1
    
    def test_generate_recommendations_healthy(self):
        """Test generating recommendations for healthy system."""
        diagnostics = {
            "health_status": {"overall_status": "healthy"},
            "data_integrity": {"integrity_checks": {"disk_space": {"status": "ok"}}},
            "configuration": {"config_files": {}},
            "performance": {"bottlenecks": []},
            "error_analysis": {"error_patterns": {}}
        }
        
        recommendations = self.diagnostic_tool._generate_recommendations(diagnostics)
        
        assert len(recommendations) == 1
        assert "normally" in recommendations[0].lower()
    
    def test_generate_recommendations_critical(self):
        """Test generating recommendations for critical issues."""
        diagnostics = {
            "health_status": {"overall_status": "critical"},
            "data_integrity": {
                "integrity_checks": {
                    "disk_space": {"status": "critical"},
                    "critical_files": {
                        "trades.json": {"exists": True, "valid_json": False}
                    }
                }
            },
            "configuration": {
                "config_files": {
                    "config.json": {"exists": False, "valid": False}
                }
            },
            "performance": {"bottlenecks": ["High CPU usage"]},
            "error_analysis": {"error_patterns": {"ValueError": 15}}
        }
        
        recommendations = self.diagnostic_tool._generate_recommendations(diagnostics)
        
        assert len(recommendations) >= 5
        assert any("CRITICAL" in rec for rec in recommendations)
        assert any("disk space" in rec.lower() for rec in recommendations)
        assert any("corruption" in rec.lower() for rec in recommendations)
        assert any("missing configuration" in rec.lower() for rec in recommendations)
        assert any("performance issue" in rec.lower() for rec in recommendations)
        assert any("high error rate" in rec.lower() for rec in recommendations)
    
    def test_export_diagnostics(self):
        """Test exporting diagnostics to file."""
        # Run diagnostics first
        self.diagnostic_tool.diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "test_data": {"value": 42}
        }
        
        # Export to custom path
        export_path = str(Path(self.temp_dir) / "test_diagnostics.json")
        result_path = self.diagnostic_tool.export_diagnostics(export_path)
        
        assert result_path == export_path
        assert Path(export_path).exists()
        
        # Verify content
        with open(export_path, 'r') as f:
            exported_data = json.load(f)
        
        assert exported_data["test_data"]["value"] == 42
    
    def test_export_diagnostics_auto_filename(self):
        """Test exporting diagnostics with auto-generated filename."""
        self.diagnostic_tool.diagnostics = {"test": "data"}
        
        result_path = self.diagnostic_tool.export_diagnostics()
        
        assert result_path is not None
        assert "diagnostics_" in result_path
        assert result_path.endswith(".json")
        assert Path(result_path).exists()
    
    def test_export_diagnostics_no_data(self):
        """Test exporting diagnostics when no data exists."""
        with patch.object(self.diagnostic_tool, 'run_full_diagnostics') as mock_run:
            mock_run.return_value = {"test": "data"}
            
            result_path = self.diagnostic_tool.export_diagnostics()
            
            mock_run.assert_called_once()
            assert result_path is not None
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('app.utils.diagnostics.system_monitor')
    @patch('app.utils.diagnostics.error_reporter')
    def test_get_quick_status(self, mock_error_reporter, mock_system_monitor, 
                             mock_disk_usage, mock_memory, mock_cpu):
        """Test getting quick status summary."""
        # Mock system monitor
        mock_health_checker = Mock()
        mock_health_checker.run_all_checks.return_value = [
            HealthCheckResult("test", HealthStatus.HEALTHY, "OK")
        ]
        mock_health_checker.get_overall_status.return_value = HealthStatus.HEALTHY
        mock_system_monitor.health_checker = mock_health_checker
        
        # Mock system metrics
        mock_cpu.return_value = 45.0
        mock_memory.return_value = Mock(percent=60.0)
        mock_disk_usage.return_value = Mock(free=5000000000)  # 5GB
        
        # Mock error reporter
        mock_error_reporter.get_recent_reports.return_value = [{"error": "test"}]
        
        # Create data directory
        os.makedirs(self.temp_dir, exist_ok=True)
        
        result = self.diagnostic_tool.get_quick_status()
        
        assert "overall_health" in result
        assert "cpu_percent" in result
        assert "memory_percent" in result
        assert "disk_free_gb" in result
        assert "data_directory_exists" in result
        assert "recent_errors" in result
        assert "timestamp" in result
        
        assert result["overall_health"] == "healthy"
        assert result["cpu_percent"] == 45.0
        assert result["memory_percent"] == 60.0
        assert result["data_directory_exists"] is True
        assert result["recent_errors"] == 1
    
    def test_get_quick_status_failure(self):
        """Test getting quick status with failure."""
        with patch('psutil.cpu_percent', side_effect=Exception("psutil error")):
            result = self.diagnostic_tool.get_quick_status()
            
            assert "error" in result
            assert "timestamp" in result
            assert "psutil error" in result["error"]


class TestGlobalDiagnosticTool:
    """Test global diagnostic tool instance."""
    
    def test_global_instance_exists(self):
        """Test that global diagnostic tool instance exists."""
        assert diagnostic_tool is not None
        assert isinstance(diagnostic_tool, DiagnosticTool)
    
    def test_global_instance_functionality(self):
        """Test that global instance is functional."""
        # Should be able to get quick status
        with patch('psutil.cpu_percent', return_value=50.0):
            with patch('psutil.virtual_memory', return_value=Mock(percent=60.0)):
                with patch('psutil.disk_usage', return_value=Mock(free=1000000000)):
                    with patch('app.utils.diagnostics.system_monitor') as mock_monitor:
                        mock_health_checker = Mock()
                        mock_health_checker.run_all_checks.return_value = []
                        mock_health_checker.get_overall_status.return_value = HealthStatus.HEALTHY
                        mock_monitor.health_checker = mock_health_checker
                        
                        with patch('app.utils.diagnostics.error_reporter') as mock_reporter:
                            mock_reporter.get_recent_reports.return_value = []
                            
                            status = diagnostic_tool.get_quick_status()
                            
                            assert "overall_health" in status
                            assert "cpu_percent" in status


class TestDiagnosticsIntegration:
    """Integration tests for diagnostics system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('app.utils.diagnostics.system_monitor')
    @patch('app.utils.diagnostics.error_reporter')
    def test_end_to_end_diagnostics(self, mock_error_reporter, mock_system_monitor):
        """Test complete diagnostics workflow."""
        # Set up test environment
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Create test files
        test_files = {
            "trades.json": {"trades": []},
            "config.json": {"version": "1.0"}
        }
        
        for filename, content in test_files.items():
            with open(Path(self.temp_dir) / filename, 'w') as f:
                json.dump(content, f)
        
        # Mock dependencies
        mock_system_monitor.get_system_status.return_value = {
            "overall_status": "healthy",
            "health_checks": []
        }
        mock_error_reporter.get_recent_reports.return_value = []
        
        # Create diagnostic tool and run diagnostics
        tool = DiagnosticTool(self.temp_dir)
        
        with patch('app.utils.diagnostics.DebugInfo') as mock_debug_info:
            mock_debug_info.get_system_info.return_value = {"platform": "test"}
            mock_debug_info.get_application_state.return_value = {"session": "test"}
            mock_debug_info.get_file_system_info.return_value = {"files": []}
            
            diagnostics = tool.run_full_diagnostics()
        
        # Verify results
        assert "timestamp" in diagnostics
        assert "recommendations" in diagnostics
        assert len(diagnostics["recommendations"]) > 0
        
        # Export and verify
        export_path = tool.export_diagnostics()
        assert Path(export_path).exists()
        
        with open(export_path, 'r') as f:
            exported = json.load(f)
        
        assert exported["timestamp"] == diagnostics["timestamp"]