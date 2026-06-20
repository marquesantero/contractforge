import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter
from contractforge_databricks.sources import delta_share_options, render_delta_share_python


def test_delta_share_options_require_profile_and_table() -> None:
    with pytest.raises(ValueError, match="profile_file"):
        delta_share_options({"type": "delta_share", "table": "share.schema.table"})
    with pytest.raises(ValueError, match="table"):
        delta_share_options({"type": "delta_share", "profile_file": "/Volumes/sec/profile.share"})


def test_render_delta_share_python_redacts_profile_review() -> None:
    code = render_delta_share_python(
        {
            "type": "delta_share",
            "profile_file": "/Volumes/sec/profile.share",
            "table": "share.schema.table",
        }
    )

    assert ".format('deltaSharing')" in code
    assert ".option('profileFile', '/Volumes/sec/profile.share')" in code
    assert ".option('table', 'share.schema.table')" in code


def test_databricks_bundle_renders_delta_share_artifact() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "delta_share",
                "profile_file": "/Volumes/sec/profile.share",
                "table": "share.schema.orders",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    artifacts = adapter.render_contract(contract)

    assert "main_bronze_orders.source_delta_share.py" in artifacts.artifacts
