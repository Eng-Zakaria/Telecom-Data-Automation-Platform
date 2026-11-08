variable "name" {
  type        = string
  description = "Key Vault name (3-24 chars, globally unique)"

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]$", var.name))
    error_message = "Key Vault names are 3-24 characters: letters, digits and dashes, starting with a letter."
  }
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
  description = "Environment name (prod enables purge protection and 90-day soft delete)"
}

variable "use_local_dev" {
  type        = bool
  default     = false
  description = "When true, nothing is created (secrets come from environment variables)"
}

variable "network_default_action" {
  type        = string
  default     = "Allow"
  description = "Allow for dev/CI runners; Deny + private endpoint in a hardened prod"

  validation {
    condition     = contains(["Allow", "Deny"], var.network_default_action)
    error_message = "network_default_action must be Allow or Deny."
  }
}

variable "allowed_ip_ranges" {
  type        = list(string)
  default     = []
  description = "CIDRs allowed when network_default_action is Deny"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply"
}
