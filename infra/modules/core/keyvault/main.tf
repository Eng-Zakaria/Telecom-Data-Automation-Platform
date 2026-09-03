resource "azurerm_key_vault" "main" {
  count                   = var.use_local_dev ? 0 : 1
  name                    = var.name
  resource_group_name     = var.resource_group_name
  location                = var.location
  tenant_id               = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days = 90
  purge_protection_enabled    = true
  sku_name                    = "standard"

  enable_rbac_authorization   = true
  network_acls {
    default_action = "deny"
    bypass         = "AzureServices"
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "keyvault_contributor" {
  count                = var.use_local_dev ? 0 : 1
  role_definition_name = "Key Vault Administrator"
  principal_id           = data.azurerm_client_config.current.object_id
  scope                   = azurerm_key_vault.main[0].id
}

resource "random_password" "storage_connection_string" {
  count  = var.use_local_dev ? 0 : 1
  length = 84
  special = false
}

resource "azurerm_key_vault_secret" "storage_connection_string" {
  count         = var.use_local_dev ? 0 : 1
  name          = "storage-connection-string"
  key_vault_id  = azurerm_key_vault.main[0].id
  value         = azurerm_storage_account.main[0].primary_connection_string
  content_type  = "application/octet-stream"
}

resource "azurerm_key_vault_secret" "eventhubs_primary_key" {
  count         = var.use_local_dev ? 0 : 1
  name          = "eventhubs-primary-key"
  key_vault_id  = azurerm_key_vault.main[0].id
  value         = azurerm_namespace.authorization[0].default_primary_connection_string
  content_type  = "application/octet-stream"
}

resource "azurerm_key_vault_secret" "databricks_access_token" {
  count         = var.use_local_dev ? 0 : 1
  name          = "databricks-access-token"
  key_vault_id  = azurerm_key_vault.main[0].id
  value         = random_password.databricks_token[0].result
  content_type  = "application/octet-stream"
}

resource "azurerm_storage_account" "main" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "kv${replace(var.name, "-", "")}sa"
  resource_group_name  = var.resource_group_name
  location             = var.location
  account_tier         = "Standard"
  account_replication_type = "LRS"
  enable_https_traffic_only = true

  tags = var.tags
}

data "azurerm_client_config" "current" {}

output "key_vault_id" {
  value       = var.use_local_dev ? "" : azurerm_key_vault.main[0].id
  description = "Key Vault resource ID"
}

output "vault_uri" {
  value       = var.use_local_dev ? "" : azurerm_key_vault.main[0].vault_uri
  description = "Key Vault URI for accessing secrets"
}

output "storage_connection_string" {
  value       = var.use_local_dev ? "Use local Azurite" : azurerm_key_vault_secret.storage_connection_string[0].value
  description = "Storage connection string (secret)"
  sensitive   = true
}
