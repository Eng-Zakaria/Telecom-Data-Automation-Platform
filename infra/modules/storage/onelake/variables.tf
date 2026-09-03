variable "workspace_name" {
  type        = string
  description = "Fabric workspace name"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "environment" {
  type        = string
  description = "Environment name"
}

variable "use_local_dev" {
  type        = bool
  default     = false
  description = "When true, skips Fabric provisioning"
}

variable "capacity_sku" {
  type        = string
  default     = "F2"
  description = "Fabric capacity SKU (F2, F4, etc.)"
}

variable "storage_account_id" {
  type        = string
  description = "Storage account ID for OneLake"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
