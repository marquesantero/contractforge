"""AWS shape.flatten rendering via runtime schema-introspection helper."""

from __future__ import annotations

from contractforge_aws import render_aws_contract


def _glue_job(flatten) -> str:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/events"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
            "shape": {"flatten": flatten},
        }
    )
    job = artifacts.artifacts["lake_bronze_events.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    return job


def test_flatten_bool_true_uses_defaults() -> None:
    job = _glue_job(True)
    assert "def _cf_flatten(df, separator, max_depth, include, exclude):" in job
    assert "df = _cf_flatten(" in job
    assert "separator='_'," in job
    assert "max_depth=10," in job


def test_flatten_config_passes_options() -> None:
    job = _glue_job(
        {"enabled": True, "separator": "__", "max_depth": 3, "exclude": ["audit"], "include": ["payload"]}
    )
    assert "separator='__'," in job
    assert "max_depth=3," in job
    assert "include=['payload']," in job
    assert "exclude=['audit']," in job


def test_flatten_disabled_renders_nothing() -> None:
    job = _glue_job(False)
    assert "_cf_flatten" not in job


def test_flatten_helper_is_valid_python() -> None:
    from contractforge_aws.preparation import render_flatten_helper

    compile(render_flatten_helper(), "helper.py", "exec")
