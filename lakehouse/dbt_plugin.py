"""dbt-duckdb source plugin: read lakehouse Delta tables with the pipeline's own settings.

Sources declare `plugin: lake` and a `layer`; the table path, emulator-vs-ADLS location
and auth all come from lakehouse.storage.Lake (CLOUDKIT_MODE, LAKE_PREFIX), so dbt and the
Python jobs can never disagree about where the data lives.

    sources:
      - name: silver
        meta: { plugin: lake, layer: silver }
        tables: [{ name: cdr }]
"""

from __future__ import annotations

from typing import Any

from dbt.adapters.duckdb.plugins import BasePlugin
from dbt.adapters.duckdb.utils import SourceConfig
from deltalake import DeltaTable

from .storage import Lake


class Plugin(BasePlugin):
    def initialize(self, config: dict[str, Any]) -> None:
        self.lake = Lake.from_env()

    def load(self, source_config: SourceConfig):
        layer = source_config.get("layer", "silver")
        table = source_config.get("lake_table", source_config.identifier)
        dt = DeltaTable(self.lake.uri(layer, table), storage_options=self.lake.storage_options)
        return dt.to_pyarrow_dataset()

    def default_materialization(self) -> str:
        # "table" copies the Delta snapshot into DuckDB once per run. A "view" would point
        # at an Arrow object registered on one cursor, which other threads cannot see.
        return "table"
