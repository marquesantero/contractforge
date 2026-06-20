from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _tracker() -> dict:
    return json.loads((ROOT / "docs" / "reports" / "aws-snowflake-production-maturity-plan.json").read_text(encoding="utf-8"))


def test_adapter_production_maturity_plan_tracks_aws_and_snowflake() -> None:
    tracker = _tracker()

    assert tracker["kind"] == "contractforge_adapter_production_maturity_plan"
    assert tracker["target"] == "stable_final"
    assert set(tracker["adapters"]) == {"contractforge-aws", "contractforge-snowflake"}
    assert tracker["summary"]["source_spec"] == "docs/specs/aws-snowflake-production-maturity-plan.md"


def test_adapter_production_maturity_plan_has_required_gates() -> None:
    gates = {gate["id"]: gate for gate in _tracker()["gates"]}

    assert set(gates) == {
        "AWS-HASHDIFF-PROD",
        "AWS-LF-CONSUMER-MATRIX",
        "AWS-KAFKA-PROVIDER-MATRIX",
        "AWS-HISTORICAL-SEMANTICS",
        "SNOWFLAKE-TASK-GRAPH-LIVE",
        "SNOWFLAKE-HASHDIFF-PROD",
        "SNOWFLAKE-ACCESS-POLICY-SMOKE",
        "SNOWFLAKE-CONTINUOUS-INGESTION-DECISION",
        "SNOWFLAKE-HISTORICAL-SEMANTICS",
    }
    assert gates["AWS-HASHDIFF-PROD"]["surface"] == "aws_glue_iceberg"
    assert gates["SNOWFLAKE-TASK-GRAPH-LIVE"]["surface"] == "snowflake_sql_warehouse"
    assert gates["SNOWFLAKE-TASK-GRAPH-LIVE"]["status"] == "PASS"


def test_adapter_production_maturity_gates_are_actionable() -> None:
    allowed_statuses = {
        "OPEN",
        "READY_TO_RUN",
        "COST_PENDING",
        "BLOCKED",
        "READ_VALIDATION_PENDING",
        "DECISION_REQUIRED",
        "PASS",
        "EXCLUDED_FROM_STABLE_FINAL",
    }

    for gate in _tracker()["gates"]:
        assert gate["status"] in allowed_statuses
        assert gate["adapter"] in {"contractforge-aws", "contractforge-snowflake"}
        assert gate["current_decision"] in {"SUPPORTED_WITH_WARNINGS", "REVIEW_REQUIRED", "EXCLUDED_FROM_STABLE_FINAL"}
        assert gate["next_action"]
        assert gate["acceptance"]
        assert gate["evidence_target"].startswith("docs/reports/")
        assert gate["evidence_target"].endswith(".json")


def test_adapter_production_maturity_execution_order_matches_gates() -> None:
    tracker = _tracker()
    gate_ids = {gate["id"] for gate in tracker["gates"]}

    assert tracker["execution_order"][0] == "AWS-HASHDIFF-PROD"
    assert set(tracker["execution_order"]) == gate_ids


def test_adapter_production_maturity_docs_are_linked() -> None:
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
    spec = (ROOT / "docs" / "specs" / "aws-snowflake-production-maturity-plan.md").read_text(encoding="utf-8")

    assert "specs/aws-snowflake-production-maturity-plan.md" in index
    assert "specs/hash-diff-production-benchmark-runbook.md" in index
    assert "specs/aws-snowflake-production-maturity-plan.md" in roadmap
    assert "../reports/aws-snowflake-production-maturity-plan.json" in spec
    assert "hash-diff-production-benchmark-runbook.md" in spec
    assert "contractforge-aws stabilization-report --strict-final" in spec
    assert "contractforge-snowflake stabilization-report --strict-final" in spec


def test_hashdiff_benchmark_manifests_exist_for_non_passing_gates() -> None:
    tracker = _tracker()
    pending_gates = {
        gate["id"]: gate
        for gate in tracker["gates"]
        if gate["id"].endswith("-HASHDIFF-PROD") and gate["status"] != "PASS"
    }

    assert pending_gates == {}
    for gate_id, gate in pending_gates.items():
        manifest_path = ROOT / gate["evidence_target"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert manifest["kind"] == "contractforge_hashdiff_production_benchmark"
        assert manifest["maturity_gate"] == gate_id
        assert manifest["adapter"] == gate["adapter"]
        assert manifest["subtarget"] == gate["surface"]
        assert manifest["status"] == gate["status"]
        assert manifest["stable_final_blocker"] is True
        assert manifest["runbook"] == "docs/specs/hash-diff-production-benchmark-runbook.md"
        assert set(manifest["required_cases"]) == {
            "initial_load",
            "no_change_replay",
            "changed_row_wave",
            "concurrent_or_overlap_guard",
            "duplicate_key_failure",
            "null_key_failure",
        }


def test_snowflake_hashdiff_benchmark_gate_has_live_success_evidence() -> None:
    tracker = _tracker()
    gate = next(item for item in tracker["gates"] if item["id"] == "SNOWFLAKE-HASHDIFF-PROD")
    manifest = json.loads((ROOT / gate["evidence_target"]).read_text(encoding="utf-8"))

    assert gate["status"] == "PASS"
    assert manifest["kind"] == "contractforge_hashdiff_production_benchmark"
    assert manifest["maturity_gate"] == "SNOWFLAKE-HASHDIFF-PROD"
    assert manifest["status"] == "PASS"
    assert manifest["stable_final_blocker"] is False
    assert {result["case"] for result in manifest["live_results"]} == {
        "initial_load",
        "no_change_replay",
        "changed_row_wave",
        "concurrent_or_overlap_guard",
        "duplicate_key_failure",
        "null_key_failure",
    }
    assert manifest["cost_reconciliation"]["status"] == "RECORDED"
    assert manifest["cost_reconciliation"]["query_count"] == 2
    assert manifest["cleanup_status"] == "RETAINED_FOR_AUDIT"
    assert any(result["status"] == "EXPECTED_FAILURE" for result in manifest["live_results"])
    no_change = next(result for result in manifest["live_results"] if result["case"] == "no_change_replay")
    changed_wave = next(result for result in manifest["live_results"] if result["case"] == "changed_row_wave")
    assert no_change["hash_diff_candidate_rows"] == 0
    assert no_change["write_query_id"]
    assert no_change["query_ids"]
    assert changed_wave["hash_diff_candidate_rows"] == 2


def test_aws_hashdiff_benchmark_gate_has_live_success_evidence() -> None:
    tracker = _tracker()
    gate = next(item for item in tracker["gates"] if item["id"] == "AWS-HASHDIFF-PROD")
    manifest = json.loads((ROOT / gate["evidence_target"]).read_text(encoding="utf-8"))

    assert gate["status"] == "PASS"
    assert manifest["kind"] == "contractforge_hashdiff_production_benchmark"
    assert manifest["maturity_gate"] == "AWS-HASHDIFF-PROD"
    assert manifest["status"] == "PASS"
    assert manifest["stable_final_blocker"] is False
    assert {result["case"] for result in manifest["live_results"]} == {
        "initial_load",
        "no_change_replay",
        "changed_row_wave",
        "concurrent_or_overlap_guard",
        "duplicate_key_failure",
        "null_key_failure",
    }
    assert manifest["cleanup_status"] == "RETAINED_FOR_AUDIT"
    assert any(result["status"] == "EXPECTED_FAILURE" for result in manifest["live_results"])


def test_aws_lake_formation_gate_records_consumer_matrix_blockers() -> None:
    tracker = _tracker()
    gate = next(item for item in tracker["gates"] if item["id"] == "AWS-LF-CONSUMER-MATRIX")
    manifest = json.loads((ROOT / gate["evidence_target"]).read_text(encoding="utf-8"))

    assert gate["status"] == "PASS"
    assert manifest["kind"] == "contractforge_aws_lake_formation_consumer_matrix"
    assert manifest["maturity_gate"] == "AWS-LF-CONSUMER-MATRIX"
    assert manifest["status"] == "PASS"
    assert manifest["result"]["status"] == "PASS"
    assert manifest["result"]["glue_table"]["is_registered_with_lakeformation"] is True
    assert manifest["result"]["lakeformation_data_cells_filter_count"] == 1
    assert manifest["result"]["consumer_principal"].endswith(":role/ContractForgeLfGlueAllowedRole")
    assert manifest["result"]["broad_iam_allowed_principals_revoked"] is True
    assert manifest["result"]["athena_read_validation"]["status"] == "PASS"
    assert manifest["result"]["athena_read_validation"]["allowed_role_count"]["query_id"]
    assert manifest["result"]["athena_read_validation"]["denied_role_count"]["expected_failure"] is True
    assert manifest["result"]["glue_read_validation"]["status"] == "PASS"
    assert manifest["result"]["glue_read_validation"]["allowed_role_count"]["run_id"]
    assert manifest["result"]["glue_read_validation"]["denied_role_count"]["expected_failure"] is True
    assert manifest["result"]["ctrl_ingestion_access_evidence"]["status"] == "RECORDED_IN_MANIFEST"
    assert manifest["result"]["temporary_runner_cleanup"]["access_keys_remaining"] == 0
    assert manifest["result"]["blockers"] == []
    assert "athena_allowed_principal_reads_declared_rows" in manifest["required_cases"]
    assert manifest["open_items"] == []


def test_aws_kafka_provider_matrix_records_msk_maturity_pass() -> None:
    tracker = _tracker()
    gate = next(item for item in tracker["gates"] if item["id"] == "AWS-KAFKA-PROVIDER-MATRIX")
    manifest = json.loads((ROOT / gate["evidence_target"]).read_text(encoding="utf-8"))

    assert gate["status"] == "PASS"
    assert manifest["kind"] == "contractforge_aws_kafka_provider_matrix"
    assert manifest["maturity_gate"] == "AWS-KAFKA-PROVIDER-MATRIX"
    assert manifest["status"] == "PASS"
    assert manifest["result"]["status"] == "PASS"
    assert manifest["result"]["maturity_scope"]["required_provider"] == "msk"
    assert manifest["result"]["providers"]["event_hubs_kafka"]["status"] == "PASS"
    assert manifest["result"]["providers"]["msk"]["status"] == "PASS"
    assert manifest["result"]["providers"]["msk"]["cluster_arn"].startswith("arn:aws:kafka:us-east-1:000000000000:cluster/cf-msk-serverless-validation")
    assert manifest["result"]["providers"]["msk"]["state"] == "ACTIVE"
    assert manifest["result"]["providers"]["msk"]["bootstrap_brokers"]["BootstrapBrokerStringSaslIam"]
    assert manifest["result"]["providers"]["msk"]["athena_evidence"]["audit_status"] == "AUDITED"
    assert manifest["result"]["providers"]["confluent_compatible"]["status"] == "OPTIONAL_READY_TO_RUN"
    assert manifest["result"]["providers"]["confluent_compatible"]["scope"] == "OPTIONAL_COMPATIBILITY"
    assert manifest["result"]["providers"]["confluent_compatible"]["secret_arn"].startswith(
        "arn:aws:secretsmanager:us-east-1:000000000000:secret:contractforge/confluent/kafka"
    )
    assert manifest["result"]["blockers"] == []
    assert "checkpoint_progress_recorded" in manifest["required_cases"]
    assert manifest["open_items"] == []
    assert any("Confluent-compatible" in item for item in manifest["optional_compatibility_items"])


def test_historical_semantics_are_explicitly_excluded_from_stable_final() -> None:
    tracker = _tracker()
    for gate_id, adapter in [
        ("AWS-HISTORICAL-SEMANTICS", "contractforge-aws"),
        ("SNOWFLAKE-HISTORICAL-SEMANTICS", "contractforge-snowflake"),
    ]:
        gate = next(item for item in tracker["gates"] if item["id"] == gate_id)
        manifest = json.loads((ROOT / gate["evidence_target"]).read_text(encoding="utf-8"))

        assert gate["status"] == "EXCLUDED_FROM_STABLE_FINAL"
        assert manifest["kind"] == "contractforge_historical_semantics_decision"
        assert manifest["adapter"] == adapter
        assert manifest["maturity_gate"] == gate_id
        assert manifest["status"] == "EXCLUDED_FROM_STABLE_FINAL"
        assert manifest["decision"]["stable_final_scope"] == "EXCLUDED"
        assert set(manifest["decision"]["excluded_modes"]) == {"historical", "snapshot_reconcile_soft_delete"}
        assert "Do not silently fall back" in manifest["decision"]["planner_behavior"]
        assert manifest["required_before_promotion"]


def test_snowflake_continuous_ingestion_is_explicitly_excluded_from_stable_final() -> None:
    tracker = _tracker()
    gate = next(item for item in tracker["gates"] if item["id"] == "SNOWFLAKE-CONTINUOUS-INGESTION-DECISION")
    manifest = json.loads((ROOT / gate["evidence_target"]).read_text(encoding="utf-8"))

    assert gate["status"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert manifest["kind"] == "contractforge_snowflake_continuous_ingestion_decision"
    assert manifest["adapter"] == "contractforge-snowflake"
    assert manifest["maturity_gate"] == "SNOWFLAKE-CONTINUOUS-INGESTION-DECISION"
    assert manifest["status"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert manifest["decision"]["stable_final_scope"] == "EXCLUDED"
    assert "kafka_available_now" in manifest["decision"]["excluded_sources"]
    assert "Do not silently fall back" in manifest["decision"]["planner_behavior"]
    assert manifest["required_before_promotion"]
    assert manifest["open_items"] == []


def test_snowflake_task_graph_gate_has_live_success_evidence() -> None:
    tracker = _tracker()
    gate = next(item for item in tracker["gates"] if item["id"] == "SNOWFLAKE-TASK-GRAPH-LIVE")
    manifest = json.loads((ROOT / gate["evidence_target"]).read_text(encoding="utf-8"))

    assert gate["status"] == "PASS"
    assert manifest["kind"] == "contractforge_snowflake_task_graph_live_smoke"
    assert manifest["maturity_gate"] == "SNOWFLAKE-TASK-GRAPH-LIVE"
    assert manifest["status"] == "PASS"
    assert manifest["result"]["status"] == "SUCCESS"
    assert manifest["result"]["bronze_count"] == 2
    assert manifest["result"]["silver_count"] == 2
    assert [task["state"] for task in manifest["result"]["task_wait"]["tasks"]] == ["SUCCEEDED", "SUCCEEDED"]
    assert "CREATE TASK" in manifest["grants"]["required_schema_grants"]
    assert "EXECUTE TASK" in manifest["grants"]["required_account_grants"]
    assert manifest["cleanup"]["status"] == "PASS"
    assert any(command.startswith("DROP STAGE IF EXISTS") for command in manifest["cleanup"]["commands"])


def test_snowflake_access_policy_gate_is_explicitly_excluded_from_stable_final() -> None:
    tracker = _tracker()
    gate = next(item for item in tracker["gates"] if item["id"] == "SNOWFLAKE-ACCESS-POLICY-SMOKE")
    manifest = json.loads((ROOT / gate["evidence_target"]).read_text(encoding="utf-8"))

    assert gate["status"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert manifest["kind"] == "contractforge_snowflake_access_policy_smoke"
    assert manifest["maturity_gate"] == "SNOWFLAKE-ACCESS-POLICY-SMOKE"
    assert manifest["status"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert manifest["decision"]["stable_final_scope"] == "EXCLUDED"
    assert manifest["result"]["error_code"] == "000002"
    assert "ROW ACCESS POLICY" in manifest["result"]["error_message"]
    assert "Do not silently apply weaker" in manifest["decision"]["planner_behavior"]
    assert "table_grant_apply" in manifest["required_cases"]
    assert "ctrl_ingestion_access_evidence" in manifest["required_cases"]
    assert manifest["required_before_promotion"]
