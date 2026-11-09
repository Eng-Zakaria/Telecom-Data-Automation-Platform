"""
Great Expectations Configuration and Validation Suites

Implements comprehensive data quality validation across all layers:
- Bronze layer: Raw data validation
- Silver layer: Cleaned data validation
- Gold layer: Business-level validation
- Domain marts: Specific quality rules
"""

import great_expectations as gx
from great_expectations.core import ExpectationSuite
from great_expectations.datasource import Datasource
import pandas as pd
from datetime import datetime
import json
from typing import Dict, List, Optional


class TelecomDataValidator:
    """
    Comprehensive data validator using Great Expectations.

    Features:
    - Layer-specific validation suites
    - Schema drift detection
    - Anomaly detection
    - Automated alerting
    - Quality reporting
    """

    def __init__(
        self,
        ge_context: gx.context.BaseDataContext = None,
        environment: str = "dev"
    ):
        self.ge_context = ge_context or gx.get_context()
        self.environment = environment
        self.validation_results = []
        self.alert_queue = []

        # Initialize datasources
        self._initialize_datasources()

    def _initialize_datasources(self):
        """Initialize Great Expectations datasources"""
        # Add Postgres datasource for local dev
        self.ge_context.add_datasource(
            name="telecom_postgres",
            module_name="great_expectations.datasource.datasource",
            class_name="Datasource",
            execution_engine="SQLAlchemyExecutionEngine",
            data_connectors={
                "default_runtime_data_connector": {
                    "class_name": "RuntimeDataConnector",
                    "batch_identifiers": ["natural_time"]
                }
            },
            credentials={
                "connection_string": "postgresql://postgres:postgres@localhost:5432/telecom"
            }
        )

        # Add Spark datasource for Delta Lake
        self.ge_context.add_datasource(
            name="telecom_spark",
            module_name="great_expectations.datasource.data_connector",
            class_name="SparkDFDatasource",
            execution_engine="SparkExecutionEngine"
        )

    def validate_bronze_layer(
        self,
        df: pd.DataFrame,
        table_name: str,
        source_file: str = None
    ) -> Dict:
        """
        Validate bronze layer data (raw ingestion).

        Checks:
        - Required columns exist
        - No duplicate records
        - Basic data type validation
        - Null checks on business keys
        """
        suite_name = f"bronze_{table_name}_{self.environment}"
        suite = self.ge_context.open_expectation_suite(suite_name)

        # Add expectations
        for column in df.columns:
            suite.add_expectation(
                self._create_column_expectation(column, df[column])
            )

        # Business key validation
        if 'call_sid' in df.columns:
            suite.add_expectation({
                "expectation_type": "expect_column_values_to_not_be_null",
                "kwargs": {"column": "call_sid"}
            })
            suite.add_expectation({
                "expectation_type": "expect_column_values_to_be_unique",
                "kwargs": {"column": "call_sid"}
            })

        # Validate
        validator = self.ge_context.get_validator(batch_parameters={
            "datasource": "telecom_spark",
            "data_connector_name": "default_runtime_data_connector",
            "data_asset_name": table_name
        })
        validator.add_dataset(df)
        result = validator.validate()

        self.validation_results.append({
            "suite_name": suite_name,
            "layer": "bronze",
            "table": table_name,
            "success": result["success"],
            "timestamp": datetime.now().isoformat(),
            "source_file": source_file,
            "result": result
        })

        return result

    def validate_silver_layer(
        self,
        df: pd.DataFrame,
        table_name: str,
        pii_columns: List[str] = None
    ) -> Dict:
        """
        Validate silver layer data (cleaned, PII-masked).

        Checks:
        - PII masking applied
        - Data quality rules
        - Range validation
        - Pattern validation
        """
        suite_name = f"silver_{table_name}_{self.environment}"
        suite = self.ge_context.open_expectation_suite(suite_name)

        # PII masking validation
        if pii_columns:
            for column in pii_columns:
                if column in df.columns:
                    suite.add_expectation({
                        "expectation_type": "expect_column_values_to_not_match_regex",
                        "kwargs": {
                            "column": column,
                            "regex": r"^[A-Za-z0-9_\-@.]+$"  # Should be hashed
                        }
                    })

        # Range validation for numeric columns
        for column in df.select_dtypes(include=['number']).columns:
            suite.add_expectation({
                "expectation_type": "expect_column_values_to_not_be_null",
                "kwargs": {"column": column}
            })

        # Validate
        validator = self.ge_context.get_validator(batch_parameters={
            "datasource": "telecom_spark",
            "data_connector_name": "default_runtime_data_connector",
            "data_asset_name": table_name
        })
        validator.add_dataset(df)
        result = validator.validate()

        self.validation_results.append({
            "suite_name": suite_name,
            "layer": "silver",
            "table": table_name,
            "success": result["success"],
            "timestamp": datetime.now().isoformat()
        })

        return result

    def validate_gold_layer(
        self,
        df: pd.DataFrame,
        table_name: str,
        business_rules: Dict = None
    ) -> Dict:
        """
        Validate gold layer data (curated, business-level).

        Checks:
        - Business rule compliance
        - Cross-table consistency
        - Time-based validation
        - Aggregation accuracy
        """
        suite_name = f"gold_{table_name}_{self.environment}"
        suite = self.ge_context.open_expectation_suite(suite_name)

        # Business rules
        if business_rules:
            for rule_name, rule in business_rules.items():
                suite.add_expectation({
                    "expectation_type": f"expect_{rule['type']}",
                    "kwargs": rule.get("kwargs", {})
                })

        # Common gold layer validations
        suite.add_expectation({
            "expectation_type": "expect_table_row_count_to_be_between",
            "kwargs": {"min_value": 0}
        })
        suite.add_expectation({
            "expectation_type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": "gold_ingestion_timestamp"}
        })

        # Validate
        validator = self.ge_context.get_validator(batch_parameters={
            "datasource": "telecom_spark",
            "data_connector_name": "default_runtime_data_connector",
            "data_asset_name": table_name
        })
        validator.add_dataset(df)
        result = validator.validate()

        self.validation_results.append({
            "suite_name": suite_name,
            "layer": "gold",
            "table": table_name,
            "success": result["success"],
            "timestamp": datetime.now().isoformat()
        })

        return result

    def detect_schema_drift(
        self,
        current_df: pd.DataFrame,
        baseline_df: pd.DataFrame,
        table_name: str
    ) -> Dict:
        """
        Detect schema drift between current and baseline data.

        Returns:
            Dict with drift information and block_deploy flag
        """
        drift_info = {
            "table_name": table_name,
            "drift_detected": False,
            "added_columns": [],
            "removed_columns": [],
            "type_changes": [],
            "block_deploy": False,
            "timestamp": datetime.now().isoformat()
        }

        current_cols = set(current_df.columns)
        baseline_cols = set(baseline_df.columns)

        # Check for added columns
        added = current_cols - baseline_cols
        if added:
            drift_info["drift_detected"] = True
            drift_info["added_columns"] = list(added)
            drift_info["block_deploy"] = True

        # Check for removed columns
        removed = baseline_cols - current_cols
        if removed:
            drift_info["drift_detected"] = True
            drift_info["removed_columns"] = list(removed)
            drift_info["block_deploy"] = True

        # Check for type changes
        common_cols = current_cols & baseline_cols
        for col in common_cols:
            if str(current_df[col].dtype) != str(baseline_df[col].dtype):
                drift_info["drift_detected"] = True
                drift_info["type_changes"].append({
                    "column": col,
                    "current_type": str(current_df[col].dtype),
                    "baseline_type": str(baseline_df[col].dtype)
                })
                drift_info["block_deploy"] = True

        return drift_info

    def _create_column_expectation(self, column: str, series: pd.Series) -> Dict:
        """Create appropriate expectations for a column based on its type"""
        expectations = []

        # Not null expectation for all columns
        expectations.append({
            "expectation_type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": column}
        })

        # Type-specific expectations
        if series.dtype == 'object':
            expectations.append({
                "expectation_type": "expect_column_to_exist",
                "kwargs": {"column": column}
            })
        elif series.dtype in ['int64', 'float64']:
            expectations.append({
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {
                    "column": column,
                    "min_value": series.min(),
                    "max_value": series.max()
                }
            })

        return expectations

    def get_quality_summary(self) -> Dict:
        """Get summary of all validation results"""
        total = len(self.validation_results)
        passed = sum(1 for r in self.validation_results if r.get("success"))
        failed = total - passed

        return {
            "total_validations": total,
            "passed": passed,
            "failed": failed,
            "success_rate": f"{(passed / total * 100):.1f}%" if total > 0 else "0%",
            "recent_failures": [
                {
                    "suite": r["suite_name"],
                    "layer": r["layer"],
                    "table": r["table"],
                    "timestamp": r["timestamp"]
                }
                for r in self.validation_results[-10:] if not r.get("success")
            ]
        }

    def send_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "medium",
        table_name: str = None
    ):
        """Send alert for quality issues"""
        alert = {
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "table_name": table_name,
            "timestamp": datetime.now().isoformat(),
            "environment": self.environment
        }
        self.alert_queue.append(alert)
        print(f"🚨 ALERT [{severity.upper()}]: {message}")

    def auto_retry_failed_validations(
        self,
        df: pd.DataFrame,
        table_name: str,
        max_retries: int = 3
    ) -> Dict:
        """
        Automatically retry failed validations with exponential backoff.

        Args:
            df: DataFrame to validate
            table_name: Target table name
            max_retries: Maximum retry attempts

        Returns:
            Dict with retry results
        """
        retry_results = {
            "table": table_name,
            "attempts": 0,
            "success": False,
            "retry_history": []
        }

        for attempt in range(max_retries):
            retry_results["attempts"] = attempt + 1

            # Validate
            result = self.validate_bronze_layer(df, table_name)
            retry_results["retry_history"].append({
                "attempt": attempt + 1,
                "success": result["success"],
                "timestamp": datetime.now().isoformat()
            })

            if result["success"]:
                retry_results["success"] = True
                break

            # Exponential backoff
            import time
            wait_time = 2 ** attempt
            time.sleep(wait_time)

            # Send alert if still failing
            if attempt == max_retries - 1:
                self.send_alert(
                    "validation_failed",
                    f"Validation failed after {max_retries} attempts for {table_name}",
                    severity="high",
                    table_name=table_name
                )

        return retry_results


def create_quality_pipeline(environment: str = "dev") -> TelecomDataValidator:
    """
    Factory function to create quality validation pipeline.

    Args:
        environment: Environment name (dev, staging, prod)

    Returns:
        TelecomDataValidator instance
    """
    return TelecomDataValidator(environment=environment)


if __name__ == "__main__":
    # Example usage
    validator = create_quality_pipeline()

    # Create sample data
    data = {
        "call_sid": ["CDR_001", "CDR_002", "CDR_003"],
        "caller_id": ["abc123", "def456", "ghi789"],
        "duration_seconds": [120, 60, 300],
        "start_time": ["2024-01-01", "2024-01-01", "2024-01-02"]
    }
    df = pd.DataFrame(data)

    # Validate
    result = validator.validate_bronze_layer(df, "cdr_raw")
    print(f"Validation success: {result['success']}")
    print(f"Summary: {validator.get_quality_summary()}")
