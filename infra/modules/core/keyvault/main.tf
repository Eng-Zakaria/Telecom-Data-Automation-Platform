# Key Vault in RBAC mode. The platform is keyless (Entra ID everywhere), so the vault
# holds only genuinely external secrets (partner API tokens, SMTP, etc.).
# Local twin: environment variables read through cloudkit.get_secret().

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  count                         = var.use_local_dev ? 0 : 1
  name                          = var.name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  soft_delete_retention_days    = var.environment == "prod" ? 90 : 7
  purge_protection_enabled      = var.environment == "prod"
  public_network_access_enabled = true

  network_acls {
    default_action = var.network_default_action
    bypass         = "AzureServices"
    ip_rules       = var.allowed_ip_ranges
  }

  tags = var.tags
}

# The identity running Terraform (CI service principal or you) manages secrets.
resource "azurerm_role_assignment" "deployer_secrets_officer" {
  count                = var.use_local_dev ? 0 : 1
  scope                = azurerm_key_vault.main[0].id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

output "key_vault_id" {
  value       = var.use_local_dev ? "" : azurerm_key_vault.main[0].id
  description = "Key Vault resource ID"
}

output "key_vault_name" {
  value       = var.use_local_dev ? "" : azurerm_key_vault.main[0].name
  description = "Key Vault name (cloudkit: AZURE_KEY_VAULT_NAME)"
}

output "vault_uri" {
  value       = var.use_local_dev ? "" : azurerm_key_vault.main[0].vault_uri
  description = "Key Vault URI"
}
