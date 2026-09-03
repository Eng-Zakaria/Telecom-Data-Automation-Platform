resource "azurerm_databricks_workspace" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                  = var.workspace_name
  resource_group_name   = var.resource_group_name
  location              = var.location
  sku                   = "premium"
  managed_resource_group_id = azurerm_resource_group.databricks[0].id

  custom_parameters {
    no_public_ip                                         = true
    private_subnet_id                                    = var.processing_subnet_id
    private_point_to_site_vpn_profile_id                 = null
    public_network_access_enabled                        = false
    virtual_network_id                                   = var.vnet_id
  }

  tags = var.tags
}

resource "azurerm_resource_group" "databricks" {
  count       = var.use_local_dev ? 0 : 1
  name        = "${var.resource_group_name}-databricks"
  location    = var.location
  tags        = var.tags
}

resource "azurerm_databricks_workspace_policy" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                  = "default-policy"
  workspace_id          = azurerm_databricks_workspace.main[0].id
  json                  = jsonencode({
    "enable_custom_cluster_tags" = false
    "custom_cluster_tags"        = {}
    "remove_default_pg_cidr"     = true
  })
}

resource "azurerm_databricks_access_connector" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                  = "dbc-telecom-${var.environment}"
  resource_group_name   = var.resource_group_name
  location              = var.location
  identity_type         = "SystemAssigned"
}

output "workspace_id" {
  value       = var.use_local_dev ? "" : azurerm_databricks_workspace.main[0].id
  description = "Databricks workspace ID"
}

output "workspace_url" {
  value       = var.use_local_dev ? "" : azurerm_databricks_workspace.main[0].workspace_url
  description = "Databricks workspace URL"
}

output "workspace_fqid" {
  value       = var.use_local_dev ? "" : azurerm_databricks_workspace.main[0].fqdn
  description = "Databricks workspace FQDN"
}
