"""Testes puros: build_plan_from_kwargs, validações de modo, normalização."""
from __future__ import annotations

import pytest

from lakehouse_ingestion import IngestionPlan, QualityRules, ingest
from lakehouse_ingestion.plan import (
    build_plan_from_kwargs,
    normalize_quality_rules,
    validate_write_mode,
)


def test_validate_write_mode_accepts_valid():
    assert validate_write_mode("scd0_append") == "scd0_append"
    assert validate_write_mode("scd2_historical") == "scd2_historical"


def test_validate_write_mode_default_when_missing():
    assert validate_write_mode(None) == "scd0_append"
    assert validate_write_mode("") == "scd0_append"


def test_validate_write_mode_rejects_unknown():
    with pytest.raises(ValueError, match="Modo de escrita não suportado"):
        validate_write_mode("scd9_inventado")


def test_normalize_quality_rules_passthrough():
    qr = QualityRules(not_null=["a"])
    assert normalize_quality_rules(qr) is qr


def test_normalize_quality_rules_from_dict():
    qr = normalize_quality_rules({"not_null": ["a"], "min_rows": 5})
    assert isinstance(qr, QualityRules)
    assert qr.not_null == ["a"]
    assert qr.min_rows == 5


def test_normalize_quality_rules_none():
    assert normalize_quality_rules(None) is None


def test_build_plan_basic():
    plan = build_plan_from_kwargs(
        source="raw_orders",
        target_table="b_orders",
        catalog="c1",
        layer="bronze",
        mode="scd0_append",
    )
    assert isinstance(plan, IngestionPlan)
    assert plan.target_table == "b_orders"
    assert plan.mode == "scd0_append"
    assert plan.merge_keys == []


def test_build_plan_normalizes_pipe_separated_lists():
    plan = build_plan_from_kwargs(
        source="x",
        target_table="t",
        merge_keys="id|tenant_id",
        watermark_columns="updated_at",
    )
    assert plan.merge_keys == ["id", "tenant_id"]
    assert plan.watermark_columns == ["updated_at"]


def test_build_plan_rejects_unknown_kwargs():
    with pytest.raises(ValueError, match="não reconhecidos"):
        build_plan_from_kwargs(source="x", target_table="t", invalid_param=True)


def test_build_plan_quality_rules_dict():
    plan = build_plan_from_kwargs(
        source="x",
        target_table="t",
        quality_rules={"not_null": ["id"], "min_rows": 1},
    )
    assert isinstance(plan.quality_rules, QualityRules)
    assert plan.quality_rules.not_null == ["id"]


def test_ingest_rejects_unknown_kwargs(monkeypatch):
    """A função pública não deve aceitar parâmetros desconhecidos."""
    with pytest.raises(ValueError):
        ingest(source="x", target_table="t", typo_param=1)
