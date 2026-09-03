output "workspace_id" {
  value       = azurerm_fabric_workspace.main[0].id
  description = "Fabric workspace ID"
}

output "workspace_url" {
  value       = azurerm_fabric_workspace.main[0].web_url
  description = "Fabric workspace URL"
}

output "capacity_id" {
  value       = azurerm_fabric_capacity.main[0].id
  description = "Fabric capacity ID"
}
