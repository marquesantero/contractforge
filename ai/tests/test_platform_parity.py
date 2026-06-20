from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from contractforge_ai.adapter_validation.registry import AdapterPlannerSpec, DEFAULT_ADAPTER_PLANNERS
from contractforge_ai.cli import main
from contractforge_ai.parity import compare_platforms


def test_compare_platforms_reports_adapter_status_and_artifacts(tmp_path: Path, monkeypatch) -> None:
    contract = _write_contract(tmp_path)
    _install_fake_adapter(monkeypatch, "databricks", status="SUPPORTED", artifacts={"orders.databricks.yml": "resources: {}"})
    _install_fake_adapter(
        monkeypatch,
        "aws",
        status="REVIEW_REQUIRED",
        warnings=(SimpleNamespace(code="lake_formation_review", message="Review Lake Formation policies."),),
        artifacts={"orders.glue_job.py": "print('run')", "orders.deployment_manifest.json": "{}"},
    )

    report = compare_platforms(contract=contract, adapters=("databricks", "aws"))

    assert report.status == "NEEDS_DECISIONS"
    assert report.contracts[0].target == "main.bronze.orders"
    outcomes = {outcome.adapter: outcome for outcome in report.contracts[0].adapter_outcomes}
    assert outcomes["databricks"].status == "READY"
    assert outcomes["databricks"].artifact_types == ["databricks_asset_bundle"]
    assert outcomes["aws"].status == "NEEDS_DECISIONS"
    assert outcomes["aws"].artifact_types == ["aws_glue_job_runtime", "deployment_manifest"]
    assert report.contracts[0].shared_fields == ["source.type", "target", "mode"]
    assert report.contracts[0].review_required_adapters == ["aws"]
    assert report.contracts[0].unsupported_adapters == []
    assert report.contracts[0].deployment_differences == {
        "databricks": ["databricks_asset_bundle"],
        "aws": ["aws_glue_job_runtime", "deployment_manifest"],
    }
    assert "Delta control tables" in report.contracts[0].evidence_differences["databricks"]
    assert "Iceberg/Glue evidence tables" in report.contracts[0].evidence_differences["aws"]


def test_compare_platforms_cli_outputs_json(tmp_path: Path, monkeypatch, capsys) -> None:
    contract = _write_contract(tmp_path)
    _install_fake_adapter(monkeypatch, "databricks", status="SUPPORTED", artifacts={"orders.databricks.yml": "resources: {}"})
    _install_fake_adapter(monkeypatch, "aws", status="SUPPORTED", artifacts={"orders.glue_job.py": "print('run')"})

    exit_code = main(
        [
            "compare-platforms",
            "--contract",
            str(contract),
            "--adapter",
            "databricks",
            "--adapter",
            "aws",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "READY"
    assert payload["contracts"][0]["adapter_outcomes"][0]["artifact_types"]
    assert payload["contracts"][0]["shared_fields"] == ["source.type", "target", "mode"]
    assert payload["contracts"][0]["deployment_differences"]
    assert payload["contracts"][0]["evidence_differences"]["aws"]


def test_compare_platforms_cli_outputs_markdown_sections(tmp_path: Path, monkeypatch, capsys) -> None:
    contract = _write_contract(tmp_path)
    _install_fake_adapter(monkeypatch, "databricks", status="SUPPORTED", artifacts={"orders.databricks.yml": "resources: {}"})
    _install_fake_adapter(monkeypatch, "aws", status="UNSUPPORTED", artifacts={})

    exit_code = main(
        [
            "compare-platforms",
            "--contract",
            str(contract),
            "--adapter",
            "databricks",
            "--adapter",
            "aws",
            "--format",
            "markdown",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Shared contract fields" in output
    assert "Unsupported adapters: `aws`" in output
    assert "### Deployment Differences" in output
    assert "### Evidence Differences" in output
    assert "Delta control tables" in output
    assert "Iceberg/Glue evidence tables" in output


def test_compare_platforms_cli_outputs_html_report(tmp_path: Path, monkeypatch, capsys) -> None:
    contract = _write_contract(tmp_path)
    _install_fake_adapter(monkeypatch, "databricks", status="SUPPORTED", artifacts={"orders.databricks.yml": "resources: {}"})
    _install_fake_adapter(monkeypatch, "aws", status="SUPPORTED", artifacts={"orders.glue_job.py": "print('run')"})

    exit_code = main(
        [
            "compare-platforms",
            "--contract",
            str(contract),
            "--adapter",
            "databricks",
            "--adapter",
            "aws",
            "--format",
            "html",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "<!doctype html>" in output
    assert "ContractForge Platform Parity Report" in output
    assert "Deployment Differences" in output
    assert "Evidence Differences" in output


def _write_contract(root: Path) -> Path:
    path = root / "orders.yaml"
    path.write_text(
        """
source:
  type: connector
  connector: files
  path: /landing/orders
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    return path


def _install_fake_adapter(
    monkeypatch,
    name: str,
    *,
    status: str,
    warnings=(),
    blockers=(),
    artifacts: dict[str, str] | None = None,
) -> None:
    package_name = f"contractforge_{name}"
    module_name = f"{package_name}.api"
    package = types.ModuleType(package_name)
    package.__path__ = []
    module = types.ModuleType(module_name)

    def planner(contract, **kwargs):
        return SimpleNamespace(status=status, warnings=warnings, blockers=blockers)

    def renderer(contract, **kwargs):
        return SimpleNamespace(artifacts=artifacts or {})

    setattr(module, f"plan_{name}_contract", planner)
    setattr(module, f"render_{name}_contract", renderer)
    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setitem(
        DEFAULT_ADAPTER_PLANNERS,
        name,
        AdapterPlannerSpec(
            name=name,
            module=module_name,
            function=f"plan_{name}_contract",
            render_function=f"render_{name}_contract",
        ),
    )
