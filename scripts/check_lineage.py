"""Assert the lineage graph is complete: every gold table traces back to a source.

    uv run python scripts/check_lineage.py                         # artifacts/lineage/events.jsonl
    uv run python scripts/check_lineage.py --marquez http://localhost:5000

Fails (exit 1) if a gold dataset has no upstream path to a raw source, which is how
an undocumented hand-made table or a job that forgot to report its inputs shows up.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

NAMESPACE = "telecom-platform"
SOURCE_PREFIXES = ("generator://", "eventhubs://")


def edges_from_file(path: Path) -> list[tuple[str, str, str]]:
    edges = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ev = json.loads(line)
        if ev.get("eventType") != "COMPLETE":
            continue
        job = ev["job"]["name"]
        for i in ev.get("inputs", []):
            for o in ev.get("outputs", []):
                edges.append(
                    (f"{i['namespace']}/{i['name']}", job, f"{o['namespace']}/{o['name']}")
                )
        for i in ev.get("inputs", []):  # jobs with inputs but no outputs still anchor their inputs
            edges.append((f"{i['namespace']}/{i['name']}", job, ""))
    return edges


def edges_from_marquez(url: str) -> list[tuple[str, str, str]]:
    with urllib.request.urlopen(
        f"{url}/api/v1/namespaces/{NAMESPACE}/jobs?limit=500", timeout=10
    ) as r:
        jobs = json.load(r)["jobs"]
    edges = []
    for j in jobs:
        ins = [f"{d['namespace']}/{d['name']}" for d in j["inputs"]]
        outs = [f"{d['namespace']}/{d['name']}" for d in j["outputs"]]
        for i in ins:
            for o in outs or [""]:
                edges.append((i, j["name"], o))
    return edges


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="artifacts/lineage/events.jsonl")
    ap.add_argument("--marquez", default=None)
    args = ap.parse_args()

    edges = edges_from_marquez(args.marquez) if args.marquez else edges_from_file(Path(args.file))
    upstream: dict[str, set[str]] = defaultdict(set)
    for src, _, dst in edges:
        if dst:
            upstream[dst].add(src)

    def reaches_source(ds: str, seen: set[str]) -> bool:
        if ds.startswith(SOURCE_PREFIXES):
            return True
        if ds in seen:
            return False
        seen.add(ds)
        return any(reaches_source(u, seen) for u in upstream.get(ds, ()))

    gold = sorted(d for d in upstream if "/gold/" in d)
    if not gold:
        print("no gold datasets found in lineage")
        return 1
    broken = [g for g in gold if not reaches_source(g, set())]
    for g in gold:
        print(("BROKEN " if g in broken else "ok     ") + g)
    print(f"{len(gold) - len(broken)}/{len(gold)} gold datasets trace back to a source")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
