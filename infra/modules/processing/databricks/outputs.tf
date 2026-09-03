output "workspace_id" {
  value       = azurerm_databricks_workspace.main[0].id
  description = "Databricks workspace ID"
}

output "workspace_url" {
  value       = azurerm_databricks_workspace.main[0].workspace_url
  description = "Databricks workspace URL"
}

output "workspace_fqid" {
  value       = azurerm_databricks_workspace.main[0].fqdn
  description = "Databricks workspace FQDN"
}
