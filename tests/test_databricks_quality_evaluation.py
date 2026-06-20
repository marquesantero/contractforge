from __future__ import annotations

import sys
import types

import pytest

from contractforge_core.config import MAX_INLINE_ACCEPTED_VALUES
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.quality import clear_quality_rule_registry, evaluate_quality, register_quality_rule


class Expr:
    def __init__(self, value: str) -> None:
        self.value = value

    def __or__(self, other: "Expr") -> "Expr":
        return Expr(f"({self.value} OR {other.value})")

    def __invert__(self) -> "Expr":
        return Expr(f"NOT {self.value}")

    def __eq__(self, other: object) -> "Expr":  # type: ignore[override]
        return Expr(f"{self.value} = {other!r}")


class FakeFunctions:
    @staticmethod
    def lit(value: object) -> Expr:
        return Expr(f"lit({value!r})")

    @staticmethod
    def col(value: str) -> Expr:
        return Expr(f"col({value})")


class FakeDF:
    def __init__(self, columns: list[str], count_value: int = 0) -> None:
        self.columns = columns
        self.count_value = count_value
        self.where_calls = []

    def limit(self, value: int) -> "FakeDF":
        return FakeDF(self.columns, 0)

    def count(self) -> int:
        return self.count_value

    def where(self, condition: Expr) -> "FakeDF":
        self.where_calls.append(condition.value)
        return FakeDF(self.columns, self.count_value)


@pytest.fixture(autouse=True)
def fake_pyspark(monkeypatch):
    pyspark = types.ModuleType("pyspark")
    sql = types.ModuleType("pyspark.sql")
    sql.functions = FakeFunctions
    monkeypatch.setitem(sys.modules, "pyspark", pyspark)
    monkeypatch.setitem(sys.modules, "pyspark.sql", sql)
    yield
    clear_quality_rule_registry()


def test_evaluate_quality_returns_not_configured_without_rules() -> None:
    status, results, valid_df, quarantined_df, quarantined_count = evaluate_quality(FakeDF(["id"], 3), ())

    assert status == "NOT_CONFIGURED"
    assert results == ()
    assert isinstance(valid_df, FakeDF)
    assert quarantined_df.count() == 0
    assert quarantined_count == 0


def test_evaluate_quality_handles_required_columns_and_min_rows() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "quality_rules": {"required_columns": ["id", "status"], "min_rows": 5},
        }
    )

    status, results, _, _, quarantined_count = evaluate_quality(FakeDF(["id"], 3), contract)

    assert status == "FAILED"
    assert [result.rule_name for result in results] == ["required_columns", "min_rows"]
    assert results[0].details == {"missing": ["status"]}
    assert results[1].details == {"min_rows": 5, "actual": 3}
    assert quarantined_count == 0


def test_evaluate_quality_runs_custom_rules_from_core_extension() -> None:
    def evaluator(df, rule_name, config):
        assert rule_name == "business_threshold"
        assert config["threshold"] == 5
        return {
            "failed_count": 2,
            "severity": "quarantine",
            "condition": FakeFunctions.col("status") == "bad",
            "details": {"threshold": config["threshold"]},
        }

    register_quality_rule("threshold_check", evaluator)
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "quality_rules": {
                "custom": {
                    "business_threshold": {
                        "type": "threshold_check",
                        "severity": "quarantine",
                        "threshold": 5,
                    }
                }
            },
        }
    )
    df = FakeDF(["id", "status"], 3)

    status, results, _, _, quarantined_count = evaluate_quality(df, contract)

    assert status == "FAILED"
    assert results[0].rule_name == "custom:business_threshold"
    assert results[0].details == {"name": "business_threshold", "type": "threshold_check", "threshold": 5}
    assert quarantined_count == 3
    assert df.where_calls == ["(lit(False) OR col(status) = 'bad')", "NOT (lit(False) OR col(status) = 'bad')"]


def test_evaluate_quality_rejects_large_inline_accepted_values() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "quality_rules": {"accepted_values": {"status": list(range(MAX_INLINE_ACCEPTED_VALUES + 1))}},
        }
    )

    with pytest.raises(ValueError, match="accepted_values.status"):
        evaluate_quality(FakeDF(["status"], 3), contract)
