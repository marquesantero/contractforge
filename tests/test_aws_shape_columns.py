"""AWS shape.columns projection rendering."""

from __future__ import annotations

from contractforge_aws import render_aws_contract


def _glue_job(columns: dict) -> str:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/events"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
            "shape": {"columns": columns},
        }
    )
    job = artifacts.artifacts["lake_bronze_events.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    return job


def test_columns_string_shorthand_is_alias() -> None:
    job = _glue_job({"payload.id": "order_id"})
    assert "df = df.select(" in job
    assert "F.col('payload.id').alias('order_id')," in job


def test_columns_expression_and_cast() -> None:
    job = _glue_job(
        {
            "total": {"expression": "price * quantity", "cast": "double", "alias": "total_amount"},
            "raw_id": {"cast": "string"},
        }
    )
    assert "F.expr('price * quantity').cast('double').alias('total_amount')," in job
    assert "F.col('raw_id').cast('string').alias('raw_id')," in job


def test_columns_default_alias_from_path() -> None:
    job = _glue_job({"payload.customer.id": {}})
    assert "F.col('payload.customer.id').alias('payload_customer_id')," in job
