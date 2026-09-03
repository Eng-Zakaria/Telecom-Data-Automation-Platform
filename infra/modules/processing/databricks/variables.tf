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
  description = "When true, skips Databricks provisioning"
}

variable "keyvault_id" {
  type        = string
  description = "Key Vault ID for secret access"
  default     = ""
}

variable "vnet_id" {
  type        = string
  description = "Virtual network ID for private networking"
  default     = ""
}

variable "processing_subnet_id" {
  type        = string
  description = "Subnet ID for processing resources"
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
