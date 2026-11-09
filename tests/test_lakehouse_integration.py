"""Full pipeline against azure-local-lab (Azurite + Event Hubs emulator).

(cd ../azure-local-lab && docker compose --profile streaming up -d)
uv run pytest -m integration
"""

import json
import uuid

import pytest

from lakehouse import jobs
from lakehouse.run import main
from lakehouse.storage import Lake

pytestmark = pytest.mark.integration


@pytest.fixture
def prefix():
    return f"tests/{uuid.uuid4().hex[:8]}"


def _run(tmp_path, prefix, *extra):
    summary = tmp_path / "summary.json"
    lineage = tmp_path / "lineage.jsonl"
    import os

    os.environ["LINEAGE_FILE"] = str(lineage)
    code = main(
        [
            "--cdr",
            "600",
            "--customers",
            "100",
            "--towers",
            "5",
            "--days",
            "1",
            "--prefix",
            prefix,
            "--summary",
            str(summary),
            *extra,
        ]
    )
    return (
        code,
        json.loads(summary.read_text()),
        [json.loads(x) for x in lineage.read_text().splitlines()],
    )


def test_batch_run_publishes_gold_and_lineage(tmp_path, prefix):
    code, s, events = _run(tmp_path, prefix, "--chaos", "0.02")
    assert code == 0 and s["gates_passed"]
    assert s["silver"]["cdr"]["quarantined"] == 12  # 2% of 600, every corrupted row caught
    assert s["silver"]["cdr"]["duplicates_removed"] == 12
    assert set(s["gold"]) == {"network_health_hourly", "subscriber_usage_daily", "revenue_by_plan"}

    lake = Lake.from_env(prefix=prefix)
    assert len(jobs.read(lake, "silver", "cdr")) == s["silver"]["cdr"]["valid"]
    assert len(jobs.read(lake, "quarantine", "cdr")) == 12

    done = {e["job"]["name"]: e for e in events if e["eventType"] == "COMPLETE"}
    assert {i["name"] for i in done["gold.network_health_hourly"]["inputs"]} == {
        "silver/network_kpi",
        "silver/cdr",
    }
    silver_out = {o["name"]: o for o in done["silver.cdr"]["outputs"]}
    assertions = silver_out["silver/cdr"]["facets"]["dataQualityAssertions"]["assertions"]
    assert all(a["success"] for a in assertions)


def test_rerun_of_same_data_is_idempotent(tmp_path, prefix):
    _run(tmp_path, prefix)
    first = len(jobs.read(Lake.from_env(prefix=prefix), "silver", "cdr"))
    _run(tmp_path, prefix)  # same seed -> same business keys -> MERGE updates, no growth
    assert len(jobs.read(Lake.from_env(prefix=prefix), "silver", "cdr")) == first


def test_failed_gate_blocks_gold(tmp_path, prefix):
    code, s, _events = _run(tmp_path, prefix, "--chaos", "0.2")  # 20% bad > 5% budget
    assert code == 1 and not s["gates_passed"] and s["gold"] == {}
    assert jobs.read(Lake.from_env(prefix=prefix), "silver", "cdr").empty  # nothing published


def test_streaming_path_matches_batch(tmp_path, prefix):
    code, _s, events = _run(tmp_path, prefix, "--stream")
    assert code == 0
    names = [e["job"]["name"] for e in events if e["eventType"] == "COMPLETE"]
    assert "stream.publish" in names and "stream.consume" in names
    bronze = next(
        e for e in events if e["eventType"] == "COMPLETE" and e["job"]["name"] == "bronze.cdr"
    )
    assert bronze["inputs"][0]["namespace"] == "eventhubs://cdr-stream"


def test_dbt_marts_build_test_and_publish(tmp_path, prefix):
    """silver -> dbt build (models + tests) -> gold marts, with lineage through every model."""
    code, s, events = _run(tmp_path, prefix, "--dbt")
    assert code == 0, s.get("dbt")
    d = s["dbt"]
    assert d["success"] and d["models"] >= 30 and d["tests"] >= 60 and not d["failures"]
    for mart in ("f_customers", "f_revenue_leakage", "f_churn_prediction", "f_executive_dashboard"):
        assert d["published"].get(mart, 0) > 0, mart

    lake = Lake.from_env(prefix=prefix)
    customers = jobs.read(lake, "gold", "f_customers")
    assert customers.subscriber_key.is_unique
    assert customers.total_calls.notna().mean() > 0.9  # cross-feed join really matches

    done = {e["job"]["name"]: e for e in events if e["eventType"] == "COMPLETE"}
    assert {i["name"] for i in done["dbt.stg_cdr"]["inputs"]} == {"silver/cdr"}
    assert "stg_billing" in {i["name"] for i in done["dbt.f_customers"]["inputs"]}
