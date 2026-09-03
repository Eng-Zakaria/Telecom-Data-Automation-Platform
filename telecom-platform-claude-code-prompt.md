# Project Brief: Telecom Enterprise Data & Automation Platform

You are acting as a senior data platform engineer building a **production-grade, enterprise-scope** telecom analytics platform for a portfolio project. Treat every deliverable as if it will be reviewed by a hiring panel and run in an on-call rotation. This brief covers the full scope intentionally — it is a multi-phase, long-running build, not a weekend project. Prioritize correctness, maintainability, and defensibility of design decisions over speed. Where a shortcut would compromise "production-grade," call it out explicitly instead of silently taking it.

**Core design principle: build the shared foundation once, then add business domains as modules on top of it.** All 8 domains below read from the same Customer 360 / Network / Billing / Support gold-layer tables. This isn't just scope management — it's how a real telecom data platform is actually architected, and it's a strong thing to be able to explain in an interview.

## 1. Business Scope — All 8 Domains, Full Depth

Each domain must ship: a working data pipeline into the shared gold layer, at least one non-trivial model or aggregation answering its core question, a dashboard/report, and documented business logic (in `docs/domains/<domain>.md`).

1. **Customer & Retention** — churn prediction (30/60/90-day), customer 360 profile, next-best-offer/next-best-action, customer segmentation (usage-based clustering), customer lifetime value modeling.
2. **Revenue Assurance & Fraud** — SIM-box/roaming fraud detection (anomalous call pattern detection), revenue leakage detection, billing anomaly detection, usage-vs-billing reconciliation.
3. **Network Operations & Engineering** — network KPI monitoring (dropped calls, congestion, latency), capacity/congestion forecasting, predictive maintenance (tower/equipment failure prediction from KPI trends), coverage gap analysis correlated with churn.
4. **Marketing & Sales** — campaign performance/attribution, cross-sell/upsell propensity modeling, pricing elasticity analysis, promo/bundle optimization.
5. **Customer Care** — bilingual (Arabic/English) complaint/sentiment analytics, ticket routing and first-contact-resolution analysis, agent performance metrics.
6. **Finance & Executive Reporting** — ARPU/ARPAU trending, revenue forecasting, cost-to-serve analysis, a unified executive KPI dashboard pulling from every domain below it.
7. **Roaming & Partner Settlement** — roaming revenue tracking, partner settlement reconciliation, roaming fraud cross-reference with domain 2.
8. **Product/Plan Management** — plan performance analysis, bundle/dynamic pricing recommendations, plan migration pattern analysis.

## 2. Data Sources

Maximize **real** data wherever it's genuinely obtainable; use synthetic generation only for the pieces that have no legitimate public source (raw CDRs are internal/regulated telecom data — no operator publishes these, so this piece must be synthetic regardless of approach). Document sourcing honestly in `docs/data_dictionary.md` — "real scraped X + synthetic Y modeled on Z standard" is itself a strong engineering story and should be stated plainly, not obscured.

- **CDR (Call Detail Records)** — synthetic (no public source exists): realistic call/SMS/data-session records at scale (millions of rows) — caller/callee hashed IDs, timestamp, duration, cell tower ID, call type, data volume, roaming flag. Base the schema on real CDR field standards (e.g., 3GPP-style CDR fields — research and cite).
- **Network KPI data** — synthetic per-cell-tower time series (signal strength, dropped call rate, congestion %, latency), grounded in real public reference sources: national regulator network-quality reports (e.g., NTRA), OpenCelliD for real cell tower geolocation. Inject realistic degradation patterns in a subset of towers so correlations (churn, fraud, care tickets) are discoverable, not random.
- **Billing/subscription data** — synthetic customer master + billing records (plan type, tenure, monthly charges, payment history, contract type), calibrated against real public telecom pricing/plan structures.
- **Customer support/complaints** — real data via web scraping (respect robots.txt, rate-limit, cache): app store reviews for telecom operator apps, public social media complaints, public regulator complaint databases where available. Bilingual where possible.
- **Roaming/partner data** — synthetic partner network + settlement records, modeled on real GSMA roaming/settlement data standards (research and cite the relevant standard, e.g., TAP/NRTRDE conventions).
- **Marketing/campaign data** — synthetic campaign records (channel, spend, targeting segment, response) — optionally supplement with real public ad-platform benchmark data for realism calibration.
- **Streaming source** — a real public streaming/polling source (e.g., a public network-status or outage-report feed) streamed through the platform in addition to the simulated CDR stream, so the streaming layer isn't purely synthetic.
- **Pluggable source connectors** — source-agnostic ingestion interface so any local/private data source can be swapped in later without touching downstream pipeline code.

## 3. Architecture

**Primary platform: Microsoft Fabric + Azure**, with Databricks and Snowflake used where a real hybrid telecom stack would genuinely use them.

- **Storage**: OneLake (Fabric) as the primary lakehouse, Delta Lake format throughout (bronze/silver/gold medallion).
- **Local dev stack**: Docker Compose with Azurite (Blob-compatible) and/or MinIO (S3-compatible), Kafka/Redpanda for streaming, Postgres for a local source system — the full pipeline is built and tested here before any cloud account is touched.
- **Batch ingestion**: Fabric Data Factory pipelines (Azure Data Factory only if a specific feature requires it — document why).
- **Streaming ingestion**: Fabric Eventstream (or Event Hubs/Kafka if Eventstream can't cover a needed pattern).
- **Transformation**: PySpark notebooks (Fabric/Databricks) for heavy transforms and ML; dbt-core (dbt-fabric/dbt-databricks adapter) for testable SQL business logic across all 8 domains — organize dbt models into per-domain marts on top of shared core models.
- **Warehouse/serving**: Fabric Warehouse as primary; Snowflake as a secondary serving target for a subset of gold tables (document the realistic business rationale for the split, e.g. "finance standardized on Snowflake pre-migration").
- **ML/MLOps**: Databricks with MLflow for experiment tracking and model registry — churn, fraud, network-failure-prediction, propensity, and elasticity models all live here.
- **Orchestration**: Fabric Data Factory pipelines as primary orchestrator; Databricks Workflows for ML-specific pipelines, with the split documented.
- **Governance/catalog**: Microsoft Purview for lineage/cataloging across the estate; Unity Catalog on the Databricks side, with the relationship between the two documented.
- **Secrets**: Azure Key Vault — no credentials in code, ever.
- **IaC**: Terraform for all provisionable Azure resources; Fabric-native items Terraform can't reach are documented as Fabric-CLI-provisioned steps.

## 4. Automation & Operational Excellence (cross-cutting — applies to every domain)

This is a first-class requirement, not a nice-to-have. Build:

- **CI/CD automation**: GitHub Actions running lint, dbt tests, Great Expectations checks, and unit tests on every PR; automatic promotion dev → staging → prod gated strictly on test pass; automatic rollback on failed deploy.
- **Orchestration automation**: full DAG dependency management across ingestion → transform → ML → serving, automatic retries with backoff, automated backfill capability (re-run any historical date range on demand), SLA-based automatic escalation (alert if a pipeline is late, not just if it fails).
- **Infrastructure automation**: Terraform-driven, including ephemeral environment provisioning/teardown for PR-based testing (spin up an isolated environment per PR, tear it down on merge/close).
- **Data quality automation**: automated schema-drift detection that blocks deployment, automated anomaly detection on key metrics that triggers alerts before bad data reaches a dashboard.
- **MLOps automation**: automated retraining triggered by drift detection (not a fixed schedule), automated champion/challenger model evaluation before promoting a new model to production.
- **ChatOps**: a Teams or Slack bot with commands to check pipeline status, trigger a manual run, and approve a staged deployment — this is a strong, concrete automation demo for an interview.
- **Auto-documentation**: dbt docs auto-generated and published on every merge; the data dictionary stays in sync with the actual models rather than drifting out of date.
- **Self-healing patterns**: automated quarantine of bad records to a dead-letter table with automatic reprocessing once the upstream issue is fixed, rather than manual intervention every time.

## 5. Repository Structure

```
telecom-platform/
├── infra/                    # Terraform modules (incl. ephemeral env automation)
├── ingestion/
│   ├── cdr_generator/
│   ├── network_kpi_generator/
│   ├── billing_generator/
│   ├── roaming_partner_generator/
│   ├── campaign_generator/
│   └── complaint_scraper/
├── pipelines/
│   ├── fabric/
│   └── streaming/
├── transform/
│   └── dbt/
│       ├── models/core/           # shared Customer 360 / Network / Billing / Support gold layer
│       └── models/marts/
│           ├── retention/
│           ├── revenue_assurance/
│           ├── network_ops/
│           ├── marketing/
│           ├── customer_care/
│           ├── finance/
│           ├── roaming/
│           └── product/
├── ml/
│   ├── churn_model/
│   ├── fraud_detection/
│   ├── network_failure_prediction/
│   ├── propensity_model/
│   ├── pricing_elasticity/
│   └── mlflow_tracking/
├── quality/                   # Great Expectations suites
├── automation/
│   ├── chatops_bot/
│   └── self_healing/
├── ci/                        # GitHub Actions workflows
└── docs/
    ├── architecture.md
    ├── data_dictionary.md
    ├── runbook.md
    ├── domains/                # one doc per business domain
    └── decisions/              # ADRs
```

## 6. Implementation Phasing

Confirm each phase's definition of done before moving to the next.

- **Phase 0 — Foundations**: repo scaffold, Terraform base infra, local Docker Compose dev stack (Azurite/MinIO, Kafka/Redpanda, Postgres), Key Vault, environment configs, README skeleton.
- **Phase 1 — Core data generation**: CDR, network KPI, billing, roaming/partner, campaign generators; complaint scraper. All write into the local stack first.
- **Phase 2 — Core ingestion**: batch + streaming ingestion into bronze Delta tables, locally validated.
- **Phase 3 — Shared core transformation**: dbt core models building the shared Customer 360 / Network / Billing / Support gold layer that every domain mart reads from.
- **Phase 4 — Data quality, observability & automation foundation**: Great Expectations, logging, alerting, CI/CD pipeline, schema-drift gating, self-healing dead-letter pattern — build the automation layer now, before domain sprawl makes it harder to retrofit.
- **Phase 5 — Domain modules (build in this order, each is a self-contained sub-phase)**:
  - 5a. Customer & Retention
  - 5b. Revenue Assurance & Fraud
  - 5c. Network Operations & Engineering
  - 5d. Customer Care
  - 5e. Marketing & Sales
  - 5f. Roaming & Partner Settlement
  - 5g. Product/Plan Management
  - 5h. Finance & Executive Reporting (built last since it aggregates across all the others)
- **Phase 6 — MLOps automation**: drift-triggered retraining, champion/challenger promotion, applied across the churn/fraud/network-failure/propensity/elasticity models built in Phase 5.
- **Phase 7 — ChatOps**: Slack/Teams bot for pipeline status, manual triggers, deployment approval.
- **Phase 8 — Cloud deployment**: authenticate and deploy via `fab`, `databricks`, and `snow` CLIs — port the proven local pipeline onto Fabric (OneLake, Data Factory/Eventstream), Databricks Workflows, and Snowflake. Document local→cloud parity explicitly.
- **Phase 9 — Governance & security**: Purview lineage, PII masking/classification, ADRs.
- **Phase 10 — Documentation & interview prep**: architecture doc + diagram, runbook, per-domain docs, and `docs/interview_narrative.md` covering the platform-vs-domain-module architecture decision, the local→cloud parity approach, and what you'd change at 10x scale.

## 7. Non-Negotiable "Production-Grade" Checklist

- [ ] No hardcoded credentials anywhere
- [ ] Every pipeline has a documented failure mode and alerts rather than failing silently
- [ ] Idempotent writes everywhere
- [ ] Schema evolution handled explicitly
- [ ] PII classified and masked before reaching any reporting layer
- [ ] Every domain mart reads from the shared core gold layer — no domain re-implements its own customer/network/billing logic
- [ ] CI/CD gates every deploy on passing tests, with automatic rollback on failure
- [ ] At least one genuine self-healing pattern is implemented, not just described
- [ ] Every non-obvious architectural choice has a short ADR
- [ ] README lets a stranger understand the system in under 5 minutes

## 8. What I want from you (Claude Code) right now

Start with **Phase 0**. Given the full scope above, first give me a realistic time/effort estimate per phase so I can plan this as a proper multi-milestone build rather than underestimating it. Then propose the Terraform module layout and repo scaffold, confirm the Azure/Fabric resources needed, and ask any clarifying questions about scale targets before generating code. Proceed phase by phase, pausing for confirmation at the end of each.
