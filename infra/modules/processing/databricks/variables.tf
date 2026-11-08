variable "workspace_name" {
  type        = string
  description = "Databricks workspace name"
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
  description = "When true, nothing is created (use local PySpark/Delta)"
}

variable "storage_account_id" {
  type        = string
  description = "Lake storage account ID that Unity Catalog reads and writes"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply"
}
