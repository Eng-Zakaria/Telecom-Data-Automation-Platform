variable "namespace_name" {
  type        = string
  description = "Event Hubs namespace name"
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
  description = "When true, uses Redpanda instead of Event Hubs"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
