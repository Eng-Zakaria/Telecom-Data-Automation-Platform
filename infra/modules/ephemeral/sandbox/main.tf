resource "azurerm_resource_group" "ephemeral" {
  name     = "${var.resource_group_name}-${var.branch_name}"
  location = var.location
  tags = merge(var.tags, {
    Environment = "ephemeral"
    Branch      = var.branch_name
    AutoDelete  = "true"
  })
}

resource "azurerm_management_lock" "protect" {
  count       = var.protect_from_deletion ? 1 : 0
  name        = "lock-ephemeral-${var.branch_name}"
  scope       = azurerm_resource_group.ephemeral.id
  lock_level  = "CanNotDelete"
  notes       = "Ephemeral environment - do not delete manually"
}

resource "azurerm_key_vault" "ephemeral" {
  count                   = var.use_local_dev ? 0 : 1
  name                    = "kv-ephemeral-${replace(var.branch_name, "-", "")}"
  resource_group_name     = azurerm_resource_group.ephemeral.name
  location                = azurerm_resource_group.ephemeral.location
  tenant_id               = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days = 7
  purge_protection_enabled    = false
  sku_name                    = "standard"
  enable_rbac_authorization   = true
  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }

  tags = merge(var.tags, {
    Environment = "ephemeral"
    Branch      = var.branch_name
  })
}

resource "azurerm_storage_account" "ephemeral" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "stephemeral${replace(var.branch_name, "-", "")}001"
  resource_group_name  = azurerm_resource_group.ephemeral.name
  location             = azurerm_resource_group.ephemeral.location
  account_tier         = "Standard"
  account_replication_type = "LRS"
  enable_https_traffic_only = true

  tags = merge(var.tags, {
    Environment = "ephemeral"
    Branch      = var.branch_name
  })
}

resource "time_sleep" "wait_for_cleanup" {
  count           = var.auto_delete ? 1 : 0
  depends_on      = [azurerm_resource_group.ephemeral]
  create_duration = var.auto_delete_after

  triggers = {
    auto_delete = "true"
  }
}

data "azurerm_client_config" "current" {}

output "resource_group_id" {
  value       = azurerm_resource_group.ephemeral.id
  description = "Ephemeral resource group ID"
}

output "resource_group_name" {
  value       = azurerm_resource_group.ephemeral.name
  description = "Ephemeral resource group name"
}

output "keyvault_id" {
  value       = var.use_local_dev ? "" : azurerm_key_vault.ephemeral[0].id
  description = "Key Vault ID"
}

output "storage_account_id" {
  value       = var.use_local_dev ? "" : azurerm_storage_account.ephemeral[0].id
  description = "Storage account ID"
}
