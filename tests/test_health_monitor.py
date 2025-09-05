"""
Unit tests for the health monitoring system.
"""

import pytest
import tempfile
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.utils.health_monitor import (
    HealthStatus, HealthCheckResult, PerformanceMetric,
    HealthChecker, PerformanceMonitor, SystemMonitor
)


class TestHealthStatus:
    """Test HealthStatus enum."""
    
    def test_health_status_values(self):
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.WARNING.value == "warning"
        assert HealthStatus.CRITICAL.value == "critical"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestHealthCheckResult:
    """Test HealthCheckResult dataclass."""
    
    def test_health_check_result_creation(self):
        """Test creating HealthCheckResult."""
        result = HealthCheckResult(
            name="test_check",
            status=HealthStatus.HEALTHY,
            message="All good",
            details={"value": 42},
            duration_ms=123.45
        )
        
        assert result.name == "test_check"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "All good"
        assert result.details == {"value": 42}
        assert result.duration_ms == 123.45
        assert isinstance(result.timestamp, datetime)
    
    def test_health_check_result_defaults(self):
        """Test HealthCheckResult with default values."""
        result = HealthCheckResult(
            name="test_check",
            status=HealthStatus.HEALTHY,
            message="Test message"
        )
        
        assert result.details == {}
        assert result.duration_ms == 0.0
        assert isinstance(result.timestamp, datetime)


class TestPerformanceMetric:
    """Test PerformanceMetric dataclass."""
    
    def test_performance_metric_creation(self):
        """Test creating PerformanceMetric."""
        metric = PerformanceMetric(
            name="cpu_usage",
            value=75.5,
            unit="%",
            tags={"host": "localhost"}
        )
        
        assert metric.name == "cpu_usage"
        assert metric.value == 75.5
        assert metric.unit == "%"
        assert metric.tags == {"host": "localhost"}
        assert isinstance(metric.timestamp, datetime)
    
    def test_performance_metric_defaults(self):
        """Test PerformanceMetric with default values."""
        metric = PerformanceMetric(
            name="test_metric",
            value=100.0,
            unit="count"
        )
        
        assert metric.tags == {}
        assert isinstance(metric.timestamp, datetime)


class TestHealthChecker:
    """Test HealthChecker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.health_checker = HealthChecker(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test HealthChecker initialization."""
        assert self.health_checker.data_path == self.temp_dir
        assert len(self.health_checker.checks) >= 4  # Default checks
        
        # Check that default checks are registered
        expected_checks = ["memory_usage", "disk_space", "data_directory", "log_directory"]
        for check_name in expected_checks:
            assert check_name in self.health_checker.checks
    
    def test_register_custom_check(self):
        """Test registering a custom health check."""
        def custom_check():
            return HealthCheckResult(
                name="custom_check",
                status=HealthStatus.HEALTHY,
                message="Custom check passed"
            )
        
        self.health_checker.register_check("custom_check", custom_check)
        
        assert "custom_check" in self.health_checker.checks
        
        # Test running the custom check
        result = self.health_checker.run_check("custom_check")
        assert result.name == "custom_check"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Custom check passed"
    
    @patch('psutil.Process')
    def test_memory_usage_check_healthy(self, mock_process):
        """Test memory usage check with healthy status."""
        mock_proc = Mock()
        mock_proc.memory_info.return_value = Mock(rss=1000000, vms=2000000)
        mock_proc.memory_percent.return_value = 45.0  # Healthy level
        mock_process.return_value = mock_proc
        
        result = self.health_checker._check_memory_usage()
        
        assert result.name == "memory_usage"
        assert result.status == HealthStatus.HEALTHY
        assert "normal" in result.message.lower()
        assert result.details["memory_percent"] == 45.0
    
    @patch('psutil.Process')
    def test_memory_usage_check_warning(self, mock_process):
        """Test memory usage check with warning status."""
        mock_proc = Mock()
        mock_proc.memory_info.return_value = Mock(rss=1000000, vms=2000000)
        mock_proc.memory_percent.return_value = 70.0  # Warning level
        mock_process.return_value = mock_proc
        
        result = self.health_checker._check_memory_usage()
        
        assert result.name == "memory_usage"
        assert result.status == HealthStatus.WARNING
        assert "elevated" in result.message.lower()
    
    @patch('psutil.Process')
    def test_memory_usage_check_critical(self, mock_process):
        """Test memory usage check with critical status."""
        mock_proc = Mock()
        mock_proc.memory_info.return_value = Mock(rss=1000000, vms=2000000)
        mock_proc.memory_percent.return_value = 85.0  # Critical level
        mock_process.return_value = mock_proc
        
        result = self.health_checker._check_memory_usage()
        
        assert result.name == "memory_usage"
        assert result.status == HealthStatus.CRITICAL
        assert "high" in result.message.lower()
    
    @patch('psutil.Process')
    def test_memory_usage_check_failure(self, mock_process):
        """Test memory usage check with failure."""
        mock_process.side_effect = Exception("psutil error")
        
        result = self.health_checker._check_memory_usage()
        
        assert result.name == "memory_usage"
        assert result.status == HealthStatus.UNKNOWN
        assert "failed" in result.message.lower()
        assert "error" in result.details
    
    @patch('psutil.disk_usage')
    def test_disk_space_check_healthy(self, mock_disk_usage):
        """Test disk space check with healthy status."""
        mock_disk_usage.return_value = Mock(
            total=1000000000000,  # 1TB
            used=500000000000,    # 500GB (50% used)
            free=500000000000     # 500GB free
        )
        
        result = self.health_checker._check_disk_space()
        
        assert result.name == "disk_space"
        assert result.status == HealthStatus.HEALTHY
        assert "adequate" in result.message.lower()
    
    @patch('psutil.disk_usage')
    def test_disk_space_check_critical(self, mock_disk_usage):
        """Test disk space check with critical status."""
        mock_disk_usage.return_value = Mock(
            total=1000000000000,  # 1TB
            used=950000000000,    # 950GB (95% used)
            free=50000000000      # 50GB free
        )
        
        result = self.health_checker._check_disk_space()
        
        assert result.name == "disk_space"
        assert result.status == HealthStatus.CRITICAL
        assert "low" in result.message.lower()
    
    def test_data_directory_check_exists(self):
        """Test data directory check when directory exists."""
        # Create the data directory
        import os
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Create a test file
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        result = self.health_checker._check_data_directory()
        
        assert result.name == "data_directory"
        assert result.status == HealthStatus.HEALTHY
        assert "accessible" in result.message.lower()
        assert result.details["exists"] is True
        assert result.details["writable"] is True
        assert result.details["file_count"] >= 1
    
    def test_data_directory_check_missing(self):
        """Test data directory check when directory doesn't exist."""
        # Use a non-existent directory
        non_existent_checker = HealthChecker("/non/existent/path")
        
        result = non_existent_checker._check_data_directory()
        
        assert result.name == "data_directory"
        assert result.status == HealthStatus.CRITICAL
        assert "does not exist" in result.message
        assert result.details["exists"] is False
    
    def test_run_check_unknown(self):
        """Test running an unknown health check."""
        result = self.health_checker.run_check("unknown_check")
        
        assert result.name == "unknown_check"
        assert result.status == HealthStatus.UNKNOWN
        assert "unknown" in result.message.lower()
    
    def test_run_check_with_exception(self):
        """Test running a check that raises an exception."""
        def failing_check():
            raise ValueError("Check failed")
        
        self.health_checker.register_check("failing_check", failing_check)
        
        result = self.health_checker.run_check("failing_check")
        
        assert result.name == "failing_check"
        assert result.status == HealthStatus.CRITICAL
        assert "failed" in result.message.lower()
        assert result.duration_ms > 0
    
    def test_run_all_checks(self):
        """Test running all registered health checks."""
        results = self.health_checker.run_all_checks()
        
        assert len(results) >= 4  # At least the default checks
        
        # Check that all results are HealthCheckResult instances
        for result in results:
            assert isinstance(result, HealthCheckResult)
            assert result.name in self.health_checker.checks
    
    def test_get_overall_status_healthy(self):
        """Test getting overall status when all checks are healthy."""
        # Mock all checks to return healthy status
        healthy_results = [
            HealthCheckResult("check1", HealthStatus.HEALTHY, "OK"),
            HealthCheckResult("check2", HealthStatus.HEALTHY, "OK"),
            HealthCheckResult("check3", HealthStatus.HEALTHY, "OK")
        ]
        
        overall_status = self.health_checker.get_overall_status(healthy_results)
        assert overall_status == HealthStatus.HEALTHY
    
    def test_get_overall_status_warning(self):
        """Test getting overall status with warning checks."""
        mixed_results = [
            HealthCheckResult("check1", HealthStatus.HEALTHY, "OK"),
            HealthCheckResult("check2", HealthStatus.WARNING, "Warning"),
            HealthCheckResult("check3", HealthStatus.HEALTHY, "OK")
        ]
        
        overall_status = self.health_checker.get_overall_status(mixed_results)
        assert overall_status == HealthStatus.WARNING
    
    def test_get_overall_status_critical(self):
        """Test getting overall status with critical checks."""
        mixed_results = [
            HealthCheckResult("check1", HealthStatus.HEALTHY, "OK"),
            HealthCheckResult("check2", HealthStatus.WARNING, "Warning"),
            HealthCheckResult("check3", HealthStatus.CRITICAL, "Critical")
        ]
        
        overall_status = self.health_checker.get_overall_status(mixed_results)
        assert overall_status == HealthStatus.CRITICAL
    
    def test_get_overall_status_empty(self):
        """Test getting overall status with no results."""
        overall_status = self.health_checker.get_overall_status([])
        assert overall_status == HealthStatus.UNKNOWN


class TestPerformanceMonitor:
    """Test PerformanceMonitor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = PerformanceMonitor(max_metrics=100)
    
    def test_initialization(self):
        """Test PerformanceMonitor initialization."""
        assert self.monitor.max_metrics == 100
        assert len(self.monitor.metrics) == 0
    
    def test_record_metric(self):
        """Test recording a performance metric."""
        self.monitor.record_metric("cpu_usage", 75.5, "%", {"host": "test"})
        
        assert len(self.monitor.metrics) == 1
        
        metric = self.monitor.metrics[0]
        assert metric.name == "cpu_usage"
        assert metric.value == 75.5
        assert metric.unit == "%"
        assert metric.tags == {"host": "test"}
    
    def test_record_multiple_metrics(self):
        """Test recording multiple metrics."""
        for i in range(10):
            self.monitor.record_metric(f"metric_{i}", float(i), "count")
        
        assert len(self.monitor.metrics) == 10
        
        # Check that metrics are in order
        for i, metric in enumerate(self.monitor.metrics):
            assert metric.name == f"metric_{i}"
            assert metric.value == float(i)
    
    def test_max_metrics_limit(self):
        """Test that metrics are limited to max_metrics."""
        monitor = PerformanceMonitor(max_metrics=5)
        
        # Record more metrics than the limit
        for i in range(10):
            monitor.record_metric(f"metric_{i}", float(i), "count")
        
        # Should only keep the last 5 metrics
        assert len(monitor.metrics) == 5
        
        # Check that we have the most recent metrics
        for i, metric in enumerate(monitor.metrics):
            expected_value = float(i + 5)  # Should be metrics 5-9
            assert metric.value == expected_value
    
    def test_get_metrics_no_filter(self):
        """Test getting all metrics without filters."""
        for i in range(5):
            self.monitor.record_metric("test_metric", float(i), "count")
        
        metrics = self.monitor.get_metrics()
        
        assert len(metrics) == 5
        # Should be sorted by timestamp (most recent first)
        assert metrics[0].value == 4.0
        assert metrics[-1].value == 0.0
    
    def test_get_metrics_by_name(self):
        """Test getting metrics filtered by name."""
        self.monitor.record_metric("cpu_usage", 50.0, "%")
        self.monitor.record_metric("memory_usage", 60.0, "%")
        self.monitor.record_metric("cpu_usage", 55.0, "%")
        
        cpu_metrics = self.monitor.get_metrics(name="cpu_usage")
        
        assert len(cpu_metrics) == 2
        for metric in cpu_metrics:
            assert metric.name == "cpu_usage"
    
    def test_get_metrics_since_timestamp(self):
        """Test getting metrics since a specific timestamp."""
        # Record some metrics with a delay
        self.monitor.record_metric("test", 1.0, "count")
        time.sleep(0.01)  # Small delay
        
        cutoff_time = datetime.now()
        time.sleep(0.01)  # Small delay
        
        self.monitor.record_metric("test", 2.0, "count")
        self.monitor.record_metric("test", 3.0, "count")
        
        recent_metrics = self.monitor.get_metrics(since=cutoff_time)
        
        assert len(recent_metrics) == 2
        assert all(m.value >= 2.0 for m in recent_metrics)
    
    def test_get_metrics_with_limit(self):
        """Test getting metrics with limit."""
        for i in range(10):
            self.monitor.record_metric("test", float(i), "count")
        
        limited_metrics = self.monitor.get_metrics(limit=3)
        
        assert len(limited_metrics) == 3
        # Should get the most recent 3
        assert limited_metrics[0].value == 9.0
        assert limited_metrics[1].value == 8.0
        assert limited_metrics[2].value == 7.0
    
    def test_get_metric_summary(self):
        """Test getting metric summary statistics."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for value in values:
            self.monitor.record_metric("test_metric", value, "units")
        
        summary = self.monitor.get_metric_summary("test_metric")
        
        assert summary["count"] == 5
        assert summary["min"] == 10.0
        assert summary["max"] == 50.0
        assert summary["avg"] == 30.0
        assert summary["latest"] == 50.0  # Most recent
        assert summary["unit"] == "units"
    
    def test_get_metric_summary_empty(self):
        """Test getting summary for non-existent metric."""
        summary = self.monitor.get_metric_summary("nonexistent")
        
        assert summary["count"] == 0
    
    def test_clear_metrics_all(self):
        """Test clearing all metrics."""
        for i in range(5):
            self.monitor.record_metric("test", float(i), "count")
        
        assert len(self.monitor.metrics) == 5
        
        cleared_count = self.monitor.clear_metrics()
        
        assert cleared_count == 5
        assert len(self.monitor.metrics) == 0
    
    def test_clear_metrics_older_than(self):
        """Test clearing metrics older than a specific time."""
        # Record some old metrics
        self.monitor.record_metric("test", 1.0, "count")
        self.monitor.record_metric("test", 2.0, "count")
        
        time.sleep(0.01)  # Small delay
        cutoff_time = datetime.now()
        time.sleep(0.01)  # Small delay
        
        # Record some new metrics
        self.monitor.record_metric("test", 3.0, "count")
        self.monitor.record_metric("test", 4.0, "count")
        
        cleared_count = self.monitor.clear_metrics(older_than=cutoff_time)
        
        assert cleared_count == 2  # Should clear the first 2 metrics
        assert len(self.monitor.metrics) == 2
        
        # Remaining metrics should be the newer ones
        remaining_values = [m.value for m in self.monitor.metrics]
        assert 3.0 in remaining_values
        assert 4.0 in remaining_values


class TestSystemMonitor:
    """Test SystemMonitor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.system_monitor = SystemMonitor(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if self.system_monitor._monitoring_active:
            self.system_monitor.stop_monitoring()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test SystemMonitor initialization."""
        assert isinstance(self.system_monitor.health_checker, HealthChecker)
        assert isinstance(self.system_monitor.performance_monitor, PerformanceMonitor)
        assert not self.system_monitor._monitoring_active
        assert self.system_monitor._monitor_thread is None
    
    def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring."""
        # Start monitoring
        self.system_monitor.start_monitoring(interval_seconds=0.1)
        
        assert self.system_monitor._monitoring_active
        assert self.system_monitor._monitor_thread is not None
        assert self.system_monitor._monitor_thread.is_alive()
        
        # Let it run for a short time
        time.sleep(0.2)
        
        # Stop monitoring
        self.system_monitor.stop_monitoring()
        
        assert not self.system_monitor._monitoring_active
        
        # Wait for thread to finish
        time.sleep(0.1)
        assert not self.system_monitor._monitor_thread.is_alive()
    
    def test_start_monitoring_already_active(self):
        """Test starting monitoring when already active."""
        self.system_monitor.start_monitoring(interval_seconds=0.1)
        
        # Try to start again
        self.system_monitor.start_monitoring(interval_seconds=0.1)
        
        # Should still be active with only one thread
        assert self.system_monitor._monitoring_active
        
        self.system_monitor.stop_monitoring()
    
    def test_stop_monitoring_not_active(self):
        """Test stopping monitoring when not active."""
        # Should not raise an exception
        self.system_monitor.stop_monitoring()
        
        assert not self.system_monitor._monitoring_active
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.Process')
    def test_record_system_metrics(self, mock_process, mock_memory, mock_cpu):
        """Test recording system metrics."""
        # Mock system metrics
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0, available=4000000000)
        
        mock_proc = Mock()
        mock_proc.memory_percent.return_value = 25.0
        mock_proc.cpu_percent.return_value = 15.0
        mock_proc.num_threads.return_value = 8
        mock_process.return_value = mock_proc
        
        # Record metrics
        self.system_monitor._record_system_metrics()
        
        # Check that metrics were recorded
        metrics = self.system_monitor.performance_monitor.get_metrics()
        
        metric_names = [m.name for m in metrics]
        assert "cpu_usage" in metric_names
        assert "memory_usage" in metric_names
        assert "memory_available" in metric_names
        assert "process_memory" in metric_names
        assert "process_cpu" in metric_names
        assert "process_threads" in metric_names
    
    def test_get_system_status(self):
        """Test getting comprehensive system status."""
        status = self.system_monitor.get_system_status()
        
        assert "overall_status" in status
        assert "health_checks" in status
        assert "performance_metrics" in status
        assert "monitoring_active" in status
        assert "timestamp" in status
        
        # Check that overall_status is a valid status
        valid_statuses = ["healthy", "warning", "critical", "unknown"]
        assert status["overall_status"] in valid_statuses
        
        # Check that health_checks is a list
        assert isinstance(status["health_checks"], list)
        
        # Check that performance_metrics is a dict
        assert isinstance(status["performance_metrics"], dict)
    
    def test_monitoring_loop_integration(self):
        """Test the monitoring loop integration."""
        # Start monitoring with very short interval
        self.system_monitor.start_monitoring(interval_seconds=0.05)
        
        # Let it run for a short time to collect some metrics
        time.sleep(0.15)
        
        # Stop monitoring
        self.system_monitor.stop_monitoring()
        
        # Check that some metrics were collected
        metrics = self.system_monitor.performance_monitor.get_metrics()
        assert len(metrics) > 0
        
        # Check that health check metrics were recorded
        health_metrics = [m for m in metrics if m.name.startswith("health_")]
        assert len(health_metrics) > 0