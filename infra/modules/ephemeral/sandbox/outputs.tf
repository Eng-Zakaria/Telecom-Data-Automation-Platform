output "resource_group_id" {
  value       = azurerm_resource_group.ephemeral.id
  description = "Ephemeral resource group ID"
}

output "resource_group_name" {
  value       = azurerm_resource_group.ephemeral.name
  description = "Ephemeral resource group name"
}

output "keyvault_id" {
  value       = azurerm_key_vault.ephemeral[0].id
  description = "Key Vault ID"
}

output "storage_account_id" {
  value       = azurerm_storage_account.ephemeral[0].id
  description = "Storage account ID"
}
