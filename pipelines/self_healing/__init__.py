"""
Self-Healing Pipeline Module

Implements automated quarantine and reprocessing of bad records.
Features:
- Automatic detection of data quality issues
- Quarantine to dead-letter tables
- Automatic retry with configurable backoff
- Alerting on persistent failures
- Manual review queue
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import pandas as pd
from delta.tables import DeltaTable
import pyspark.sql.functions as F
from pyspark.sql import SparkSession


@dataclass
class QuarantinePolicy:
    """Policy for quarantining bad records"""
    table_name: str
    dead_letter_table: str
    max_retry_count: int = 3
    retry_delay_hours: int = 24
    alert_threshold: int = 10  # Alert if more than N failures
    quarantine_reasons: List[str] = field(default_factory=list)


class SelfHealingPipeline:
    """
    Self-healing pipeline for data quality issues.

    Features:
    - Automatic quarantine of bad records
    - Retry logic with backoff
    - Persistent failure detection
    - Alert generation
    - Manual review queue
    """

    def __init__(
        self,
        spark: SparkSession,
        policies: Dict[str, QuarantinePolicy]
    ):
        self.spark = spark
        self.policies = policies
        self.alert_queue = []

    def process_batch(
        self,
        df: pd.DataFrame,
        table_name: str,
        validation_fn=None
    ) -> Dict:
        """
        Process a batch with self-healing logic.

        Args:
            df: Input DataFrame
            table_name: Target table name
            validation_fn: Optional validation function

        Returns:
            Dict with processing metrics
        """
        policy = self.policies.get(table_name)
        if not policy:
            return {
                "status": "no_policy",
                "table": table_name,
                "records_processed": len(df)
            }

        # Validate if function provided
        if validation_fn:
            valid_df, invalid_df = validation_fn(df)
        else:
            # Default validation: check for nulls in required fields
            required_fields = self._get_required_fields(table_name)
            invalid_mask = df[required_fields].isnull().any(axis=1)
            valid_df = df[~invalid_mask]
            invalid_df = df[invalid_mask]

        # Quarantine invalid records
        if len(invalid_df) > 0:
            self._quarantine(invalid_df, table_name, policy)

        # Insert valid records
        success_count = self._insert_valid(valid_df, table_name)

        return {
            "status": "success" if len(invalid_df) == 0 else "partial",
            "table": table_name,
            "total_records": len(df),
            "valid_records": len(valid_df),
            "invalid_records": len(invalid_df),
            "quarantined": len(invalid_df) > 0
        }

    def _get_required_fields(self, table_name: str) -> List[str]:
        """Get list of required fields for a table"""
        required_fields_map = {
            "cdr": ["call_sid", "caller_id", "callee_id", "start_time"],
            "network_kpi": ["tower_id", "timestamp"],
            "billing": ["customer_id", "billing_month"],
            "roaming": ["session_id", "customer_id", "partner_id"]
        }
        return required_fields_map.get(table_name, ["id"])

    def _quarantine(
        self,
        df: pd.DataFrame,
        table_name: str,
        policy: QuarantinePolicy
    ):
        """Quarantine invalid records to dead-letter table"""
        # Add quarantine metadata
        quarantine_df = df.withColumn(
            "quarantine_timestamp",
            F.current_timestamp()
        ).withColumn(
            "quarantine_reason",
            F.lit(f"Auto-quarantined: {len(df)} invalid records")
        ).withColumn(
            "retry_count",
            F.lit(0)
        ).withColumn(
            "next_retry_time",
            F.date_add(F.current_date(), policy.retry_delay_hours // 24)
        )

        # Write to dead-letter table
        dead_letter_path = f"/{policy.dead_letter_table}"
        quarantine_df.write.format("delta").mode("append").save(dead_letter_path)

        # Check if alert threshold reached
        failure_count = self._count_recent_failures(table_name, policy.alert_threshold)
        if failure_count >= policy.alert_threshold:
            self._send_alert(table_name, failure_count)

    def _insert_valid(
        self,
        df: pd.DataFrame,
        table_name: str
    ) -> int:
        """Insert valid records into target table"""
        # Check if table exists
        table_path = f"/{table_name}"
        table_exists = DeltaTable.isDeltaTable(self.spark, table_path)

        if table_exists:
            # Merge operation
            delta_table = DeltaTable.forPath(self.spark, table_path)
            # Use business key for merge
            merge_keys = ["id"]  # Default, should be configured per table
            delta_table.alias("target").merge(
                df.alias("source"),
                " AND ".join([f"target.{key} = source.{key}" for key in merge_keys])
            ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
        else:
            # Create new table
            df.write.format("delta").mode("overwrite").save(table_path)

        return len(df)

    def _count_recent_failures(
        self,
        table_name: str,
        threshold: int
    ) -> int:
        """Count recent failures for a table"""
        policy = self.policies.get(table_name)
        if not policy:
            return 0

        dead_letter_path = f"/{policy.dead_letter_table}"
        try:
            df = self.spark.read.format("delta").load(dead_letter_path)
            recent = df.filter(
                F.col("quarantine_timestamp") > F.date_sub(F.current_timestamp(), 24 * 3600)
            )
            return recent.count()
        except:
            return 0

    def _send_alert(
        self,
        table_name: str,
        failure_count: int
    ):
        """Send alert for persistent failures"""
        alert = {
            "alert_type": "persistent_failure",
            "table": table_name,
            "failure_count": failure_count,
            "timestamp": datetime.now().isoformat(),
            "message": f"Table {table_name} has {failure_count} failures in last 24 hours"
        }
        self.alert_queue.append(alert)
        print(f"🚨 ALERT: {alert['message']}")

    def retry_quarantined_records(
        self,
        table_name: str,
        max_retries: int = None
    ) -> Dict:
        """
        Retry previously quarantined records.

        Args:
            table_name: Target table name
            max_retries: Maximum retry count override

        Returns:
            Dict with retry metrics
        """
        policy = self.policies.get(table_name)
        if not policy:
            return {"status": "no_policy", "table": table_name}

        dead_letter_path = f"/{policy.dead_letter_table}"
        max_retry = max_retries or policy.max_retry_count

        # Read quarantined records
        try:
            quarantine_df = self.spark.read.format("delta").load(dead_letter_path)

            # Filter records eligible for retry
            retry_df = quarantine_df.filter(
                (F.col("retry_count") < max_retry) &
                (F.col("next_retry_time") <= F.current_date())
            )

            if retry_df.count() == 0:
                return {
                    "status": "no_retries",
                    "table": table_name,
                    "records_eligible": 0
                }

            # Process retries
            retry_df_processed = self._process_retry_batch(retry_df, table_name)

            # Update retry count
            updated_df = retry_df_processed.withColumn(
                "retry_count",
                F.col("retry_count") + 1
            )

            # Write back to dead-letter (updated)
            from delta.tables import DeltaTable
            dead_letter_table = DeltaTable.forPath(self.spark, dead_letter_path)
            dead_letter_table.alias("target").merge(
                updated_df.alias("source"),
                "target.call_sid = source.call_sid"  # Adjust key as needed
            ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

            return {
                "status": "success",
                "table": table_name,
                "records_retried": retry_df.count(),
                "records_inserted": retry_df_processed.count()
            }

        except Exception as e:
            return {
                "status": "error",
                "table": table_name,
                "error": str(e)
            }

    def _process_retry_batch(
        self,
        df: pd.DataFrame,
        table_name: str
    ) -> pd.DataFrame:
        """Process a batch of retry records"""
        # Re-run validation
        validation_fn = self._get_validation_fn(table_name)
        if validation_fn:
            valid_df, _ = validation_fn(df)
            return valid_df
        return df

    def _get_validation_fn(self, table_name: str) -> Optional[callable]:
        """Get validation function for a table"""
        # This would be configured per table
        return None

    def get_alerts(self) -> List[Dict]:
        """Get all pending alerts"""
        return self.alert_queue


def create_self_healing_pipeline(
    spark: SparkSession,
    policies: Dict[str, QuarantinePolicy]
) -> SelfHealingPipeline:
    """
    Factory function to create self-healing pipeline.

    Args:
        spark: PySpark session
        policies: Dictionary of quarantine policies

    Returns:
        SelfHealingPipeline instance
    """
    return SelfHealingPipeline(spark, policies)


if __name__ == "__main__":
    # Example usage
    from pyspark.sql import SparkSession

    spark = SparkSession.builder \
        .appName("SelfHealingPipeline") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

    # Define policies
    policies = {
        "cdr": QuarantinePolicy(
            table_name="cdr",
            dead_letter_table="cdr_deadletter",
            max_retry_count=3,
            retry_delay_hours=24,
            alert_threshold=10
        ),
        "network_kpi": QuarantinePolicy(
            table_name="network_kpi",
            dead_letter_table="network_kpi_deadletter",
            max_retry_count=2,
            retry_delay_hours=12,
            alert_threshold=5
        )
    }

    # Create pipeline
    pipeline = create_self_healing_pipeline(spark, policies)
    print("Self-healing pipeline created")
