# Microsoft Fabric: an F-SKU capacity (ARM, azurerm) plus a workspace on it and one
# lakehouse per medallion layer (Fabric REST, microsoft/fabric provider).
# Pause the capacity when idle: billing is per second while it runs.
# Local twin: Delta tables written by pipelines/run_local.py (deltalake engine).

terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
    fabric  = { source = "microsoft/fabric" }
  }
}

resource "azurerm_fabric_capacity" "main" {
  count                  = var.use_local_dev ? 0 : 1
  name                   = replace(lower(var.capacity_name), "-", "")
  resource_group_name    = var.resource_group_name
  location               = var.location
  administration_members = var.admin_members

  sku {
    name = var.capacity_sku
    tier = "Fabric"
  }

  tags = var.tags
}

# The Fabric API identifies capacities by their Fabric GUID, not the ARM ID.
data "fabric_capacity" "main" {
  count        = var.use_local_dev ? 0 : 1
  display_name = azurerm_fabric_capacity.main[0].name
}

resource "fabric_workspace" "main" {
  count        = var.use_local_dev ? 0 : 1
  display_name = var.workspace_name
  description  = "Telecom data platform (${var.environment})"
  capacity_id  = data.fabric_capacity.main[0].id
}

resource "fabric_lakehouse" "layer" {
  for_each     = var.use_local_dev ? toset([]) : toset(var.lakehouse_layers)
  display_name = "lh_${each.key}"
  workspace_id = fabric_workspace.main[0].id

  configuration = {
    enable_schemas = true
  }
}

output "capacity_id" {
  value       = var.use_local_dev ? "" : azurerm_fabric_capacity.main[0].id
  description = "Fabric capacity ARM ID"
}

output "workspace_id" {
  value       = var.use_local_dev ? "" : fabric_workspace.main[0].id
  description = "Fabric workspace ID"
}

output "lakehouse_ids" {
  value       = { for k, v in fabric_lakehouse.layer : k => v.id }
  description = "Lakehouse ID per medallion layer"
}
