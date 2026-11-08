# One composition for every environment. Environments differ only in the inputs
# (size, cost flags, alerting), never in structure, so dev/staging/prod cannot drift.

terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
    fabric  = { source = "microsoft/fabric" }
  }
}

locals {
  base = "telecom-${var.environment}${var.name_suffix == "" ? "" : "-${var.name_suffix}"}"
  # Globally unique, lowercase, <= 24 chars: st<env><suffix><hash>
  compact = substr(replace(lower("${var.environment}${var.name_suffix}"), "/[^a-z0-9]/", ""), 0, 10)
  unique  = substr(sha1("${var.subscription_scope}-${local.base}"), 0, 6)
  tags = merge(var.tags, {
    project     = "telecom-platform"
    environment = var.environment
    managed_by  = "terraform"
  })
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.base}"
  location = var.location
  tags     = local.tags
}

module "lake" {
  source              = "../storage/blob"
  name                = "sttel${local.compact}${local.unique}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  replication_type    = var.environment == "prod" ? "ZRS" : "LRS"
  tags                = local.tags
}

module "keyvault" {
  source              = "../core/keyvault"
  name                = "kv-tel-${local.compact}${local.unique}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  tags                = local.tags
}

module "eventhubs" {
  source               = "../ingestion/eventhubs"
  namespace_name       = "evhns-${local.base}-${local.unique}"
  resource_group_name  = azurerm_resource_group.main.name
  location             = var.location
  environment          = var.environment
  throughput_units     = var.eventhubs_throughput_units
  max_throughput_units = var.eventhubs_max_throughput_units
  tags                 = local.tags
}

module "observability" {
  source              = "../observability"
  name                = local.base
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  retention_days      = var.environment == "prod" ? 90 : 30
  daily_quota_gb      = var.environment == "prod" ? 5 : 1
  alert_emails        = var.alert_emails
  tags                = local.tags
}

module "data_factory" {
  source               = "../processing/data-factory"
  count                = var.enable_data_factory ? 1 : 0
  name                 = "adf-${local.base}-${local.unique}"
  resource_group_name  = azurerm_resource_group.main.name
  location             = var.location
  environment          = var.environment
  storage_account_id   = module.lake.storage_account_id
  storage_dfs_endpoint = module.lake.dfs_endpoint
  key_vault_id         = module.keyvault.key_vault_id
  tags                 = local.tags
}

module "databricks" {
  source              = "../processing/databricks"
  count               = var.enable_databricks ? 1 : 0
  workspace_name      = "dbw-${local.base}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  storage_account_id  = module.lake.storage_account_id
  tags                = local.tags
}

module "fabric" {
  source              = "../fabric/workspace"
  count               = var.enable_fabric ? 1 : 0
  workspace_name      = "ws-${local.base}"
  capacity_name       = "fc${local.compact}${local.unique}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  capacity_sku        = var.fabric_capacity_sku
  admin_members       = var.fabric_admin_members
  tags                = local.tags
}

# Data-plane access for the identities that run pipelines (CI principal, a
# Container Apps job identity, your own user for local-against-cloud runs).
locals {
  grants = merge([
    for pid in var.pipeline_principal_ids : {
      "${pid}/lake" = { principal = pid, scope = module.lake.storage_account_id, role = "Storage Blob Data Contributor" }
      "${pid}/evh"  = { principal = pid, scope = module.eventhubs.namespace_id, role = "Azure Event Hubs Data Owner" }
      "${pid}/kv"   = { principal = pid, scope = module.keyvault.key_vault_id, role = "Key Vault Secrets User" }
    }
  ]...)
}

resource "azurerm_role_assignment" "pipeline" {
  for_each             = local.grants
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = each.value.principal
}
