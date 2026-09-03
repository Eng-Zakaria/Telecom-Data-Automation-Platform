# Architecture Guide

## System Design

### Core Principle: Build Once, Module Always

All 8 business domains read from the same shared gold-layer tables. This isn't just scope management — it's how real telecom platforms are architected.

### Data Flow

```
Sources → Ingestion → Bronze → Silver → Gold → Domain Marts
```

1. **Bronze**: Raw ingested data (immutable)
2. **Silver**: Cleaned, validated, PII-masked
3. **Gold**: Curated, business-level constructs
4. **Domain Marts**: Domain-specific aggregations

### Azure Resource Map

| Component | Azure Service | Local Alternative |
|-----------|---------------|-------------------|
| Storage | Azure Blob + OneLake | Azurite + MinIO |
| Streaming | Event Hubs | Redpanda (Kafka-compatible) |
| Processing | Synapse/Databricks | Docker containers |
| Orchestration | Data Factory | Airflow/Makefile |
| ML | Databricks + MLflow | Local MLflow |
| Warehouse | Fabric Warehouse | Snowflake (dev) |
| Governance | Purview | dbt docs |

## Security Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                     INTERNET                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────┐
│              Public Subnet (DMZ)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │  API Gateway │  │  Web Apps   │  │  Load Balancer   │    │
│  └─────────────┘  └─────────────┘  └──────────────────┘    │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────┐
│              Private Subnets                                │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │  Ingestion  │  │  Processing │  │    Storage       │    │
│  │  (Event     │  │  (Spark)    │  │   (OneLake)      │    │
│  │   Hubs)     │  │             │  │                  │    │
│  └─────────────┘  └─────────────┘  └──────────────────┘    │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────┐
│              Data Plane                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │   Key Vault │  │  Purview    │  │  Monitoring      │    │
│  │             │  │             │  │  (Log Analytics) │    │
│  └─────────────┘  └─────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Failure Modes & Alerts

| Failure | Alert Mechanism | Recovery |
|---------|----------------|----------|
| Pipeline failure | Logic App → Teams | Auto-retry (3x) → Dead-letter |
| Schema drift | Great Expectations → Alert | Block deployment + notify |
| Data quality drop | Anomaly detection → Alert | Quarantine → Investigate |
| Capacity limit | Azure Monitor → Alert | Scale up or backfill |
| Secret rotation | Key Vault alert → Auto | Rotate + update policies |

## Key Design Decisions

### 1. Medallion Architecture
**Why**: Immutable bronze layer enables reproducibility and auditing. Gold layer ensures single source of truth.

### 2. Local-Cloud Parity
**Why**: Develop without cloud access, test in realistic environments, prevent "works locally" issues.

### 3. Ephemeral Environments
**Why**: PR-based testing, cost optimization, faster iteration.

### 4. Separation of Terraform and Fabric CLI
**Why**: Clear boundaries, industry-standard IaC, Fabric-specific features via CLI.

### 5. Key Vault for All Secrets
**Why**: Centralized management, rotation capability, no hardcoded credentials.
