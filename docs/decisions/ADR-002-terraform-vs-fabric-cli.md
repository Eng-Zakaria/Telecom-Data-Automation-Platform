# ADR-002: Terraform vs Fabric CLI Provisioning

## Status
Accepted

## Context
Fabric provides CLI tools for workspace and lakehouse management, but lacks infrastructure-as-code capabilities for networking, security, and other Azure resources.

## Decision
Use Terraform for all provisionable Azure resources; use Fabric CLI only for Fabric-native items (workspaces, lakehouses, semantic models).

### Boundary
**Terraform provisions:**
- Key Vault
- Storage accounts
- Event Hubs
- Data Factory
- Networking
- Managed identities
- Access policies

**Fabric CLI provisions:**
- Workspaces
- Lakehouses
- Datasets
- Semantic models
- Reports

## Consequences

### Positive
- Industry-standard IaC (Terraform)
- Supports ephemeral environments and CI/CD
- Clear separation of concerns
- Matches real-world telecom platform architecture

### Negative
- Need to document Fabric CLI steps separately
- Some manual steps required for Fabric resources
- Two tooling paradigms to learn

## Alternatives Considered
1. **Terraform provider for Fabric** - Not yet stable
2. **Fabric CLI only** - Lacks IaC features
3. **Azure Bicep** - Less mature than Terraform

## References
- Terraform AzureRM provider
- Fabric CLI documentation
