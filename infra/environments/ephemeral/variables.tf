variable "pipeline_principal_ids" {
  type        = list(string)
  default     = []
  description = "Object IDs granted data-plane access (CI principal, job identities)"
}

variable "alert_emails" {
  type        = list(string)
  default     = []
  description = "Quality-gate alert recipients"
}

variable "fabric_admin_members" {
  type        = list(string)
  default     = []
  description = "Fabric capacity admins (required when Fabric is enabled)"
}

variable "pr_number" {
  type        = string
  description = "Pull request number; names the environment and its state key"

  validation {
    condition     = can(regex("^[0-9]+$", var.pr_number))
    error_message = "pr_number must be digits only."
  }
}
