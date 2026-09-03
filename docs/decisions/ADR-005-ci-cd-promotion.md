# ADR-005: CI/CD Promotion Strategy

## Status
Accepted

## Context
Need automated promotion from dev → staging → prod with quality gates. Must prevent bad code from reaching production.

## Decision
Automatic promotion gated strictly on test pass. Automatic rollback on failure.

### Flow
```
PR → Ephemeral env → Tests pass → Merge → Dev → Staging tests → Prod
                                                              ↓
                                              Rollback on failure
```

## Consequences

### Positive
- Prevents bad code from reaching production
- Reduces manual intervention
- Enables rapid iteration
- Production reliability

### Negative
- Need comprehensive test suite
- Automated rollback complexity
- Monitoring and alerting required
- Initial setup overhead

## Alternatives Considered
1. **Manual promotion** - Rejected: Too slow, error-prone
2. **Continuous deployment** - Rejected: Too risky without staging
3. **Approval gates only** - Rejected: Slows development

## References
- GitHub Actions workflows
- Terraform state management
- Azure Deployments
