resource "azurerm_storage_account" "main" {
  count                = var.use_local_dev ? 0 : 1
  name                 = var.name
  resource_group_name  = var.resource_group_name
  location             = var.location
  account_tier         = "Standard"
  account_replication_type = "LRS"
  enable_https_traffic_only = true

  network_rules {
    default_action             = "Deny"
    ip_rules                   = []
    virtual_network_subnet_ids = [var.keyvault_id]
  }

  tags = var.tags
}

resource "azurerm_storage_container" "bronze" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "bronze"
  storage_account_name = azurerm_storage_account.main[0].name
  container_access_type = "private"
}

resource "azurerm_storage_container" "silver" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "silver"
  storage_account_name = azurerm_storage_account.main[0].name
  container_access_type = "private"
}

resource "azurerm_storage_container" "gold" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "gold"
  storage_account_name = azurerm_storage_account.main[0].name
  container_access_type = "private"
}

resource "azurerm_storage_container" "deadletter" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "deadletter"
  storage_account_name = azurerm_storage_account.main[0].name
  container_access_type = "private"
}

output "storage_account_id" {
  value       = var.use_local_dev ? "" : azurerm_storage_account.main[0].id
  description = "Storage account ID"
}

output "storage_account_name" {
  value       = var.use_local_dev ? "" : azurerm_storage_account.main[0].name
  description = "Storage account name"
}

output "storage_connection_string" {
  value       = var.use_local_dev ? "Use Azurite at localhost:10000" : azurerm_storage_account.main[0].primary_connection_string
  description = "Storage connection string"
  sensitive   = true
}

output "blob_endpoint" {
  value       = var.use_local_dev ? "http://localhost:10000" : azurerm_storage_account.main[0].primary_blob_endpoint
  description = "Blob endpoint URL"
}
