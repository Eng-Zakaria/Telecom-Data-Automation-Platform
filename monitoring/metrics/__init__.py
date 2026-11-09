"""
Metrics Collection and Monitoring

Provides real-time metrics collection and monitoring:
- Pipeline performance
- Data quality
- System health
- Business KPIs
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import json


class MetricsCollector:
    """
    Centralized metrics collector for telecom platform.

    Features:
    - Real-time metrics collection
    - Time-series storage
    - Alerting on thresholds
    - Dashboard-ready format
    """

    def __init__(self):
        self.metrics = defaultdict(list)
        self.thresholds = {}
        self.alerts = []

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None,
        metric_type: str = "gauge"
    ):
        """
        Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags (e.g., {'table': 'cdr', 'env': 'prod'})
            metric_type: Type of metric (gauge, counter, histogram)
        """
        metric = {
            "name": name,
            "value": value,
            "timestamp": datetime.now().isoformat(),
            "tags": tags or {},
            "type": metric_type
        }
        self.metrics[name].append(metric)

        # Check thresholds
        self._check_thresholds(name, value, tags)

    def record_counter(
        self,
        name: str,
        increment: float = 1,
        tags: Dict[str, str] = None
    ):
        """Record a counter metric (always increases)"""
        self.record_metric(name, increment, tags, "counter")

    def record_histogram(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None
    ):
        """Record a histogram metric (distribution)"""
        self.record_metric(name, value, tags, "histogram")

    def set_threshold(
        self,
        metric_name: str,
        warning_threshold: float,
        critical_threshold: float,
        comparison: str = "greater_than"
    ):
        """Set alerting thresholds for a metric"""
        self.thresholds[metric_name] = {
            "warning": warning_threshold,
            "critical": critical_threshold,
            "comparison": comparison
        }

    def _check_thresholds(
        self,
        metric_name: str,
        value: float,
        tags: Dict[str, str]
    ):
        """Check if metric value exceeds thresholds"""
        if metric_name not in self.thresholds:
            return

        threshold = self.thresholds[metric_name]
        should_alert = False
        severity = None

        if threshold["comparison"] == "greater_than":
            if value > threshold["critical"]:
                should_alert = True
                severity = "critical"
            elif value > threshold["warning"]:
                should_alert = True
                severity = "warning"
        elif threshold["comparison"] == "less_than":
            if value < threshold["critical"]:
                should_alert = True
                severity = "critical"
            elif value < threshold["warning"]:
                should_alert = True
                severity = "warning"

        if should_alert:
            self._send_alert(metric_name, value, severity, tags)

    def _send_alert(
        self,
        metric_name: str,
        value: float,
        severity: str,
        tags: Dict[str, str]
    ):
        """Send alert for threshold breach"""
        alert = {
            "metric_name": metric_name,
            "value": value,
            "severity": severity,
            "tags": tags,
            "timestamp": datetime.now().isoformat(),
            "message": f"Metric {metric_name} breached {severity} threshold: {value}"
        }
        self.alerts.append(alert)
        print(f"⚠️  ALERT [{severity.upper()}]: {alert['message']}")

    def get_metric_value(
        self,
        name: str,
        tags: Dict[str, str] = None,
        latest: bool = True
    ) -> Optional[float]:
        """Get current metric value"""
        if name not in self.metrics:
            return None

        values = self.metrics[name]
        if tags:
            values = [m for m in values if all(
                m["tags"].get(k) == v for k, v in tags.items()
            )]

        if not values:
            return None

        if latest:
            return values[-1]["value"]

        return values

    def get_metric_average(
        self,
        name: str,
        hours: int = 1,
        tags: Dict[str, str] = None
    ) -> Optional[float]:
        """Get average metric value over time period"""
        values = self.get_metric_value(name, tags, latest=False)
        if not values:
            return None

        cutoff = datetime.now() - timedelta(hours=hours)
        recent_values = [
            v["value"] for v in values
            if datetime.fromisoformat(v["timestamp"]) > cutoff
        ]

        return sum(recent_values) / len(recent_values) if recent_values else None

    def get_dashboard_data(self) -> Dict:
        """Get data formatted for dashboard display"""
        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
            "alerts": self.alerts[-10:],  # Last 10 alerts
            "summary": {}
        }

        # Aggregate metrics
        for name, values in self.metrics.items():
            recent = [v for v in values if
                     datetime.fromisoformat(v["timestamp"]) >
                     datetime.now() - timedelta(hours=1)]

            if recent:
                dashboard["metrics"][name] = {
                    "current": recent[-1]["value"],
                    "average": sum(v["value"] for v in recent) / len(recent),
                    "min": min(v["value"] for v in recent),
                    "max": max(v["value"] for v in recent),
                    "count": len(recent)
                }

        # Summary statistics
        dashboard["summary"] = {
            "total_metrics": len(self.metrics),
            "active_alerts": len(self.alerts),
            "metrics_collected": sum(len(v) for v in self.metrics.values())
        }

        return dashboard

    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in specified format"""
        if format == "json":
            return json.dumps(self.get_dashboard_data(), indent=2)
        elif format == "prometheus":
            return self._export_prometheus()
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        for name, values in self.metrics.items():
            if values:
                latest = values[-1]
                tags = ",".join(
                    f'{k}="{v}"' for k, v in latest["tags"].items()
                )
                lines.append(
                    f'{name}{{{tags}}} {latest["value"]} {int(time.time() * 1000)}'
                )
        return "\n".join(lines)

    def clear_old_metrics(self, hours: int = 24):
        """Clear metrics older than specified hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        for name in self.metrics:
            self.metrics[name] = [
                m for m in self.metrics[name]
                if datetime.fromisoformat(m["timestamp"]) > cutoff
            ]


# Global metrics collector instance
_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance"""
    return _collector


def record_metric(*args, **kwargs):
    """Convenience function to record a metric"""
    return _collector.record_metric(*args, **kwargs)


def record_counter(*args, **kwargs):
    """Convenience function to record a counter"""
    return _collector.record_counter(*args, **kwargs)


def get_dashboard() -> Dict:
    """Get dashboard data"""
    return _collector.get_dashboard_data()


if __name__ == "__main__":
    # Example usage
    collector = MetricsCollector()

    # Set thresholds
    collector.set_threshold(
        "pipeline_latency_ms",
        warning_threshold=1000,
        critical_threshold=5000
    )

    # Record metrics
    collector.record_counter("records_processed", 100, {"table": "cdr"})
    collector.record_counter("records_processed", 150, {"table": "network_kpi"})
    collector.record_metric("pipeline_latency_ms", 500, {"stage": "bronze"})
    collector.record_metric("pipeline_latency_ms", 1500, {"stage": "silver"})
    collector.record_metric("pipeline_latency_ms", 6000, {"stage": "gold"})

    # Get dashboard
    print(json.dumps(collector.get_dashboard(), indent=2))

    # Export metrics
    print("\nPrometheus format:")
    print(collector.export_metrics("prometheus"))
