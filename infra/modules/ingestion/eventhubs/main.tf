resource "azurerm_eventhub_namespace" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                  = var.namespace_name
  resource_group_name   = var.resource_group_name
  location              = var.location
  sku                   = "Standard"
  capacity              = 1
  zone_redundant        = true

  tags = var.tags
}

resource "azulvm_eventhub" "cdr" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "cdr-stream"
  namespace_name       = azurerm_eventhub_namespace.main[0].name
  resource_group_name  = var.resource_group_name
  partition_count      = 4
  message_retention_in_days = 7
}

resource "azurerm_eventhub" "network_kpi" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "network-kpi-stream"
  namespace_name       = azurerm_eventhub_namespace.main[0].name
  resource_group_name  = var.resource_group_name
  partition_count      = 4
  message_retention_in_days = 7
}

resource "azurerm_eventhub" "billing" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "billing-stream"
  namespace_name       = azurerm_eventhub_namespace.main[0].name
  resource_group_name  = var.resource_group_name
  partition_count      = 2
  message_retention_in_days = 30
}

resource "azurerm_eventhub_consumer_group" "analytics" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "analytics"
  namespace_name       = azurerm_eventhub_namespace.main[0].name
  eventhub_name        = azurerm_eventhub.cdr[0].name
  resource_group_name  = var.resource_group_name
}

resource "azurerm_eventhub_namespace_authorization_rule" "main" {
  count                 = var.use_local_dev ? 0 : 1
  name                  = "RootManageSharedAccessKey"
  namespace_name        = azurerm_eventhub_namespace.main[0].name
  resource_group_name   = var.resource_group_name
  listen                = true
  send                = true
  manage              = true
}

output "namespace_id" {
  value       = var.use_local_dev ? "" : azurerm_eventhub_namespace.main[0].id
  description = "Event Hubs namespace ID"
}

output "namespace_primary_access_key" {
  value       = var.use_local_dev ? "" : azurerm_eventhub_namespace_authorization_rule.main[0].primary_key
  description = "Primary access key"
  sensitive   = true
}

output "connection_string" {
  value       = var.use_local_dev ? "Use Redpanda at localhost:9092" : azurerm_eventhub_namespace.main[0].default_primary_connection_string
  description = "Event Hubs connection string"
  sensitive   = true
}
