variable "environment" {
  type    = string
  default = "ephemeral"
}

variable "resource_group_name" {
  type    = string
  default = "rg-telecom-ephemeral"
}

variable "branch_name" {
  type        = string
  description = "Git branch name for this ephemeral environment"
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

variable "auto_delete_after" {
  type    = string
  default = "24h"
}

locals {
  common_tags = {
    Project     = "telecom-platform"
    Environment = var.environment
    ManagedBy   = "terraform"
    Branch      = var.branch_name
  }
}

terraform {
  backend "azurerm" {
    resource_group_name  = "rg-telecom-state"
    storage_account_name = "sttelecomstate001"
    container_name       = "terraform-state"
    key                  = "ephemeral/${var.branch_name}/terraform.tfstate"
  }
}

module "ephemeral_sandbox" {
  source = "../../modules/ephemeral/sandbox"

  branch_name         = var.branch_name
  resource_group_name = var.resource_group_name
  location            = "eastus2"
  environment         = var.environment
  use_local_dev       = var.use_local_dev
  auto_delete         = true
  auto_delete_after   = var.auto_delete_after
  tags                = local.common_tags
}

output "resource_group_id" {
  value       = module.ephemeral_sandbox.resource_group_id
  description = "Ephemeral resource group ID"
}

output "resource_group_name" {
  value       = module.ephemeral_sandbox.resource_group_name
  description = "Ephemeral resource group name"
}
