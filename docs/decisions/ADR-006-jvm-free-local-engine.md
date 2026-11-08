# ADR-006: JVM-free local engine (deltalake + DuckDB), Spark optional

**Status:** accepted, 2026-11-08

## Context
The original pipelines (`pipelines/bronze|silver`) were PySpark + delta-spark. Running them
locally needs a JVM, Spark and Hadoop Azure jars, and nobody had ever run them: there was no
dependency manifest and the CI referenced requirements files that did not exist. A pipeline
that cannot be run on a laptop in minutes is not reviewable, testable or demoable.

## Decision
The runnable pipeline (`lakehouse/`) uses:
- **deltalake** (delta-rs, Rust) to read/write Delta tables directly in Azurite or ADLS Gen2.
  The tables are standard Delta: Databricks, Fabric and Synapse read them unchanged.
- **DuckDB** for gold transformations (SQL over Arrow, in-process).
- **pandas** for data contracts, so contract logic is engine-agnostic and unit-testable.

Spark stays available as an optional extra (`uv sync --extra spark`), and Terraform can
provision Databricks and Fabric (`enable_databricks`, `enable_fabric`) for volumes that need it.

## Consequences
- The full pipeline runs in seconds on a laptop and in CI against emulators, with no JVM.
- Single-node: gold SQL is bounded by one machine's memory. At telecom production volumes
  (billions of CDRs/day) the silver/gold jobs move to Databricks or Fabric Spark; the Delta
  tables, contracts and lineage namespaces stay the same.
- `MERGE` semantics come from delta-rs and match Spark's for the upsert-on-key pattern used here.
