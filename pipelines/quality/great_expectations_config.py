"""
Great Expectations Configuration

Sets up Great Expectations context with:
- Data context configuration
- Datasource definitions
- Suite names
- Store directories
"""

import great_expectations as gx
from great_expectations.datasource import Datasource
from great_expectations.datasource.types import BatchKwargsType


def create_ge_context(
    store_path: str = "great_expectations",
    datasources: dict = None
) -> gx.context.BaseDataContext:
    """
    Create Great Expectations context.

    Args:
        store_path: Path to store GE files
        datasources: Dictionary of datasource configurations

    Returns:
        Great Expectations data context
    """
    # Initialize context
    context = gx.get_context()

    # Configure store paths
    context.filestore.set_store_path(store_path)

    # Add datasources
    if datasources:
        for name, config in datasources.items():
            context.add_datasource(**config)

    return context


def create_spark_datasource(
    context: gx.context.BaseDataContext,
    name: str,
    connection_string: str,
    batch_interval: int = 86400
) -> None:
    """
    Create Spark datasource for Delta Lake.

    Args:
        context: Great Expectations context
        name: Datasource name
        connection_string: Spark connection string
        batch_interval: Batch interval in seconds
    """
    context.add_datasource(
        name=name,
        module_name="great_expectations.datasource.data_connector",
        class_name="SparkDFDatasource",
        execution_engine="SparkExecutionEngine",
        data_connectors={
            "default_inferred_data_connector_name": {
                "class_name": "InferredAssetHtmlDataConnector",
                "base_directory": connection_string,
                "default_regex": {
                    "group_names": ["data_asset_name"],
                    "regex": r"(.* )"
                }
            }
        }
    )


def create_sql_datasource(
    context: gx.context.BaseDataContext,
    name: str,
    connection_string: str
) -> None:
    """
    Create SQL datasource.

    Args:
        context: Great Expectations context
        name: Datasource name
        connection_string: SQL connection string
    """
    context.add_datasource(
        name=name,
        module_name="great_expectations.datasource.datasource",
        class_name="Datasource",
        execution_engine="SQLAlchemyExecutionEngine",
        data_connectors={
            "default_runtime_data_connector_name": {
                "class_name": "RuntimeDataConnector",
                "batch_identifiers": ["natural_time"]
            }
        },
        credentials={
            "connection_string": connection_string
        }
    )


if __name__ == "__main__":
    # Example usage
    context = create_ge_context()
    print(f"Great Expectations context created at: {context.root_dir}")
