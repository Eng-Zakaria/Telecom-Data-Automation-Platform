variable "environment" {
  type    = string
  default = "staging"
}

variable "resource_group_name" {
  type    = string
  default = "rg-telecom-staging"
}

variable "keyvault_name" {
  type    = string
  default = "kv-telecom-staging"
}

variable "storage_account_name" {
  type    = string
  default = "sttelecomstaging001"
}

variable "eventhubs_namespace" {
  type    = string
  default = "eh-telecom-staging"
}

variable "databricks_workspace_name" {
  type    = string
  default = "dbx-telecom-staging"
}

variable "fabric_workspace_name" {
  type    = string
  default = "fbc-telecom-staging"
}

variable "subscription_id" {
  type      = string
  default   = ""
  sensitive = true
}

variable "use_local_dev" {
  type    = bool
  default = false
}

variable "branch_name" {
  type    = string
  default = "staging"
}

locals {
  common_tags = {
    Project     = "telecom-platform"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

terraform {
  backend "azurerm" {
    resource_group_name  = "rg-telecom-state"
    storage_account_name = "sttelecomstate001"
    container_name       = "terraform-state"
    key                  = "staging/terraform.tfstate"
  }
}

module "core_keyvault" {
  source = "../../modules/core/keyvault"

  name                = var.keyvault_name
  resource_group_name = var.resource_group_name
  location            = "eastus2"
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  tags                = local.common_tags
}

module "core_networking" {
  source = "../../modules/core/networking"

  name                = "telecom-vnet-staging"
  resource_group_name = var.resource_group_name
  location            = "eastus2"
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  tags                = local.common_tags
}

module "storage_blob" {
  source = "../../modules/storage/blob"

  name                 = var.storage_account_name
  resource_group_name  = var.resource_group_name
  location             = "eastus2"
  environment          = var.environment
  use_local_dev        = var.use_local_dev
  keyvault_id          = module.core_keyvault.key_vault_id
  tags                 = local.common_tags
}

module "storage_onelake" {
  source = "../../modules/storage/onelake"

  workspace_name      = var.fabric_workspace_name
  resource_group_name = var.resource_group_name
  location            = "eastus2"
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  storage_account_id  = module.storage_blob.storage_account_id
  tags                = local.common_tags
}

module "ingestion_eventhubs" {
  source = "../../modules/ingestion/eventhubs"

  namespace_name      = var.eventhubs_namespace
  resource_group_name = var.resource_group_name
  location            = "eastus2"
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  tags                = local.common_tags
}

module "processing_databricks" {
  source = "../../modules/processing/databricks"

  workspace_name      = var.databricks_workspace_name
  resource_group_name = var.resource_group_name
  location            = "eastus2"
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  keyvault_id         = module.core_keyvault.key_vault_id
  tags                = local.common_tags
}

module "processing_data_factory" {
  source = "../../modules/processing/data-factory"

  name                = "adf-telecom-staging"
  resource_group_name = var.resource_group_name
  location            = "eastus2"
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  tags                = local.common_tags
}

module "fabric_workspace" {
  source = "../../modules/fabric/workspace"

  workspace_name      = var.fabric_workspace_name
  resource_group_name = var.resource_group_name
  location            = "eastus2"
  environment         = var.environment
  capacity_sku        = "F4"
  tags                = local.common_tags
}

output "keyvault_endpoint" {
  value       = module.core_keyvault.vault_uri
  description = "Key Vault endpoint"
}

output "storage_connection_string" {
  value       = module.storage_blob.storage_connection_string
  description = "Storage connection string"
  sensitive   = true
}
