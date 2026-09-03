resource "azurerm_data_factory" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                  = var.name
  location              = var.location
  resource_group_name   = var.resource_group_name
  github_account {
    account_name    = "github-account"
    repository_name = "data-factory-pipelines"
    branch_name     = "main"
    root_folder     = "/"
  }

  tags = var.tags
}

resource "azurerm_data_factory_integration_runtime" "self_hosted" {
  count                 = var.use_local_dev ? 0 : 1
  name                    = "self-hosted-ir"
  data_factory_id         = azurerm_data_factory.main[0].id
  type                    = "SelfHosted"
  description             = "Self-hosted integration runtime for on-premises data sources"
}

resource "azurerm_data_factory_linked_service_azurerm" "blob" {
  count               = var.use_local_dev ? 0 : 1
  name                  = "LinkedServiceAzureStorage"
  data_factory_id       = azurerm_data_factory.main[0].id
  azure_storage {
    connection_string     = var.storage_connection_string
  }
}

resource "azurerm_data_factory_linked_service_key_vault" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                  = "LinkedServiceKeyVault"
  data_factory_id       = azurerm_data_factory.main[0].id
  azure_key_vault {
    base_url            = var.keyvault_url
  }
}

output "data_factory_id" {
  value       = var.use_local_dev ? "" : azurerm_data_factory.main[0].id
  description = "Data Factory ID"
}

output "data_factory_url" {
  value       = var.use_local_dev ? "" : azurerm_data_factory.main[0].url
  description = "Data Factory URL"
}
