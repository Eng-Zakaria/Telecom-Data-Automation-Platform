variable "name" {
  type        = string
  description = "Virtual network name"
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

variable "subnet_prefixes" {
  type        = list(string)
  description = "Subnet address prefixes"
}

variable "use_local_dev" {
  type        = bool
  default     = false
  description = "When true, skips Azure network resources"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
