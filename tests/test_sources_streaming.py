from __future__ import annotations

import pytest

from lakehouse_ingestion.ingestion import ingest_plan
from lakehouse_ingestion.plan import SourceSpec, build_plan_from_kwargs
from lakehouse_ingestion.sources import (
    AutoloaderResolver,
    get_source_resolver,
    register_source_resolver,
)


def test_register_and_get_source_resolver():
    class Resolver:
        def resolve_stream(self, spec, plan):
            return None, "test"

    resolver = Resolver()
    register_source_resolver("unit_test_source", resolver)
    assert get_source_resolver("unit_test_source") is resolver


def test_get_source_resolver_rejects_unknown():
    with pytest.raises(ValueError, match="não tem resolver"):
        get_source_resolver("missing_source")


def test_autoloader_resolver_uses_read_stream_and_options(monkeypatch):
    calls = {"format": None, "options": {}, "load": None}

    class Reader:
        def format(self, value):
            calls["format"] = value
            return self

        def option(self, key, value):
            calls["options"][key] = value
            return self

        def options(self, **kwargs):
            calls["options"].update(kwargs)
            return self

        def load(self, path):
            calls["load"] = path
            return "df"

    class FakeSpark:
        readStream = Reader()

    monkeypatch.setattr("lakehouse_ingestion.sources.spark", FakeSpark())
    spec = SourceSpec(
        type="autoloader",
        path="/landing/orders",
        format="json",
        schema_location="/schemas/orders",
        checkpoint_location="/checkpoints/orders",
        schema_hints="id BIGINT",
        options={"cloudFiles.inferColumnTypes": "true"},
        max_files_per_trigger=5,
    )

    df, label = AutoloaderResolver().resolve_stream(spec, build_plan_from_kwargs(source="x", target_table="t"))

    assert df == "df"
    assert label == "autoloader:/landing/orders"
    assert calls["format"] == "cloudFiles"
    assert calls["load"] == "/landing/orders"
    assert calls["options"]["cloudFiles.format"] == "json"
    assert calls["options"]["cloudFiles.schemaLocation"] == "/schemas/orders"
    assert calls["options"]["cloudFiles.includeExistingFiles"] == "true"
    assert calls["options"]["cloudFiles.schemaHints"] == "id BIGINT"
    assert calls["options"]["cloudFiles.maxFilesPerTrigger"] == "5"
    assert calls["options"]["cloudFiles.inferColumnTypes"] == "true"


def test_ingest_plan_dispatches_source_spec_to_stream(monkeypatch):
    plan = build_plan_from_kwargs(
        source={
            "type": "autoloader",
            "path": "/landing/orders",
            "schema_location": "/schemas/orders",
            "checkpoint_location": "/checkpoints/orders",
        },
        target_table="b_orders",
    )

    def fake_stream(inner_plan):
        return {"status": "DRY_RUN", "stream_run_id": "stream-1", "source": inner_plan.source.path}

    monkeypatch.setattr("lakehouse_ingestion.ingestion.ingest_stream_plan", fake_stream)

    assert ingest_plan(plan) == {
        "status": "DRY_RUN",
        "stream_run_id": "stream-1",
        "source": "/landing/orders",
    }
