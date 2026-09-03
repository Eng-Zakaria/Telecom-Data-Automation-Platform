output "storage_account_id" {
  value       = azurerm_storage_account.main[0].id
  description = "Storage account ID"
}

output "storage_account_name" {
  value       = azurerm_storage_account.main[0].name
  description = "Storage account name"
}

output "storage_connection_string" {
  value       = azurerm_storage_account.main[0].primary_connection_string
  description = "Storage connection string"
  sensitive   = true
}

output "blob_endpoint" {
  value       = azurerm_storage_account.main[0].primary_blob_endpoint
  description = "Blob endpoint URL"
}
