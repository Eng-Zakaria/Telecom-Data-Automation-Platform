# ADLS Gen2 lake: hierarchical namespace, Entra ID only (shared keys disabled),
# one container per medallion layer plus a quarantine zone for rejected records.
# Local twin: Azurite in azure-local-lab, same containers, same SDK.

resource "azurerm_storage_account" "main" {
  count                           = var.use_local_dev ? 0 : 1
  name                            = var.name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_kind                    = "StorageV2"
  account_replication_type        = var.replication_type
  is_hns_enabled                  = true
  https_traffic_only_enabled      = true
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  local_user_enabled              = false # no SFTP/local users: Entra ID only
  allow_nested_items_to_be_public = false
  default_to_oauth_authentication = true

  blob_properties {
    delete_retention_policy {
      days = var.soft_delete_days
    }
    container_delete_retention_policy {
      days = var.soft_delete_days
    }
  }

  tags = var.tags
}

resource "azurerm_storage_container" "layer" {
  for_each              = var.use_local_dev ? toset([]) : toset(var.containers)
  name                  = each.key
  storage_account_id    = azurerm_storage_account.main[0].id
  container_access_type = "private"
}

# Bronze is cheap to re-derive from sources; move it to Cool after 30 days.
resource "azurerm_storage_management_policy" "lifecycle" {
  count              = var.use_local_dev ? 0 : 1
  storage_account_id = azurerm_storage_account.main[0].id

  rule {
    name    = "bronze-to-cool"
    enabled = true
    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["bronze/"]
    }
    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than = 30
      }
    }
  }

  rule {
    name    = "expire-quarantine"
    enabled = true
    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["quarantine/"]
    }
    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = 90
      }
    }
  }
}

output "storage_account_id" {
  value       = var.use_local_dev ? "" : azurerm_storage_account.main[0].id
  description = "Storage account ID"
}

output "storage_account_name" {
  value       = var.use_local_dev ? "devstoreaccount1" : azurerm_storage_account.main[0].name
  description = "Storage account name (cloudkit: AZURE_STORAGE_ACCOUNT)"
}

output "dfs_endpoint" {
  value       = var.use_local_dev ? "http://localhost:10000/devstoreaccount1" : azurerm_storage_account.main[0].primary_dfs_endpoint
  description = "ADLS Gen2 DFS endpoint"
}

output "blob_endpoint" {
  value       = var.use_local_dev ? "http://localhost:10000/devstoreaccount1" : azurerm_storage_account.main[0].primary_blob_endpoint
  description = "Blob endpoint"
}
