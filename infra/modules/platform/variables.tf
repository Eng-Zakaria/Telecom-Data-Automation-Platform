variable "environment" {
  type        = string
  description = "dev, staging, prod or ephemeral"

  validation {
    condition     = contains(["dev", "staging", "prod", "ephemeral"], var.environment)
    error_message = "environment must be dev, staging, prod or ephemeral."
  }
}

variable "name_suffix" {
  type        = string
  default     = ""
  description = "Extra name part, e.g. pr123 for ephemeral environments"
}

variable "subscription_scope" {
  type        = string
  default     = ""
  description = "Mixed into the name hash so the same env in two subscriptions gets unique names"
}

variable "location" {
  type        = string
  default     = "westeurope"
  description = "Azure region"
}

variable "enable_data_factory" {
  type        = bool
  default     = false
  description = "ADF (pay per activity run, ~0 idle)"
}

variable "enable_databricks" {
  type        = bool
  default     = false
  description = "Databricks workspace (no idle cost; clusters bill when running)"
}

variable "enable_fabric" {
  type        = bool
  default     = false
  description = "Fabric capacity (bills per second while running; pause it when idle)"
}

variable "fabric_capacity_sku" {
  type        = string
  default     = "F2"
  description = "Fabric capacity SKU"
}

variable "fabric_admin_members" {
  type        = list(string)
  default     = []
  description = "Fabric capacity admins (UPNs); required when enable_fabric is true"
}

variable "eventhubs_throughput_units" {
  type        = number
  default     = 1
  description = "Event Hubs baseline throughput units"
}

variable "eventhubs_max_throughput_units" {
  type        = number
  default     = 0
  description = "Auto-inflate ceiling (0 = off)"
}

variable "pipeline_principal_ids" {
  type        = list(string)
  default     = []
  description = "Object IDs that get data-plane access to lake, Event Hubs and Key Vault"
}

variable "alert_emails" {
  type        = list(string)
  default     = []
  description = "Quality-gate alert recipients"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Extra tags"
}
