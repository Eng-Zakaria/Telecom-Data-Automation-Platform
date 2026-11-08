"""Run telemetry: OpenTelemetry traces/metrics + OpenLineage lineage for every job.

Traces & metrics  -> Grafana LGTM locally, Azure Monitor / App Insights in Azure
                     (cloudkit.telemetry picks the exporter from CLOUDKIT_MODE).
Lineage           -> OPENLINEAGE_URL set: HTTP (Marquez locally, or Purview/any OL backend);
                     otherwise newline-delimited JSON in artifacts/lineage/events.jsonl.

Metric names are a contract with infra/modules/observability (the KQL alert reads
telecom.quality.gate_failures), so change both together. The per-job attribute is
`pipeline_job`, not `job`: Prometheus reserves `job` for the service name.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from cloudkit import telemetry
from opentelemetry import metrics, trace

from .quality import QualityReport

NAMESPACE = "telecom-platform"
SERVICE = "telecom-lakehouse"

_tracer = trace.get_tracer(SERVICE)
_meter = metrics.get_meter(SERVICE)
ROWS_IN = _meter.create_counter("telecom.rows.in", unit="{row}", description="Rows read by a job")
ROWS_OUT = _meter.create_counter("telecom.rows.out", unit="{row}", description="Rows written")
ROWS_QUARANTINED = _meter.create_counter(
    "telecom.rows.quarantined", unit="{row}", description="Rows rejected by data contracts"
)
GATE_FAILURES = _meter.create_counter(
    "telecom.quality.gate_failures", unit="{gate}", description="Failed quality gates"
)
JOB_DURATION = _meter.create_histogram(
    "telecom.job.duration",
    unit="s",
    description="Job wall time",
    # Default OTel buckets start at 0/5/10s, too coarse for sub-second jobs.
    explicit_bucket_boundaries_advisory=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 900],
)


def start(service: str = SERVICE) -> None:
    telemetry.configure(service)


def stop() -> None:
    telemetry.shutdown()


# ------------------------------------------------------------------ lineage ---
def _lineage_client():
    from openlineage.client import OpenLineageClient
    from openlineage.client.transport.file import FileConfig, FileTransport

    url = os.environ.get("OPENLINEAGE_URL")
    if url:
        return OpenLineageClient(url=url)
    path = Path(os.environ.get("LINEAGE_FILE", "artifacts/lineage/events.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return OpenLineageClient(
        transport=FileTransport(FileConfig(log_file_path=str(path), append=True))
    )


def _schema_facet(df: pd.DataFrame):
    from openlineage.client.facet_v2 import schema_dataset

    return schema_dataset.SchemaDatasetFacet(
        fields=[
            schema_dataset.SchemaDatasetFacetFields(name=c, type=str(t))
            for c, t in df.dtypes.items()
        ]
    )


@dataclass
class Dataset:
    """A table a job read or wrote, with what we know about it for lineage."""

    namespace: str
    name: str  # e.g. silver/cdr
    frame: pd.DataFrame | None = None
    report: QualityReport | None = None


@dataclass
class JobRun:
    name: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    inputs: list[Dataset] = field(default_factory=list)
    outputs: list[Dataset] = field(default_factory=list)
    attributes: dict[str, object] = field(default_factory=dict)

    def read(self, ds: Dataset) -> None:
        self.inputs.append(ds)
        if ds.frame is not None:
            ROWS_IN.add(len(ds.frame), {"pipeline_job": self.name, "dataset": ds.name})

    def wrote(self, ds: Dataset) -> None:
        self.outputs.append(ds)
        if ds.frame is not None:
            ROWS_OUT.add(len(ds.frame), {"pipeline_job": self.name, "dataset": ds.name})
        if ds.report is not None:
            ROWS_QUARANTINED.add(
                ds.report.rows_quarantined, {"pipeline_job": self.name, "dataset": ds.name}
            )
            failed = [g for g in ds.report.gates if not g.passed]
            for g in failed:
                GATE_FAILURES.add(
                    1, {"pipeline_job": self.name, "dataset": ds.name, "gate": g.name}
                )


def _event(run: JobRun, state: str, error: BaseException | None = None):
    from openlineage.client.event_v2 import (
        InputDataset,
        Job,
        OutputDataset,
        Run,
        RunEvent,
        RunState,
    )
    from openlineage.client.facet_v2 import (
        data_quality_assertions_dataset as dqa,
    )
    from openlineage.client.facet_v2 import (
        error_message_run,
        job_type_job,
        output_statistics_output_dataset,
    )

    run_facets = {}
    if error is not None:
        run_facets["errorMessage"] = error_message_run.ErrorMessageRunFacet(
            message=str(error), programmingLanguage="python"
        )

    def facets_for(ds: Dataset) -> dict:
        f = {}
        if ds.frame is not None:
            f["schema"] = _schema_facet(ds.frame)
        if ds.report is not None:
            f["dataQualityAssertions"] = dqa.DataQualityAssertionsDatasetFacet(
                assertions=[
                    dqa.Assertion(assertion=g.name, success=g.passed, column=g.column)
                    for g in ds.report.gates
                ]
            )
        return f

    complete = state == "COMPLETE"
    return RunEvent(
        eventType=getattr(RunState, state),
        eventTime=datetime.now(UTC).isoformat(),
        run=Run(runId=run.run_id, facets=run_facets),
        job=Job(
            namespace=NAMESPACE,
            name=run.name,
            facets={
                "jobType": job_type_job.JobTypeJobFacet(
                    processingType="BATCH", integration="CUSTOM", jobType="JOB"
                )
            },
        ),
        inputs=[
            InputDataset(namespace=d.namespace, name=d.name, facets=facets_for(d))
            for d in run.inputs
        ]
        if complete
        else [],
        outputs=[
            OutputDataset(
                namespace=d.namespace,
                name=d.name,
                facets=facets_for(d),
                outputFacets={
                    "outputStatistics": output_statistics_output_dataset.OutputStatisticsOutputDatasetFacet(
                        rowCount=len(d.frame)
                    )
                }
                if d.frame is not None
                else {},
            )
            for d in run.outputs
        ]
        if complete
        else [],
    )


@contextmanager
def job(name: str, **attributes: object) -> Iterator[JobRun]:
    """Trace a job, record its metrics and emit OpenLineage START/COMPLETE/FAIL."""
    run = JobRun(name=name, attributes=dict(attributes))
    client = _lineage_client()
    client.emit(_event(run, "START"))
    t0 = time.perf_counter()
    with _tracer.start_as_current_span(f"lakehouse.{name}") as span:
        span.set_attribute("openlineage.run_id", run.run_id)
        for k, v in attributes.items():
            span.set_attribute(f"lakehouse.{k}", str(v))
        try:
            yield run
        except BaseException as exc:
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            client.emit(_event(run, "FAIL", exc))
            raise
        finally:
            JOB_DURATION.record(time.perf_counter() - t0, {"pipeline_job": name})
        for ds in run.outputs:
            if ds.frame is not None:
                span.set_attribute(f"rows_out.{ds.name}", len(ds.frame))
            if ds.report is not None:
                span.set_attribute(f"quarantined.{ds.name}", ds.report.rows_quarantined)
                if not ds.report.passed:
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, f"quality gate failed: {ds.name}")
                    )
        client.emit(_event(run, "COMPLETE"))
