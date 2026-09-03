output "namespace_id" {
  value       = azurerm_eventhub_namespace.main[0].id
  description = "Event Hubs namespace ID"
}

output "namespace_primary_access_key" {
  value       = azurerm_eventhub_namespace_authorization_rule.main[0].primary_key
  description = "Primary access key"
  sensitive   = true
}

output "connection_string" {
  value       = azurerm_eventhub_namespace.main[0].default_primary_connection_string
  description = "Event Hubs connection string"
  sensitive   = true
}
