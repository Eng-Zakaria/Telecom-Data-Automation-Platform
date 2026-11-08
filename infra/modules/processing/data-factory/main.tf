# Azure Data Factory with a system-assigned identity.
# Linked services authenticate with that identity (no connection strings in ADF).
# Local twin: the Python orchestrator in pipelines/ (run_local.py).

resource "azurerm_data_factory" "main" {
  count                  = var.use_local_dev ? 0 : 1
  name                   = var.name
  location               = var.location
  resource_group_name    = var.resource_group_name
  public_network_enabled = true

  identity {
    type = "SystemAssigned"
  }

  dynamic "github_configuration" {
    for_each = var.git_repository == null ? [] : [var.git_repository]
    content {
      account_name       = github_configuration.value.account_name
      repository_name    = github_configuration.value.repository_name
      branch_name        = github_configuration.value.branch_name
      root_folder        = github_configuration.value.root_folder
      git_url            = "https://github.com"
      publishing_enabled = true
    }
  }

  tags = var.tags
}

resource "azurerm_data_factory_linked_service_data_lake_storage_gen2" "lake" {
  count                = var.use_local_dev ? 0 : 1
  name                 = "ls_adls_lake"
  data_factory_id      = azurerm_data_factory.main[0].id
  url                  = var.storage_dfs_endpoint
  use_managed_identity = true
}

resource "azurerm_data_factory_linked_service_key_vault" "main" {
  count           = var.use_local_dev ? 0 : 1
  name            = "ls_key_vault"
  data_factory_id = azurerm_data_factory.main[0].id
  key_vault_id    = var.key_vault_id
}

# Data-plane access for ADF's identity: write the lake, read secrets.
resource "azurerm_role_assignment" "adf_lake" {
  count                = var.use_local_dev ? 0 : 1
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_data_factory.main[0].identity[0].principal_id
}

resource "azurerm_role_assignment" "adf_secrets" {
  count                = var.use_local_dev ? 0 : 1
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_data_factory.main[0].identity[0].principal_id
}

output "data_factory_id" {
  value       = var.use_local_dev ? "" : azurerm_data_factory.main[0].id
  description = "Data Factory ID"
}

output "data_factory_principal_id" {
  value       = var.use_local_dev ? "" : azurerm_data_factory.main[0].identity[0].principal_id
  description = "Object ID of the factory's managed identity"
}
