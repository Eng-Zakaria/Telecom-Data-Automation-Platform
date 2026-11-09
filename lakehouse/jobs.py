"""Medallion jobs. Each job is a pure function of (lake, inputs) -> outputs, wrapped in
observe.job() so it is traced, metered and lineage-tracked the same way everywhere.

bronze  append-only Delta, raw columns + ingestion metadata (_batch_id, _ingested_at, _source)
silver  contract-enforced: typed, deduplicated on the business key, upserted (MERGE);
        rejected rows land in quarantine/<table> with the failing rule names
gold    business tables computed with DuckDB SQL over silver, overwritten per run
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import TableNotFoundError

from . import observe
from .quality import CONTRACTS, QualityReport
from .storage import Lake


# --------------------------------------------------------------------- io ---
def _to_arrow(df: pd.DataFrame) -> pa.Table:
    # Delta has no nanosecond timestamps; normalise to microseconds UTC-naive.
    out = df.copy()
    for col in out.columns:
        if isinstance(out[col].dtype, pd.DatetimeTZDtype):  # e.g. dbt CURRENT_TIMESTAMP columns
            out[col] = out[col].dt.tz_convert("UTC").dt.tz_localize(None)
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype("datetime64[us]")
    return pa.Table.from_pandas(out, preserve_index=False)


def read(lake: Lake, layer: str, table: str) -> pd.DataFrame:
    try:
        dt = DeltaTable(lake.uri(layer, table), storage_options=lake.storage_options)
    except TableNotFoundError:
        return pd.DataFrame()
    return dt.to_pandas()


def append(lake: Lake, layer: str, table: str, df: pd.DataFrame) -> None:
    write_deltalake(
        lake.uri(layer, table),
        _to_arrow(df),
        mode="append",
        schema_mode="merge",
        storage_options=lake.storage_options,
    )


def overwrite(lake: Lake, layer: str, table: str, df: pd.DataFrame) -> None:
    write_deltalake(
        lake.uri(layer, table),
        _to_arrow(df),
        mode="overwrite",
        schema_mode="overwrite",
        storage_options=lake.storage_options,
    )


def upsert(lake: Lake, layer: str, table: str, df: pd.DataFrame, key: tuple[str, ...]) -> None:
    uri = lake.uri(layer, table)
    try:
        dt = DeltaTable(uri, storage_options=lake.storage_options)
    except TableNotFoundError:
        overwrite(lake, layer, table, df)
        return
    predicate = " AND ".join(f"t.{k} = s.{k}" for k in key)
    (
        dt.merge(_to_arrow(df), predicate=predicate, source_alias="s", target_alias="t")
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute()
    )


# ----------------------------------------------------------------- bronze ---
def inject_chaos(df: pd.DataFrame, table: str, rate: float, seed: int = 7) -> pd.DataFrame:
    """Corrupt a fraction of rows the way real feeds break, to prove quarantine works."""
    if rate <= 0 or df.empty:
        return df
    rng = np.random.default_rng(seed)
    out = df.copy()
    n = max(1, int(len(out) * rate))
    idx = rng.choice(out.index, size=n, replace=False)
    thirds = np.array_split(idx, 3)
    if table == "cdr":
        out.loc[thirds[0], "duration_seconds"] = -5  # clock skew on the switch
        out.loc[thirds[1], "caller_id"] = None  # truncated record
        out.loc[thirds[2], "signal_strength_dbm"] = 0  # sensor default value
    elif table == "network_kpi":
        out.loc[thirds[0], "dropped_call_rate_pct"] = 140.0
        out.loc[thirds[1], "tower_id"] = None
        out.loc[thirds[2], "latency_ms"] = -1.0
    elif table == "billing":
        out.loc[thirds[0], "total_charge"] = -10.0
        out.loc[thirds[1], "plan_id"] = None
        out.loc[thirds[2], "num_overdue_months"] = 999
    # and replay a few rows: at-least-once delivery means duplicates are normal
    return pd.concat([out, out.sample(n=min(len(out), n), random_state=seed)], ignore_index=True)


def ingest_bronze(
    lake: Lake, table: str, df: pd.DataFrame, batch_id: str, source: str
) -> pd.DataFrame:
    with observe.job(f"bronze.{table}", batch_id=batch_id, source=source) as run:
        landed = df.assign(
            _batch_id=batch_id,
            _ingested_at=datetime.now(UTC).replace(tzinfo=None),
            _source=source,
        )
        append(lake, "bronze", table, landed)
        if source.startswith("eventhubs:"):  # same dataset identity stream.publish wrote
            hub = source.split(":", 1)[1]
            run.read(observe.Dataset(f"eventhubs://{hub}", hub, landed))
        else:
            run.read(observe.Dataset(f"generator://{source}", table, landed))
        run.wrote(observe.Dataset(lake.dataset_namespace(), f"bronze/{table}", landed))
        return landed


# ----------------------------------------------------------------- silver ---
@dataclass
class SilverResult:
    table: str
    report: QualityReport
    valid: pd.DataFrame


def build_silver(lake: Lake, table: str, batch_id: str) -> SilverResult:
    contract = CONTRACTS[table]
    with observe.job(f"silver.{table}", batch_id=batch_id) as run:
        bronze = read(lake, "bronze", table)
        batch = bronze[bronze["_batch_id"] == batch_id].drop(columns=["_batch_id", "_source"])
        run.read(observe.Dataset(lake.dataset_namespace(), f"bronze/{table}", batch))

        valid, quarantined, report = contract.apply(batch)
        if not quarantined.empty:
            append(lake, "quarantine", table, quarantined.assign(_batch_id=batch_id))
            run.wrote(observe.Dataset(lake.dataset_namespace(), f"quarantine/{table}", quarantined))

        if report.passed:
            upsert(lake, "silver", table, valid, contract.key)
        run.wrote(observe.Dataset(lake.dataset_namespace(), f"silver/{table}", valid, report))
        return SilverResult(table, report, valid)


# ------------------------------------------------------------------- gold ---
GOLD_SQL = {
    # Hourly cell health: radio KPIs joined with the traffic each cell actually carried.
    "network_health_hourly": """
        WITH kpi AS (
            SELECT tower_id,
                   date_trunc('hour', "timestamp")              AS hour,
                   avg(dropped_call_rate_pct)                   AS dropped_call_rate_pct,
                   avg(congestion_pct)                          AS congestion_pct,
                   quantile_cont(latency_ms, 0.95)              AS latency_p95_ms,
                   avg(handover_success_rate_pct)               AS handover_success_pct,
                   sum(total_calls)                             AS reported_calls
            FROM network_kpi GROUP BY ALL
        ),
        traffic AS (
            SELECT cell_tower_id                                AS tower_id,
                   date_trunc('hour', start_time)               AS hour,
                   count(*)                                     AS cdr_calls,
                   sum(duration_seconds) / 60.0                 AS minutes,
                   avg(CASE WHEN error_code IS NOT NULL THEN 1 ELSE 0 END) AS error_rate
            FROM cdr GROUP BY ALL
        )
        SELECT k.*,
               coalesce(t.cdr_calls, 0)  AS cdr_calls,
               coalesce(t.minutes, 0)    AS minutes,
               coalesce(t.error_rate, 0) AS cdr_error_rate,
               greatest(0, 100
                   - 20 * least(k.dropped_call_rate_pct, 5)
                   - 0.5 * k.congestion_pct
                   - 0.05 * greatest(k.latency_p95_ms - 50, 0)) AS health_score,
               (k.dropped_call_rate_pct > 2 OR k.latency_p95_ms > 150) AS sla_breach
        FROM kpi k LEFT JOIN traffic t USING (tower_id, hour)
        ORDER BY hour, tower_id
    """,
    # Daily usage per subscriber: the input to churn, propensity and fraud features.
    "subscriber_usage_daily": """
        SELECT caller_id                                        AS subscriber_id,
               CAST(start_time AS DATE)                         AS usage_date,
               count(*)                                         AS events,
               count(*) FILTER (WHERE call_type = 'voice')      AS voice_calls,
               sum(duration_seconds) / 60.0                     AS voice_minutes,
               sum(data_volume_mb)                              AS data_mb,
               count(*) FILTER (WHERE roaming_flag)             AS roaming_events,
               count(DISTINCT cell_tower_id)                    AS distinct_cells,
               avg(CASE WHEN error_code IS NOT NULL THEN 1 ELSE 0 END) AS error_rate
        FROM cdr GROUP BY ALL
        ORDER BY usage_date, subscriber_id
    """,
    # Revenue by plan: MRR, ARPU and collections risk for finance and product.
    "revenue_by_plan": """
        SELECT plan_id,
               count(*)                                         AS subscribers,
               round(sum(monthly_charge), 2)                    AS mrr,
               round(avg(total_charge), 2)                      AS arpu,
               round(avg(tenure_days) / 30.4, 1)                AS avg_tenure_months,
               round(avg(CASE WHEN payment_status IN ('overdue', 'defaulted') THEN 1 ELSE 0 END), 4)
                                                                AS overdue_rate,
               round(coalesce(sum(total_charge * num_overdue_months)
                     FILTER (WHERE payment_status IN ('overdue', 'defaulted')), 0), 2)
                                                                AS revenue_at_risk,
               round(avg(lifetime_value), 2)                    AS avg_ltv
        FROM billing GROUP BY ALL
        ORDER BY mrr DESC
    """,
}

GOLD_INPUTS = {
    "network_health_hourly": ("network_kpi", "cdr"),
    "subscriber_usage_daily": ("cdr",),
    "revenue_by_plan": ("billing",),
}


def build_gold(lake: Lake, name: str) -> pd.DataFrame:
    with observe.job(f"gold.{name}") as run:
        con = duckdb.connect()
        for src in GOLD_INPUTS[name]:
            frame = read(lake, "silver", src)
            con.register(src, frame)
            run.read(observe.Dataset(lake.dataset_namespace(), f"silver/{src}", frame))
        out = con.execute(GOLD_SQL[name]).df()
        overwrite(lake, "gold", name, out)
        run.wrote(observe.Dataset(lake.dataset_namespace(), f"gold/{name}", out))
        return out
