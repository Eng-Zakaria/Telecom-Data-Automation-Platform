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

SILVER_TABLES = (
    "towers",
    "cdr",
    "network_kpi",
    "billing",
    "billing_monthly",
    "plans",
    "complaints",
    "roaming_sessions",
    "roaming_partners",
    "roaming_settlements",
    "campaigns",
    "campaign_responses",
)


def generate(
    cdr_rows: int, customers: int, towers: int, days: int, seed: int
) -> dict[str, pd.DataFrame]:
    from ingestion.billing_generator import BillingGenerator
    from ingestion.campaign_generator.campaign_generator import CampaignGenerator
    from ingestion.cdr_generator import CDRGenerator
    from ingestion.complaint_scraper.scraper import ComplaintScraper
    from ingestion.network_kpi_generator import NetworkKPIGenerator
    from ingestion.roaming_partner_generator.roaming_generator import RoamingGenerator

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
    bg = BillingGenerator(num_customers=customers, seed=seed)
    billing = bg.generate_billing_data()
    # invoices end in the month the CDR window starts, so usage and billing overlap
    billing_monthly = bg.generate_usage_charges(
        num_months=6, num_customers=customers, end_month=cdr["start_time"].min().to_pydatetime()
    )
    plans = pd.DataFrame([p.__dict__ for p in bg.plans]).assign(
        features=lambda d: d["features"].map(",".join)  # Delta-friendly scalar column
    )

    # Every generator hashes CUST_nnnnnn with sha256[:16], so all feeds share one
    # pseudonymous subscriber key. Sizes stay within the same customer universe.
    complaints = ComplaintScraper(
        num_complaints=max(1, customers // 2),
        seed=seed,
        end_date=cdr["start_time"].max().to_pydatetime(),  # same period as the usage
        window_days=180,
    ).generate_complaints()
    sessions, settlements, partners = RoamingGenerator(
        num_customers=customers, num_partners=12, date_range_days=days, seed=seed
    ).generate_roaming_data(num_sessions=max(50, cdr_rows // 6))
    campaigns, responses = CampaignGenerator(
        num_customers=customers, num_campaigns=8, seed=seed
    ).generate_campaign_data()
    return {
        "towers": pd.DataFrame([tw.__dict__ for tw in g.towers]),
        "cdr": cdr,
        "network_kpi": kpi,
        "billing": billing,
        "billing_monthly": billing_monthly,
        "plans": plans,
        "complaints": complaints,
        "roaming_sessions": sessions,
        "roaming_partners": partners,
        "roaming_settlements": settlements,
        "campaigns": campaigns,
        "campaign_responses": responses,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lakehouse", description=__doc__.splitlines()[0])
    p.add_argument("--cdr", type=int, default=5000, help="CDR rows to generate")
    p.add_argument("--customers", type=int, default=500)
    p.add_argument("--towers", type=int, default=20)
    p.add_argument("--days", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--chaos", type=float, default=0.0, help="fraction of rows to corrupt (0-1)")
    p.add_argument("--stream", action="store_true", help="route CDRs through Event Hubs")
    p.add_argument("--dbt", action="store_true", help="build + test the dbt marts, publish to gold")
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
                since = stream.publish(df, batch_id)
                df = stream.consume(batch_id, expected=len(df), since=since)
                source = f"eventhubs:{stream.HUB}"
            jobs.ingest_bronze(lake, table, df, batch_id, source)

        silver = {t: jobs.build_silver(lake, t, batch_id) for t in SILVER_TABLES}
        gates_ok = all(r.report.passed for r in silver.values())
        gold = {name: jobs.build_gold(lake, name) for name in jobs.GOLD_SQL} if gates_ok else {}

        dbt_summary = None
        if args.dbt and gates_ok:
            from . import transform

            result = transform.run_dbt(lake)
            if result.success:
                result.published = transform.publish_marts(lake)
            gates_ok = result.success  # a failed dbt test blocks publishing like a contract
            dbt_summary = {
                "success": result.success,
                "models": result.models,
                "tests": result.tests,
                "failures": result.failures,
                "warnings": result.warnings,
                "published": result.published,
            }
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
        "dbt": dbt_summary,
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
    if s.get("dbt"):
        d = s["dbt"]
        status = "ok" if d["success"] else f"FAIL {d['failures']}"
        if d.get("warnings"):
            status += f"  ({len(d['warnings'])} warning: {', '.join(w.split('.')[-1] for w in d['warnings'])})"
        print(f"dbt build: {d['models']} models, {d['tests']} tests  {status}")
        if d["published"]:
            print(
                f"gold (dbt marts): {len(d['published'])} tables, {sum(d['published'].values())} rows"
            )
    print("RESULT:", "PASS" if s["gates_passed"] else "FAIL (gold not published)")


if __name__ == "__main__":
    sys.exit(main())
