"""
Data Quality Validation Module

Implements Great Expectations validation suites for each layer.
Provides:
- Automated schema validation
- Data quality checks
- Anomaly detection
- Alerting on failures
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import great_expectations as gx
from great_expectations.core import ExpectationSuite, ExpectationValidationResult
import great_expectations.checkpoint as gx_checkpoint


@dataclass
class ValidationResult:
    """Result of a validation run"""
    suite_name: str
    success: bool
    statistics: Dict
    expectations_results: List[Dict]
    run_time: datetime
    exception_info: Optional[str] = None


class DataQualityValidator:
    """
    Data quality validation engine.

    Features:
    - Great Expectations integration
    - Schema drift detection
    - Anomaly detection
    - Alerting capabilities
    - Result reporting
    """

    def __init__(
        self,
        ge_context: gx.context.BaseDataContext,
        suite_name: str = "telecom_quality_suite"
    ):
        self.ge_context = ge_context
        self.suite_name = suite_name
        self.validation_results = []

    def create_expectation_suite(self, table_name: str) -> ExpectationSuite:
        """Create expectation suite for a table"""
        suite = self.ge_context.open_expectation_suite(suite_name)
        suite_suite_name = f"{suite_name}_{table_name}"

        # Define expectations based on table type
        if "cdr" in table_name:
            expectations = self._create_cdr_expectations()
        elif "network" in table_name:
            expectations = self._create_network_expectations()
        elif "billing" in table_name:
            expectations = self._create_billing_expectations()
        else:
            expectations = self._create_generic_expectations()

        # Add expectations to suite
        for expectation in expectations:
            suite.add_expectation(expectation)

        # Save suite
        self.ge_context.save_expectation_suite(suite)

        return suite

    def _create_cdr_expectations(self) -> List:
        """Create CDR-specific expectations"""
        return [
            {
                "expectation_type": "expect_column_values_to_not_be_null",
                "kwargs": {"column": "call_sid"}
            },
            {
                "expectation_type": "expect_column_values_to_be_unique",
                "kwargs": {"column": "call_sid"}
            },
            {
                "expectation_type": "expect_column_values_to_match_regex",
                "kwargs": {
                    "column": "caller_id",
                    "regex": "^[a-f0-9]{16}$"
                }
            },
            {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {
                    "column": "duration_seconds",
                    "min_value": 0,
                    "max_value": 86400
                }
            },
            {
                "expectation_type": "expect_column_values_to_not_be_null",
                "kwargs": {"column": "start_time"}
            }
        ]

    def _create_network_expectations(self) -> List:
        """Create network KPI expectations"""
        return [
            {
                "expectation_type": "expect_column_values_to_not_be_null",
                "kwargs": {"column": "tower_id"}
            },
            {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {
                    "column": "rsrp_dbm",
                    "min_value": -140,
                    "max_value": -50
                }
            },
            {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {
                    "column": "sinr_db",
                    "min_value": -20,
                    "max_value": 30
                }
            },
            {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {
                    "column": "dropped_call_rate_pct",
                    "min_value": 0,
                    "max_value": 100
                }
            },
            {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {
                    "column": "congestion_pct",
                    "min_value": 0,
                    "max_value": 100
                }
            }
        ]

    def _create_billing_expectations(self) -> List:
        """Create billing expectations"""
        return [
            {
                "expectation_type": "expect_column_values_to_not_be_null",
                "kwargs": {"column": "customer_id"}
            },
            {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {
                    "column": "monthly_charge",
                    "min_value": 0,
                    "max_value": 10000
                }
            },
            {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {
                    "column": "total_charge",
                    "min_value": 0,
                    "max_value": 50000
                }
            },
            {
                "expectation_type": "expect_column_values_to_be_in_set",
                "kwargs": {
                    "column": "payment_status",
                    "value_set": ["paid", "pending", "overdue", "defaulted"]
                }
            }
        ]

    def _create_generic_expectations(self) -> List:
        """Create generic expectations for unknown tables"""
        return [
            {
                "expectation_type": "expect_table_row_count_to_be_between",
                "kwargs": {"min_value": 0}
            }
        ]

    def validate(
        self,
        dataframe: pd.DataFrame,
        table_name: str
    ) -> ValidationResult:
        """
        Validate DataFrame against expectations.

        Args:
            dataframe: DataFrame to validate
            table_name: Name of the table

        Returns:
            ValidationResult with success/failure and statistics
        """
        try:
            # Create validator
            validator = self.ge_context.get_validator(
                batch_parameters={"database": "sqlite://", "table_name": table_name}
            )

            # Add dataframe as batch
            validator.add_dataset(dataframe)

            # Run validation
            validation_result = validator.validate()

            # Extract results
            success = validation_result["success"]
            statistics = validation_result["statistics"]
            expectations_results = validation_result["results"]

            result = ValidationResult(
                suite_name=f"{self.suite_name}_{table_name}",
                success=success,
                statistics=statistics,
                expectations_results=expectations_results,
                run_time=datetime.now()
            )

            self.validation_results.append(result)
            return result

        except Exception as e:
            return ValidationResult(
                suite_name=f"{self.suite_name}_{table_name}",
                success=False,
                statistics={},
                expectations_results=[],
                run_time=datetime.now(),
                exception_info=str(e)
            )

    def detect_schema_drift(
        self,
        current_df: pd.DataFrame,
        baseline_df: pd.DataFrame,
        table_name: str
    ) -> Dict:
        """
        Detect schema drift between current and baseline data.

        Args:
            current_df: Current DataFrame
            baseline_df: Baseline DataFrame
            table_name: Name of the table

        Returns:
            Dict with drift information
        """
        drift_info = {
            "table_name": table_name,
            "drift_detected": False,
            "added_columns": [],
            "removed_columns": [],
            "type_changes": [],
            "block_deploy": False
        }

        current_cols = set(current_df.columns)
        baseline_cols = set(baseline_df.columns)

        # Check for added columns
        added = current_cols - baseline_cols
        if added:
            drift_info["drift_detected"] = True
            drift_info["added_columns"] = list(added)
            drift_info["block_deploy"] = True  # Block deployment on new columns

        # Check for removed columns
        removed = baseline_cols - current_cols
        if removed:
            drift_info["drift_detected"] = True
            drift_info["removed_columns"] = list(removed)
            drift_info["block_deploy"] = True  # Block deployment on missing columns

        # Check for type changes
        common_cols = current_cols & baseline_cols
        for col in common_cols:
            if current_df[col].dtype != baseline_df[col].dtype:
                drift_info["drift_detected"] = True
                drift_info["type_changes"].append({
                    "column": col,
                    "current_type": str(current_df[col].dtype),
                    "baseline_type": str(baseline_df[col].dtype)
                })
                drift_info["block_deploy"] = True

        return drift_info

    def get_alert_summary(self) -> Dict:
        """Get summary of recent validation alerts"""
        failed_validations = [
            r for r in self.validation_results
            if not r.success
        ]

        return {
            "total_validations": len(self.validation_results),
            "failed_validations": len(failed_validations),
            "recent_failures": [
                {
                    "suite": r.suite_name,
                    "time": r.run_time.isoformat(),
                    "stats": r.statistics
                }
                for r in failed_validations[-10:]  # Last 10 failures
            ]
        }


def create_quality_validator(
    data_context: gx.context.BaseDataContext = None,
    suite_name: str = "telecom_quality"
) -> DataQualityValidator:
    """
    Factory function to create data quality validator.

    Args:
        data_context: Great Expectations data context (creates new one if None)
        suite_name: Name of the expectation suite

    Returns:
        DataQualityValidator instance
    """
    if data_context is None:
        # Create in-memory context
        data_context = gx.get_context()

    return DataQualityValidator(data_context, suite_name)


if __name__ == "__main__":
    # Example usage
    import pandas as pd

    # Create validator
    validator = create_quality_validator()

    # Create sample data
    data = {
        "call_sid": ["CDR_001", "CDR_002", "CDR_003"],
        "caller_id": ["abc123", "def456", "ghi789"],
        "duration_seconds": [120, 60, 300],
        "start_time": ["2024-01-01", "2024-01-01", "2024-01-02"]
    }
    df = pd.DataFrame(data)

    # Validate
    result = validator.validate(df, "cdr_silver")
    print(f"Validation success: {result.success}")
    print(f"Statistics: {result.statistics}")
