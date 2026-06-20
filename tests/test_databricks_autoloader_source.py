import pytest

from contractforge_databricks.sources import render_autoloader_python


def test_render_incremental_files_as_autoloader() -> None:
    code = render_autoloader_python(
        {
            "type": "incremental_files",
            "path": "s3://bucket/landing/events",
            "format": "json",
            "schema_tracking_location": "s3://bucket/_schemas/events",
            "progress_location": "s3://bucket/_progress/events",
            "options": {"cloudFiles.inferColumnTypes": "true"},
        }
    )

    assert ".format('cloudFiles')" in code
    assert ".option('cloudFiles.format', 'json')" in code
    assert ".option('cloudFiles.schemaLocation', 's3://bucket/_schemas/events')" in code
    assert "checkpoint_location = 's3://bucket/_progress/events'" in code


def test_render_autoloader_rejects_platform_specific_alias() -> None:
    with pytest.raises(ValueError, match="source.type incremental_files"):
        render_autoloader_python({"type": "autoloader", "path": "/Volumes/main/landing/orders", "format": "parquet"})


def test_autoloader_render_rejects_other_source_types() -> None:
    with pytest.raises(ValueError, match="requires source.type"):
        render_autoloader_python({"type": "jdbc", "table": "public.orders"})
