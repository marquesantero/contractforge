from __future__ import annotations

import json
from pathlib import Path

from contractforge_aws.cli import main


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples" / "real-world" / "aws-incremental-files" / "project.yaml"


def test_aws_incremental_files_project_dry_run_compiles(capsys) -> None:
    assert main(["deploy-project", str(PROJECT), "--dry-run", "--summary-only"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert [step["name"] for step in payload["steps"]] == ["bronze_incremental_events"]

    step = payload["steps"][0]
    assert step["planning_status"] == "SUPPORTED_WITH_WARNINGS"
    assert step["python_compile_status"] == "PASS"
    assert step["python_artifacts_compiled"] == 2
    assert step["runnable"] is True
    assert "AWS_INCREMENTAL_FILES_STRATEGY_REVIEW" in step["warning_codes"]


def test_aws_incremental_files_project_has_upload_waves() -> None:
    base = PROJECT.parent
    wave1 = base / "data" / "events" / "wave1" / "events_2026_06_01.csv"
    wave2 = base / "data" / "events" / "wave2" / "events_2026_06_01_late.csv"

    assert wave1.exists()
    assert wave2.exists()
    assert len(wave1.read_text(encoding="utf-8").splitlines()) == 5
    assert len(wave2.read_text(encoding="utf-8").splitlines()) == 5
