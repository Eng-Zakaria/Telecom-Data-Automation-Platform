variable "name" {
  type        = string
  description = "Data Factory name"
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
  description = "When true, skips Data Factory provisioning"
}

variable "storage_connection_string" {
  type        = string
  description = "Storage connection string"
  sensitive   = true
}

variable "keyvault_url" {
  type        = string
  description = "Key Vault URL"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
