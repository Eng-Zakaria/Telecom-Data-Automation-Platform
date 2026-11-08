# Event Hubs namespace + one hub per streaming source.
# Standard tier: Kafka endpoint on :9093, max 7 days retention, consumer groups per hub.
# Local twin: the Event Hubs emulator in azure-local-lab (same SDK, same Kafka protocol).

locals {
  hubs = var.use_local_dev ? {} : var.hubs
  consumer_groups = merge([
    for hub, cfg in local.hubs : {
      for cg in cfg.consumer_groups : "${hub}/${cg}" => { hub = hub, name = cg }
    }
  ]...)
}

resource "azurerm_eventhub_namespace" "main" {
  count                         = var.use_local_dev ? 0 : 1
  name                          = var.namespace_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = "Standard"
  capacity                      = var.throughput_units
  auto_inflate_enabled          = var.max_throughput_units > var.throughput_units
  maximum_throughput_units      = var.max_throughput_units > var.throughput_units ? var.max_throughput_units : null
  local_authentication_enabled  = false # Entra ID (RBAC) only: no SAS keys to leak
  public_network_access_enabled = true
  minimum_tls_version           = "1.2"

  tags = var.tags
}

resource "azurerm_eventhub" "hub" {
  for_each          = local.hubs
  name              = each.key
  namespace_id      = azurerm_eventhub_namespace.main[0].id
  partition_count   = each.value.partitions
  message_retention = each.value.retention_days
}

resource "azurerm_eventhub_consumer_group" "cg" {
  for_each            = local.consumer_groups
  name                = each.value.name
  namespace_name      = azurerm_eventhub_namespace.main[0].name
  eventhub_name       = azurerm_eventhub.hub[each.value.hub].name
  resource_group_name = var.resource_group_name
}

output "namespace_id" {
  value       = var.use_local_dev ? "" : azurerm_eventhub_namespace.main[0].id
  description = "Event Hubs namespace ID (scope for RBAC role assignments)"
}

output "namespace_fqdn" {
  value       = var.use_local_dev ? "localhost:5672" : "${azurerm_eventhub_namespace.main[0].name}.servicebus.windows.net"
  description = "Fully qualified namespace for SDK clients (cloudkit: AZURE_EVENTHUBS_NAMESPACE)"
}

output "kafka_bootstrap" {
  value       = var.use_local_dev ? "localhost:9092" : "${azurerm_eventhub_namespace.main[0].name}.servicebus.windows.net:9093"
  description = "Kafka bootstrap servers"
}

output "hub_names" {
  value       = keys(local.hubs)
  description = "Provisioned event hubs"
}
