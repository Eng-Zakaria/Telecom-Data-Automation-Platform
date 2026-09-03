variable "branch_name" {
  type        = string
  description = "Git branch name for this ephemeral environment"
}

variable "resource_group_name" {
  type        = string
  description = "Base resource group name"
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
  description = "When true, uses local resources instead of Azure"
}

variable "protect_from_deletion" {
  type        = bool
  default     = false
  description = "Whether to prevent manual deletion of the environment"
}

variable "auto_delete" {
  type        = bool
  default     = true
  description = "Whether to automatically delete after a period"
}

variable "auto_delete_after" {
  type        = string
  default     = "24h"
  description = "Duration before auto-deletion (e.g., 24h, 7d)"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
