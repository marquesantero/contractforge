import json
import sys
import types
from types import SimpleNamespace

from contractforge_ai.adapter_validation.registry import AdapterPlannerSpec, DEFAULT_ADAPTER_PLANNERS, known_adapter_names
from contractforge_ai.models import RequiredDecision
from contractforge_ai.projects import DecisionReport, ProjectArtifact, ProjectPlan
from contractforge_ai.validation import (
    validate_contract_artifact,
    validate_model_artifact,
    validate_project_plan_artifact,
)


VALID_CONTRACT = {
    "_metadata": {"draft": True, "review_required": True},
    "source": {"type": "connector", "connector": "files", "path": "/landing/orders"},
    "target": {"catalog": "main", "schema": "bronze", "table": "b_orders"},
    "mode": "scd0_append",
    "operations": {"technical_owner": "data-engineering"},
}


def test_validate_contract_artifact_maps_clean_contract_to_ready():
    report = validate_contract_artifact(VALID_CONTRACT, use_contractforge=False)

    assert report.status == "READY"
    assert report.ready is True
    assert report.checks[0].kind == "contract"


def test_validate_contract_artifact_maps_structural_failure_to_invalid():
    report = validate_contract_artifact({"mode": "scd1_hash_diff"}, use_contractforge=False)

    assert report.status == "INVALID"
    assert report.ready is False
    assert any("generated.merge_keys.missing" == finding.code for check in report.checks for finding in check.findings)


def test_validate_model_artifact_maps_schema_failure_to_invalid():
    report = validate_model_artifact({"kind": "project_plan"}, prompt_name="project.plan.enrichment.v1")

    assert report.status == "INVALID"
    assert any(
        finding.code == "structured_output.required_missing"
        for check in report.checks
        for finding in check.findings
    )


def test_validate_model_artifact_passes_registered_schema():
    report = validate_model_artifact(
        json.dumps(
            {
                "kind": "project_plan",
                "summary": "Reviewable project plan.",
                "recommendations": ["Confirm keys."],
                "evidence": ["Deterministic planner reported a required decision."],
                "assumptions": [],
                "decisions_required": ["Confirm merge keys."],
                "confidence": 0.82,
                "review_required": True,
            }
        ),
        prompt_name="project.plan.enrichment.v1",
    )

    assert report.status == "READY"


def test_validate_project_plan_detects_open_decisions():
    plan = ProjectPlan(
        name="orders",
        target="contractforge-yaml",
        artifacts=[
            ProjectArtifact(path="contracts/bronze/orders.ingestion.yaml", kind="contract", content=_contract_yaml())
        ],
        report=DecisionReport(
            title="Orders",
            summary="Generated project.",
            decisions_required=[
                RequiredDecision(question="Confirm catalog", reason="Catalog is environment-specific.", path="target.catalog")
            ],
        ),
    )

    report = validate_project_plan_artifact(plan, use_contractforge=False)

    assert report.status == "NEEDS_DECISIONS"
    assert any("Project still has required decisions" == finding.title for check in report.checks for finding in check.findings)


def test_validate_project_plan_detects_inline_secret_as_unsafe():
    plan = ProjectPlan(
        name="orders",
        target="contractforge-yaml",
        artifacts=[
            ProjectArtifact(
                path="contracts/bronze/orders.ingestion.yaml",
                kind="contract",
                content=_contract_yaml(extra="  auth:\n    password: plain-text-password\n"),
            )
        ],
        report=DecisionReport(title="Orders", summary="Generated project."),
    )

    report = validate_project_plan_artifact(plan, use_contractforge=False)

    assert report.status == "UNSAFE"
    assert any("artifact.secret.inline_value" == finding.code for check in report.checks for finding in check.findings)


def test_validate_project_plan_allows_secret_references():
    plan = ProjectPlan(
        name="orders",
        target="contractforge-yaml",
        artifacts=[
            ProjectArtifact(
                path="contracts/bronze/orders.ingestion.yaml",
                kind="contract",
                content=_contract_yaml(extra='  auth:\n    password: "{{ secret:scope/key }}"\n'),
            )
        ],
        report=DecisionReport(title="Orders", summary="Generated project."),
    )

    report = validate_project_plan_artifact(plan, use_contractforge=False)

    assert report.status == "READY"


def test_validate_contract_artifact_runs_optional_adapter_planner(monkeypatch):
    _install_fake_adapter(
        monkeypatch,
        "fake",
        status="SUPPORTED_WITH_WARNINGS",
        warnings=(SimpleNamespace(code="needs_review", message="Review the generated contract."),),
        artifacts={
            "orders.deployment_manifest.json": "{}",
            "orders.glue_job.py": "print('run')",
            "orders.evidence_ddl.sql": "create table t (id int)",
        },
    )

    report = validate_contract_artifact(VALID_CONTRACT, use_contractforge=False, adapters=("fake",))

    assert report.status == "NEEDS_DECISIONS"
    assert any(check.kind == "adapter" and check.name == "fake" for check in report.checks)
    assert any("adapter.fake.planning.warning.needs_review" == finding.code for check in report.checks for finding in check.findings)
    adapter_evidence = next(item for check in report.checks for item in check.evidence if item.source == "contractforge_fake")
    assert adapter_evidence.value["artifact_count"] == 3
    assert adapter_evidence.value["artifact_types"] == ["aws_glue_job_runtime", "deployment_manifest", "evidence_ddl_sql"]


def test_known_adapter_registry_includes_stable_cloud_adapters():
    assert {"aws", "databricks", "snowflake", "fabric", "gcp"}.issubset(set(known_adapter_names()))


def test_validate_contract_artifact_classifies_cloud_adapter_rendered_artifacts(monkeypatch):
    cases = [
        (
            "snowflake",
            {
                "orders.snowflake.runtime.sql": "select 1;",
                "orders.snowflake.task_graph.sql": "create task example;",
                "orders.contract.json": "{}",
            },
            ["contract_snapshot", "snowflake_runtime_sql", "snowflake_task_graph_sql"],
        ),
        (
            "fabric",
            {
                "orders.fabric.notebook.py": "print('run')",
                "orders.fabric.deployment.json": "{}",
            },
            ["fabric_deployment", "fabric_notebook"],
        ),
        (
            "gcp",
            {
                "orders.gcp.source_materialization.json": "{}",
                "orders.gcp.write.sql": "select 1;",
                "orders.gcp.advanced_write_mode_review.json": "{}",
            },
            ["gcp_advanced_write_review", "gcp_source_materialization", "gcp_write_sql"],
        ),
    ]

    for adapter, artifacts, expected_types in cases:
        _install_fake_adapter(monkeypatch, adapter, status="SUPPORTED", artifacts=artifacts)
        report = validate_contract_artifact(VALID_CONTRACT, use_contractforge=False, adapters=(adapter,))
        evidence = next(item for check in report.checks for item in check.evidence if item.source == f"contractforge_{adapter}")

        assert report.status == "READY"
        assert evidence.value["artifact_types"] == expected_types


def test_validate_contract_artifact_skips_adapter_rendering_for_review_placeholders(monkeypatch):
    _install_fake_adapter(
        monkeypatch,
        "fake_review",
        status="SUPPORTED",
        artifacts={"orders.glue_job.py": "print('run')"},
    )
    contract = {
        **VALID_CONTRACT,
        "source": {"type": "connector", "connector": "s3", "path": "s3://landing/orders", "format": "REVIEW_REQUIRED"},
    }

    report = validate_contract_artifact(contract, use_contractforge=False, adapters=("fake_review",))

    assert report.status == "NEEDS_DECISIONS"
    assert any("adapter.fake_review.render_review_required" == finding.code for check in report.checks for finding in check.findings)
    adapter_evidence = next(item for check in report.checks for item in check.evidence if item.source == "contractforge_fake_review")
    assert adapter_evidence.value["artifact_count"] == 0


def test_validate_project_plan_parses_toml_artifacts():
    plan = ProjectPlan(
        name="orders-python",
        target="contractforge-python",
        artifacts=[
            ProjectArtifact(
                path="pyproject.toml",
                kind="config",
                content='[project]\nname = "orders-python"\nversion = "0.1.0"\n',
            )
        ],
        report=DecisionReport(title="Orders Python", summary="Generated project."),
    )

    report = validate_project_plan_artifact(plan, use_contractforge=False)

    assert report.status == "READY"


def test_validate_project_plan_rejects_invalid_toml_artifacts():
    plan = ProjectPlan(
        name="orders-python",
        target="contractforge-python",
        artifacts=[ProjectArtifact(path="pyproject.toml", kind="config", content='[project]\nname = "orders-python"\n=')],
        report=DecisionReport(title="Orders Python", summary="Generated project."),
    )

    report = validate_project_plan_artifact(plan, use_contractforge=False)

    assert report.status == "INVALID"
    assert any(finding.code == "artifact.syntax_invalid" for check in report.checks for finding in check.findings)


def _contract_yaml(*, extra: str = "") -> str:
    return f"""
_metadata:
  draft: true
  review_required: true
source:
  type: connector
  connector: files
  path: /landing/orders
{extra}
target:
  catalog: main
  schema: bronze
  table: b_orders
mode: scd0_append
operations:
  technical_owner: data-engineering
""".lstrip()


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
