"""
Health monitoring and performance tracking utilities for the crypto trading journal application.
Provides system health checks, performance monitoring, and diagnostic capabilities.
"""

import logging
import time
import psutil
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import streamlit as st

from .logging_config import get_logger
from .error_handler import handle_exceptions, TradingJournalError


logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health check status enumeration."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0


@dataclass
class PerformanceMetric:
    """Performance metric data point."""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


class HealthChecker:
    """Performs various health checks on the application."""
    
    def __init__(self, data_path: str = "data"):
        self.data_path = data_path
        self.checks: Dict[str, Callable[[], HealthCheckResult]] = {}
        self._register_default_checks()
    
    def _register_default_checks(self) -> None:
        """Register default health checks."""
        self.register_check("memory_usage", self._check_memory_usage)
        self.register_check("disk_space", self._check_disk_space)
        self.register_check("data_directory", self._check_data_directory)
        self.register_check("log_directory", self._check_log_directory)
    
    def register_check(self, name: str, check_function: Callable[[], HealthCheckResult]) -> None:
        """
        Register a custom health check.
        
        Args:
            name: Name of the health check
            check_function: Function that performs the check and returns HealthCheckResult
        """
        self.checks[name] = check_function
        logger.debug(f"Registered health check: {name}")
    
    @handle_exceptions(context="Memory Usage Check", show_to_user=False)
    def _check_memory_usage(self) -> HealthCheckResult:
        """Check system memory usage."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            # Determine status based on memory usage
            if memory_percent > 80:
                status = HealthStatus.CRITICAL
                message = f"High memory usage: {memory_percent:.1f}%"
            elif memory_percent > 60:
                status = HealthStatus.WARNING
                message = f"Elevated memory usage: {memory_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_percent:.1f}%"
            
            return HealthCheckResult(
                name="memory_usage",
                status=status,
                message=message,
                details={
                    "memory_percent": memory_percent,
                    "memory_rss": memory_info.rss,
                    "memory_vms": memory_info.vms,
                    "memory_rss_mb": memory_info.rss / (1024 * 1024),
                    "memory_vms_mb": memory_info.vms / (1024 * 1024)
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name="memory_usage",
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check memory usage: {e}",
                details={"error": str(e)}
            )
    
    @handle_exceptions(context="Disk Space Check", show_to_user=False)
    def _check_disk_space(self) -> HealthCheckResult:
        """Check available disk space."""
        try:
            import os
            if os.name == 'nt':  # Windows
                disk_usage = psutil.disk_usage('C:\\')
            else:  # Unix-like
                disk_usage = psutil.disk_usage('/')
            
            used_percent = (disk_usage.used / disk_usage.total) * 100
            free_gb = disk_usage.free / (1024 ** 3)
            
            # Determine status based on disk usage
            if used_percent > 90:
                status = HealthStatus.CRITICAL
                message = f"Low disk space: {used_percent:.1f}% used, {free_gb:.1f}GB free"
            elif used_percent > 80:
                status = HealthStatus.WARNING
                message = f"Disk space getting low: {used_percent:.1f}% used, {free_gb:.1f}GB free"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space adequate: {used_percent:.1f}% used, {free_gb:.1f}GB free"
            
            return HealthCheckResult(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "used_percent": used_percent,
                    "free_gb": free_gb,
                    "total_gb": disk_usage.total / (1024 ** 3),
                    "used_gb": disk_usage.used / (1024 ** 3)
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check disk space: {e}",
                details={"error": str(e)}
            )
    
    @handle_exceptions(context="Data Directory Check", show_to_user=False)
    def _check_data_directory(self) -> HealthCheckResult:
        """Check data directory accessibility."""
        try:
            from pathlib import Path
            import os
            
            data_dir = Path(self.data_path)
            
            # Check if directory exists
            if not data_dir.exists():
                return HealthCheckResult(
                    name="data_directory",
                    status=HealthStatus.CRITICAL,
                    message=f"Data directory does not exist: {data_dir}",
                    details={"path": str(data_dir), "exists": False}
                )
            
            # Check if directory is writable
            if not os.access(data_dir, os.W_OK):
                return HealthCheckResult(
                    name="data_directory",
                    status=HealthStatus.CRITICAL,
                    message=f"Data directory is not writable: {data_dir}",
                    details={"path": str(data_dir), "writable": False}
                )
            
            # Check directory size and file count
            total_size = 0
            file_count = 0
            for item in data_dir.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
            
            size_mb = total_size / (1024 * 1024)
            
            return HealthCheckResult(
                name="data_directory",
                status=HealthStatus.HEALTHY,
                message=f"Data directory accessible: {file_count} files, {size_mb:.1f}MB",
                details={
                    "path": str(data_dir),
                    "exists": True,
                    "writable": True,
                    "file_count": file_count,
                    "size_mb": size_mb
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name="data_directory",
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check data directory: {e}",
                details={"error": str(e)}
            )
    
    @handle_exceptions(context="Log Directory Check", show_to_user=False)
    def _check_log_directory(self) -> HealthCheckResult:
        """Check log directory and recent log activity."""
        try:
            from pathlib import Path
            
            log_dir = Path(self.data_path) / "logs"
            
            if not log_dir.exists():
                return HealthCheckResult(
                    name="log_directory",
                    status=HealthStatus.WARNING,
                    message="Log directory does not exist",
                    details={"path": str(log_dir), "exists": False}
                )
            
            # Check for recent log activity
            log_files = list(log_dir.glob("*.log"))
            if not log_files:
                return HealthCheckResult(
                    name="log_directory",
                    status=HealthStatus.WARNING,
                    message="No log files found",
                    details={"path": str(log_dir), "log_files": 0}
                )
            
            # Check most recent log file
            most_recent = max(log_files, key=lambda f: f.stat().st_mtime)
            last_modified = datetime.fromtimestamp(most_recent.stat().st_mtime)
            age_minutes = (datetime.now() - last_modified).total_seconds() / 60
            
            if age_minutes > 60:  # No log activity in last hour
                status = HealthStatus.WARNING
                message = f"No recent log activity: last log {age_minutes:.0f} minutes ago"
            else:
                status = HealthStatus.HEALTHY
                message = f"Log directory active: {len(log_files)} files, last activity {age_minutes:.0f} minutes ago"
            
            return HealthCheckResult(
                name="log_directory",
                status=status,
                message=message,
                details={
                    "path": str(log_dir),
                    "log_files": len(log_files),
                    "last_activity_minutes": age_minutes,
                    "most_recent_file": most_recent.name
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name="log_directory",
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check log directory: {e}",
                details={"error": str(e)}
            )
    
    def run_check(self, check_name: str) -> HealthCheckResult:
        """
        Run a specific health check.
        
        Args:
            check_name: Name of the check to run
        
        Returns:
            HealthCheckResult with check results
        """
        if check_name not in self.checks:
            return HealthCheckResult(
                name=check_name,
                status=HealthStatus.UNKNOWN,
                message=f"Unknown health check: {check_name}"
            )
        
        start_time = time.time()
        try:
            result = self.checks[check_name]()
            result.duration_ms = (time.time() - start_time) * 1000
            return result
        except Exception as e:
            return HealthCheckResult(
                name=check_name,
                status=HealthStatus.CRITICAL,
                message=f"Health check failed: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000
            )
    
    def run_all_checks(self) -> List[HealthCheckResult]:
        """
        Run all registered health checks.
        
        Returns:
            List of HealthCheckResult objects
        """
        results = []
        for check_name in self.checks:
            result = self.run_check(check_name)
            results.append(result)
        
        logger.info(f"Completed {len(results)} health checks")
        return results
    
    def get_overall_status(self, results: List[HealthCheckResult] = None) -> HealthStatus:
        """
        Get overall health status based on check results.
        
        Args:
            results: Optional list of check results. If None, runs all checks.
        
        Returns:
            Overall HealthStatus
        """
        if results is None:
            results = self.run_all_checks()
        
        if not results:
            return HealthStatus.UNKNOWN
        
        # Determine overall status based on worst individual status
        statuses = [result.status for result in results]
        
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        elif HealthStatus.UNKNOWN in statuses:
            return HealthStatus.UNKNOWN
        else:
            return HealthStatus.HEALTHY


class PerformanceMonitor:
    """Monitors application performance metrics."""
    
    def __init__(self, max_metrics: int = 1000):
        self.max_metrics = max_metrics
        self.metrics: List[PerformanceMetric] = []
        self._lock = threading.Lock()
    
    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: Dict[str, str] = None
    ) -> None:
        """
        Record a performance metric.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            tags: Optional tags for categorization
        """
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {}
        )
        
        with self._lock:
            self.metrics.append(metric)
            
            # Keep only the most recent metrics
            if len(self.metrics) > self.max_metrics:
                self.metrics = self.metrics[-self.max_metrics:]
        
        logger.debug(f"Recorded metric: {name}={value}{unit}")
    
    def get_metrics(
        self,
        name: str = None,
        since: datetime = None,
        limit: int = None
    ) -> List[PerformanceMetric]:
        """
        Get performance metrics with optional filtering.
        
        Args:
            name: Filter by metric name
            since: Filter metrics since this timestamp
            limit: Maximum number of metrics to return
        
        Returns:
            List of PerformanceMetric objects
        """
        with self._lock:
            filtered_metrics = self.metrics.copy()
        
        # Apply filters
        if name:
            filtered_metrics = [m for m in filtered_metrics if m.name == name]
        
        if since:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp >= since]
        
        # Sort by timestamp (most recent first)
        filtered_metrics.sort(key=lambda m: m.timestamp, reverse=True)
        
        if limit:
            filtered_metrics = filtered_metrics[:limit]
        
        return filtered_metrics
    
    def get_metric_summary(self, name: str, since: datetime = None) -> Dict[str, Any]:
        """
        Get summary statistics for a metric.
        
        Args:
            name: Metric name
            since: Calculate summary since this timestamp
        
        Returns:
            Dictionary with summary statistics
        """
        metrics = self.get_metrics(name=name, since=since)
        
        if not metrics:
            return {"count": 0}
        
        values = [m.value for m in metrics]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[0] if values else None,
            "unit": metrics[0].unit if metrics else ""
        }
    
    def clear_metrics(self, older_than: datetime = None) -> int:
        """
        Clear metrics, optionally only those older than specified time.
        
        Args:
            older_than: Only clear metrics older than this timestamp
        
        Returns:
            Number of metrics cleared
        """
        with self._lock:
            if older_than:
                original_count = len(self.metrics)
                self.metrics = [m for m in self.metrics if m.timestamp >= older_than]
                cleared_count = original_count - len(self.metrics)
            else:
                cleared_count = len(self.metrics)
                self.metrics.clear()
        
        logger.info(f"Cleared {cleared_count} performance metrics")
        return cleared_count


class SystemMonitor:
    """Comprehensive system monitoring combining health checks and performance metrics."""
    
    def __init__(self, data_path: str = "data"):
        self.health_checker = HealthChecker(data_path)
        self.performance_monitor = PerformanceMonitor()
        self._monitoring_active = False
        self._monitor_thread = None
        self._monitor_interval = 60  # seconds
    
    def start_monitoring(self, interval_seconds: int = 60) -> None:
        """
        Start continuous system monitoring.
        
        Args:
            interval_seconds: Monitoring interval in seconds
        """
        if self._monitoring_active:
            logger.warning("Monitoring is already active")
            return
        
        self._monitor_interval = interval_seconds
        self._monitoring_active = True
        
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self._monitor_thread.start()
        
        logger.info(f"Started system monitoring with {interval_seconds}s interval")
    
    def stop_monitoring(self) -> None:
        """Stop continuous system monitoring."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        logger.info("Stopped system monitoring")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while self._monitoring_active:
            try:
                # Run health checks and record as metrics
                health_results = self.health_checker.run_all_checks()
                
                for result in health_results:
                    # Record health check duration
                    self.performance_monitor.record_metric(
                        f"health_check_duration_{result.name}",
                        result.duration_ms,
                        "ms"
                    )
                    
                    # Record health status as numeric value
                    status_value = {
                        HealthStatus.HEALTHY: 1,
                        HealthStatus.WARNING: 0.5,
                        HealthStatus.CRITICAL: 0,
                        HealthStatus.UNKNOWN: -1
                    }.get(result.status, -1)
                    
                    self.performance_monitor.record_metric(
                        f"health_status_{result.name}",
                        status_value,
                        "status"
                    )
                
                # Record system metrics
                self._record_system_metrics()
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            # Wait for next interval
            time.sleep(self._monitor_interval)
    
    def _record_system_metrics(self) -> None:
        """Record system performance metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.performance_monitor.record_metric("cpu_usage", cpu_percent, "%")
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.performance_monitor.record_metric("memory_usage", memory.percent, "%")
            self.performance_monitor.record_metric("memory_available", memory.available / (1024**3), "GB")
            
            # Process-specific metrics
            process = psutil.Process()
            self.performance_monitor.record_metric("process_memory", process.memory_percent(), "%")
            self.performance_monitor.record_metric("process_cpu", process.cpu_percent(), "%")
            self.performance_monitor.record_metric("process_threads", process.num_threads(), "count")
            
        except Exception as e:
            logger.warning(f"Failed to record system metrics: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary with system status information
        """
        health_results = self.health_checker.run_all_checks()
        overall_status = self.health_checker.get_overall_status(health_results)
        
        # Get recent performance metrics
        recent_metrics = {}
        metric_names = ["cpu_usage", "memory_usage", "process_memory", "process_cpu"]
        
        for metric_name in metric_names:
            summary = self.performance_monitor.get_metric_summary(
                metric_name,
                since=datetime.now() - timedelta(minutes=10)
            )
            if summary["count"] > 0:
                recent_metrics[metric_name] = summary
        
        return {
            "overall_status": overall_status.value,
            "health_checks": [
                {
                    "name": result.name,
                    "status": result.status.value,
                    "message": result.message,
                    "duration_ms": result.duration_ms
                }
                for result in health_results
            ],
            "performance_metrics": recent_metrics,
            "monitoring_active": self._monitoring_active,
            "timestamp": datetime.now().isoformat()
        }


# Global system monitor instance
system_monitor = SystemMonitor()