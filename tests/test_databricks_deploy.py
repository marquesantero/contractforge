from __future__ import annotations

import json
import subprocess

from contractforge_databricks.cli import main
from contractforge_databricks.runtime.deploy import (
    DEFAULT_CLI_TIMEOUT_SECONDS,
    _run_databricks_cli,
    deploy_databricks_bundle,
    deploy_databricks_project,
)


def test_deploy_databricks_bundle_validates_deploys_and_runs(tmp_path) -> None:
    bundle = tmp_path / "databricks.yml"
    bundle.write_text(_bundle_yaml("orders_job"), encoding="utf-8")
    calls: list[tuple[tuple[str, ...], str]] = []

    def runner(command, cwd):
        calls.append((command, str(cwd)))
        return {"command": list(command), "returncode": 0, "stdout": json.dumps({"ok": True}), "stderr": "", "json": {"ok": True}}

    result = deploy_databricks_bundle(bundle, profile="dbc-dev", target="dev", run=True, command_runner=runner)

    assert result["status"] == "SUCCESS"
    assert result["job_key"] == "orders_job"
    assert [item["step"] for item in result["steps"]] == ["validate", "deploy", "run"]
    assert calls == [
        (("databricks", "--profile", "dbc-dev", "bundle", "validate", "--target", "dev", "--output", "json"), str(tmp_path)),
        (("databricks", "--profile", "dbc-dev", "bundle", "deploy", "--target", "dev", "--output", "json"), str(tmp_path)),
        (("databricks", "--profile", "dbc-dev", "bundle", "run", "orders_job", "--target", "dev", "--output", "json"), str(tmp_path)),
    ]


def test_deploy_databricks_bundle_rejects_unsafe_profile_target_and_job_key(tmp_path) -> None:
    bundle = tmp_path / "databricks.yml"
    bundle.write_text(_bundle_yaml("orders_job"), encoding="utf-8")

    try:
        deploy_databricks_bundle(bundle, profile="--config-file", target="dev", command_runner=lambda command, cwd: {})
    except ValueError as exc:
        assert "Databricks profile" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("unsafe Databricks profile was accepted")

    try:
        deploy_databricks_bundle(bundle, profile="dbc-dev", target="../prod", command_runner=lambda command, cwd: {})
    except ValueError as exc:
        assert "Databricks target" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("unsafe Databricks target was accepted")

    bundle.write_text(_bundle_yaml("--config-file"), encoding="utf-8")
    try:
        deploy_databricks_bundle(bundle, profile="dbc-dev", target="dev", run=True, command_runner=lambda command, cwd: {})
    except ValueError as exc:
        assert "Databricks job key" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("unsafe Databricks job key was accepted")


def test_run_databricks_cli_uses_timeout(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "{}", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = _run_databricks_cli(("databricks", "bundle", "validate"), tmp_path)

    assert result["returncode"] == 0
    assert calls[0][1]["timeout"] == DEFAULT_CLI_TIMEOUT_SECONDS


def test_run_databricks_cli_reports_timeout(monkeypatch, tmp_path) -> None:
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, timeout=kwargs["timeout"], output="partial")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = _run_databricks_cli(("databricks", "bundle", "validate"), tmp_path)

    assert result["returncode"] == 124
    assert result["stdout"] == "partial"
    assert "timed out" in result["stderr"]
    assert result["json"] is None


def test_deploy_databricks_project_uses_validation_bundle_path(tmp_path) -> None:
    (tmp_path / "project.yaml").write_text(
        """
name: demo
validation:
  databricks:
    bundle: dab/databricks.yml
""".lstrip(),
        encoding="utf-8",
    )
    dab = tmp_path / "dab"
    dab.mkdir()
    (dab / "databricks.yml").write_text(_bundle_yaml("demo_job"), encoding="utf-8")
    calls: list[str] = []

    def runner(command, cwd):
        calls.append(str(cwd))
        return {"command": list(command), "returncode": 0, "stdout": "{}", "stderr": "", "json": {}}

    result = deploy_databricks_project(tmp_path / "project.yaml", validate=False, command_runner=runner)

    assert result["status"] == "SUCCESS"
    assert result["bundle_root"] == str(dab)
    assert [item["step"] for item in result["steps"]] == ["deploy"]
    assert calls == [str(dab)]


def test_deploy_databricks_project_accepts_project_directory(tmp_path) -> None:
    (tmp_path / "project.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "databricks.yml").write_text(_bundle_yaml("demo_job"), encoding="utf-8")

    result = deploy_databricks_project(
        tmp_path,
        validate=False,
        command_runner=lambda command, cwd: {"command": list(command), "returncode": 0, "stdout": "{}", "stderr": "", "json": {}},
    )

    assert result["status"] == "SUCCESS"
    assert result["bundle_file"] == str(tmp_path / "databricks.yml")


def test_deploy_databricks_project_can_render_bundle_before_deploy(tmp_path) -> None:
    (tmp_path / "project.yaml").write_text(
        """
name: demo
execution_order:
  - name: bronze
    contracts:
      databricks: contracts/bronze.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )

    result = deploy_databricks_project(
        tmp_path / "project.yaml",
        validate=False,
        render_bundle=True,
        command_runner=lambda command, cwd: {"command": list(command), "returncode": 0, "stdout": "{}", "stderr": "", "json": {}},
    )

    assert result["status"] == "SUCCESS"
    assert result["render"]["bundle_file"] == str(tmp_path / "databricks.yml")
    assert (tmp_path / "databricks.yml").exists()


def test_databricks_deploy_project_cli(monkeypatch, tmp_path, capsys) -> None:
    project = tmp_path / "project.yaml"
    project.write_text("name: demo\nvalidation:\n  databricks:\n    bundle: databricks.yml\n", encoding="utf-8")
    (tmp_path / "databricks.yml").write_text(_bundle_yaml("demo_job"), encoding="utf-8")

    def fake_deploy_project(*args, **kwargs):
        assert kwargs["render_bundle"] is True
        assert kwargs["force_render"] is True
        return {"status": "SUCCESS", "steps": [{"step": "deploy"}]}

    monkeypatch.setattr("contractforge_databricks.cli_deploy.deploy_databricks_project", fake_deploy_project)

    assert (
        main(
            [
                "deploy-project",
                str(project),
                "--profile",
                "dbc-dev",
                "--target",
                "dev",
                "--skip-validate",
                "--render-bundle",
                "--force-render",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "SUCCESS"
    assert payload["steps"] == [{"step": "deploy"}]


def _bundle_yaml(job_key: str) -> str:
    return f"""
bundle:
  name: demo
resources:
  jobs:
    {job_key}:
      name: demo
      tasks:
        - task_key: run
          notebook_task:
            notebook_path: ./run.py
targets:
  dev:
    default: true
""".lstrip()
