variable "name" {
  type        = string
  description = "Storage account name"
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
  description = "When true, uses Azurite instead of Azure Storage"
}

variable "keyvault_id" {
  type        = string
  description = "Key Vault ID for network access"
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
