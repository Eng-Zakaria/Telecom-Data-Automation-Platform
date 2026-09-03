output "key_vault_id" {
  value       = azurerm_key_vault.main[0].id
  description = "Key Vault resource ID"
}

output "vault_uri" {
  value       = azurerm_key_vault.main[0].vault_uri
  description = "Key Vault URI for accessing secrets"
}

output "storage_connection_string" {
  value       = azurerm_key_vault_secret.storage_connection_string[0].value
  description = "Storage connection string"
  sensitive   = true
}

output "eventhubs_primary_key" {
  value       = azurerm_key_vault_secret.eventhubs_primary_key[0].value
  description = "Event Hubs primary access key"
  sensitive   = true
}
