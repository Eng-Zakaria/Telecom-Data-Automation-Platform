variable "name" {
  type        = string
  description = "Name suffix, e.g. telecom-dev"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "use_local_dev" {
  type        = bool
  default     = false
  description = "When true, nothing is created (use Grafana LGTM from azure-local-lab)"
}

variable "retention_days" {
  type        = number
  default     = 30
  description = "Log retention"
}

variable "daily_quota_gb" {
  type        = number
  default     = 1
  description = "Ingestion cap per day; protects the budget from a log storm"
}

variable "alert_emails" {
  type        = list(string)
  default     = []
  description = "Who gets quality-gate alerts; empty disables alerting"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply"
}
