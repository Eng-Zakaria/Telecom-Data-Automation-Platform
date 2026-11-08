"""Streaming path: CDRs go through Event Hubs (the emulator locally) and are landed
into bronze in micro-batches, exactly like a Stream Analytics / Databricks
Structured Streaming job would.

The consumer uses a dedicated consumer group ("bronze-writer") so it can replay from
the start of the retention window without disturbing other readers.
"""

from __future__ import annotations

import json
import threading
import time

import pandas as pd
from cloudkit import eventhub_consumer, eventhub_producer

from . import observe

HUB = "cdr-stream"
CONSUMER_GROUP = "bronze-writer"


def publish(df: pd.DataFrame, batch_id: str, hub: str = HUB) -> int:
    from azure.eventhub import EventData

    sent = 0
    with (
        observe.job("stream.publish", hub=hub, batch_id=batch_id) as run,
        eventhub_producer(hub) as producer,
    ):
        batch = producer.create_batch()
        for rec in df.to_dict(orient="records"):
            payload = json.dumps({**rec, "_batch_id": batch_id}, default=str)
            try:
                batch.add(EventData(payload))
            except ValueError:  # batch full: ship it and start a new one
                producer.send_batch(batch)
                batch = producer.create_batch()
                batch.add(EventData(payload))
            sent += 1
        if len(batch):
            producer.send_batch(batch)
        run.read(observe.Dataset("generator://cdr", "cdr", df))
        run.wrote(observe.Dataset(f"eventhubs://{hub}", hub, df))
    return sent


def consume(batch_id: str, expected: int, timeout_s: float = 60, hub: str = HUB) -> pd.DataFrame:
    """Read this batch's events from the hub (all partitions) until `expected` arrive."""
    rows: list[dict] = []
    done = threading.Event()
    client = eventhub_consumer(hub, consumer_group=CONSUMER_GROUP)

    def on_event_batch(partition_context, events):
        for ev in events:
            rec = json.loads(ev.body_as_str())
            if rec.get("_batch_id") == batch_id:
                rows.append(rec)
        if len(rows) >= expected:
            done.set()

    with observe.job("stream.consume", hub=hub, batch_id=batch_id) as run:
        worker = threading.Thread(
            target=client.receive_batch,
            kwargs={
                "on_event_batch": on_event_batch,
                "starting_position": "-1",
                "max_batch_size": 500,
            },
            daemon=True,
        )
        worker.start()
        deadline = time.monotonic() + timeout_s
        while not done.is_set() and time.monotonic() < deadline:
            done.wait(0.5)
        client.close()
        worker.join(timeout=10)
        df = pd.DataFrame(rows).drop(columns=["_batch_id"], errors="ignore")
        if "start_time" in df:
            df["start_time"] = pd.to_datetime(df["start_time"])
        run.read(observe.Dataset(f"eventhubs://{hub}", hub, df))
        if len(rows) < expected:
            raise TimeoutError(f"received {len(rows)}/{expected} events from {hub} in {timeout_s}s")
        return df
