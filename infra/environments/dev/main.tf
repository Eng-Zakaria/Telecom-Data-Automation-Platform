terraform {
  backend "azurerm" {}
}

variable "environment" {
  type        = string
  default     = "dev"
}

variable "resource_group_name" {
  type    = string
  default = "rg-telecom-dev"
}

variable "keyvault_name" {
  type    = string
  default = "kv-telecom-dev"
}

variable "storage_account_name" {
  type    = string
  default = "sttelecomdev001"
}

variable "eventhubs_namespace" {
  type    = string
  default = "eh-telecom-dev"
}

variable "databricks_workspace_name" {
  type    = string
  default = "dbx-telecom-dev"
}

variable "fabric_workspace_name" {
  type    = string
  default = "fbc-telecom-dev"
}

variable "subscription_id" {
  type      = string
  default   = ""
  sensitive = true
}

variable "use_local_dev" {
  type    = bool
  default = true
}

variable "branch_name" {
  type    = string
  default = "main"
}

locals {
  common_tags = {
    Project     = "telecom-platform"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Backend configuration
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-telecom-state"
    storage_account_name = "sttelecomstate001"
    container_name       = "terraform-state"
    key                  = "dev/terraform.tfstate"
  }
}

# Core modules
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

  name                = "telecom-vnet-dev"
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

  name                = "adf-telecom-dev"
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
  capacity_sku        = "F2"
  tags                = local.common_tags
}

output "keyvault_endpoint" {
  value       = module.core_keyvault.vault_uri
  description = "Key Vault endpoint"
}

output "storage_connection_string" {
  value       = module.storage_blob.storage_connection_string
  description = "Storage account connection string"
  sensitive   = true
}
