import json

from contractforge_aws.cli import main
from contractforge_aws.orchestration import (
    render_eventbridge_scheduler_payload,
    render_stepfunctions_state_machine_definition,
)


def test_stepfunctions_renderer_maps_project_dependency_waves() -> None:
    project = {
        "name": "orders_project",
        "execution_order": [
            {"name": "bronze"},
            {"name": "silver_a", "depends_on": ["bronze"]},
            {"name": "silver_b", "depends_on": ["bronze"]},
            {"name": "gold", "depends_on": ["silver_a", "silver_b"]},
        ],
    }
    jobs = {
        "bronze": "cf_bronze",
        "silver_a": "cf_silver_a",
        "silver_b": "cf_silver_b",
        "gold": "cf_gold",
    }

    definition = render_stepfunctions_state_machine_definition(project, jobs)

    assert definition["StartAt"] == "Wave1"
    assert definition["States"]["Wave1"]["Parameters"]["JobName"] == "cf_bronze"
    assert definition["States"]["Wave1"]["Parameters"]["Arguments"] == {
        "--CONTRACTFORGE_MASTER_JOB_ID.$": "$$.StateMachine.Id",
        "--CONTRACTFORGE_MASTER_RUN_ID.$": "$$.Execution.Id",
        "--CONTRACTFORGE_PARENT_RUN_ID.$": "$$.Execution.Id",
        "--CONTRACTFORGE_RUN_GROUP_ID.$": "$$.Execution.Id",
    }
    assert definition["States"]["Wave1"]["Next"] == "Wave2"
    assert definition["States"]["Wave2"]["Type"] == "Parallel"
    branch_jobs = [
        branch["States"][branch["StartAt"]]["Parameters"]["JobName"]
        for branch in definition["States"]["Wave2"]["Branches"]
    ]
    assert branch_jobs == ["cf_silver_a", "cf_silver_b"]
    assert definition["States"]["Wave3"]["Parameters"]["JobName"] == "cf_gold"
    assert definition["States"]["Wave3"]["End"] is True


def test_stepfunctions_renderer_allows_external_project_dependencies() -> None:
    project = {
        "name": "orders_project",
        "execution_order": [
            {"name": "bronze", "depends_on": ["verify_source"]},
            {"name": "silver", "depends_on": ["bronze"]},
        ],
    }

    definition = render_stepfunctions_state_machine_definition(project, {"bronze": "cf_bronze", "silver": "cf_silver"})

    assert definition["States"]["Wave1"]["Parameters"]["JobName"] == "cf_bronze"
    assert definition["States"]["Wave2"]["Parameters"]["JobName"] == "cf_silver"


def test_eventbridge_scheduler_payload_is_optional_and_targets_state_machine() -> None:
    project = {
        "name": "orders_project",
        "schedule": {
            "cron": "0 6 * * *",
            "timezone": "America/Sao_Paulo",
            "enabled": False,
            "adapters": {
                "aws": {
                    "state": "DISABLED",
                }
            },
        },
    }

    payload = render_eventbridge_scheduler_payload(
        project,
        state_machine_arn="arn:aws:states:us-east-1:123:stateMachine:orders",
        role_arn="arn:aws:iam::123:role/scheduler",
    )

    assert payload["Name"] == "orders-project-schedule"
    assert payload["ScheduleExpression"] == "cron(0 6 * * ? *)"
    assert payload["ScheduleExpressionTimezone"] == "America/Sao_Paulo"
    assert payload["State"] == "DISABLED"
    assert payload["Target"]["Arn"].endswith(":stateMachine:orders")


def test_eventbridge_scheduler_payload_can_use_aws_native_expression_override() -> None:
    project = {
        "name": "orders_project",
        "schedule": {
            "cron": "0 6 * * *",
            "timezone": "America/Sao_Paulo",
            "adapters": {
                "aws": {
                    "expression": "rate(1 day)",
                    "state": "DISABLED",
                }
            },
        },
    }

    payload = render_eventbridge_scheduler_payload(project)

    assert payload["ScheduleExpression"] == "rate(1 day)"


def test_eventbridge_scheduler_payload_rejects_ambiguous_cron_days() -> None:
    project = {
        "name": "orders_project",
        "schedule": {"cron": "0 6 1 * MON", "timezone": "America/Sao_Paulo"},
    }

    try:
        render_eventbridge_scheduler_payload(project)
    except ValueError as exc:
        assert "day-of-month and day-of-week" in str(exc)
    else:
        raise AssertionError("AWS cron with both day fields should fail")


def test_deploy_project_dry_run_can_render_aws_orchestration(tmp_path, capsys) -> None:
    project_path, _env_path, contract_path = _project_files(tmp_path)
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

    assert main(["deploy-project", str(project_path), "--dry-run", "--render-orchestration"]) == 0

    payload = json.loads(capsys.readouterr().out)
    orchestration = payload["orchestration"]
    assert orchestration["type"] == "stepfunctions"
    assert orchestration["jobs"]["orders"] == "contractforge_lake_bronze_orders"
    assert orchestration["state_machine"]["definition"]["States"]["Wave1"]["Parameters"]["JobName"] == (
        "contractforge_lake_bronze_orders"
    )
    assert "deployment" not in orchestration


def test_deploy_project_can_create_stepfunctions_orchestration(tmp_path, monkeypatch, capsys) -> None:
    project_path, _env_path, contract_path = _project_files(tmp_path)
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

    from contractforge_aws.cli import project as cli_project, project_orchestration as cli_project_orchestration

    from contractforge_aws.runtime.deploy import AWSGlueContractDeployment

    monkeypatch.setattr(
        cli_project,
        "deploy_aws_contract_to_glue",
        lambda *args, **kwargs: AWSGlueContractDeployment(
            job_name="contractforge_lake_bronze_orders",
            action="updated",
            job_arn=None,
            job_definition_uri="s3://bucket/job.json",
            script_uri="s3://bucket/job.py",
            artifacts=(),
        ),
    )
    from contractforge_aws.runtime.orchestration import StepFunctionsDeployment

    monkeypatch.setattr(
        cli_project_orchestration,
        "create_or_update_state_machine_payload",
        lambda payload, state_machine_arn=None: StepFunctionsDeployment(
            name=payload["name"],
            arn="arn:aws:states:us-east-1:123:stateMachine:project",
            action="created",
        ),
    )

    assert main(["deploy-project", str(project_path), "--deploy-orchestration"]) == 0

    orchestration = json.loads(capsys.readouterr().out)["orchestration"]
    assert orchestration["deployment"]["action"] == "created"
    assert orchestration["deployment"]["arn"].endswith(":stateMachine:project")


def test_deploy_project_can_run_and_wait_stepfunctions_orchestration(tmp_path, monkeypatch, capsys) -> None:
    project_path, _env_path, contract_path = _project_files(tmp_path)
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

    from contractforge_aws.cli import project as cli_project, project_orchestration as cli_project_orchestration
    from contractforge_aws.runtime.deploy import AWSGlueContractDeployment
    from contractforge_aws.runtime.orchestration import (
        StepFunctionsDeployment,
        StepFunctionsExecution,
        StepFunctionsExecutionStatus,
    )

    monkeypatch.setattr(
        cli_project,
        "deploy_aws_contract_to_glue",
        lambda *args, **kwargs: AWSGlueContractDeployment(
            job_name="contractforge_lake_bronze_orders",
            action="updated",
            job_arn=None,
            job_definition_uri="s3://bucket/job.json",
            script_uri="s3://bucket/job.py",
            artifacts=(),
        ),
    )
    monkeypatch.setattr(
        cli_project_orchestration,
        "create_or_update_state_machine_payload",
        lambda payload, state_machine_arn=None: StepFunctionsDeployment(
            name=payload["name"],
            arn="arn:aws:states:us-east-1:123:stateMachine:project",
            action="updated",
        ),
    )
    monkeypatch.setattr(
        cli_project_orchestration,
        "start_state_machine_execution",
        lambda **kwargs: StepFunctionsExecution(
            execution_arn="arn:aws:states:us-east-1:123:execution:project:run",
            start_date="2026-06-01 20:00:00",
        ),
    )
    monkeypatch.setattr(
        cli_project_orchestration,
        "wait_state_machine_execution",
        lambda **kwargs: StepFunctionsExecutionStatus(
            execution_arn=kwargs["execution_arn"],
            status="SUCCEEDED",
            start_date="2026-06-01 20:00:00",
            stop_date="2026-06-01 20:05:00",
            output=json.dumps(
                {
                    "orders": {
                        "JobName": "contractforge_lake_bronze_orders",
                        "JobRunId": "jr-stepfunctions-1",
                    }
                }
            ),
        ),
    )

    assert main(["deploy-project", str(project_path), "--deploy-orchestration", "--wait-orchestration"]) == 0

    orchestration = json.loads(capsys.readouterr().out)["orchestration"]
    assert orchestration["execution"]["execution_arn"].endswith(":execution:project:run")
    assert orchestration["wait"]["status"] == "SUCCEEDED"
    assert "jr-stepfunctions-1" in orchestration["wait"]["output"]


def test_deploy_project_can_record_cost_after_stepfunctions_wait(tmp_path, monkeypatch, capsys) -> None:
    project_path, _env_path, contract_path = _project_files(tmp_path)
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

    from contractforge_aws.cli import project as cli_project, project_orchestration as cli_project_orchestration
    from contractforge_aws.runtime.deploy import AWSGlueContractDeployment
    from contractforge_aws.runtime.orchestration import (
        StepFunctionsDeployment,
        StepFunctionsExecution,
        StepFunctionsExecutionStatus,
    )

    monkeypatch.setattr(
        cli_project,
        "deploy_aws_contract_to_glue",
        lambda *args, **kwargs: AWSGlueContractDeployment(
            job_name="contractforge_lake_bronze_orders",
            action="updated",
            job_arn=None,
            job_definition_uri="s3://bucket/job.json",
            script_uri="s3://bucket/job.py",
            artifacts=(),
        ),
    )
    monkeypatch.setattr(
        cli_project_orchestration,
        "create_or_update_state_machine_payload",
        lambda payload, state_machine_arn=None: StepFunctionsDeployment(
            name=payload["name"],
            arn="arn:aws:states:us-east-1:123:stateMachine:project",
            action="updated",
        ),
    )
    monkeypatch.setattr(
        cli_project_orchestration,
        "start_state_machine_execution",
        lambda **kwargs: StepFunctionsExecution(execution_arn="arn:aws:states:us-east-1:123:execution:project:run"),
    )
    monkeypatch.setattr(
        cli_project_orchestration,
        "wait_state_machine_execution",
        lambda **kwargs: StepFunctionsExecutionStatus(
            execution_arn=kwargs["execution_arn"],
            status="SUCCEEDED",
            output=json.dumps({"orders": {"JobName": "contractforge_lake_bronze_orders", "JobRunId": "jr-1"}}),
        ),
    )
    monkeypatch.setattr(
        cli_project,
        "record_orchestration_cost_evidence",
        lambda *args, **kwargs: [{"step": "orders", "run_id": "contractforge_lake_bronze_orders:jr-1", "status": "RECORDED"}],
    )

    assert (
        main(
            [
                "deploy-project",
                str(project_path),
                "--deploy-orchestration",
                "--wait-orchestration",
                "--record-cost-evidence",
                "--athena-output-location",
                "s3://bucket/results/",
            ]
        )
        == 0
    )

    cost = json.loads(capsys.readouterr().out)["orchestration"]["cost_evidence"]
    assert cost == [{"step": "orders", "run_id": "contractforge_lake_bronze_orders:jr-1", "status": "RECORDED"}]


def test_deploy_project_rejects_direct_and_orchestrated_runs_together(tmp_path) -> None:
    project_path, _env_path, contract_path = _project_files(tmp_path)
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

    try:
        main(["deploy-project", str(project_path), "--run", "--deploy-orchestration", "--run-orchestration"])
    except ValueError as exc:
        assert "direct Glue" in str(exc)
    else:
        raise AssertionError("direct Glue run and Step Functions run should be mutually exclusive")


def test_deploy_project_orchestration_requires_roles_before_calling_aws(tmp_path, monkeypatch) -> None:
    from contractforge_aws.cli import project_orchestration as cli_project_orchestration
    from contractforge_aws.cli.project_orchestration import project_orchestration_payload

    monkeypatch.setattr(
        cli_project_orchestration,
        "create_or_update_state_machine_payload",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must validate before AWS calls")),
    )

    try:
        project_orchestration_payload(
            {"name": "project", "execution_order": [{"name": "orders"}]},
            [{"name": "orders", "job_name": "contractforge_orders"}],
            {"parameters": {"aws": {}}},
            deploy=True,
        )
    except ValueError as exc:
        assert "parameters.aws.step_functions.role_arn" in str(exc)
    else:
        raise AssertionError("missing Step Functions role should fail")


def _project_files(tmp_path):
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
deployment:
  aws:
    state_machine_name: contractforge_project
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
parameters:
  aws:
    step_functions:
      role_arn: arn:aws:iam::123:role/ContractForgeStepFunctionsRole
""".lstrip(),
        encoding="utf-8",
    )
    return project_path, env_path, contract_path
