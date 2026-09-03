variable "name" {
  type        = string
  description = "Key Vault name"
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
  description = "Environment name (dev, staging, prod)"
}

variable "use_local_dev" {
  type        = bool
  default     = false
  description = "When true, uses local development resources instead of Azure"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}
