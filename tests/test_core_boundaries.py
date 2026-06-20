from __future__ import annotations

import ast
from pathlib import Path

from contractforge_core.contracts import contract_model_schemas, validate_contract
from contractforge_core.evidence import EvidenceRequirement
import contractforge_core.config as core_config
from contractforge_core.portability import classify_write_mode


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "contractforge_core"


def test_root_contract_schema_is_available() -> None:
    schemas = contract_model_schemas()

    assert "contract" in schemas
    assert "quality_rules" in schemas
    assert schemas["contract"]["properties"]["mode"]["default"] == "append"


def test_validate_contract_accepts_contractforge_shape() -> None:
    contract = validate_contract(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    assert contract["target"]["table"] == "orders"


def test_portability_classifies_review_prone_modes() -> None:
    assert classify_write_mode("scd0_append").classification == "PORTABLE"
    assert classify_write_mode("append").classification == "PORTABLE"
    assert classify_write_mode("scd2_historical").classification == "REVIEW_REQUIRED"
    assert classify_write_mode("historical").classification == "REVIEW_REQUIRED"
    assert classify_write_mode("snapshot_soft_delete").classification == "REVIEW_REQUIRED"


def test_evidence_requirement_uses_platform_neutral_terms() -> None:
    requirement = EvidenceRequirement()

    assert "run" in requirement.event_types
    assert "lineage_event" in requirement.event_types


def test_core_config_does_not_define_platform_physical_merge_strategies() -> None:
    assert not hasattr(core_config, "MergeStrategy")
    assert not hasattr(core_config, "VALID_MERGE_STRATEGIES")


def test_core_does_not_import_platform_runtime_sdks() -> None:
    forbidden_roots = {
        "azure",
        "boto3",
        "botocore",
        "contractforge_aws",
        "contractforge_databricks",
        "contractforge_snowflake",
        "databricks",
        "fabric",
        "pyspark",
    }
    offenders: list[str] = []

    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                if name in forbidden_roots:
                    offenders.append(f"{path.relative_to(ROOT)} imports {name}")

    assert offenders == []


def test_core_messages_do_not_reference_adapter_extension_namespaces() -> None:
    forbidden = (
        "extensions.databricks",
        "extensions.aws",
        "DatabricksIngestOptions",
        "AWSIngestOptions",
    )
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)} references {token}")

    assert offenders == []
