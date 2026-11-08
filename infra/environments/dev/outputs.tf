output "cloudkit_env" {
  description = "Env vars for running pipelines against this environment"
  value = {
    CLOUDKIT_MODE             = module.platform.CLOUDKIT_MODE
    AZURE_STORAGE_ACCOUNT     = module.platform.AZURE_STORAGE_ACCOUNT
    AZURE_EVENTHUBS_NAMESPACE = module.platform.AZURE_EVENTHUBS_NAMESPACE
    AZURE_KEY_VAULT_NAME      = module.platform.AZURE_KEY_VAULT_NAME
  }
}

output "appinsights_connection_string" {
  value     = module.platform.APPLICATIONINSIGHTS_CONNECTION_STRING
  sensitive = true
}

output "resource_group_name" {
  value = module.platform.resource_group_name
}
