"""Run the dbt project over silver, gate on its tests, publish marts to gold, and report
lineage for every model from dbt's own manifest.

    silver (Delta) --dbt-duckdb--> core + marts (DuckDB) --publish--> gold/<model> (Delta)

A failing dbt test is treated exactly like a failed data contract: nothing is published.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from . import jobs, observe
from .storage import Lake

DBT_DIR = Path(__file__).resolve().parents[1] / "transform" / "dbt"
DBT_NAMESPACE = "duckdb://telecom-dbt"
# Marts worth publishing as gold tables (staging views stay inside the dbt database).
PUBLISH_PREFIXES = ("f_", "dim_")


@dataclass
class DbtResult:
    success: bool
    models: int = 0
    tests: int = 0
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    published: dict[str, int] = field(default_factory=dict)


def _db_path(lake: Lake) -> Path:
    slug = (lake.prefix or "default").replace("/", "_")
    return Path("artifacts") / "dbt" / f"{slug}.duckdb"


def run_dbt(lake: Lake) -> DbtResult:
    from dbt.cli.main import dbtRunner

    db = _db_path(lake).resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    for stale in (db, db.with_suffix(".duckdb.wal")):
        stale.unlink(missing_ok=True)  # each run rebuilds from silver; no state carries over

    os.environ["LAKE_PREFIX"] = lake.prefix
    os.environ["DBT_DUCKDB_PATH"] = str(db)
    target = db.parent / "target"
    with observe.job("dbt.build", project="telecom_platform") as run:
        res = dbtRunner().invoke(
            [
                "build",
                "--project-dir",
                str(DBT_DIR),
                "--profiles-dir",
                str(DBT_DIR),
                "--target-path",
                str(target),
                "--log-path",
                str(db.parent / "logs"),
                "--quiet",
            ]
        )
        results = json.loads((target / "run_results.json").read_text())["results"]
        failures = [
            r["unique_id"] for r in results if r["status"] in ("error", "fail", "runtime error")
        ]
        warnings = [r["unique_id"] for r in results if r["status"] == "warn"]
        out = DbtResult(
            success=bool(res.success) and not failures,
            models=sum(r["unique_id"].startswith("model.") for r in results),
            tests=sum(r["unique_id"].startswith("test.") for r in results),
            failures=failures,
            warnings=warnings,
        )
        run.attributes.update(models=out.models, tests=out.tests, failures=len(failures))
        _emit_model_lineage(lake, target / "manifest.json")
        _release_dbt_connection()
        if out.failures:
            observe.GATE_FAILURES.add(
                len(out.failures),
                {"pipeline_job": "dbt.build", "dataset": "dbt", "gate": "dbt_test"},
            )
    return out


def _release_dbt_connection() -> None:
    """dbt-duckdb caches its DuckDB handle for the process; close it so the file can be
    reopened (read-only) by publish_marts and by the next run."""
    from dbt.adapters.duckdb.connections import DuckDBConnectionManager

    DuckDBConnectionManager.close_all_connections()


def _emit_model_lineage(lake: Lake, manifest_path: Path) -> None:
    """One OpenLineage COMPLETE event per dbt model, with its real upstream nodes."""
    manifest = json.loads(manifest_path.read_text())
    nodes, sources = manifest["nodes"], manifest["sources"]
    for node in nodes.values():
        if node["resource_type"] != "model":
            continue
        with observe.job(f"dbt.{node['name']}", materialized=node["config"]["materialized"]) as run:
            for dep in node["depends_on"]["nodes"]:
                if dep in sources:
                    run.read(
                        observe.Dataset(lake.dataset_namespace(), f"silver/{sources[dep]['name']}")
                    )
                elif dep in nodes:
                    run.read(observe.Dataset(DBT_NAMESPACE, nodes[dep]["name"]))
            run.wrote(observe.Dataset(DBT_NAMESPACE, node["name"]))


def publish_marts(lake: Lake) -> dict[str, int]:
    """Copy dbt marts from DuckDB to gold Delta tables (what BI / Fabric / Power BI read)."""
    published: dict[str, int] = {}
    con = duckdb.connect(str(_db_path(lake).resolve()), read_only=True)
    try:
        names = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
            ).fetchall()
            if r[0].startswith(PUBLISH_PREFIXES)
        ]
        for name in sorted(names):
            with observe.job(f"gold.{name}", source="dbt") as run:
                df = con.execute(f'SELECT * FROM main."{name}"').df()
                run.read(observe.Dataset(DBT_NAMESPACE, name, df))
                jobs.overwrite(lake, "gold", name, df)
                run.wrote(observe.Dataset(lake.dataset_namespace(), f"gold/{name}", df))
                published[name] = len(df)
    finally:
        con.close()
    return published
