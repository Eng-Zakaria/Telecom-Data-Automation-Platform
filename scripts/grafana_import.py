"""Install the pipeline-health dashboard into the azure-local-lab Grafana.

uv run python scripts/grafana_import.py            # http://localhost:3001, admin/admin
GRAFANA_URL=http://host:3000 uv run python scripts/grafana_import.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

DASHBOARD = (
    Path(__file__).resolve().parents[1] / "observability" / "grafana" / "telecom-lakehouse.json"
)


def main() -> int:
    url = os.environ.get("GRAFANA_URL", "http://localhost:3001").rstrip("/")
    auth = os.environ.get("GRAFANA_AUTH", "admin:admin")
    body = json.dumps({"dashboard": json.loads(DASHBOARD.read_text()), "overwrite": True}).encode()
    req = urllib.request.Request(
        f"{url}/api/dashboards/db",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Basic " + base64.b64encode(auth.encode()).decode(),
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.load(resp)
    print(f"{result.get('status')}: {url}{result.get('url')}")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
