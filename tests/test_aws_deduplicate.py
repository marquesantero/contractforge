"""AWS transform.deduplicate rendering (Window + row_number)."""

from __future__ import annotations

from contractforge_aws import render_aws_contract


def _dedup_contract(deduplicate: dict) -> dict:
    return {
        "source": {"type": "parquet", "path": "s3://landing/orders"},
        "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
        "mode": "scd0_append",
        "transform": {"deduplicate": deduplicate},
    }


def _glue_job(deduplicate: dict) -> str:
    artifacts = render_aws_contract(_dedup_contract(deduplicate))
    job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    return job


def test_dedup_list_order_by_asc_and_desc() -> None:
    job = _glue_job(
        {
            "keys": ["order_id", "region"],
            "order_by": [
                {"column": "updated_at", "direction": "desc"},
                {"column": "ingested_at", "direction": "asc", "nulls": "first"},
            ],
        }
    )
    assert "deduplicate_keys = ['order_id', 'region']" in job
    assert (
        "Window.partitionBy(*deduplicate_keys).orderBy(F.col('updated_at').desc(), F.col('ingested_at').asc_nulls_first())"
        in job
    )


def test_dedup_string_order_by_is_parsed() -> None:
    job = _glue_job({"keys": "order_id", "order_by": "updated_at DESC NULLS LAST"})
    assert "deduplicate_keys = ['order_id']" in job
    assert "orderBy(F.col('updated_at').desc_nulls_last())" in job


def test_dedup_string_order_by_expression_is_review_only() -> None:
    artifacts = render_aws_contract(_dedup_contract({"keys": ["order_id"], "order_by": "length(payload) DESC"}))
    assert "lake_bronze_orders.glue_job.py" not in artifacts.artifacts
    assert "lake_bronze_orders.glue_job.todo.md" in artifacts.artifacts


def test_dedup_guards_missing_keys_at_runtime() -> None:
    job = _glue_job({"keys": ["order_id"], "order_by": [{"column": "updated_at"}]})
    assert "missing_deduplicate_keys" in job
    assert "transform.deduplicate.keys references missing columns" in job
