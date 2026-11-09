"""
Alert Management System

Provides alert routing, escalation, and notification:
- Multiple alert channels (Slack, Teams, Email, PagerDuty)
- Alert grouping and deduplication
- Escalation policies
- Alert suppression
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertChannel(Enum):
    """Alert notification channels"""
    SLACK = "slack"
    TEAMS = "teams"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


@dataclass
class Alert:
    """Alert definition"""
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    channel: AlertChannel
    source: str
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    resolved: bool = False
    escalation_level: int = 0


class AlertManager:
    """
    Centralized alert management system.

    Features:
    - Multi-channel notifications
    - Alert grouping
    - Escalation policies
    - Silence/deduplication
    - Alert history
    """

    def __init__(self):
        self.alerts: List[Alert] = []
        self.escalation_policies = {}
        self.silenced_alerts = {}
        self.notification_handlers = {
            AlertChannel.SLACK: self._send_slack,
            AlertChannel.TEAMS: self._send_teams,
            AlertChannel.EMAIL: self._send_email,
            AlertChannel.PAGERDUTY: self._send_Pagerduty,
            AlertChannel.WEBHOOK: self._send_webhook
        }

    def create_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        channel: AlertChannel,
        source: str,
        metadata: Dict = None
    ) -> Alert:
        """
        Create and send a new alert.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity
            channel: Notification channel
            source: Alert source system
            metadata: Additional metadata

        Returns:
            Created Alert object
        """
        alert = Alert(
            alert_id=f"ALERT_{int(time.time())}_{hash(title) % 10000}",
            title=title,
            message=message,
            severity=severity,
            channel=channel,
            source=source,
            metadata=metadata or {}
        )

        self.alerts.append(alert)

        # Send notification
        self._send_notification(alert)

        # Check for escalation
        self._check_escalation(alert)

        return alert

    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now()
                break

    def resolve_alert(self, alert_id: str, resolution: str = ""):
        """Resolve an alert"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.now()
                alert.resolution_notes = resolution
                break

    def silence_alert(self, alert_id: str, duration_hours: int = 1):
        """Silence an alert for specified duration"""
        self.silenced_alerts[alert_id] = {
            "until": datetime.now() + timedelta(hours=duration_hours),
            "reason": "Manual silence"
        }

    def _send_notification(self, alert: Alert):
        """Send alert notification"""
        # Check if silenced
        if alert.alert_id in self.silenced_alerts:
            silence_until = self.silenced_alerts[alert.alert_id]["until"]
            if datetime.now() < silence_until:
                return

        # Send via configured channel
        handler = self.notification_handlers.get(alert.channel)
        if handler:
            handler(alert)

    def _send_slack(self, alert: Alert):
        """Send alert to Slack"""
        color = self._get_slack_color(alert.severity)
        payload = {
            "text": f"🚨 {alert.title}",
            "attachments": [{
                "color": color,
                "title": alert.title,
                "text": alert.message,
                "fields": [
                    {"title": "Severity", "value": alert.severity.value, "short": True},
                    {"title": "Source", "value": alert.source, "short": True},
                    {"title": "Time", "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"), "short": True}
                ],
                "footer": "Telecom Platform Alert"
            }]
        }
        print(f"Slack Alert: {json.dumps(payload, indent=2)}")

    def _send_teams(self, alert: Alert):
        """Send alert to Microsoft Teams"""
        color = self._get_teams_color(alert.severity)
        payload = {
            "@context": "https://schema.org/extensions",
            "@type": "MessageCard",
            "themeColor": color,
            "summary": alert.title,
            "sections": [{
                "activityTitle": alert.title,
                "activitySubtitle": alert.severity.value,
                "activityText": alert.message,
                "facts": [
                    {"name": "Source", "value": alert.source},
                    {"name": "Time", "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
                ]
            }]
        }
        print(f"Teams Alert: {json.dumps(payload, indent=2)}")

    def _send_email(self, alert: Alert):
        """Send alert via email"""
        subject = f"[{alert.severity.value.upper()}] {alert.title}"
        body = f"""
Alert: {alert.title}
Severity: {alert.severity.value}
Source: {alert.source}
Time: {alert.timestamp}

Message:
{alert.message}
        """
        print(f"Email Alert: {subject}\n{body}")

    def _send_Pagerduty(self, alert: Alert):
        """Send alert to PagerDuty"""
        payload = {
            "routing_key": "your_routing_key",
            "event_action": "trigger",
            "payload": {
                "summary": alert.title,
                "severity": alert.severity.value,
                "source": alert.source,
                "component": "telecom-platform",
                "group": "alerts",
                "class": alert.alert_id,
                "custom_details": {
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat()
                }
            }
        }
        print(f"PagerDuty Alert: {json.dumps(payload, indent=2)}")

    def _send_webhook(self, alert: Alert):
        """Send alert to webhook"""
        payload = {
            "alert_id": alert.alert_id,
            "title": alert.title,
            "message": alert.message,
            "severity": alert.severity.value,
            "source": alert.source,
            "timestamp": alert.timestamp.isoformat(),
            "metadata": alert.metadata
        }
        print(f"Webhook Alert: {json.dumps(payload, indent=2)}")

    def _check_escalation(self, alert: Alert):
        """Check if alert needs escalation"""
        policy = self.escalation_policies.get(alert.severity)
        if not policy:
            return

        # Check if alert has been unacknowledged for too long
        if not alert.acknowledged:
            elapsed = datetime.now() - alert.timestamp
            if elapsed > timedelta(minutes=policy.get("escalate_after_minutes", 15)):
                alert.escalation_level += 1
                # Re-send with higher severity
                if alert.escalation_level >= policy.get("max_escalation", 3):
                    self.create_alert(
                        f"[ESCALATED x{alert.escalation_level}] {alert.title}",
                        alert.message,
                        AlertSeverity.EMERGENCY,
                        AlertChannel.PAGERDUTY,
                        alert.source
                    )

    def _get_slack_color(self, severity: AlertSeverity) -> str:
        """Get Slack color for severity"""
        colors = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff8800",
            AlertSeverity.CRITICAL: "#ff0000",
            AlertSeverity.EMERGENCY: "#8b0000"
        }
        return colors.get(severity, "#999999")

    def _get_teams_color(self, severity: AlertSeverity) -> str:
        """Get Teams color for severity"""
        colors = {
            AlertSeverity.INFO: "00FF00",
            AlertSeverity.WARNING: "FFA500",
            AlertSeverity.CRITICAL: "FF0000",
            AlertSeverity.EMERGENCY: "8B0000"
        }
        return colors.get(severity, "999999")

    def get_active_alerts(self) -> List[Alert]:
        """Get all active (unresolved) alerts"""
        return [a for a in self.alerts if not a.resolved]

    def get_alert_summary(self) -> Dict:
        """Get summary of alerts"""
        active = self.get_active_alerts()
        return {
            "total_alerts": len(self.alerts),
            "active_alerts": len(active),
            "by_severity": {
                sev.value: len([a for a in active if a.severity == sev])
                for sev in AlertSeverity
            },
            "by_channel": {
                chan.value: len([a for a in active if a.channel == chan])
                for chan in AlertChannel
            },
            "recent_alerts": [
                {
                    "id": a.alert_id,
                    "title": a.title,
                    "severity": a.severity.value,
                    "source": a.source,
                    "timestamp": a.timestamp.isoformat()
                }
                for a in active[-10:]
            ]
        }


def create_alert_manager() -> AlertManager:
    """Factory function to create alert manager"""
    return AlertManager()


# Global alert manager instance
_alert_manager = AlertManager()


def create_alert(*args, **kwargs):
    """Convenience function to create an alert"""
    return _alert_manager.create_alert(*args, **kwargs)


def get_active_alerts():
    """Get active alerts"""
    return _alert_manager.get_active_alerts()


if __name__ == "__main__":
    # Example usage
    manager = create_alert_manager()

    # Create test alerts
    manager.create_alert(
        title="Pipeline Failed",
        message="CDR ingestion pipeline failed with error: Connection timeout",
        severity=AlertSeverity.CRITICAL,
        channel=AlertChannel.SLACK,
        source="cdr_pipeline",
        metadata={"error_code": "CONN_TIMEOUT"}
    )

    manager.create_alert(
        title="High Latency Detected",
        message="Network KPI pipeline latency exceeded 5 seconds",
        severity=AlertSeverity.WARNING,
        channel=AlertChannel.TEAMS,
        source="network_pipeline"
    )

    # Get summary
    print(json.dumps(manager.get_alert_summary(), indent=2))
