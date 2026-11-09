"""
Centralized Logging System

Provides structured logging across all pipelines with:
- Log aggregation
- Error tracking
- Performance metrics
- Alert integration
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path


class TelecomLogger:
    """
    Centralized logger for telecom platform.

    Features:
    - Structured JSON logging
    - Log rotation
    - Error tracking
    - Performance metrics
    - Alert integration
    """

    def __init__(
        self,
        service_name: str,
        environment: str = "dev",
        log_level: str = "INFO",
        log_dir: str = "logs"
    ):
        self.service_name = service_name
        self.environment = environment
        self.log_level = getattr(logging, log_level.upper())
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Setup logger
        self.logger = logging.getLogger(f"telecom.{service_name}")
        self.logger.setLevel(self.log_level)

        # Add handlers
        self._setup_handlers()

        # Metrics tracking
        self.metrics = {
            "records_processed": 0,
            "records_failed": 0,
            "errors": [],
            "start_time": datetime.now()
        }

    def _setup_handlers(self):
        """Setup log handlers"""
        # File handler with rotation
        file_handler = logging.FileHandler(
            self.log_dir / f"{self.service_name}.log"
        )
        file_handler.setLevel(self.log_level)

        # JSON formatter
        formatter = logging.Formatter(
            json.dumps(self._get_base_log())
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def _get_base_log(self) -> Dict:
        """Get base log structure"""
        return {
            "service": self.service_name,
            "environment": self.environment,
            "timestamp": datetime.now().isoformat(),
            "host": os.environ.get("HOSTNAME", "unknown")
        }

    def info(self, message: str, **kwargs):
        """Log info message"""
        log_data = {
            **self._get_base_log(),
            "level": "info",
            "message": message,
            **kwargs
        }
        self.logger.info(json.dumps(log_data))

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        log_data = {
            **self._get_base_log(),
            "level": "warning",
            "message": message,
            **kwargs
        }
        self.logger.warning(json.dumps(log_data))

    def error(self, message: str, **kwargs):
        """Log error message"""
        log_data = {
            **self._get_base_log(),
            "level": "error",
            "message": message,
            **kwargs
        }
        self.logger.error(json.dumps(log_data))

        # Track error
        self.metrics["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            **kwargs
        })

    def performance_metric(self, metric_name: str, value: float, unit: str = ""):
        """Log performance metric"""
        log_data = {
            **self._get_base_log(),
            "level": "info",
            "type": "performance_metric",
            "metric_name": metric_name,
            "value": value,
            "unit": unit
        }
        self.logger.info(json.dumps(log_data))

    def record_processed(self, count: int = 1):
        """Track records processed"""
        self.metrics["records_processed"] += count
        self.performance_metric(
            "records_processed",
            self.metrics["records_processed"]
        )

    def record_failed(self, count: int = 1, reason: str = None):
        """Track records failed"""
        self.metrics["records_failed"] += count
        self.performance_metric(
            "records_failed",
            self.metrics["records_failed"]
        )
        if reason:
            self.error(f"Record processing failed: {reason}")

    def get_metrics(self) -> Dict:
        """Get current metrics"""
        uptime = (datetime.now() - self.metrics["start_time"]).total_seconds()
        return {
            **self.metrics,
            "uptime_seconds": uptime,
            "records_per_second": (
                self.metrics["records_processed"] / uptime
                if uptime > 0 else 0
            )
        }

    def get_log_summary(self, hours: int = 24) -> Dict:
        """Get log summary for recent period"""
        try:
            log_file = self.log_dir / f"{self.service_name}.log"
            if not log_file.exists():
                return {"error": "No log file found"}

            # Read and parse logs
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = [json.loads(line) for line in f if line.strip()]

            # Filter by time
            cutoff = datetime.now().timestamp() - (hours * 3600)
            recent_logs = [
                log for log in logs
                if datetime.fromisoformat(log["timestamp"]).timestamp() > cutoff
            ]

            # Count by level
            info_count = sum(1 for l in recent_logs if l.get("level") == "info")
            warning_count = sum(1 for l in recent_logs if l.get("level") == "warning")
            error_count = sum(1 for l in recent_logs if l.get("level") == "error")

            return {
                "service": self.service_name,
                "hours": hours,
                "total_logs": len(recent_logs),
                "info": info_count,
                "warnings": warning_count,
                "errors": error_count,
                "recent_errors": [
                    log for log in recent_logs
                    if log.get("level") == "error"
               ][-10:]
            }
        except Exception as e:
            return {"error": str(e)}


def get_logger(
    service_name: str,
    environment: str = "dev",
    log_level: str = "INFO"
) -> TelecomLogger:
    """
    Factory function to create logger.

    Args:
        service_name: Name of the service
        environment: Environment name
        log_level: Logging level

    Returns:
        TelecomLogger instance
    """
    return TelecomLogger(
        service_name=service_name,
        environment=environment,
        log_level=log_level
    )


if __name__ == "__main__":
    # Example usage
    logger = get_logger("test_service")

    logger.info("Service started")
    logger.record_processed(100)
    logger.record_failed(5, reason="Schema mismatch")
    logger.warning("High latency detected")
    logger.error("Connection timeout")

    print(f"Metrics: {logger.get_metrics()}")
    print(f"Log summary: {logger.get_log_summary()}")
