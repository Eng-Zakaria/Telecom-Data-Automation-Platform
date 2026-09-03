# ADR-003: Ephemeral Environment Strategy

## Status
Accepted

## Context
Need to support PR-based testing without affecting shared environments. Current approach requires manual environment setup for each feature branch.

## Decision
Implement per-PR ephemeral environment provisioning with automatic cleanup after 24 hours.

### Implementation
- Branch-prefixed resource names: `rg-ephemeral-{branch}`
- Auto-delete tags on all resources
- GitHub Actions triggers on PR open/close
- Lightweight state index tracks active ephemeral environments

## Consequences

### Positive
- PR-based testing without affecting shared environments
- Reduced cloud costs (auto-deletion)
- Encourages smaller, frequent PRs
- Matches GitHub Actions workflows

### Negative
- State management complexity
- Resource naming constraints
- Need cleanup policies
- Potential for orphaned resources if cleanup fails

## Alternatives Considered
1. **Shared dev environment** - Rejected: Conflicts between developers
2. **Permanent preview environments** - Rejected: Cost prohibitive
3. **No isolation** - Rejected: Risk of breaking shared state

## References
- Terraform Cloud workspaces
- GitHub Actions environments
