variable "workspace_name" {
  type        = string
  description = "Fabric workspace display name"
}

variable "capacity_name" {
  type        = string
  description = "Fabric capacity name (lowercase letters and digits; dashes are stripped)"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for the capacity"
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
  description = "When true, nothing is created (Delta tables are written locally)"
}

variable "capacity_sku" {
  type        = string
  default     = "F2"
  description = "Fabric capacity SKU (F2 is the smallest; pause it when idle)"

  validation {
    condition     = can(regex("^F(2|4|8|16|32|64|128|256|512|1024|2048)$", var.capacity_sku))
    error_message = "capacity_sku must be an F-SKU such as F2, F4 or F64."
  }
}

variable "admin_members" {
  type        = list(string)
  default     = []
  description = "UPNs or object IDs of capacity administrators (Azure requires at least one to deploy)"
}

variable "lakehouse_layers" {
  type        = list(string)
  default     = ["bronze", "silver", "gold"]
  description = "One lakehouse per medallion layer"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply"
}
