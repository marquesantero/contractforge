import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.sources import interpret_incremental_files_source, is_incremental_file_source, render_source_artifacts


def test_interpret_incremental_files_maps_core_options_to_cloudfiles() -> None:
    interpreted = interpret_incremental_files_source(
        {
            "type": "incremental_files",
            "path": "s3://bucket/events",
            "format": "json",
            "schema_tracking_location": "s3://bucket/_schemas/events",
            "progress_location": "s3://bucket/_progress/events",
            "max_files_per_trigger": 100,
            "options": {"infer_column_types": True, "rescued_data_column": "_rescued"},
        }
    )

    assert interpreted["options"]["cloudFiles.inferColumnTypes"] == "true"
    assert interpreted["options"]["cloudFiles.maxFilesPerTrigger"] == "100"
    assert interpreted["options"]["rescued_data_column"] == "_rescued"
    assert "infer_column_types" not in interpreted["options"]


def test_environment_parameters_feed_databricks_source_interpretation() -> None:
    env = DatabricksEnvironment.from_contract(
        {
            "name": "prod",
            "adapter": "databricks",
            "parameters": {"databricks": {"incremental_files.infer_column_types": True}},
        }
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "incremental_files", "path": "s3://bucket/events", "format": "json"},
            "target": {"catalog": "main", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
        }
    )

    artifacts = render_source_artifacts(contract, environment=env)

    assert ".option('cloudFiles.inferColumnTypes', 'true')" in artifacts["main_bronze_events.source_autoloader.py"]


def test_file_stream_intent_maps_to_databricks_incremental_files() -> None:
    source = {
        "type": "s3",
        "intent": "file_stream",
        "path": "s3://bucket/events",
        "format": "json",
        "state": {
            "storage": "external",
            "location": {"type": "object_storage", "path": "s3://bucket/_progress/events"},
        },
    }

    interpreted = interpret_incremental_files_source(source)

    assert is_incremental_file_source(source) is True
    assert interpreted["type"] == "incremental_files"
    assert interpreted["path"] == "s3://bucket/events"
    assert interpreted["progress_location"] == "s3://bucket/_progress/events"


def test_file_stream_intent_requires_path_for_databricks_autoloader() -> None:
    with pytest.raises(ValueError, match="file_stream source requires source.path"):
        interpret_incremental_files_source({"type": "s3", "intent": "file_stream", "format": "json"})
