terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    minio = {
      source  = "aminueza/minio"
      version = "~> 1.0"
    }
    kafka = {
      source  = "hashicorp/kafka"
      version = "~> 1.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
    key_vault {
      purge_soft_deleted_secrets_on_destroy = false
      recover_soft_deleted_key_vaults     = false
    }
  }
}

locals {
  common_tags = {
    Project     = "telecom-platform"
    Environment = var.environment
    ManagedBy   = "terraform"
    CreatedAt   = timestamp()
  }
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Environment name (dev, staging, prod, ephemeral)"

  validation {
    condition     = contains(["dev", "staging", "prod", "ephemeral"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod, ephemeral"
  }
}

variable "location" {
  type        = string
  default     = "eastus2"
  description = "Azure region for resource deployment"
}

variable "use_local_dev" {
  type        = bool
  default     = false
  description = "When true, provisions local development resources instead of Azure resources"
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription ID"
  sensitive   = true
}

variable "resource_group_name" {
  type        = string
  description = "Base resource group name"
}

variable "keyvault_name" {
  type        = string
  description = "Key Vault name"
}

variable "storage_account_name" {
  type        = string
  description = "Storage account name"
}

variable "eventhubs_namespace" {
  type        = string
  description = "Event Hubs namespace name"
}

variable "databricks_workspace_name" {
  type        = string
  description = "Databricks workspace name"
}

variable "fabric_workspace_name" {
  type        = string
  description = "Fabric workspace name"
}

variable "network_name" {
  type        = string
  default     = "telecom-vnet"
  description = "Virtual network name"
}

variable "subnet_prefixes" {
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  description = "Subnet address prefixes"
}

# Core infrastructure modules

module "core_keyvault" {
  source = "../../modules/core/keyvault"

  name                = var.keyvault_name
  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  tags                = local.common_tags
}

module "core_networking" {
  source = "../../modules/core/networking"

  name                = var.network_name
  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment
  subnet_prefixes     = var.subnet_prefixes
  use_local_dev       = var.use_local_dev
  tags                = local.common_tags
}

module "storage_blob" {
  source = "../../modules/storage/blob"

  name                 = var.storage_account_name
  resource_group_name  = var.resource_group_name
  location             = var.location
  environment          = var.environment
  use_local_dev        = var.use_local_dev
  keyvault_id          = module.core_keyvault.key_vault_id
  tags                 = local.common_tags
}

module "storage_onelake" {
  source = "../../modules/storage/onelake"

  workspace_name      = var.fabric_workspace_name
  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  storage_account_id  = module.storage_blob.storage_account_id
  tags                = local.common_tags
}

module "ingestion_eventhubs" {
  source = "../../modules/ingestion/eventhubs"

  namespace_name      = var.eventhubs_namespace
  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  tags                = local.common_tags
}

module "processing_databricks" {
  source = "../../modules/processing/databricks"

  workspace_name      = var.databricks_workspace_name
  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  keyvault_id         = module.core_keyvault.key_vault_id
  tags                = local.common_tags
}

module "processing_data_factory" {
  source = "../../modules/processing/data-factory"

  name                = "${var.resource_group_name}-adf"
  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  tags                = local.common_tags
}

module "fabric_workspace" {
  source = "../../modules/fabric/workspace"

  workspace_name      = var.fabric_workspace_name
  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment
  capacity_sku        = "F2"
  tags                = local.common_tags
}

# Ephemeral environment support
module "ephemeral_sandbox" {
  source = "../../modules/ephemeral/sandbox"

  count               = var.environment == "ephemeral" ? 1 : 0
  branch_name         = var.branch_name
  resource_group_name = "${var.resource_group_name}-ephemeral"
  location            = var.location
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  tags                = local.common_tags
}

output "keyvault_id" {
  value       = module.core_keyvault.key_vault_id
  description = "Key Vault ID"
}

output "keyvault_endpoint" {
  value       = module.core_keyvault.vault_uri
  description = "Key Vault endpoint URI"
}

output "storage_account_id" {
  value       = module.storage_blob.storage_account_id
  description = "Storage account ID"
}

output "storage_account_name" {
  value       = module.storage_blob.storage_account_name
  description = "Storage account name"
}

output "eventhubs_namespace_id" {
  value       = module.ingestion_eventhubs.namespace_id
  description = "Event Hubs namespace ID"
}

output "eventhubs_namespace_primary_key" {
  value       = module.ingestion_eventhubs.namespace_primary_access_key
  description = "Event Hubs namespace primary access key"
  sensitive   = true
}

output "databricks_workspace_id" {
  value       = module.processing_databricks.workspace_id
  description = "Databricks workspace ID"
}

output "databricks_workspace_url" {
  value       = module.processing_databricks.workspace_url
  description = "Databricks workspace URL"
}

output "fabric_workspace_id" {
  value       = module.fabric_workspace.workspace_id
  description = "Fabric workspace ID"
}

output "resource_group_name" {
  value       = var.resource_group_name
  description = "Resource group name"
}
