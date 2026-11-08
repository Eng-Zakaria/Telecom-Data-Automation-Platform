# These map 1:1 to the env vars cloudkit reads, so a pipeline can run against this
# environment with:  terraform output -json | scripts/tf_outputs_to_env.py > .env.azure

output "CLOUDKIT_MODE" {
  value = "azure"
}

output "AZURE_STORAGE_ACCOUNT" {
  value = module.lake.storage_account_name
}

output "AZURE_EVENTHUBS_NAMESPACE" {
  value = trimsuffix(module.eventhubs.namespace_fqdn, ".servicebus.windows.net")
}

output "AZURE_KEY_VAULT_NAME" {
  value = module.keyvault.key_vault_name
}

output "APPLICATIONINSIGHTS_CONNECTION_STRING" {
  value     = module.observability.connection_string
  sensitive = true
}

output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "databricks_workspace_url" {
  value = var.enable_databricks ? module.databricks[0].workspace_url : ""
}

output "fabric_workspace_id" {
  value = var.enable_fabric ? module.fabric[0].workspace_id : ""
}
