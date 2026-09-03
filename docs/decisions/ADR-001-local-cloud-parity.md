# ADR-001: Local-Cloud Parity Strategy

## Status
Accepted

## Context
The platform must support local development without Azure access while maintaining identical behavior to production. Developers need to test code locally before deploying to cloud.

## Decision
Use `var.use_local_dev` boolean to gate all local development resources. Maintain identical Terraform configuration for local and cloud, swapping providers based on environment.

### Implementation
- Local: Docker Compose (Azurite, MinIO, Redpanda, Postgres)
- Cloud: Azure services (Blob, OneLake, Event Hubs, Synapse)
- Configuration: `USE_LOCAL_DEV=true` in .env for local

## Consequences

### Positive
- Developers can work without cloud access
- Identical configuration reduces "works locally" bugs
- Simplifies onboarding
- Enables local debugging

### Negative
- Must maintain dual provider configurations
- Slightly more complex Terraform modules
- Need to test both paths regularly

## Alternatives Considered
1. **Mock services only** - Rejected: Less realistic than local emulators
2. **Cloud-only development** - Rejected: Requires Azure access, expensive for testing
3. **Separate local config** - Rejected: Drifts from production config

## References
- Terraform conditional resource pattern
- Azure Storage Emulator documentation
- Redpanda Kafka compatibility
