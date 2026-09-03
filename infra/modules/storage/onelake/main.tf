# OneLake is provisioned through Fabric workspace
# This module handles the lakehouse configuration

resource "azurerm_fabric_capacity" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                  = var.workspace_name
  resource_group_name   = var.resource_group_name
  location              = var.location
  sku                   = var.capacity_sku
  availability_zone     = "1,2,3"

  tags = var.tags
}

resource "azurerm_fabric_workspace" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                  = var.workspace_name
  description           = "Telecom Data Platform - ${var.environment} Workspace"
  capacity_id           = azurerm_fabric_capacity.main[0].id
  default_semantic_model_capacity_id = azurerm_fabric_capacity.main[0].id
  groups_enabled        = true
  compatibility_level   = 1500
  state                 = "Active"

  tags = var.tags
}

resource "azurerm_fabric_lakehouse" "bronze" {
  count               = var.use_local_dev ? 0 : 1
  name                  = "lakehouse-bronze"
  fabric_workspace_id   = azurerm_fabric_workspace.main[0].id
  storage_account_id    = var.storage_account_id
}

resource "azurerm_fabric_lakehouse" "silver" {
  count               = var.use_local_dev ? 0 : 1
  name                  = "lakehouse-silver"
  fabric_workspace_id   = azurerm_fabric_workspace.main[0].id
  storage_account_id    = var.storage_account_id
}

resource "azurerm_fabric_lakehouse" "gold" {
  count               = var.use_local_dev ? 0 : 1
  name                  = "lakehouse-gold"
  fabric_workspace_id   = azurerm_fabric_workspace.main[0].id
  storage_account_id    = var.storage_account_id
}

output "workspace_id" {
  value       = var.use_local_dev ? "" : azurerm_fabric_workspace.main[0].id
  description = "Fabric workspace ID"
}

output "workspace_url" {
  value       = var.use_local_dev ? "" : azurerm_fabric_workspace.main[0].web_url
  description = "Fabric workspace URL"
}
