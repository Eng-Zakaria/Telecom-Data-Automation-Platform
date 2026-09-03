output "data_factory_id" {
  value       = azurerm_data_factory.main[0].id
  description = "Data Factory ID"
}

output "data_factory_url" {
  value       = azurerm_data_factory.main[0].url
  description = "Data Factory URL"
}
