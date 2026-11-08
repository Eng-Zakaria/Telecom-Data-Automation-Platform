# Log Analytics + workspace-based Application Insights.
# Pipelines export OpenTelemetry through cloudkit.telemetry; in Azure the exporter
# switches to Azure Monitor using this connection string. Locally: Grafana LGTM.

resource "azurerm_log_analytics_workspace" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                = "log-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_days
  daily_quota_gb      = var.daily_quota_gb

  tags = var.tags
}

resource "azurerm_application_insights" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                = "appi-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.main[0].id
  application_type    = "other"

  tags = var.tags
}

# Pipeline SLO: alert when a run reports a failed quality gate.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "quality_gate_failed" {
  count                = var.use_local_dev || length(var.alert_emails) == 0 ? 0 : 1
  name                 = "alert-${var.name}-quality-gate"
  resource_group_name  = var.resource_group_name
  location             = var.location
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 2
  evaluation_frequency = "PT15M"
  window_duration      = "PT15M"
  description          = "A pipeline run finished with a failed data quality gate"

  criteria {
    query                   = <<-KQL
      customMetrics
      | where name == "telecom.quality.gate_failures"
      | summarize failures = sum(valueSum)
    KQL
    time_aggregation_method = "Total"
    metric_measure_column   = "failures"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.oncall[0].id]
  }

  tags = var.tags
}

resource "azurerm_monitor_action_group" "oncall" {
  count               = var.use_local_dev || length(var.alert_emails) == 0 ? 0 : 1
  name                = "ag-${var.name}-oncall"
  resource_group_name = var.resource_group_name
  short_name          = "dataoncall"

  dynamic "email_receiver" {
    for_each = var.alert_emails
    content {
      name          = "email-${email_receiver.key}"
      email_address = email_receiver.value
    }
  }

  tags = var.tags
}

output "connection_string" {
  value       = var.use_local_dev ? "" : azurerm_application_insights.main[0].connection_string
  description = "App Insights connection string (cloudkit: APPLICATIONINSIGHTS_CONNECTION_STRING)"
  sensitive   = true
}

output "log_analytics_workspace_id" {
  value       = var.use_local_dev ? "" : azurerm_log_analytics_workspace.main[0].id
  description = "Log Analytics workspace ID (for diagnostic settings)"
}
