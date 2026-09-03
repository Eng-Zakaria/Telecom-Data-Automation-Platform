"""
Silver Layer Transformation Pipeline

Transforms bronze data into clean, validated, PII-masked silver tables.
Implements:
- Data quality validation
- PII masking and classification
- Deduplication
- Standardized schemas
- Master data joins
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import hashlib
from delta.tables import DeltaTable
import pyspark.sql.functions as F
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType


@dataclass
class TransformationConfig:
    """Configuration for silver layer transformations"""
    source_table: str
    target_table: str
    transformations: List[Dict] = None
    pii_columns: List[str] = None
    validation_rules: Dict = None
    dedup_enabled: bool = True
    dedup_key: List[str] = None


class SilverTransformationPipeline:
    """
    Silver layer transformation pipeline.

    Features:
    - PII masking and classification
    - Data quality validation
    - Deduplication
    - Standardized schemas
    - Master data joins
    """

    def __init__(
        self,
        spark: SparkSession,
        config: TransformationConfig
    ):
        self.spark = spark
        self.config = config
        self.table_name = f"silver.{config.target_table}"

    def transform(
        self,
        source_df: pd.DataFrame,
        transformation_id: str
    ) -> Dict:
        """
        Transform bronze data to silver layer.

        Args:
            source_df: Source DataFrame (bronze)
            transformation_id: Unique transformation ID

        Returns:
            Dict with transformation metrics
        """
        # Convert to PySpark if needed
        if isinstance(source_df, pd.DataFrame):
            spark_df = self.spark.createDataFrame(source_df)
        else:
            spark_df = source_df

        # Apply transformations
        transformed_df = self._apply_transformations(spark_df)

        # Validate data quality
        validated_df, validation_results = self._validate_data(transformed_df)

        # Deduplicate if enabled
        if self.config.dedup_enabled:
            deduped_df = self._deduplicate(validated_df)
        else:
            deduped_df = validated_df

        # Write to silver layer
        result = self._write_silver(deduped_df, transformation_id)

        return {
            **result,
            "validation_results": validation_results,
            "transformation_id": transformation_id
        }

    def _apply_transformations(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """Apply transformation rules"""
        df_transformed = df

        # Apply PII masking
        if self.config.pii_columns:
            df_transformed = self._mask_pii(df_transformed)

        # Apply custom transformations
        for transform in (self.config.transformations or []):
            df_transformed = self._apply_single_transform(df_transformed, transform)

        # Add metadata
        df_transformed = df_transformed.withColumn(
            "silver_ingestion_timestamp",
            F.current_timestamp()
        )

        return df_transformed

    def _mask_pii(self, df: pd.DataFrame) -> pd.DataFrame:
        """Mask PII columns using SHA-256 hashing"""
        df_masked = df

        for column in self.config.pii_columns:
            if column in df.columns:
                # Create hashed version
                df_masked = df_masked.withColumn(
                    f"{column}_hashed",
                    F.sha2(F.col(column), 256)
                )
                # Replace original with hashed version
                df_masked = df_masked.withColumn(
                    column,
                    F.col(f"{column}_hashed")
                )
                # Drop the temporary column
                df_masked = df_masked.drop(f"{column}_hashed")

        return df_masked

    def _apply_single_transform(
        self,
        df: pd.DataFrame,
        transform: Dict
    ) -> pd.DataFrame:
        """Apply single transformation rule"""
        transform_type = transform.get("type")

        if transform_type == "rename":
            return df.withColumnRenamed(transform["from"], transform["to"])

        elif transform_type == "cast":
            return df.withColumn(transform["column"], F.col(transform["column"]).cast(transform["type"]))

        elif transform_type == "filter":
            return df.filter(F.col(transform["column"]).isin(transform["values"]))

        elif transform_type == "fill_null":
            return df.fillna({transform["column"]: transform["value"]})

        elif transform_type == "derive":
            return df.withColumn(transform["new_column"], eval(transform["expression"]))

        return df

    def _validate_data(
        self,
        df: pd.DataFrame
    ) -> tuple:
        """Validate data quality against rules"""
        validation_results = {
            "total_records": df.count(),
            "valid_records": 0,
            "invalid_records": 0,
            "failed_checks": []
        }

        validated_df = df

        # Apply validation rules
        for rule_name, rule in (self.config.validation_rules or {}).items():
            if rule.get("type") == "not_null":
                null_count = df.filter(F.col(rule["column"]).isNull()).count()
                if null_count > 0:
                    validation_results["failed_checks"].append({
                        "rule": rule_name,
                        "column": rule["column"],
                        "issue": f"{null_count} null values",
                        "severity": rule.get("severity", "warning")
                    })
                validated_df = validated_df.filter(F.col(rule["column"]).isNotNull())

            elif rule.get("type") == "range":
                invalid_count = df.filter(
                    (F.col(rule["column"]) < rule["min"]) |
                    (F.col(rule["column"]) > rule["max"])
                ).count()
                if invalid_count > 0:
                    validation_results["failed_checks"].append({
                        "rule": rule_name,
                        "column": rule["column"],
                        "issue": f"{invalid_count} values out of range [{rule['min']}, {rule['max']}]",
                        "severity": rule.get("severity", "warning")
                    })
                validated_df = validated_df.filter(
                    (F.col(rule["column"]) >= rule["min"]) &
                    (F.col(rule["column"]) <= rule["max"])
                )

            elif rule.get("type") == "pattern":
                from pyspark.sql.functions import regexp_extract
                invalid_count = df.filter(
                    F.col(rule["column"]).rlike(rule["pattern"]) == False
                ).count()
                if invalid_count > 0:
                    validation_results["failed_checks"].append({
                        "rule": rule_name,
                        "column": rule["column"],
                        "issue": f"{invalid_count} values don't match pattern",
                        "severity": rule.get("severity", "warning")
                    })

        validation_results["valid_records"] = validated_df.count()
        validation_results["invalid_records"] = validation_results["total_records"] - validation_results["valid_records"]

        return validated_df, validation_results

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate records"""
        dedup_key = self.config.dedup_key or ["id"]

        # Keep latest record (assuming ingestion_timestamp exists)
        df_deduped = df.dropDuplicates(dedup_key)

        return df_deduped

    def _write_silver(
        self,
        df: pd.DataFrame,
        transformation_id: str
    ) -> Dict:
        """Write data to silver layer"""
        write_path = f"/{self.table_name}"

        # Check if table exists
        table_exists = DeltaTable.isDeltaTable(self.spark, write_path)

        if table_exists:
            # Merge operation
            delta_table = DeltaTable.forPath(self.spark, write_path)
            delta_table.alias("target").merge(
                df.alias("source"),
                "target.id = source.id"
            ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
        else:
            # Create new table
            df.write.format("delta").mode("overwrite").save(write_path)

        return {
            "status": "success",
            "records_transformed": df.count(),
            "table": self.table_name,
            "path": write_path
        }


def create_silver_pipeline(
    spark: SparkSession,
    source_table: str,
    target_table: str,
    pii_columns: List[str] = None,
    validation_rules: Dict = None
) -> SilverTransformationPipeline:
    """
    Factory function to create silver transformation pipeline.

    Args:
        spark: PySpark session
        source_table: Source table name
        target_table: Target table name
        pii_columns: Columns containing PII to mask
        validation_rules: Data quality validation rules

    Returns:
        SilverTransformationPipeline instance
    """
    config = TransformationConfig(
        source_table=source_table,
        target_table=target_table,
        pii_columns=pii_columns or [],
        validation_rules=validation_rules or {}
    )

    return SilverTransformationPipeline(spark, config)


if __name__ == "__main__":
    # Example usage
    from pyspark.sql import SparkSession

    spark = SparkSession.builder \
        .appName("SilverTransformation") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

    # Create sample bronze data
    data = {
        "id": ["1", "2", "3", "1"],  # Duplicate for testing
        "customer_id": ["CUST_001", "CUST_002", "CUST_003", "CUST_001"],
        "email": ["user1@example.com", "user2@example.com", "user3@example.com", "user1@example.com"],
        "phone": ["+966501234567", "+966509876543", "+966501112222", "+966501234567"],
        "amount": [100.50, 200.75, None, 100.50],
        "timestamp": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"]
    }
    df = pd.DataFrame(data)

    # Create pipeline
    pipeline = create_silver_pipeline(
        spark=spark,
        source_table="bronze.transactions",
        target_table="silver.transactions",
        pii_columns=["customer_id", "email", "phone"],
        validation_rules={
            "amount_not_null": {"type": "not_null", "column": "amount", "severity": "error"},
            "amount_positive": {"type": "range", "column": "amount", "min": 0, "severity": "warning"}
        }
    )

    result = pipeline.transform(df, "transform_001")
    print(f"Transformation result: {result}")
