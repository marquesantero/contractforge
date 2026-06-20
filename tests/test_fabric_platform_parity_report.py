from __future__ import annotations

import json
from pathlib import Path

from tools.platform_parity.report import build_report


ROOT = Path(__file__).resolve().parents[1]


def test_fabric_platform_parity_report_matches_shared_generator() -> None:
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-platform-parity.json").read_text(encoding="utf-8"))
    report = build_report()

    assert manifest["kind"] == "contractforge_fabric_platform_parity"
    assert manifest["status"] == "PASS_WITH_REVIEW_BOUNDARIES"
    assert manifest["platforms"] == ["databricks", "aws", "snowflake", "fabric"]
    assert manifest["scenario_count"] == report["scenario_count"]
    assert manifest["portable_signature_equal_all"] is True

    expected = {
        item["scenario"]: {
            "databricks_status": item["databricks_status"],
            "aws_status": item["aws_status"],
            "snowflake_status": item["snowflake_status"],
            "fabric_status": item["fabric_status"],
            "portable_signature_equal": item["portable_signature_equal"],
        }
        for item in report["results"]
    }
    actual = {
        item["scenario"]: {
            "databricks_status": item["databricks_status"],
            "aws_status": item["aws_status"],
            "snowflake_status": item["snowflake_status"],
            "fabric_status": item["fabric_status"],
            "portable_signature_equal": item["portable_signature_equal"],
        }
        for item in manifest["results"]
    }

    assert actual == expected
