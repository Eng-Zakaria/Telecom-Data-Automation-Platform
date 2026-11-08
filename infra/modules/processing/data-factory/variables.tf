variable "name" {
  type        = string
  description = "Data Factory name (globally unique)"
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
  description = "When true, nothing is created (pipelines run locally)"
}

variable "storage_account_id" {
  type        = string
  description = "Lake storage account ID (scope of the Blob Data Contributor grant)"
}

variable "storage_dfs_endpoint" {
  type        = string
  description = "ADLS Gen2 DFS endpoint, e.g. https://<account>.dfs.core.windows.net"
}

variable "key_vault_id" {
  type        = string
  description = "Key Vault ID for the linked service and secret-read grant"
}

variable "git_repository" {
  type = object({
    account_name    = string
    repository_name = string
    branch_name     = string
    root_folder     = string
  })
  default     = null
  description = "Optional GitHub integration for ADF authoring (dev only; promote via ARM export in CI)"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply"
}
