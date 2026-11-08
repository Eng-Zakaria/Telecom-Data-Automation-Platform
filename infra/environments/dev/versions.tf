terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.14"
    }
    fabric = {
      source  = "microsoft/fabric"
      version = "~> 1.0"
    }
  }

  # Partial config: CI passes -backend-config="key=<env>.tfstate" plus the state
  # account (see .github/workflows/infra.yml). Local validation uses -backend=false.
  backend "azurerm" {
    use_azuread_auth = true
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
  storage_use_azuread = true
}

provider "fabric" {}
