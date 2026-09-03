# Key Vault Module

Manages Azure Key Vault for secure secret storage.

## Features
- Soft delete enabled (90 days)
- Purge protection enabled
- RBAC authorization
- Network ACLs (deny by default)
- Connection strings and tokens stored as secrets

## Usage

```hcl
module "keyvault" {
  source = "./modules/core/keyvault"

  name                = "kv-telecom-dev"
  resource_group_name = "rg-telecom-dev"
  location            = "eastus2"
  environment         = "dev"
  use_local_dev       = false
  tags                = local.common_tags
}
```

## Secrets Created
- `storage-connection-string` - Azure Blob Storage connection string
- `eventhubs-primary-key` - Event Hubs namespace primary key
- `databricks-access-token` - Databricks access token

## Outputs
- `key_vault_id` - Resource ID
- `vault_uri` - URI for REST API access
- `storage_connection_string` - Blob storage connection string
- `eventhubs_primary_key` - Event Hubs access key
