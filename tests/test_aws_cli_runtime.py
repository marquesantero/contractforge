from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from contractforge_core.evidence import CostEvidenceRecord
from contractforge_aws.cli import apply as cli_apply
from contractforge_aws.cli import deploy as cli_deploy
from contractforge_aws.cli import glue as cli_glue
from contractforge_aws.cli import plan as cli_plan
from contractforge_aws.cli import performance as cli_performance
from contractforge_aws.cli import project as cli_project
from contractforge_aws.cli import project_cost as cli_project_cost
from contractforge_aws.cli import project_run as cli_project_run
from contractforge_aws.cli import runtime as cli_runtime
from contractforge_aws.cli import main
from contractforge_aws.runtime import library_runner


@dataclass(frozen=True)
class _Registered:
    name: str
    action: str
    arn: str | None = None


@dataclass(frozen=True)
class _Status:
    job_name: str
    run_id: str
    state: str


@dataclass(frozen=True)
class _Run:
    job_name: str
    run_id: str


@dataclass(frozen=True)
class _Setup:
    database: str
    status: str
    statements_executed: int


@dataclass(frozen=True)
class _Published:
    artifact_name: str
    bucket: str
    key: str
    uri: str
    content_type: str
    bytes_written: int = 0


@dataclass(frozen=True)
class _Deployment:
    job_name: str
    action: str
    job_arn: str | None
    job_definition_uri: str
    script_uri: str
    artifacts: tuple[_Published, ...]


def _write_contract(path) -> None:
    path.write_text(
        """
source:
  type: parquet
  path: s3://landing/customers
target:
  catalog: lake
  schema: silver
  table: customers
mode: scd0_append
""",
        encoding="utf-8",
    )


def test_aws_cli_render_split_bundle_uses_environment_contract(tmp_path, capsys) -> None:
    base = tmp_path / "contracts" / "bronze" / "b_orders"
    base.parent.mkdir(parents=True)
    base.with_suffix(".ingestion.yaml").write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    base.with_suffix(".environment.yaml").write_text(
        """
name: dev
adapter: aws
evidence:
  database: cf_ops_bundle
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["render", str(base.with_suffix(".ingestion.yaml"))]) == 0

    artifacts = json.loads(capsys.readouterr().out)
    assert "CREATE DATABASE IF NOT EXISTS glue_catalog.`cf_ops_bundle`;" in artifacts["lake_bronze_orders.evidence_ddl.sql"]


def test_aws_library_runner_rejects_dynamic_execution_calls() -> None:
    with pytest.raises(ValueError, match="Unsafe AWS runtime script call"):
        library_runner._validate_rendered_runtime_script("eval('1')")


def test_aws_library_runner_rejects_process_spawning_imports() -> None:
    with pytest.raises(ValueError, match="Unsafe AWS runtime script import"):
        library_runner._validate_rendered_runtime_script("import subprocess\n")


def test_aws_library_runner_rejects_local_file_primitives() -> None:
    with pytest.raises(ValueError, match="Unsafe AWS runtime script call"):
        library_runner._validate_rendered_runtime_script("open('/tmp/secret').read()")


def test_aws_library_runner_rejects_destructive_imports() -> None:
    with pytest.raises(ValueError, match="Unsafe AWS runtime script import"):
        library_runner._validate_rendered_runtime_script("import shutil\n")


def test_aws_library_runner_accepts_adapter_rendered_runtime_script() -> None:
    script = library_runner._render_runtime_script(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        },
        environment=None,
    )

    library_runner._validate_rendered_runtime_script(script)


def test_aws_library_runner_rejects_oversized_local_runtime_artifact(tmp_path) -> None:
    artifact = tmp_path / "large.yaml"
    artifact.write_bytes(b"x" * (library_runner.MAX_RUNTIME_ARTIFACT_BYTES + 1))

    with pytest.raises(ValueError, match="runtime artifact is too large"):
        library_runner.load_text_uri(str(artifact))


def test_aws_cli_render_environment_argument_overrides_bundle_environment(tmp_path, capsys) -> None:
    base = tmp_path / "contracts" / "bronze" / "b_orders"
    base.parent.mkdir(parents=True)
    base.with_suffix(".ingestion.yaml").write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    base.with_suffix(".environment.yaml").write_text(
        """
name: dev
adapter: aws
evidence:
  database: cf_ops_bundle
""".lstrip(),
        encoding="utf-8",
    )
    override = tmp_path / "prod.environment.yaml"
    override.write_text(
        """
name: prod
adapter: aws
evidence:
  database: cf_ops_prod
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["render", str(base.with_suffix(".ingestion.yaml")), "--environment", str(override)]) == 0

    artifacts = json.loads(capsys.readouterr().out)
    assert "CREATE DATABASE IF NOT EXISTS glue_catalog.`cf_ops_prod`;" in artifacts["lake_bronze_orders.evidence_ddl.sql"]
    assert "cf_ops_bundle" not in artifacts["lake_bronze_orders.evidence_ddl.sql"]


def test_aws_cli_publish_s3_passes_environment_to_public_runtime_api(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    _write_contract(contract_path)
    env_path = tmp_path / "environment.yaml"
    env_path.write_text(
        """
name: prod
adapter: aws
evidence:
  database: cf_ops_prod
""".lstrip(),
        encoding="utf-8",
    )
    seen = {}

    def fake_publish(contract, **kwargs):
        seen["contract"] = contract
        seen["kwargs"] = kwargs
        return (
            _Published(
                artifact_name="lake_silver_customers.glue_job.py",
                bucket=kwargs["bucket"],
                key="dev/lake_silver_customers.glue_job.py",
                uri=f"s3://{kwargs['bucket']}/dev/lake_silver_customers.glue_job.py",
                content_type="text/x-python",
            ),
        )

    monkeypatch.setattr(cli_plan, "publish_aws_contract_artifacts_to_s3", fake_publish)

    assert (
        main(
            [
                "publish-s3",
                str(contract_path),
                "--environment",
                str(env_path),
                "--bucket",
                "contractforge-artifacts",
                "--prefix",
                "dev",
            ]
        )
        == 0
    )

    assert seen["contract"]["target"]["table"] == "customers"
    assert seen["kwargs"]["environment"]["evidence"]["database"] == "cf_ops_prod"
    assert json.loads(capsys.readouterr().out)[0]["bucket"] == "contractforge-artifacts"


def test_aws_cli_publish_s3_can_use_environment_artifact_uri(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    _write_contract(contract_path)
    env_path = tmp_path / "environment.yaml"
    env_path.write_text(
        """
name: prod
adapter: aws
artifacts:
  uri: s3://contractforge-artifacts/prod/orders/
""".lstrip(),
        encoding="utf-8",
    )
    seen = {}

    def fake_publish(contract, **kwargs):
        seen["contract"] = contract
        seen["kwargs"] = kwargs
        return (
            _Published(
                artifact_name="lake_silver_customers.glue_job.py",
                bucket="contractforge-artifacts",
                key="prod/orders/lake_silver_customers.glue_job.py",
                uri="s3://contractforge-artifacts/prod/orders/lake_silver_customers.glue_job.py",
                content_type="text/x-python",
            ),
        )

    monkeypatch.setattr(cli_plan, "publish_aws_contract_artifacts_to_s3", fake_publish)

    assert main(["publish-s3", str(contract_path), "--environment", str(env_path)]) == 0

    assert seen["contract"]["target"]["table"] == "customers"
    assert seen["kwargs"]["bucket"] is None
    assert seen["kwargs"]["prefix"] == ""
    assert seen["kwargs"]["environment"]["artifacts"]["uri"] == "s3://contractforge-artifacts/prod/orders/"
    assert json.loads(capsys.readouterr().out)[0]["uri"].startswith("s3://contractforge-artifacts/prod/orders/")


def test_aws_cli_publish_s3_includes_original_bundle_when_enabled(tmp_path, monkeypatch, capsys) -> None:
    base = tmp_path / "orders"
    (tmp_path / "project.yaml").write_text("name: test\n", encoding="utf-8")
    base.with_suffix(".ingestion.yaml").write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    base.with_suffix(".annotations.yaml").write_text(
        """
table:
  description: Orders table
""".lstrip(),
        encoding="utf-8",
    )
    env_path = tmp_path / "environment.yaml"
    env_path.write_text(
        """
name: prod
adapter: aws
artifacts:
  uri: s3://contractforge-artifacts/prod/orders/
  include_contract_bundle: true
""".lstrip(),
        encoding="utf-8",
    )
    seen = {}

    def fake_publish(contract, **kwargs):
        seen["contract"] = contract
        seen["kwargs"] = kwargs
        return (
            _Published(
                artifact_name="original/orders/ingestion.yaml",
                bucket="contractforge-artifacts",
                key="prod/orders/original/orders/ingestion.yaml",
                uri="s3://contractforge-artifacts/prod/orders/original/orders/ingestion.yaml",
                content_type="application/yaml",
            ),
        )

    monkeypatch.setattr(cli_plan, "publish_aws_contract_artifacts_to_s3", fake_publish)

    assert main(["publish-s3", str(base.with_suffix(".ingestion.yaml")), "--environment", str(env_path)]) == 0

    extra = seen["kwargs"]["extra_artifacts"]
    assert "original/orders/ingestion.yaml" in extra
    assert "original/orders/annotations.yaml" in extra
    assert "Orders table" in extra["original/orders/annotations.yaml"]
    assert json.loads(capsys.readouterr().out)[0]["uri"].endswith("/original/orders/ingestion.yaml")


def test_aws_cli_deploy_runs_full_publish_register_pipeline(tmp_path, monkeypatch, capsys) -> None:
    base = tmp_path / "orders"
    (tmp_path / "project.yaml").write_text("name: test\n", encoding="utf-8")
    base.with_suffix(".ingestion.yaml").write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    env_path = tmp_path / "environment.yaml"
    env_path.write_text(
        """
name: prod
adapter: aws
artifacts:
  uri: s3://contractforge-artifacts/prod/orders/
  include_contract_bundle: true
""".lstrip(),
        encoding="utf-8",
    )
    seen = {}

    def fake_deploy(contract, **kwargs):
        seen["contract"] = contract
        seen["kwargs"] = kwargs
        return _Deployment(
            job_name="contractforge_lake_bronze_orders",
            action="updated",
            job_arn="contractforge_lake_bronze_orders",
            job_definition_uri="s3://contractforge-artifacts/prod/orders/lake_bronze_orders.glue_job_definition.json",
            script_uri="s3://contractforge-artifacts/prod/orders/lake_bronze_orders.glue_job.py",
            artifacts=(
                _Published(
                    artifact_name="lake_bronze_orders.glue_job.py",
                    bucket="contractforge-artifacts",
                    key="prod/orders/lake_bronze_orders.glue_job.py",
                    uri="s3://contractforge-artifacts/prod/orders/lake_bronze_orders.glue_job.py",
                    content_type="text/x-python",
                ),
            ),
        )

    monkeypatch.setattr(cli_deploy, "deploy_aws_contract_to_glue", fake_deploy)

    assert main(["deploy", str(base.with_suffix(".ingestion.yaml")), "--environment", str(env_path)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["job_name"] == "contractforge_lake_bronze_orders"
    assert payload["script_uri"].endswith("lake_bronze_orders.glue_job.py")
    assert seen["contract"]["target"]["table"] == "orders"
    assert "original/orders/ingestion.yaml" in seen["kwargs"]["extra_artifacts"]


def test_aws_cli_deploy_project_runs_contracts_in_project_order(tmp_path, monkeypatch, capsys) -> None:
    project_path = tmp_path / "project.yaml"
    env_path = tmp_path / "environments" / "aws.environment.yaml"
    contract_a = tmp_path / "contracts" / "aws" / "bronze" / "a" / "a.ingestion.yaml"
    contract_b = tmp_path / "contracts" / "aws" / "bronze" / "b" / "b.ingestion.yaml"
    env_path.parent.mkdir(parents=True)
    contract_a.parent.mkdir(parents=True)
    contract_b.parent.mkdir(parents=True)
    project_path.write_text(
        """
name: project
environments:
  aws: environments/aws.environment.yaml
execution_order:
  - name: first
    contracts:
      aws: contracts/aws/bronze/a/a.ingestion.yaml
  - name: second
    expected_result: failed
    contracts:
      aws: contracts/aws/bronze/b/b.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )
    env_path.write_text(
        """
name: prod
adapter: aws
artifacts:
  uri: s3://contractforge-artifacts/project/
  include_contract_bundle: true
""".lstrip(),
        encoding="utf-8",
    )
    for path, table in ((contract_a, "a"), (contract_b, "b")):
        path.write_text(
            f"""
source:
  type: parquet
  path: s3://landing/{table}
target:
  catalog: lake
  schema: bronze
  table: {table}
mode: scd0_append
""".lstrip(),
            encoding="utf-8",
        )
    seen = {"deploy": [], "start": [], "wait": []}

    def fake_deploy(contract, **kwargs):
        table = contract["target"]["table"]
        seen["deploy"].append((table, kwargs))
        return _Deployment(
            job_name=f"contractforge_lake_bronze_{table}",
            action="updated",
            job_arn=None,
            job_definition_uri=f"s3://contractforge-artifacts/project/lake_bronze_{table}.glue_job_definition.json",
            script_uri=f"s3://contractforge-artifacts/project/lake_bronze_{table}.glue_job.py",
            artifacts=(),
        )

    def fake_start(**kwargs):
        seen["start"].append(kwargs["job_name"])
        return _Run(job_name=kwargs["job_name"], run_id=f"jr-{len(seen['start'])}")

    def fake_wait(**kwargs):
        seen["wait"].append(kwargs)
        if kwargs["job_name"].endswith("_b"):
            raise RuntimeError("AWS Glue job contractforge_lake_bronze_b run jr-2 ended with FAILED: expected")
        return _Status(job_name=kwargs["job_name"], run_id=kwargs["run_id"], state="SUCCEEDED")

    monkeypatch.setattr(cli_project, "deploy_aws_contract_to_glue", fake_deploy)
    monkeypatch.setattr(cli_project_run, "start_aws_glue_job_run", fake_start)
    monkeypatch.setattr(cli_project_run, "wait_aws_glue_job_run", fake_wait)

    assert (
        main(
            [
                "deploy-project",
                str(project_path),
                "--run",
                "--wait",
                "--accept-expected-failures",
                "--max-wait-seconds",
                "1",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert [item[0] for item in seen["deploy"]] == ["a", "b"]
    assert [step["name"] for step in payload["steps"]] == ["first", "second"]
    assert payload["steps"][0]["wait"]["status"] == "SUCCEEDED"
    assert payload["steps"][1]["wait"]["status"] == "EXPECTED_FAILURE"
    assert seen["deploy"][0][1]["environment"]["artifacts"]["uri"] == "s3://contractforge-artifacts/project/"
    assert "original/a/ingestion.yaml" in seen["deploy"][0][1]["extra_artifacts"]


def test_aws_project_step_start_retries_concurrent_run_limit(monkeypatch) -> None:
    attempts = []
    sleeps = []
    ticks = iter([0.0, 0.0, 1.0])

    class ConcurrentRunsExceededException(Exception):
        response = {"Error": {"Code": "ConcurrentRunsExceededException"}}

    def fake_start(**kwargs):
        attempts.append(kwargs["job_name"])
        if len(attempts) == 1:
            raise ConcurrentRunsExceededException("busy")
        return _Run(job_name=kwargs["job_name"], run_id="jr-2")

    monkeypatch.setattr(cli_project_run, "start_aws_glue_job_run", fake_start)
    monkeypatch.setattr(cli_project_run.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(cli_project_run.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = cli_project_run.start_project_step_run(
        "contractforge_lake_bronze_orders",
        poll_interval_seconds=3,
        max_wait_seconds=60,
    )

    assert result.run_id == "jr-2"
    assert attempts == ["contractforge_lake_bronze_orders", "contractforge_lake_bronze_orders"]
    assert sleeps == [3]


def test_aws_cli_cleanup_project_renders_non_destructive_plan(tmp_path, capsys) -> None:
    project_path = tmp_path / "project.yaml"
    env_path = tmp_path / "environments" / "aws.environment.yaml"
    contract_path = tmp_path / "contracts" / "aws" / "bronze" / "orders" / "orders.ingestion.yaml"
    env_path.parent.mkdir(parents=True)
    contract_path.parent.mkdir(parents=True)
    project_path.write_text(
        """
name: project
environments:
  aws: environments/aws.environment.yaml
execution_order:
  - name: orders
    contracts:
      aws: contracts/aws/bronze/orders/orders.ingestion.yaml
cleanup:
  external_resources:
    - resource: azure_resource_group
      name: rg-contractforge-stream-test
      command: [az, group, delete, --name, rg-contractforge-stream-test, --yes]
""".lstrip(),
        encoding="utf-8",
    )
    env_path.write_text(
        """
name: prod
adapter: aws
evidence:
  database: cf_ops_project
artifacts:
  uri: s3://contractforge-artifacts/project/
parameters:
  aws:
    iceberg:
      warehouse: s3://contractforge-lake/warehouse/project/
""".lstrip(),
        encoding="utf-8",
    )
    contract_path.write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["cleanup-project", str(project_path)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["destructive"] is False
    assert payload["steps"][0]["glue_job_names"] == ["contractforge_lake_bronze_orders"]
    assert payload["steps"][0]["target_database"] == "lake_bronze"
    assert payload["steps"][0]["cleanup_commands"][0]["command"] == [
        "aws",
        "glue",
        "delete-job",
        "--job-name",
        "contractforge_lake_bronze_orders",
    ]
    shared = payload["shared_resources"]
    assert shared["artifact_s3_uri"] == "s3://contractforge-artifacts/project/"
    assert shared["warehouse_s3_uri"] == "s3://contractforge-lake/warehouse/project/"
    assert shared["evidence_database"] == "cf_ops_project"
    assert shared["external_resources"][0]["resource"] == "azure_resource_group"


def test_aws_cli_stabilization_report_is_explicit_about_final_boundaries(capsys) -> None:
    assert main(["stabilization-report"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["classification"] == "STABLE_SUPPORTED_SURFACE"
    assert payload["supported_surface_ready"] is True
    assert payload["stable_final"] is True
    assert payload["stability_criteria"] == "docs/specs/aws-ga-criteria.md"
    assert payload["waiver_registry"] == "docs/specs/aws-ga-waivers.md"
    assert payload["evidence_manifest"] == "docs/reports/aws-stable-surface-evidence.json"
    assert {gate["status"] for gate in payload["gates"]} >= {"PASS", "PASS_WITH_REVIEW_BOUNDARIES"}
    assert {item["name"] for item in payload["real_validation_projects"]} >= {
        "aws_supabase_jdbc_medallion",
        "aws_eventhubs_kafka_available_now",
        "aws_hashdiff_production_benchmark",
    }
    assert {item["code"] for item in payload["accepted_review_boundaries"]} >= {
        "AWS_HASH_DIFF_PERFORMANCE_UNVALIDATED",
        "AWS_AVAILABLE_NOW_STREAMING_PROVIDER_REVIEW",
        "AWS_LAKE_FORMATION_GOVERNANCE_REVIEW",
        "AWS_SCD2_REVIEW",
    }
    scd2 = next(item for item in payload["accepted_review_boundaries"] if item["code"] == "AWS_SCD2_REVIEW")
    assert scd2["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    kafka = next(
        item for item in payload["accepted_review_boundaries"] if item["code"] == "AWS_AVAILABLE_NOW_STREAMING_PROVIDER_REVIEW"
    )
    lf = next(item for item in payload["accepted_review_boundaries"] if item["code"] == "AWS_LAKE_FORMATION_GOVERNANCE_REVIEW")
    assert kafka["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert lf["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert payload["next_promotion_gates"] == []


def test_aws_cli_stabilization_report_strict_final_passes_for_documented_scope(capsys) -> None:
    assert main(["stabilization-report", "--strict-final"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stable_final"] is True


def test_aws_cli_lakeformation_consumer_matrix_dry_run(capsys) -> None:
    assert (
        main(
            [
                "smoke-lakeformation-consumer-matrix",
                "--account-id",
                "123456789012",
                "--database",
                "lake_silver",
                "--table",
                "customers",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "DRY_RUN"
    assert payload["config"]["database"] == "lake_silver"
    assert "athena_allowed_principal_reads_declared_rows" in payload["required_cases"]
    assert "Glue table is registered with Lake Formation" in payload["required_prerequisites"]


def test_aws_cli_deploy_project_dry_run_never_calls_aws_runtime(tmp_path, monkeypatch, capsys) -> None:
    project_path = tmp_path / "project.yaml"
    env_path = tmp_path / "environments" / "aws.environment.yaml"
    contract_path = tmp_path / "contracts" / "aws" / "bronze" / "orders" / "orders.ingestion.yaml"
    env_path.parent.mkdir(parents=True)
    contract_path.parent.mkdir(parents=True)
    project_path.write_text(
        """
name: project
environments:
  aws: environments/aws.environment.yaml
execution_order:
  - name: orders
    contracts:
      aws: contracts/aws/bronze/orders/orders.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )
    env_path.write_text(
        """
name: prod
adapter: aws
artifacts:
  uri: s3://contractforge-artifacts/project/
""".lstrip(),
        encoding="utf-8",
    )
    contract_path.write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("dry-run must not call AWS runtime helpers")

    monkeypatch.setattr(cli_project, "deploy_aws_contract_to_glue", forbidden)
    monkeypatch.setattr(cli_project_run, "start_aws_glue_job_run", forbidden)
    monkeypatch.setattr(cli_project_run, "wait_aws_glue_job_run", forbidden)

    assert main(["deploy-project", str(project_path), "--dry-run"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["steps"][0]["planning_status"] == "SUPPORTED"
    assert payload["steps"][0]["runnable"] is True
    assert payload["steps"][0]["python_compile_status"] == "PASS"
    assert payload["steps"][0]["python_artifacts_compiled"] >= 1
    assert any(name.endswith(".deployment_manifest.json") for name in payload["steps"][0]["artifacts"])


def test_aws_cli_deploy_project_dry_run_summary_only_omits_artifact_names(tmp_path, capsys) -> None:
    project_path = tmp_path / "project.yaml"
    env_path = tmp_path / "environments" / "aws.environment.yaml"
    contract_path = tmp_path / "contracts" / "aws" / "bronze" / "orders" / "orders.ingestion.yaml"
    env_path.parent.mkdir(parents=True)
    contract_path.parent.mkdir(parents=True)
    project_path.write_text(
        """
name: project
environments:
  aws: environments/aws.environment.yaml
execution_order:
  - name: orders
    contracts:
      aws: contracts/aws/bronze/orders/orders.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )
    env_path.write_text("name: prod\nadapter: aws\n", encoding="utf-8")
    contract_path.write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["deploy-project", str(project_path), "--dry-run", "--summary-only"]) == 0

    step = json.loads(capsys.readouterr().out)["steps"][0]
    assert step["planning_status"] == "SUPPORTED"
    assert step["python_compile_status"] == "PASS"
    assert step["artifact_count"] > 0
    assert "artifacts" not in step


def test_aws_cli_deploy_project_summary_only_omits_deployment_artifacts(tmp_path, monkeypatch, capsys) -> None:
    project_path = tmp_path / "project.yaml"
    env_path = tmp_path / "environments" / "aws.environment.yaml"
    contract_path = tmp_path / "contracts" / "aws" / "bronze" / "orders" / "orders.ingestion.yaml"
    env_path.parent.mkdir(parents=True)
    contract_path.parent.mkdir(parents=True)
    project_path.write_text(
        """
name: project
environments:
  aws: environments/aws.environment.yaml
execution_order:
  - name: orders
    contracts:
      aws: contracts/aws/bronze/orders/orders.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )
    env_path.write_text(
        """
name: prod
adapter: aws
artifacts:
  uri: s3://contractforge-artifacts/project/
""".lstrip(),
        encoding="utf-8",
    )
    contract_path.write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_project,
        "deploy_aws_contract_to_glue",
        lambda *args, **kwargs: _Deployment(
            job_name="contractforge_lake_bronze_orders",
            action="updated",
            job_arn=None,
            job_definition_uri="s3://contractforge-artifacts/project/job.json",
            script_uri="s3://contractforge-artifacts/project/job.py",
            artifacts=(
                _Published(
                    artifact_name="lake_bronze_orders.glue_job.py",
                    bucket="contractforge-artifacts",
                    key="project/lake_bronze_orders.glue_job.py",
                    uri="s3://contractforge-artifacts/project/lake_bronze_orders.glue_job.py",
                    content_type="text/x-python",
                    bytes_written=123,
                ),
            ),
        ),
    )

    assert main(["deploy-project", str(project_path), "--summary-only"]) == 0

    deployment = json.loads(capsys.readouterr().out)["steps"][0]["deployment"]
    assert deployment["artifact_count"] == 1
    assert deployment["artifact_bytes_written"] == 123
    assert "artifacts" not in deployment


def test_aws_cli_deploy_project_can_audit_evidence_after_wait(tmp_path, monkeypatch, capsys) -> None:
    project_path = tmp_path / "project.yaml"
    env_path = tmp_path / "environments" / "aws.environment.yaml"
    contract_path = tmp_path / "contracts" / "aws" / "bronze" / "orders" / "orders.ingestion.yaml"
    env_path.parent.mkdir(parents=True)
    contract_path.parent.mkdir(parents=True)
    project_path.write_text(
        """
name: project
environments:
  aws: environments/aws.environment.yaml
execution_order:
  - name: orders
    contracts:
      aws: contracts/aws/bronze/orders/orders.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )
    env_path.write_text(
        """
name: prod
adapter: aws
evidence:
  database: cf_ops_project
artifacts:
  uri: s3://contractforge-artifacts/project/
""".lstrip(),
        encoding="utf-8",
    )
    contract_path.write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_project,
        "deploy_aws_contract_to_glue",
        lambda *args, **kwargs: _Deployment(
            job_name="contractforge_lake_bronze_orders",
            action="updated",
            job_arn=None,
            job_definition_uri="s3://contractforge-artifacts/project/job.json",
            script_uri="s3://contractforge-artifacts/project/job.py",
            artifacts=(),
        ),
    )
    monkeypatch.setattr(
        cli_project_run,
        "start_aws_glue_job_run",
        lambda **kwargs: _Run(job_name=kwargs["job_name"], run_id="jr-1"),
    )
    monkeypatch.setattr(
        cli_project_run,
        "wait_aws_glue_job_run",
        lambda **kwargs: _Status(job_name=kwargs["job_name"], run_id=kwargs["run_id"], state="SUCCEEDED"),
    )
    seen = {}

    def fake_audit(environment, **kwargs):
        seen["environment"] = environment
        seen["kwargs"] = kwargs
        return {"database": environment["evidence"]["database"], "status": "AUDITED", "checks": []}

    monkeypatch.setattr(cli_project, "run_project_evidence_audit", fake_audit)

    assert (
        main(
            [
                "deploy-project",
                str(project_path),
                "--run",
                "--wait",
                "--audit-evidence",
                "--athena-output-location",
                "s3://bucket/query-results/",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence_audit"] == {"database": "cf_ops_project", "status": "AUDITED", "checks": []}
    assert seen["kwargs"]["athena_output_location"] == "s3://bucket/query-results/"


def test_aws_cli_deploy_project_can_record_cost_evidence_after_wait(tmp_path, monkeypatch, capsys) -> None:
    project_path = tmp_path / "project.yaml"
    env_path = tmp_path / "environments" / "aws.environment.yaml"
    contract_path = tmp_path / "contracts" / "aws" / "bronze" / "orders" / "orders.ingestion.yaml"
    env_path.parent.mkdir(parents=True)
    contract_path.parent.mkdir(parents=True)
    project_path.write_text(
        """
name: project
environments:
  aws: environments/aws.environment.yaml
execution_order:
  - name: orders
    contracts:
      aws: contracts/aws/bronze/orders/orders.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )
    env_path.write_text(
        """
name: prod
adapter: aws
evidence:
  database: cf_ops_project
artifacts:
  uri: s3://contractforge-artifacts/project/
""".lstrip(),
        encoding="utf-8",
    )
    contract_path.write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli_project,
        "deploy_aws_contract_to_glue",
        lambda *args, **kwargs: _Deployment(
            job_name="contractforge_lake_bronze_orders",
            action="updated",
            job_arn=None,
            job_definition_uri="s3://contractforge-artifacts/project/job.json",
            script_uri="s3://contractforge-artifacts/project/job.py",
            artifacts=(),
        ),
    )
    monkeypatch.setattr(
        cli_project_run,
        "start_aws_glue_job_run",
        lambda **kwargs: _Run(job_name=kwargs["job_name"], run_id="jr-1"),
    )
    monkeypatch.setattr(
        cli_project_run,
        "wait_aws_glue_job_run",
        lambda **kwargs: _Status(job_name=kwargs["job_name"], run_id=kwargs["run_id"], state="SUCCEEDED"),
    )
    seen = {}

    def fake_record(environment, contract, **kwargs):
        seen["environment"] = environment
        seen["contract"] = contract
        seen["kwargs"] = kwargs
        return {"database": "cf_ops_project", "run_id": kwargs["run_id"], "status": "RECORDED"}

    monkeypatch.setattr(cli_project_run, "record_project_step_cost_evidence", fake_record)

    assert (
        main(
            [
                "deploy-project",
                str(project_path),
                "--run",
                "--wait",
                "--record-cost-evidence",
                "--athena-output-location",
                "s3://bucket/query-results/",
            ]
        )
        == 0
    )

    step = json.loads(capsys.readouterr().out)["steps"][0]
    assert step["cost_evidence"] == {"database": "cf_ops_project", "run_id": "jr-1", "status": "RECORDED"}
    assert seen["environment"]["evidence"]["database"] == "cf_ops_project"
    assert seen["contract"]["target"]["table"] == "orders"
    assert seen["kwargs"]["athena_output_location"] == "s3://bucket/query-results/"


def test_project_cost_evidence_insert_is_idempotent(monkeypatch) -> None:
    class _Runner:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.queries: list[str] = []
            self.statements: list[str] = []

        def query(self, statement: str):
            self.queries.append(statement)
            return [{"existing": "0"}]

        def sql(self, statement: str):
            self.statements.append(statement)
            return _AthenaResult(query_execution_id="qid-1")

    @dataclass(frozen=True)
    class _AthenaResult:
        query_execution_id: str

    @dataclass(frozen=True)
    class _Evidence:
        cost: CostEvidenceRecord

    runner = _Runner()
    monkeypatch.setattr(cli_project_cost, "AthenaSqlRunner", lambda **kwargs: runner)
    monkeypatch.setattr(
        cli_project_cost,
        "reconcile_aws_glue_job_run_evidence",
        lambda **kwargs: _Evidence(
            cost=CostEvidenceRecord(
                run_id=kwargs["run_id"],
                target_table=kwargs["target_table"],
                signal_name="glue_dpu_seconds",
                signal_value=12.5,
                payload={"WorkerType": "G.1X"},
                captured_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ),
    )

    result = cli_project_cost.record_project_step_cost_evidence(
        {"evidence": {"database": "cf_ops_project"}},
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        },
        job_name="cf-orders",
        run_id="jr-1",
        athena_output_location="s3://bucket/query-results/",
        athena_workgroup=None,
        poll_interval_seconds=1,
        max_wait_seconds=10,
    )

    assert result["status"] == "RECORDED"
    assert result["run_id"] == "cf-orders:jr-1"
    assert result["target_table"] == "glue_catalog.lake_bronze.orders"
    assert "WHERE run_id = 'cf-orders:jr-1'" in runner.queries[0]
    assert "FROM \"cf_ops_project\".\"ctrl_ingestion_cost\"" in runner.queries[0]
    assert "INSERT INTO \"cf_ops_project\".\"ctrl_ingestion_cost\"" in runner.statements[0]
    assert "'cf-orders:jr-1'" in runner.statements[0]
    assert '"contractforge_run_id":"cf-orders:jr-1"' in runner.statements[0]
    assert '"glue_run_id":"jr-1"' in runner.statements[0]
    assert "'glue_dpu_seconds'" in runner.statements[0]


def test_record_glue_cost_cli_records_completed_run(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "orders.ingestion.yaml"
    env_path = tmp_path / "orders.environment.yaml"
    contract_path.write_text(
        """
source:
  type: parquet
  path: s3://landing/orders
target:
  catalog: lake
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    env_path.write_text(
        """
name: prod
adapter: aws
evidence:
  database: cf_ops_orders
""".lstrip(),
        encoding="utf-8",
    )
    seen = {}

    def fake_record(environment, contract, **kwargs):
        seen["environment"] = environment
        seen["contract"] = contract
        seen["kwargs"] = kwargs
        return {
            "database": environment["evidence"]["database"],
            "run_id": f"{kwargs['job_name']}:{kwargs['run_id']}",
            "status": "RECORDED",
        }

    monkeypatch.setattr(cli_glue, "record_project_step_cost_evidence", fake_record)

    assert (
        main(
            [
                "record-glue-cost",
                str(contract_path),
                "--job-name",
                "contractforge_lake_bronze_orders",
                "--run-id",
                "jr-1",
                "--athena-output-location",
                "s3://bucket/query-results/",
                "--poll-interval-seconds",
                "3",
                "--max-wait-seconds",
                "30",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "database": "cf_ops_orders",
        "run_id": "contractforge_lake_bronze_orders:jr-1",
        "status": "RECORDED",
    }
    assert seen["environment"]["evidence"]["database"] == "cf_ops_orders"
    assert seen["contract"]["target"]["table"] == "orders"
    assert seen["kwargs"] == {
        "job_name": "contractforge_lake_bronze_orders",
        "run_id": "jr-1",
        "athena_output_location": "s3://bucket/query-results/",
        "athena_workgroup": None,
        "poll_interval_seconds": 3.0,
        "max_wait_seconds": 30.0,
    }


def test_register_glue_job_payload_cli_uses_rendered_payload(tmp_path, monkeypatch, capsys) -> None:
    payload_path = tmp_path / "job.json"
    payload_path.write_text(json.dumps({"Name": "cf-orders"}), encoding="utf-8")
    seen = {}

    def fake_register(payload):
        seen["payload"] = payload
        return _Registered(name=payload["Name"], action="created", arn="arn")

    monkeypatch.setattr(cli_runtime, "register_aws_glue_job_definition_payload", fake_register)

    assert main(["register-glue-job-payload", str(payload_path)]) == 0

    assert seen["payload"] == {"Name": "cf-orders"}
    assert json.loads(capsys.readouterr().out) == {"action": "created", "arn": "arn", "name": "cf-orders"}


def test_register_glue_job_cli_can_enable_bookmarks(monkeypatch, capsys) -> None:
    seen = {}

    def fake_register(**kwargs):
        seen.update(kwargs)
        return _Registered(name=kwargs["job_name"], action="created")

    monkeypatch.setattr(cli_glue, "register_aws_glue_job", fake_register)

    assert main(
        [
            "register-glue-job",
            "--job-name",
            "cf-orders",
            "--role-arn",
            "arn:aws:iam::123456789012:role/GlueRole",
            "--script-s3-uri",
            "s3://artifacts/orders.py",
            "--enable-job-bookmark",
        ]
    ) == 0

    assert seen["enable_job_bookmark"] is True
    assert json.loads(capsys.readouterr().out)["name"] == "cf-orders"


def test_wait_glue_job_cli_uses_public_runtime_helper(monkeypatch, capsys) -> None:
    seen = {}

    def fake_wait(**kwargs):
        seen.update(kwargs)
        return _Status(job_name=kwargs["job_name"], run_id=kwargs["run_id"], state="SUCCEEDED")

    monkeypatch.setattr(cli_runtime, "wait_aws_glue_job_run", fake_wait)

    assert main(["wait-glue-job", "--job-name", "cf-orders", "--run-id", "jr-1", "--max-wait-seconds", "1"]) == 0

    assert seen == {
        "job_name": "cf-orders",
        "run_id": "jr-1",
        "poll_interval_seconds": 10.0,
        "max_wait_seconds": 1.0,
    }
    assert json.loads(capsys.readouterr().out)["state"] == "SUCCEEDED"


def test_ensure_evidence_tables_cli_uses_athena_runner(monkeypatch, capsys) -> None:
    seen = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            seen["runner"] = kwargs

    def fake_ensure(**kwargs):
        seen["ensure"] = kwargs
        return _Setup(database=kwargs["database"], status="READY", statements_executed=11)

    monkeypatch.setattr(cli_runtime, "AthenaSqlRunner", FakeRunner)
    monkeypatch.setattr(cli_runtime, "ensure_aws_evidence_tables", fake_ensure)

    assert main(
        [
            "ensure-evidence-tables",
            "--database",
            "cf_ops",
            "--athena-output-location",
            "s3://bucket/query-results/",
            "--warehouse-uri",
            "s3://bucket/evidence/",
            "--skip-state",
        ]
    ) == 0

    assert seen["runner"]["database"] == "cf_ops"
    assert seen["runner"]["wait"] is True
    assert seen["ensure"]["include_state"] is False
    assert seen["ensure"]["dialect"] == "athena"
    assert seen["ensure"]["warehouse_uri"] == "s3://bucket/evidence/"
    assert json.loads(capsys.readouterr().out)["statements_executed"] == 11


def test_audit_evidence_cli_runs_standard_athena_queries(monkeypatch, capsys) -> None:
    seen = {"queries": []}

    class FakeRunner:
        def __init__(self, **kwargs):
            seen["runner"] = kwargs

        def query(self, statement: str):
            seen["queries"].append(statement)
            return [{"status": "SUCCESS", "runs": "5"}]

    monkeypatch.setattr(cli_runtime, "AthenaSqlRunner", FakeRunner)

    assert (
        main(
            [
                "audit-evidence",
                "--database",
                "cf_ops",
                "--athena-output-location",
                "s3://bucket/query-results/",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["database"] == "cf_ops"
    assert payload["status"] == "AUDITED"
    assert len(payload["checks"]) == 6
    assert any(check["name"] == "cost_by_target" for check in payload["checks"])
    assert seen["runner"]["database"] == "cf_ops"
    assert any('"cf_ops"."ctrl_ingestion_runs"' in statement for statement in seen["queries"])
    assert any('"cf_ops"."ctrl_ingestion_errors"' in statement for statement in seen["queries"])
    assert any('"cf_ops"."ctrl_ingestion_cost"' in statement for statement in seen["queries"])
    assert any('INNER JOIN "cf_ops"."ctrl_ingestion_runs" runs' in statement for statement in seen["queries"])


def test_benchmark_report_cli_renders_sql_without_aws_calls(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "customers.yaml"
    contract_path.write_text(
        """
source:
  type: jdbc
  url: jdbc:postgresql://host/db
  table: public.customers
target:
  catalog: lake
  schema: silver
  table: customers
mode: scd1_hash_diff
merge_keys: [customer_id]
hash_keys: [name, email]
""".lstrip(),
        encoding="utf-8",
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("benchmark-report must not call Athena without --run")

    monkeypatch.setattr(cli_performance, "AthenaSqlRunner", forbidden)

    assert main(["benchmark-report", str(contract_path)]) == 0

    output = capsys.readouterr().out
    assert "ctrl_ingestion_runs" in output
    assert "ctrl_ingestion_cost" in output
    assert "'glue_catalog.lake_silver.customers'" in output
    assert "initial_load" in output


def test_benchmark_report_cli_can_run_with_athena(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "customers.yaml"
    env_path = tmp_path / "aws.environment.yaml"
    contract_path.write_text(
        """
source:
  type: jdbc
  url: jdbc:postgresql://host/db
  table: public.customers
target:
  catalog: lake
  schema: silver
  table: customers
mode: scd1_hash_diff
merge_keys: [customer_id]
hash_keys: [name, email]
""".lstrip(),
        encoding="utf-8",
    )
    env_path.write_text("name: test\nadapter: aws\nevidence:\n  database: cf_ops\n", encoding="utf-8")
    seen = {}

    class Runner:
        def __init__(self, **kwargs):
            seen["kwargs"] = kwargs

        def query(self, statement: str):
            seen["statement"] = statement
            return [{"benchmark_case": "initial_load", "glue_dpu_seconds": "12.5"}]

    monkeypatch.setattr(cli_performance, "AthenaSqlRunner", Runner)

    assert (
        main(
            [
                "benchmark-report",
                str(contract_path),
                "--environment",
                str(env_path),
                "--run",
                "--athena-output-location",
                "s3://bucket/query-results/",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "REPORTED"
    assert payload["rows"] == [{"benchmark_case": "initial_load", "glue_dpu_seconds": "12.5"}]
    assert seen["kwargs"]["database"] == "cf_ops"
    assert '"cf_ops"."ctrl_ingestion_runs"' in seen["statement"]


def test_apply_annotations_cli_uses_public_runtime_helper(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    _write_contract(contract_path)
    seen = {}

    def fake_apply(contract, **kwargs):
        seen["contract"] = contract
        seen["kwargs"] = kwargs
        return {"status": "SUCCESS", "applied": 2}

    monkeypatch.setattr(cli_apply, "apply_aws_annotations_contract", fake_apply)

    assert main(["apply-annotations", str(contract_path), "--catalog-id", "123", "--no-skip-archive"]) == 0

    assert seen["contract"]["target"]["table"] == "customers"
    assert seen["kwargs"] == {"catalog_id": "123", "skip_archive": False}
    assert json.loads(capsys.readouterr().out)["status"] == "SUCCESS"


def test_apply_lakeformation_cli_requires_explicit_filter_flag(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    _write_contract(contract_path)
    seen = {}

    def fake_apply(contract, **kwargs):
        seen["contract"] = contract
        seen["kwargs"] = kwargs
        return {"permissions_granted": 1, "skipped_data_cells_filters": 1}

    monkeypatch.setattr(cli_apply, "apply_aws_lake_formation_contract", fake_apply)

    assert main(["apply-lakeformation", str(contract_path), "--account-id", "123"]) == 0

    assert seen["kwargs"] == {"account_id": "123", "allow_data_cells_filters": False}
    assert json.loads(capsys.readouterr().out)["skipped_data_cells_filters"] == 1


def test_record_operations_cli_uses_athena_runner(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    _write_contract(contract_path)
    seen = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            seen["runner"] = kwargs

    def fake_record(**kwargs):
        seen["record"] = kwargs
        return {"status": "RECORDED", "sql": "insert"}

    monkeypatch.setattr(cli_apply, "AthenaSqlRunner", FakeRunner)
    monkeypatch.setattr(cli_apply, "record_aws_operations_contract", fake_record)

    assert main(
        [
            "record-operations",
            str(contract_path),
            "--database",
            "lake_silver_ops",
            "--run-id",
            "run-1",
            "--athena-output-location",
            "s3://bucket/query-results/",
        ]
    ) == 0

    assert seen["runner"]["database"] == "lake_silver_ops"
    assert seen["record"]["run_id"] == "run-1"
    assert seen["record"]["contract"]["target"]["table"] == "customers"
    assert json.loads(capsys.readouterr().out)["status"] == "RECORDED"
