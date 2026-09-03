resource "azurerm_virtual_network" "main" {
  count               = var.use_local_dev ? 0 : 1
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  address_space       = ["10.0.0.0/16"]

  tags = var.tags
}

resource "azurerm_subnet" "storage" {
  count                 = var.use_local_dev ? 0 : 1
  name                   = "subnet-storage"
  resource_group_name    = var.resource_group_name
  virtual_network_name   = azurerm_virtual_network.main[0].name
  address_prefixes       = [var.subnet_prefixes[0]]
  service_endpoints      = ["Microsoft.Storage"]
}

resource "azurerm_subnet" "processing" {
  count                 = var.use_local_dev ? 0 : 1
  name                   = "subnet-processing"
  resource_group_name    = var.resource_group_name
  virtual_network_name   = azurerm_virtual_network.main[0].name
  address_prefixes       = [var.subnet_prefixes[1]]
  service_endpoints      = ["Microsoft.Storage", "Microsoft.KeyVault"]
}

resource "azurerm_subnet" "ingestion" {
  count                 = var.use_local_dev ? 0 : 1
  name                   = "subnet-ingestion"
  resource_group_name    = var.resource_group_name
  virtual_network_name   = azurerm_virtual_network.main[0].name
  address_prefixes       = [var.subnet_prefixes[2]]
  service_endpoints      = ["Microsoft.KeyVault"]
}

resource "azurerm_private_dns_zone" "storage" {
  count               = var.use_local_dev ? 0 : 1
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone_virtual_network_link" "storage" {
  count               = var.use_local_dev ? 0 : 1
  name                  = "dns-link-storage"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.storage[0].name
  virtual_network_id    = azurerm_virtual_network.main[0].id
}

output "virtual_network_id" {
  value       = var.use_local_dev ? "" : azurerm_virtual_network.main[0].id
  description = "Virtual network ID"
}

output "subnet_ids" {
  value = {
    storage   = var.use_local_dev ? "" : azurerm_subnet.storage[0].id
    processing = var.use_local_dev ? "" : azurerm_subnet.processing[0].id
    ingestion  = var.use_local_dev ? "" : azurerm_subnet.ingestion[0].id
  }
  description = "Subnet IDs by function"
}
