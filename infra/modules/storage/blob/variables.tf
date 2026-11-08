variable "name" {
  type        = string
  description = "Storage account name (3-24 lowercase letters/digits, globally unique)"

  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.name))
    error_message = "Storage account names are 3-24 lowercase letters and digits."
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
  description = "Environment name"
}

variable "use_local_dev" {
  type        = bool
  default     = false
  description = "When true, nothing is created (use Azurite)"
}

variable "replication_type" {
  type        = string
  default     = "LRS"
  description = "LRS for dev; ZRS or GZRS for prod"
}

variable "containers" {
  type        = list(string)
  default     = ["bronze", "silver", "gold", "quarantine"]
  description = "Lake containers"
}

variable "soft_delete_days" {
  type        = number
  default     = 7
  description = "Blob and container soft-delete retention"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply"
}
