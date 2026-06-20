from __future__ import annotations

import pytest

from contractforge_aws import CostModel, render_aws_operational_cost_query, render_operational_cost_query


def test_render_operational_cost_query_uses_glue_dpu_seconds() -> None:
    query = render_operational_cost_query(
        database="ops",
        cost_model=CostModel(dpu_hour_usd=0.44),
        include_failed=False,
    )

    assert "FROM glue_catalog.`ops`.`ctrl_ingestion_cost`" in query
    assert "FROM glue_catalog.`ops`.`ctrl_ingestion_runs` runs" in query
    assert "signal_name = 'glue_dpu_seconds'" in query
    assert "AND runs.status = 'SUCCESS'" in query
    assert "0.44 AS estimated_dpu_hour_usd" in query
    assert "'estimated_from_glue_dpu_seconds' AS cost_source" in query


def test_render_operational_cost_query_without_rate_keeps_cost_null() -> None:
    query = render_aws_operational_cost_query(database="ops")

    assert "NULL AS estimated_dpu_hour_usd" in query
    assert "estimated_compute_cost" in query


def test_render_operational_cost_query_rejects_invalid_group_by() -> None:
    with pytest.raises(ValueError, match="unknown group_by fields"):
        render_operational_cost_query(group_by=["target_table", "secret"])
