# Telecom Enterprise Data & Automation Platform

**Production-grade analytics platform for telecom data at enterprise scale.**

## Overview

A multi-domain analytics platform built on **Microsoft Fabric + Azure**, with full **local-to-cloud parity**. The platform ingests and transforms telecom data (CDRs, network KPIs, billing, complaints) through a medallion architecture into shared gold-layer tables that 8 business domains consume.

### Key Features

- **8 Business Domains**: Customer Retention, Revenue Assurance, Network Ops, Marketing, Customer Care, Finance, Roaming, Product Management
- **Medallion Architecture**: Bronze → Silver → Gold Delta Lake tables
- **Local Cloud Parity**: Identical config for local Docker dev and Azure production
- **Production-Grade**: Automated CI/CD, self-healing patterns, schema evolution, PII masking
- **MLOps**: MLflow tracking, drift-triggered retraining, champion/challenger promotion
- **Governance**: Purview lineage, Unity Catalog, key vault secrets

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOURCE SYSTEMS                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │
│  │ Synthetic    │  │ Real Web   │  │ Streaming (Public)   │    │
│  │ CDR Generator│  │ Scraper    │  │ Outage Feeds        │    │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘    │
└─────────┼────────────────┼────────────────────┼───────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   INGESTION LAYER                              │
│  ┌─────────────┐          ┌──────────────────────────────┐     │
│  │ Batch (ADF) │          │ Streaming (Event Hubs/Kafka) │     │
│  └──────┬──────┘          └──────────────┬───────────────┘     │
└─────────┼────────────────────────────────┼─────────────────────┘
          │                                │
          ▼                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   STORAGE (OneLake/Delta Lake)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │
│  │   Bronze    │  │   Silver    │  │      Gold           │    │
│  │ (Raw)       │  │ (Cleaned)   │  │ (Curated)           │    │
│  └─────────────┘  └─────────────┘  └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TRANSFORMATION (dbt + Spark)                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Shared Core Gold Layer                     │   │
│  │  Customer 360 | Network | Billing | Support             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                     │
│          ┌───────────────┼───────────────┐                    │
│          ▼               ▼               ▼                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │
│  │ Domain Marts│ │ Domain Marts│ │ Domain Marts│             │
│  │ (Per-Domain)│ │             │ │             │             │
│  └─────────────┘ └─────────────┘ └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker Desktop (with Kubernetes optional)
- Terraform >= 1.5.0
- Python 3.10+
- Git

### 3-Command Setup

```bash
# 1. Start local development stack
docker-compose up -d

# 2. Initialize Terraform
cd infra && terraform init

# 3. Deploy resources
terraform apply -var-file="environments/dev/dev.tfvars"
```

### Verify Deployment

```bash
# Check local services
docker-compose ps

# Test connections
curl http://localhost:10000  # Azurite
curl http://localhost:9000   # MinIO
rpk cluster info             # Redpanda
```

## Repository Structure

```
telecom-platform/
├── infra/                    # Terraform modules & environments
├── ingestion/                # Data generators (CDR, KPI, billing, etc.)
├── pipelines/                # Fabric pipelines (batch + streaming)
├── transform/
│   └── dbt/                  # dbt models (core + domain marts)
├── ml/                       # ML models with MLflow tracking
├── quality/                  # Great Expectations suites
├── automation/               # ChatOps bot + self-healing patterns
├── ci/                       # GitHub Actions workflows
└── docs/                     # Architecture, ADRs, runbooks
```

## Domains

| Domain | Focus |
|--------|-------|
| **Customer & Retention** | Churn prediction, segmentation, CLV |
| **Revenue Assurance** | Fraud detection, leakage, reconciliation |
| **Network Operations** | KPI monitoring, capacity forecasting |
| **Marketing & Sales** | Campaign performance, propensity |
| **Customer Care** | Sentiment analysis, ticket routing |
| **Finance** | ARPU trending, executive dashboards |
| **Roaming** | Settlement, partner tracking |
| **Product** | Plan performance, bundle optimization |

## Environments

| Environment | Purpose | Scale |
|-------------|---------|-------|
| **Local** | Development | Docker stack |
| **Dev** | Feature development | F2 capacity |
| **Staging** | Pre-production testing | F4 capacity |
| **Prod** | Production | F8 capacity |
| **Ephemeral** | PR testing | Auto-delete after 24h |

## Documentation

- [Architecture Guide](docs/architecture.md)
- [Data Dictionary](docs/data_dictionary.md)
- [Runbook](docs/runbook.md)
- [Architecture Decision Records](docs/decisions/)

## Contributing

1. Create feature branch from `main`
2. Open PR for review
3. Automated testing runs in ephemeral environment
4. Merge triggers promotion to staging

## License

Proprietary - Portfolio Project
