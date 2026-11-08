"""End-to-end run: generate -> (stream) -> bronze -> silver (contracts) -> gold.

    uv run python -m lakehouse --cdr 5000 --chaos 0.02 --stream

Exit code 1 if any quality gate fails, so CI and schedulers treat it as a failed run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from opentelemetry import trace

from . import jobs, observe, stream
from .storage import Lake

SILVER_TABLES = ("cdr", "network_kpi", "billing")


def generate(
    cdr_rows: int, customers: int, towers: int, days: int, seed: int
) -> dict[str, pd.DataFrame]:
    from ingestion.billing_generator import BillingGenerator
    from ingestion.cdr_generator import CDRGenerator
    from ingestion.network_kpi_generator import NetworkKPIGenerator

    g = CDRGenerator(num_customers=customers, num_towers=towers, date_range_days=days, seed=seed)
    g.generate_customers()
    g.generate_towers()
    cdr = g.inject_fraud_patterns(g.generate_cdrs(num_records=cdr_rows))
    kpi = NetworkKPIGenerator(
        date_range_days=days,
        granularity_minutes=60,
        seed=seed,
        tower_ids=[t.tower_id for t in g.towers],  # one tower registry for every feed
    ).generate_kpi_data()
    billing = BillingGenerator(num_customers=customers, seed=seed).generate_billing_data()
    return {"cdr": cdr, "network_kpi": kpi, "billing": billing}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lakehouse", description=__doc__.splitlines()[0])
    p.add_argument("--cdr", type=int, default=5000, help="CDR rows to generate")
    p.add_argument("--customers", type=int, default=500)
    p.add_argument("--towers", type=int, default=20)
    p.add_argument("--days", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--chaos", type=float, default=0.0, help="fraction of rows to corrupt (0-1)")
    p.add_argument("--stream", action="store_true", help="route CDRs through Event Hubs")
    p.add_argument("--prefix", default=None, help="lake path prefix that isolates this run")
    p.add_argument("--summary", default="artifacts/run_summary.json")
    args = p.parse_args(argv)

    lake = Lake.from_env(prefix=args.prefix)
    lake.ensure_containers()
    observe.start()
    batch_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    t0 = time.perf_counter()
    tracer = trace.get_tracer(observe.SERVICE)

    with tracer.start_as_current_span("lakehouse.run") as root:
        root.set_attribute("lakehouse.batch_id", batch_id)
        data = generate(args.cdr, args.customers, args.towers, args.days, args.seed)

        for table, df in data.items():
            df = jobs.inject_chaos(df, table, args.chaos, seed=args.seed)
            source = table
            if table == "cdr" and args.stream:
                stream.publish(df, batch_id)
                df = stream.consume(batch_id, expected=len(df))
                source = f"eventhubs:{stream.HUB}"
            jobs.ingest_bronze(lake, table, df, batch_id, source)

        silver = {t: jobs.build_silver(lake, t, batch_id) for t in SILVER_TABLES}
        gates_ok = all(r.report.passed for r in silver.values())
        gold = {name: jobs.build_gold(lake, name) for name in jobs.GOLD_SQL} if gates_ok else {}
        root.set_attribute("lakehouse.gates_passed", gates_ok)

    summary = {
        "batch_id": batch_id,
        "mode": lake.settings.mode.value,
        "seconds": round(time.perf_counter() - t0, 1),
        "trace_id": format(root.get_span_context().trace_id, "032x"),
        "silver": {
            t: {
                "rows_in": r.report.rows_in,
                "valid": r.report.rows_valid,
                "quarantined": r.report.rows_quarantined,
                "duplicates_removed": r.report.duplicates_removed,
                "failures_by_rule": r.report.failures_by_rule,
                "gates": {g.name: g.passed for g in r.report.gates},
            }
            for t, r in silver.items()
        },
        "gold": {name: len(df) for name, df in gold.items()},
        "gates_passed": gates_ok,
    }
    observe.stop()

    out = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    _print(summary)
    return 0 if gates_ok else 1


def _print(s: dict) -> None:
    print(f"\nbatch {s['batch_id']}  mode={s['mode']}  {s['seconds']}s  trace={s['trace_id']}")
    print(f"{'table':<14}{'in':>8}{'valid':>8}{'quarant.':>10}{'dupes':>7}  gates")
    for t, r in s["silver"].items():
        gates = " ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in r["gates"].items())
        print(
            f"{t:<14}{r['rows_in']:>8}{r['valid']:>8}{r['quarantined']:>10}{r['duplicates_removed']:>7}  {gates}"
        )
    for name, n in s["gold"].items():
        print(f"gold.{name:<30}{n:>8} rows")
    print("RESULT:", "PASS" if s["gates_passed"] else "FAIL (gold not published)")


if __name__ == "__main__":
    sys.exit(main())
