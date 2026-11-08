# Azure Databricks (Premium for Unity Catalog) + an Access Connector whose managed
# identity Unity Catalog uses to reach the lake. Databricks creates and owns its
# managed resource group; we only name it.
# Local twin: PySpark + Delta (`uv sync --extra spark`) or the deltalake engine.

resource "azurerm_databricks_workspace" "main" {
  count                         = var.use_local_dev ? 0 : 1
  name                          = var.workspace_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = "premium"
  managed_resource_group_name   = "${var.resource_group_name}-dbx-managed"
  public_network_access_enabled = true

  tags = var.tags
}

resource "azurerm_databricks_access_connector" "unity" {
  count               = var.use_local_dev ? 0 : 1
  name                = "dbac-telecom-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "unity_lake" {
  count                = var.use_local_dev ? 0 : 1
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.unity[0].identity[0].principal_id
}

output "workspace_id" {
  value       = var.use_local_dev ? "" : azurerm_databricks_workspace.main[0].id
  description = "Databricks workspace resource ID"
}

output "workspace_url" {
  value       = var.use_local_dev ? "" : "https://${azurerm_databricks_workspace.main[0].workspace_url}"
  description = "Databricks workspace URL"
}

output "access_connector_id" {
  value       = var.use_local_dev ? "" : azurerm_databricks_access_connector.unity[0].id
  description = "Access connector ID for the Unity Catalog storage credential"
}
