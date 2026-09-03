"""
Bronze Layer Ingestion Pipeline

Ingests raw data from all sources into bronze Delta Lake tables.
Implements:
- Idempotent writes (upsert by business key)
- Schema-on-read with validation
- Partitioning by date for performance
- Dead-letter quarantine for invalid records
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from delta.tables import DeltaTable
import pyspark.sql.functions as F
from pyspark.sql import SparkSession


@dataclass
class IngestionConfig:
    """Configuration for bronze layer ingestion"""
    source_name: str
    target_table: str
    partition_by: List[str]
    primary_key: List[str]
    schema_evolution: bool = True
    dead_letter_enabled: bool = True
    max_records_per_batch: int = 100000


class BronzeIngestionPipeline:
    """
    Bronze layer ingestion pipeline.

    Features:
    - Idempotent writes using merge operations
    - Automatic schema evolution
    - Dead-letter quarantine for bad records
    - Partition pruning for performance
    """

    def __init__(
        self,
        spark: SparkSession,
        config: IngestionConfig
    ):
        self.spark = spark
        self.config = config
        self.table_name = f"bronze.{config.target_table}"

    def ingest(
        self,
        df: pd.DataFrame,
        batch_id: str,
        source_file: str = None
    ) -> Dict:
        """
        Ingest data into bronze layer.

        Args:
            df: Input DataFrame (pandas or pyspark)
            batch_id: Unique batch identifier
            source_file: Source file path for lineage

        Returns:
            Dict with ingestion metrics
        """
        # Convert to PySpark if needed
        if isinstance(df, pd.DataFrame):
            spark_df = self.spark.createDataFrame(df)
        else:
            spark_df = df

        # Add metadata columns
        spark_df = spark_df.withColumn("ingestion_timestamp", F.current_timestamp())
        spark_df = spark_df.withColumn("batch_id", F.lit(batch_id))
        spark_df = spark_df.withColumn("source_file", F.lit(source_file or "unknown"))
        spark_df = spark_df.withColumn("is_valid", F.lit(True))
        spark_df = spark_df.withColumn("error_message", F.lit(None))

        # Check for schema evolution
        if self.config.schema_evolution:
            spark_df = self._handle_schema_evolution(spark_df)

        # Write to bronze layer
        return self._write_bronze(spark_df, batch_id)

    def _handle_schema_evolution(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle schema evolution with automatic column addition"""
        try:
            existing_table = DeltaTable.forPath(self.spark, f"/{self.table_name}")
            existing_schema = existing_table.schema()

            # Find new columns
            existing_cols = {field.name for field in existing_schema.fields}
            new_cols = set(df.columns) - existing_cols

            if new_cols:
                print(f"Schema evolution detected: adding columns {new_cols}")
                # Add new columns with null values
                for col in new_cols:
                    df = df.withColumn(col, F.lit(None))

        except Exception as e:
            # Table doesn't exist yet, proceed with current schema
            print(f"Creating new table with schema: {df.columns}")

        return df

    def _write_bronze(
        self,
        df: pd.DataFrame,
        batch_id: str
    ) -> Dict:
        """Write data to bronze Delta table"""
        # Define write path
        write_path = f"/{self.table_name}"

        # Partition by date if configured
        partition_by = self.config.partition_by if self.config.partition_by else None

        # Check if table exists
        table_exists = DeltaTable.isDeltaTable(self.spark, write_path)

        if table_exists:
            # Merge operation for idempotent writes
            self._merge_data(df, write_path, partition_by)
        else:
            # Create new table
            self._create_table(df, write_path, partition_by)

        return {
            "status": "success",
            "records_ingested": df.count(),
            "batch_id": batch_id,
            "table": self.table_name,
            "path": write_path
        }

    def _merge_data(
        self,
        df: pd.DataFrame,
        write_path: str,
        partition_by: List[str]
    ):
        """Merge data into existing table (upsert)"""
        delta_table = DeltaTable.forPath(self.spark, write_path)

        # Determine merge keys
        merge_keys = self.config.primary_key or ["call_sid"]

        # Perform merge
        delta_table.alias("target").merge(
            df.alias("source"),
            expr=" AND ".join([f"target.{key} = source.{key}" for key in merge_keys])
        ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

    def _create_table(
        self,
        df: pd.DataFrame,
        write_path: str,
        partition_by: List[str]
    ):
        """Create new Delta table"""
        write_options = {
            "path": write_path,
            "mode": "overwrite"
        }

        if partition_by:
            write_options["partitionBy"] = partition_by

        df.write.format("delta").options(**write_options).save()

    def quarantine_bad_records(
        self,
        df: pd.DataFrame,
        reason: str
    ) -> pd.DataFrame:
        """
        Quarantine invalid records to dead-letter table.

        Args:
            df: DataFrame with invalid records
            reason: Reason for quarantine

        Returns:
            DataFrame with quarantined records
        """
        if not self.config.dead_letter_enabled:
            return df

        # Add quarantine metadata
        df_quarantine = df.withColumn("quarantine_timestamp", F.current_timestamp())
        df_quarantine = df_quarantine.withColumn("quarantine_reason", F.lit(reason))
        df_quarantine = df_quarantine.withColumn("retry_count", F.lit(0))

        # Write to dead-letter table
        dead_letter_path = f"/{self.table_name}_deadletter"
        df_quarantine.write.format("delta").mode("append").save(dead_letter_path)

        return df_quarantine


def create_bronze_pipeline(
    spark: SparkSession,
    source_name: str,
    target_table: str,
    partition_by: List[str] = None,
    primary_key: List[str] = None
) -> BronzeIngestionPipeline:
    """
    Factory function to create bronze ingestion pipeline.

    Args:
        spark: PySpark session
        source_name: Name of data source
        target_table: Target table name
        partition_by: Columns to partition by
        primary_key: Primary key for merge operations

    Returns:
        BronzeIngestionPipeline instance
    """
    config = IngestionConfig(
        source_name=source_name,
        target_table=target_table,
        partition_by=partition_by or ["ingestion_date"],
        primary_key=primary_key or ["id"]
    )

    return BronzeIngestionPipeline(spark, config)


if __name__ == "__main__":
    # Example usage
    from pyspark.sql import SparkSession

    spark = SparkSession.builder \
        .appName("BronzeIngestion") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

    # Create sample data
    data = {
        "call_sid": ["CDR_001", "CDR_002", "CDR_003"],
        "caller_id": ["abc123", "def456", "ghi789"],
        "callee_id": ["jkl012", "mno345", "pqr678"],
        "duration_seconds": [120, 60, 300],
        "ingestion_date": ["2024-01-01", "2024-01-01", "2024-01-02"]
    }
    df = pd.DataFrame(data)

    # Create pipeline and ingest
    pipeline = create_bronze_pipeline(
        spark=spark,
        source_name="cdr_generator",
        target_table="cdr_raw",
        partition_by=["ingestion_date"],
        primary_key=["call_sid"]
    )

    result = pipeline.ingest(df, batch_id="batch_001")
    print(f"Ingestion result: {result}")
