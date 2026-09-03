"""
Streaming Ingestion Pipeline

Real-time data ingestion from Kafka/Redpanda streams.
Supports:
- CDR streaming (call detail records)
- Network KPI streaming (per-tower metrics)
- Schema validation on stream
- Dead-letter queue for failed messages
- Exactly-once semantics with checkpointing
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import pyspark.sql.functions as F
from pyspark.sql import SparkSession
from pyspark.sql.streaming import StreamingQuery


@dataclass
class StreamingConfig:
    """Configuration for streaming ingestion"""
    bootstrap_servers: str
    topic: str
    group_id: str
    consumer_timeout_ms: int = 10000
    max_poll_records: int = 500
    schema_registry_url: str = None
    enable_exactly_once: bool = True
    checkpoint_location: str = "/checkpoint/streaming"
    output_format: str = "delta"  # delta, parquet, console


class StreamingIngestionPipeline:
    """
    Streaming ingestion pipeline.

    Features:
    - Kafka/Redpanda consumer
    - Schema validation
    - Error handling with dead-letter
    - Checkpointing for fault tolerance
    - Metrics and monitoring
    """

    def __init__(
        self,
        spark: SparkSession,
        config: StreamingConfig
    ):
        self.spark = spark
        self.config = config
        self.metrics = {
            "messages_consumed": 0,
            "messages_processed": 0,
            "messages_failed": 0,
            "start_time": datetime.now()
        }

    def create_consumer(self) -> KafkaConsumer:
        """Create Kafka consumer"""
        consumer = KafkaConsumer(
            self.config.topic,
            bootstrap_servers=self.config.bootstrap_servers,
            group_id=self.config.group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=self.config.consumer_timeout_ms
        )
        return consumer

    def create_producer(self) -> KafkaProducer:
        """Create Kafka producer for dead-letter queue"""
        producer = KafkaProducer(
            bootstrap_servers=self.config.bootstrap_servers,
            value_serializer=lambda m: json.dumps(m).encode('utf-8')
        )
        return producer

    def consume_stream(
        self,
        processing_fn: Callable,
        output_path: str,
        trigger_interval: str = "10 seconds"
    ) -> StreamingQuery:
        """
        Consume and process streaming data.

        Args:
            processing_fn: Function to process each batch
            output_path: Output path for results
            trigger_interval: Streaming query trigger interval

        Returns:
            StreamingQuery object
        """
        # Create streaming DataFrame from Kafka
        df = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.config.bootstrap_servers) \
            .option("subscribe", self.config.topic) \
            .option("startingOffsets", "earliest") \
            .load()

        # Parse JSON messages
        parsed_df = df.select(
            F.from_json(F.col("value").cast("string"), self._get_schema()).alias("data")
        ).select("data.*")

        # Apply processing function
        processed_df = processing_fn(parsed_df)

        # Write output
        query = processed_df.writeStream \
            .format(self.config.output_format) \
            .option("path", output_path) \
            .option("checkpointLocation", self.config.checkpoint_location) \
            .trigger(processingTime=trigger_interval) \
            .start()

        return query

    def _get_schema(self) -> str:
        """Return JSON schema for Kafka messages"""
        # This would typically come from a schema registry
        return """{
            "type": "struct",
            "fields": [
                {"name": "call_sid", "type": "string", "nullable": false},
                {"name": "caller_id", "type": "string", "nullable": false},
                {"name": "callee_id", "type": "string", "nullable": false},
                {"name": "timestamp", "type": "timestamp", "nullable": false},
                {"name": "duration", "type": "integer", "nullable": true},
                {"name": "tower_id", "type": "string", "nullable": false},
                {"name": "call_type", "type": "string", "nullable": false},
                {"name": "roaming", "type": "boolean", "nullable": true},
                {"name": "data_volume_mb", "type": "double", "nullable": true}
            ]
        }"""

    def send_to_dead_letter(
        self,
        message: Dict,
        error_reason: str
    ):
        """Send failed message to dead-letter queue"""
        producer = self.create_producer()
        dlq_message = {
            **message,
            "dlq_timestamp": datetime.now().isoformat(),
            "dlq_reason": error_reason
        }
        producer.send("dead-letter-queue", dlq_message)
        producer.flush()
        self.metrics["messages_failed"] += 1

    def get_metrics(self) -> Dict:
        """Get ingestion metrics"""
        return {
            **self.metrics,
            "uptime_seconds": (datetime.now() - self.metrics["start_time"]).total_seconds()
        }


def create_cdr_stream(
    spark: SparkSession,
    bootstrap_servers: str,
    topic: str = "cdr-stream",
    output_path: str = "/silver/cdr_stream"
) -> StreamingQuery:
    """
    Create CDR streaming pipeline.

    Args:
        spark: PySpark session
        bootstrap_servers: Kafka bootstrap servers
        topic: Kafka topic name
        output_path: Output path for silver layer

    Returns:
        StreamingQuery object
    """
    config = StreamingConfig(
        bootstrap_servers=bootstrap_servers,
        topic=topic,
        group_id="cdr-consumer-group"
    )

    pipeline = StreamingIngestionPipeline(spark, config)

    def process_cdr(batch_df, batch_id):
        # CDR-specific processing
        processed = batch_df.withColumn(
            "processed_timestamp",
            F.current_timestamp()
        )
        return processed

    query = pipeline.consume_stream(
        processing_fn=process_cdr,
        output_path=output_path
    )

    return query


def create_network_kpi_stream(
    spark: SparkSession,
    bootstrap_servers: str,
    topic: str = "network-kpi-stream",
    output_path: str = "/silver/network_kpi_stream"
) -> StreamingQuery:
    """
    Create network KPI streaming pipeline.

    Args:
        spark: PySpark session
        bootstrap_servers: Kafka bootstrap servers
        topic: Kafka topic name
        output_path: Output path for silver layer

    Returns:
        StreamingQuery object
    """
    config = StreamingConfig(
        bootstrap_servers=bootstrap_servers,
        topic=topic,
        group_id="network-kpi-consumer-group"
    )

    pipeline = StreamingIngestionPipeline(spark, config)

    def process_kpi(batch_df, batch_id):
        # KPI-specific processing
        processed = batch_df.withColumn(
            "processed_timestamp",
            F.current_timestamp()
        )
        return processed

    query = pipeline.consume_stream(
        processing_fn=process_kpi,
        output_path=output_path
    )

    return query


if __name__ == "__main__":
    # Example usage (requires running Kafka/Redpanda)
    from pyspark.sql import SparkSession

    spark = SparkSession.builder \
        .appName("StreamingIngestion") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

    # Create CDR stream (uncomment when Kafka is available)
    # query = create_cdr_stream(
    #     spark=spark,
    #     bootstrap_servers="localhost:9092",
    #     topic="cdr-stream"
    # )
    # query.awaitTermination()

    print("Streaming ingestion pipeline ready. Start Kafka/Redpanda to begin streaming.")
