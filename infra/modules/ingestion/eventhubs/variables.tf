variable "namespace_name" {
  type        = string
  description = "Event Hubs namespace name (globally unique)"
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
  description = "When true, nothing is created (use the azure-local-lab Event Hubs emulator)"
}

variable "throughput_units" {
  type        = number
  default     = 1
  description = "Baseline throughput units"
}

variable "max_throughput_units" {
  type        = number
  default     = 0
  description = "Auto-inflate ceiling; 0 disables auto-inflate"
}

variable "hubs" {
  type = map(object({
    partitions      = number
    retention_days  = number
    consumer_groups = list(string)
  }))
  description = "Event hubs to create, keyed by name"
  default = {
    "cdr-stream"         = { partitions = 4, retention_days = 7, consumer_groups = ["bronze-writer", "fraud-scorer"] }
    "network-kpi-stream" = { partitions = 4, retention_days = 7, consumer_groups = ["bronze-writer", "noc-alerts"] }
    "billing-stream"     = { partitions = 2, retention_days = 7, consumer_groups = ["bronze-writer"] }
  }

  validation {
    condition     = alltrue([for h in values(var.hubs) : h.retention_days >= 1 && h.retention_days <= 7])
    error_message = "Standard tier retention must be 1-7 days (use Capture to ADLS for longer history)."
  }

  validation {
    condition     = alltrue([for h in values(var.hubs) : h.partitions >= 1 && h.partitions <= 32])
    error_message = "Standard tier allows 1-32 partitions per hub."
  }
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply"
}
