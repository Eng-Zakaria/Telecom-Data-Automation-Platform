"""Data contract behaviour: no network, no lake. Fast enough to run on every commit."""

import pandas as pd
import pytest

from lakehouse.jobs import inject_chaos
from lakehouse.quality import BILLING, CDR, NETWORK_KPI, Contract, between, not_null
from lakehouse.storage import Lake


def _cdr(n: int = 10) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "call_sid": [f"c{i}" for i in range(n)],
            "caller_id": [f"a{i}" for i in range(n)],
            "cell_tower_id": ["TOWER_M0001"] * n,
            "start_time": pd.date_range("2024-01-01", periods=n, freq="min"),
            "duration_seconds": [60] * n,
            "signal_strength_dbm": [-80] * n,
            "data_volume_mb": [1.5] * n,
            "network_type": ["4G"] * n,
        }
    )


def test_clean_batch_passes_every_gate():
    valid, quarantined, report = CDR.apply(_cdr())
    assert len(valid) == 10 and quarantined.empty
    assert report.passed and report.quarantine_rate == 0


def test_bad_rows_are_quarantined_with_every_reason():
    df = _cdr()
    df.loc[0, "duration_seconds"] = -5
    df.loc[0, "caller_id"] = None
    df.loc[1, "signal_strength_dbm"] = 0
    valid, quarantined, report = CDR.apply(df)
    assert len(valid) == 8 and len(quarantined) == 2
    reasons = dict(zip(quarantined.call_sid, quarantined._dq_reasons, strict=True))
    assert set(reasons["c0"].split(";")) == {
        "caller_id_not_null",
        "duration_seconds_between_0_86400",
    }
    assert reasons["c1"] == "signal_strength_dbm_between_-140_-30"
    assert report.failures_by_rule["caller_id_not_null"] == 1


def test_synonyms_are_standardised_not_rejected():
    df = _cdr()
    df.loc[:4, "network_type"] = "LTE"
    valid, quarantined, _ = CDR.apply(df)
    assert quarantined.empty
    assert set(valid.network_type) == {"4G"}


def test_unknown_values_are_still_rejected():
    df = _cdr()
    df.loc[0, "network_type"] = "WiMAX"
    _, quarantined, _ = CDR.apply(df)
    assert quarantined.call_sid.tolist() == ["c0"]


def test_duplicates_removed_on_business_key_keeping_latest():
    df = pd.concat([_cdr(), _cdr().assign(duration_seconds=99)], ignore_index=True)
    valid, _, report = CDR.apply(df)
    assert len(valid) == 10 and report.duplicates_removed == 10
    assert set(valid.duration_seconds) == {99}


def test_quarantine_rate_gate_blocks_publishing():
    df = _cdr()
    df.loc[:2, "caller_id"] = None  # 30% bad > 5% budget
    _, _, report = CDR.apply(df)
    assert not report.passed
    gate = next(g for g in report.gates if g.name == "max_quarantine_rate")
    assert gate.observed == pytest.approx(0.3)


def test_missing_contract_column_fails_loudly():
    with pytest.raises(KeyError, match="duration_seconds"):
        CDR.apply(_cdr().drop(columns=["duration_seconds"]))


def test_custom_contract():
    c = Contract(
        "t", key=("id",), rules=(not_null("id"), between("x", 0, 1)), max_quarantine_rate=0.5
    )
    valid, quarantined, report = c.apply(pd.DataFrame({"id": [1, 2, None], "x": [0.5, 2.0, 0.1]}))
    assert valid.id.tolist() == [1] and len(quarantined) == 2 and not report.passed


@pytest.mark.parametrize("table", ["cdr", "network_kpi", "billing"])
def test_chaos_corrupts_requested_fraction_and_replays_duplicates(table):
    base = {
        "cdr": _cdr(100),
        "network_kpi": pd.DataFrame(
            {
                "tower_id": ["t"] * 100,
                "dropped_call_rate_pct": [1.0] * 100,
                "latency_ms": [30.0] * 100,
            }
        ),
        "billing": pd.DataFrame(
            {"plan_id": ["p"] * 100, "total_charge": [10.0] * 100, "num_overdue_months": [0] * 100}
        ),
    }[table]
    out = inject_chaos(base, table, rate=0.06)
    assert len(out) == 106  # 6 replayed rows
    assert out.ne(pd.concat([base, base.head(6)], ignore_index=True)).any(axis=1).sum() >= 6


def test_contracts_cover_their_keys():
    for contract in (CDR, NETWORK_KPI, BILLING):
        assert contract.key and all(isinstance(k, str) for k in contract.key)


def test_lake_uris_switch_with_mode(monkeypatch):
    monkeypatch.delenv("CLOUDKIT_MODE", raising=False)
    local = Lake.from_env(prefix="runs/x")
    assert local.uri("silver", "cdr") == "az://silver/runs/x/cdr"
    assert local.storage_options["use_emulator"] == "true"

    monkeypatch.setenv("CLOUDKIT_MODE", "azure")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT", "sttelprod")
    cloud = Lake.from_env(prefix="")
    assert cloud.uri("gold", "revenue_by_plan") == (
        "abfss://gold@sttelprod.dfs.core.windows.net/revenue_by_plan"
    )
    assert "account_key" not in cloud.storage_options  # keyless in Azure

    with pytest.raises(ValueError):
        cloud.uri("platinum", "x")
