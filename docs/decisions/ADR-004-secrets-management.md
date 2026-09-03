# ADR-004: Secrets Management Strategy

## Status
Accepted

## Context
Multiple services need access to secrets (connection strings, API keys, tokens). Must prevent secrets from being stored in state files or Git repositories.

## Decision
All secrets come from Azure Key Vault via Terraform data sources. No secrets in state or code.

### Implementation
- Terraform data sources read secrets at apply time
- All sensitive outputs marked with `sensitive = true`
- Managed identities for service-to-service access
- Key Vault access policies grant least-privilege

## Consequences

### Positive
- Secrets never in state files
- Enables secret rotation without code changes
- Centralized secret management
- Audit trail via Key Vault access logs

### Negative
- Terraform plans show "sensitive" until apply
- Need to configure access policies for each service
- More complex initial setup

## Alternatives Considered
1. **Environment variables** - Rejected: Insecure in CI/CD
2. **Secrets in state** - Rejected: Security risk
3. **HashiCorp Vault** - Rejected: Overkill for this scale

## References
- Azure Key Vault best practices
- Terraform sensitive outputs
- Managed identities
