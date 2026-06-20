"""GCP source-family promotion planning artifacts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any

from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.source_review import gcp_source_review_payload


def render_gcp_source_promotion_plan(
    source: dict[str, Any] | str | None,
    *,
    environment: GCPEnvironment | dict[str, Any] | None = None,
) -> str:
    """Render a deterministic promotion plan for review-required source families."""

    review = gcp_source_review_payload(source)
    promotion_path = review.get("promotion_path")
    if not promotion_path:
        return ""
    payload_source = {"type": source} if isinstance(source, str) else dict(source or {})
    env = _coerce_environment(environment)
    payload = {
        "kind": "contractforge.gcp.source_family_promotion_plan.v1",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "source_type": review["source_type"],
        "status": "PLANNED_REVIEW_REQUIRED",
        "renderable": review["renderable"],
        "native_mapping": review["native_mapping"],
        "runtime_path": review["runtime_path"],
        "execution": {
            "included": False,
            "reason": "The source family has a deterministic GCP promotion path, but no stable runtime claim yet.",
        },
        "promotion_path": promotion_path,
        "review_prerequisites": review["review_prerequisites"],
        "graduation_gates": review["graduation_gates"],
        "stable_boundary": {
            "current_gate": "GCP-BQ-20C",
            "future_gate": "GCP-BQ-20",
            "decision": "PLAN_ONLY_UNTIL_REAL_ACCOUNT_E2E",
        },
    }
    biglake_registration = _biglake_iceberg_registration(payload_source, env)
    if biglake_registration:
        payload["biglake_iceberg_registration"] = biglake_registration
        payload["execution"] = {
            "included": True,
            "command": "contractforge-gcp source-promotion <contract> --execute --readback",
            "reason": "Raw Iceberg paths can be promoted by registering the declared GCS prefix as a BigLake Iceberg table, then reading back provider metadata.",
        }
        payload["stable_boundary"] = {
            "current_gate": "GCP-BQ-20E",
            "future_gate": "GCP-BQ-20",
            "decision": "RAW_ICEBERG_REGISTRATION_COMMAND_INCLUDED_FULL_SOURCE_PARITY_PENDING",
        }
    delta_materialization = _delta_materialization(payload_source, env)
    if delta_materialization:
        payload["delta_materialization"] = delta_materialization
    dataflow_streaming = _dataflow_streaming(payload_source, env)
    if dataflow_streaming:
        payload["dataflow_streaming"] = dataflow_streaming
        payload["execution"] = {
            "included": True,
            "command": "contractforge-gcp source-promotion <contract> --execute --readback",
            "reason": "Kafka/Event Hubs stream promotion can launch the declared Dataflow Kafka-to-BigQuery template, then read back Dataflow job and BigQuery target metadata.",
        }
        payload["stable_boundary"] = {
            "current_gate": "GCP-BQ-13A",
            "decision": "DATAFLOW_TEMPLATE_COMMAND_INCLUDED_CONFLUENT_PROVIDER_PARITY_VALIDATED",
        }
    dataflow_jdbc = _dataflow_jdbc(payload_source, env)
    if dataflow_jdbc:
        payload["dataflow_jdbc"] = dataflow_jdbc
        payload["execution"] = {
            "included": True,
            "command": "contractforge-gcp source-promotion <contract> --execute --readback",
            "reason": "JDBC source promotion can launch the declared Dataflow JDBC-to-BigQuery batch template, then read back Dataflow job and BigQuery target metadata.",
        }
        payload["stable_boundary"] = {
            "current_gate": "GCP-BQ-20F",
            "future_gate": "GCP-BQ-20",
            "decision": "DATAFLOW_JDBC_TEMPLATE_COMMAND_INCLUDED_FULL_SOURCE_PARITY_PENDING",
        }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def run_gcp_source_promotion(
    source: dict[str, Any] | str | None,
    *,
    environment: GCPEnvironment | dict[str, Any] | None = None,
    execute: bool = False,
    readback: bool = False,
    runner: Any | None = None,
) -> dict[str, Any]:
    """Render or execute the supported source-family promotion command surface."""

    plan_text = render_gcp_source_promotion_plan(source, environment=environment)
    if not plan_text:
        return {
            "kind": "contractforge.gcp.source_family_promotion_result.v1",
            "status": "SKIPPED",
            "reason": "No GCP source-family promotion plan is declared for this source.",
        }
    plan = json.loads(plan_text)
    result: dict[str, Any] = {
        "kind": "contractforge.gcp.source_family_promotion_result.v1",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "source_type": plan["source_type"],
        "status": "PLANNED_NOT_EXECUTED",
        "execute": execute,
        "readback": readback,
        "plan": plan,
        "operations": [],
    }
    registration = plan.get("biglake_iceberg_registration")
    dataflow = plan.get("dataflow_streaming")
    dataflow_jdbc = plan.get("dataflow_jdbc")
    if not registration and not dataflow and not dataflow_jdbc:
        result["reason"] = "This source family has a promotion plan but no adapter-owned execution path yet."
        return result
    if dataflow_jdbc:
        return _run_dataflow_jdbc_promotion(
            result=result,
            dataflow=dataflow_jdbc,
            execute=execute,
            readback=readback,
            runner=runner,
        )
    if dataflow:
        return _run_dataflow_streaming_promotion(
            result=result,
            dataflow=dataflow,
            execute=execute,
            readback=readback,
            runner=runner,
        )
    if not execute:
        result["reason"] = "Dry-run only. Pass --execute to create the registered BigLake Iceberg table."
        return result

    command = list(registration["bq_mk_command"])
    mk = _run_command(command, runner=runner)
    result["operations"].append({"name": "register_biglake_iceberg_table", **mk})
    if mk["status"] != "SUCCEEDED":
        result["status"] = "FAILED"
        return result
    if readback:
        show_command = [
            command[0],
            "--format=prettyjson",
            "show",
            registration["bq_table_arg"],
        ]
        show = _run_command(show_command, runner=runner)
        show_operation: dict[str, Any] = {"name": "readback_biglake_iceberg_table", **show}
        if show["status"] == "SUCCEEDED":
            try:
                payload = json.loads(show["stdout"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            show_operation["biglake_configuration"] = payload.get("biglakeConfiguration", {})
            show_operation["num_rows"] = payload.get("numRows")
            result["readback_assertions"] = _biglake_readback_assertions(registration, payload)
            if not all(item["passed"] for item in result["readback_assertions"]):
                show_operation["status"] = "FAILED"
                result["status"] = "FAILED"
        result["operations"].append(show_operation)
        if show_operation["status"] != "SUCCEEDED":
            result["status"] = "FAILED"
            return result
    result["status"] = "SUCCEEDED"
    return result


def _run_dataflow_jdbc_promotion(
    *,
    result: dict[str, Any],
    dataflow: dict[str, Any],
    execute: bool,
    readback: bool,
    runner: Any | None,
) -> dict[str, Any]:
    if not execute:
        result["reason"] = "Dry-run only. Pass --execute to launch the Dataflow JDBC-to-BigQuery template."
        return result

    launch = _run_dataflow_launch_command(dataflow, runner=runner)
    launch_operation: dict[str, Any] = {"name": "launch_dataflow_jdbc_to_bigquery", **launch}
    job_id = _dataflow_job_id(launch.get("stdout") or "")
    if job_id:
        launch_operation["job_id"] = job_id
    result["operations"].append(launch_operation)
    if launch["status"] != "SUCCEEDED":
        result["status"] = "FAILED"
        return result

    if readback:
        describe_job_id = job_id or str(dataflow.get("job_name") or "").strip()
        if describe_job_id:
            describe = _run_command(_dataflow_describe_command(dataflow, describe_job_id), runner=runner)
            describe_operation: dict[str, Any] = {"name": "readback_dataflow_job", **describe}
            if describe["status"] == "SUCCEEDED":
                try:
                    payload = json.loads(describe["stdout"] or "{}")
                except json.JSONDecodeError:
                    payload = {}
                describe_operation["current_state"] = payload.get("currentState") or payload.get("current_state")
                describe_operation["job_id"] = payload.get("id") or describe_job_id
                describe_operation["region"] = dataflow["location"]
            result["operations"].append(describe_operation)
            if describe_operation["status"] != "SUCCEEDED":
                result["status"] = "FAILED"
                return result
        count_command = _bigquery_count_command(str(dataflow["parameters"].get("outputTable") or ""))
        if count_command:
            count = _run_command(count_command, runner=runner)
            count_operation: dict[str, Any] = {"name": "readback_bigquery_output_table", **count}
            if count["status"] == "SUCCEEDED":
                count_operation["row_count"] = _bq_count_from_stdout(count.get("stdout") or "")
            result["operations"].append(count_operation)
            if count_operation["status"] != "SUCCEEDED":
                result["status"] = "FAILED"
                return result
    result["status"] = "SUCCEEDED"
    result["review_boundary"] = "GCP-BQ-20F proves Dataflow JDBC command/readback only; bronze-to-gold source-family parity remains GCP-BQ-20."
    return result


def _run_dataflow_streaming_promotion(
    *,
    result: dict[str, Any],
    dataflow: dict[str, Any],
    execute: bool,
    readback: bool,
    runner: Any | None,
) -> dict[str, Any]:
    if not execute:
        result["reason"] = "Dry-run only. Pass --execute to launch the Dataflow Kafka-to-BigQuery template."
        return result

    launch = _run_dataflow_launch_command(dataflow, runner=runner)
    launch_operation: dict[str, Any] = {"name": "launch_dataflow_kafka_to_bigquery", **launch}
    job_id = _dataflow_job_id(launch.get("stdout") or "")
    if job_id:
        launch_operation["job_id"] = job_id
    result["operations"].append(launch_operation)
    if launch["status"] != "SUCCEEDED":
        result["status"] = "FAILED"
        return result

    if readback:
        describe_job_id = job_id or str(dataflow.get("job_name") or "").strip()
        if describe_job_id:
            describe = _run_command(_dataflow_describe_command(dataflow, describe_job_id), runner=runner)
            describe_operation: dict[str, Any] = {"name": "readback_dataflow_job", **describe}
            if describe["status"] == "SUCCEEDED":
                try:
                    payload = json.loads(describe["stdout"] or "{}")
                except json.JSONDecodeError:
                    payload = {}
                describe_operation["job_id"] = payload.get("id") or describe_job_id
                describe_operation["current_state"] = payload.get("currentState") or payload.get("state")
                describe_operation["region"] = dataflow["location"]
            result["operations"].append(describe_operation)
            if describe_operation["status"] != "SUCCEEDED":
                result["status"] = "FAILED"
                return result
        count_command = _bigquery_count_command(str(dataflow["parameters"].get("outputTableSpec") or ""))
        if count_command:
            count = _run_command(count_command, runner=runner)
            count_operation: dict[str, Any] = {"name": "readback_bigquery_output_table", **count}
            if count["status"] == "SUCCEEDED":
                count_operation["row_count"] = _bq_count_from_stdout(count.get("stdout") or "")
            result["operations"].append(count_operation)
            if count_operation["status"] != "SUCCEEDED":
                result["status"] = "FAILED"
                return result
        dlq_count_command = _bigquery_count_command(str(dataflow["parameters"].get("outputDeadletterTable") or ""))
        if dlq_count_command:
            dlq_count = _run_command(dlq_count_command, runner=runner)
            dlq_count_operation: dict[str, Any] = {"name": "readback_bigquery_dlq_table", **dlq_count}
            if dlq_count["status"] == "SUCCEEDED":
                dlq_count_operation["row_count"] = _bq_count_from_stdout(dlq_count.get("stdout") or "")
            result["operations"].append(dlq_count_operation)
            if dlq_count_operation["status"] != "SUCCEEDED":
                result["status"] = "FAILED"
                return result

    result["status"] = "SUCCEEDED"
    result["review_boundary"] = (
        "This validates the adapter-owned Dataflow launch/readback command path. "
        "Provider maturity also requires live row, DLQ, offset, checkpoint and no-input catch-up evidence."
    )
    return result


def _coerce_environment(environment: GCPEnvironment | dict[str, Any] | None) -> GCPEnvironment:
    if isinstance(environment, GCPEnvironment):
        return environment
    if isinstance(environment, dict):
        return GCPEnvironment.from_contract(environment)
    return GCPEnvironment()


def _biglake_iceberg_registration(source: dict[str, Any], env: GCPEnvironment) -> dict[str, Any]:
    source_type = _source_type(source)
    table = str(source.get("table") or source.get("table_ref") or source.get("ref") or "").strip()
    raw_path = str(source.get("path") or "").strip()
    if source_type != "iceberg_table" or table or not raw_path.startswith("gs://"):
        return {}
    binding = source.get("registration") if isinstance(source.get("registration"), dict) else {}
    biglake = source.get("biglake") if isinstance(source.get("biglake"), dict) else {}
    binding = {**biglake, **binding}
    project_id = _value(binding.get("project_id") or binding.get("project") or env.project_id, "{{ parameter:gcp.project_id }}")
    location = _value(binding.get("location") or binding.get("connection_location") or env.location, "{{ parameter:gcp.location }}")
    dataset = _value(binding.get("dataset") or binding.get("bigquery_dataset") or env.dataset, "{{ parameter:gcp.dataset }}")
    table_name = _value(
        binding.get("table") or binding.get("registered_table") or binding.get("table_id"),
        f"registered_{_safe_table_suffix(raw_path)}",
    )
    connection_id = _value(
        binding.get("connection_id") or binding.get("connection"),
        "{{ parameter:gcp.biglake.connection_id }}",
    )
    connection_service_account = _value(
        binding.get("connection_service_account") or binding.get("service_account"),
        "{{ runtime:bigquery_connection_service_account }}",
    )
    file_format = _value(binding.get("file_format"), "PARQUET").upper()
    storage_uri = _ensure_trailing_slash(raw_path)
    schema = _schema_arg(binding.get("schema") or source.get("schema") or source.get("columns"))
    registered_table = table_name if "." in table_name else f"{project_id}.{dataset}.{table_name}"
    bq_table_arg = _bq_table_arg(table_name=table_name, project_id=project_id, dataset=dataset)
    command = [
        "bq",
        "--location",
        location,
        "mk",
        "--table",
        f"--connection_id={connection_id}",
        "--managed_table_type=BIGLAKE",
        "--table_format=ICEBERG",
        f"--file_format={file_format}",
        f"--storage_uri={storage_uri}",
        bq_table_arg,
        schema,
    ]
    return {
        "kind": "contractforge.gcp.biglake_iceberg_registration_plan.v1",
        "status": "REVIEW_REQUIRED",
        "reason": "BigQuery queries registered tables; a raw gs:// Iceberg path must be registered before the contract becomes renderable.",
        "source_storage_uri": storage_uri,
        "registered_table": registered_table,
        "bq_table_arg": bq_table_arg,
        "connection": {
            "connection_id": connection_id,
            "location": location,
            "service_account": connection_service_account,
            "required_storage_role": "roles/storage.objectAdmin",
        },
        "table_options": {
            "managed_table_type": "BIGLAKE",
            "table_format": "ICEBERG",
            "file_format": file_format,
        },
        "schema": schema,
        "bq_mk_command": command,
        "post_registration_source": {
            "type": "iceberg_table",
            "table": registered_table,
        },
        "readback_required": [
            "bq show --format=prettyjson must include biglakeConfiguration.storageUri equal to source_storage_uri.",
            "bq show --format=prettyjson must include biglakeConfiguration.tableFormat equal to ICEBERG.",
            "bq show --format=prettyjson must include the expected schema fields.",
            "A BigQuery SELECT against registered_table must return the expected row count.",
        ],
    }


def _delta_materialization(source: dict[str, Any], env: GCPEnvironment) -> dict[str, Any]:
    source_type = _source_type(source)
    if source_type not in {"delta", "delta_table", "delta_share"}:
        return {}
    binding = source.get("materialization") if isinstance(source.get("materialization"), dict) else {}
    dataproc = source.get("dataproc") if isinstance(source.get("dataproc"), dict) else {}
    binding = {**dataproc, **binding}
    project_id = _value(binding.get("project_id") or binding.get("project") or env.project_id, "{{ parameter:gcp.project_id }}")
    location = _value(binding.get("location") or binding.get("region") or env.location, "{{ parameter:gcp.location }}")
    staging_bucket = _value(binding.get("staging_bucket") or env.staging_bucket, "{{ parameter:gcp.staging_bucket }}")
    source_identity = _value(source.get("table") or source.get("table_ref") or source.get("path"), "{{ source:delta_identifier }}")
    landing_prefix = _value(
        binding.get("landing_prefix") or binding.get("gcs_prefix"),
        f"gs://{staging_bucket}/contractforge/delta-materialized/{_safe_table_suffix(source_identity)}/",
    )
    output_table = _value(binding.get("output_table") or binding.get("target_table"), "{{ target:bigquery_table }}")
    dependency_set = ["delta-spark", "google-cloud-bigquery"]
    credential_binding = "GCS/object-store IAM for path-based Delta sources."
    if source_type == "delta_share":
        dependency_set = ["delta-sharing-spark", "google-cloud-bigquery"]
        credential_binding = "Delta Sharing profile resolved outside the contract body, preferably through Secret Manager or a mounted profile file."
    return {
        "kind": "contractforge.gcp.delta_materialization_plan.v1",
        "status": "REVIEW_REQUIRED",
        "runtime": "Dataproc Serverless Spark materialization before BigQuery load/query.",
        "source_type": source_type,
        "source_identity": source_identity,
        "project_id": project_id,
        "location": location,
        "landing_prefix": _ensure_trailing_slash(landing_prefix),
        "output_table": output_table,
        "dependency_set": dependency_set,
        "credential_binding": credential_binding,
        "commands": {
            "submit_batch": [
                "gcloud",
                "dataproc",
                "batches",
                "submit",
                "pyspark",
                "{{ artifact:gcp.delta_materialization.py }}",
                "--region",
                location,
                "--project",
                project_id,
            ]
        },
        "post_materialization_source": {
            "type": "table",
            "table": output_table,
        },
        "readback_required": [
            "Dataproc batch state is SUCCEEDED and batch id is recorded in run evidence.",
            "Source snapshot/version or Delta Sharing response metadata is recorded without credentials.",
            "Materialized row count and BigQuery target row count match for the same ContractForge run id.",
            "Provider revocation and missing table/profile failures persist failed-run evidence.",
        ],
        "non_claims": [
            "Manual export/import is not promotion evidence.",
            "A staged copy alone does not prove Delta Sharing parity until version/snapshot and failure semantics are recorded.",
        ],
    }


def _dataflow_streaming(source: dict[str, Any], env: GCPEnvironment) -> dict[str, Any]:
    source_type = _source_type(source)
    if source_type not in {"kafka_bounded", "kafka_available_now", "eventhubs_bounded", "eventhubs_available_now"}:
        return {}
    binding = source.get("dataflow") if isinstance(source.get("dataflow"), dict) else {}
    output = source.get("output") if isinstance(source.get("output"), dict) else {}
    auth = source.get("auth") if isinstance(source.get("auth"), dict) else {}
    project_id = _value(binding.get("project_id") or binding.get("project") or env.project_id, "{{ parameter:gcp.project_id }}")
    location = _value(binding.get("location") or binding.get("region") or env.location, "{{ parameter:gcp.location }}")
    temp_location = _value(
        binding.get("temp_location") or binding.get("tempLocation"),
        f"gs://{_value(env.staging_bucket, '{{ parameter:gcp.staging_bucket }}')}/dataflow/temp/",
    )
    topic = _value(source.get("topic") or binding.get("topic"), "{{ source:kafka_topic }}")
    bootstrap = _value(
        source.get("bootstrap_servers") or source.get("bootstrapServers") or binding.get("bootstrap_servers"),
        "{{ secret:gcp/kafka_bootstrap_servers }}",
    )
    output_table = _value(
        output.get("table") or output.get("output_table_spec") or binding.get("output_table_spec"),
        "{{ target:project:dataset.table }}",
    )
    output_deadletter_table = _value(
        output.get("deadletter_table") or output.get("dlq_table") or binding.get("output_deadletter_table"),
        "",
    )
    consumer_group = _value(
        source.get("consumer_group_id") or source.get("consumerGroupId") or binding.get("consumer_group_id"),
        "{{ contract:stream_consumer_group }}",
    )
    checkpoint_location = _value(
        source.get("checkpoint_location") or binding.get("checkpoint_location"),
        f"gs://{_value(env.staging_bucket, '{{ parameter:gcp.staging_bucket }}')}/dataflow/checkpoints/{_safe_table_suffix(topic)}/",
    )
    message_format = _value(source.get("message_format") or source.get("format") or binding.get("message_format"), "JSON").upper()
    provider = "eventhubs_kafka" if source_type.startswith("eventhubs") else "kafka"
    kafka_auth_mode = _value(auth.get("mode") or binding.get("kafka_read_authentication_mode"), "NONE").upper()
    parameters = {
        "readBootstrapServerAndTopic": f"{bootstrap};{topic}",
        "writeMode": "SINGLE_TABLE_NAME",
        "outputTableSpec": output_table,
        "messageFormat": message_format,
        "kafkaReadAuthenticationMode": kafka_auth_mode,
        "enableCommitOffsets": "true",
        "consumerGroupId": consumer_group,
        "kafkaReadOffset": _value(source.get("starting_offsets") or source.get("starting_offset") or binding.get("kafka_read_offset"), "earliest"),
        "useBigQueryDLQ": "true",
    }
    username_secret = auth.get("username_secret_id") or binding.get("kafka_read_username_secret_id")
    password_secret = auth.get("password_secret_id") or binding.get("kafka_read_password_secret_id")
    if username_secret:
        parameters["kafkaReadUsernameSecretId"] = str(username_secret)
    if password_secret:
        parameters["kafkaReadPasswordSecretId"] = str(password_secret)
    if output_deadletter_table:
        parameters["outputDeadletterTable"] = output_deadletter_table
    launch_options = {
        "network": str(binding.get("network") or "").strip(),
        "subnetwork": str(binding.get("subnetwork") or "").strip(),
        "service_account_email": str(
            binding.get("service_account_email") or binding.get("service_account") or env.service_account or ""
        ).strip(),
        "staging_location": str(binding.get("staging_location") or binding.get("stagingLocation") or "").strip(),
        "temp_location": _ensure_trailing_slash(temp_location),
        "disable_public_ips": _bool_value(binding.get("disable_public_ips") or binding.get("disablePublicIps"), False),
        "enable_streaming_engine": _bool_value(binding.get("enable_streaming_engine"), True),
        "additional_pipeline_options": _value(
            binding.get("additional_pipeline_options"),
            "streaming=true",
        ),
        "worker_zone": str(binding.get("worker_zone") or "").strip(),
        "worker_region": str(binding.get("worker_region") or "").strip(),
        "worker_machine_type": str(binding.get("worker_machine_type") or "").strip(),
        "num_workers": str(binding.get("num_workers") or "").strip(),
        "max_workers": str(binding.get("max_workers") or "").strip(),
    }
    launch_options = {key: value for key, value in launch_options.items() if value not in (None, "", False)}
    return {
        "kind": "contractforge.gcp.dataflow_streaming_promotion_plan.v1",
        "status": "REVIEW_REQUIRED",
        "source_type": source_type,
        "provider": provider,
        "runtime": "Google-provided Dataflow Kafka to BigQuery streaming template.",
        "project_id": project_id,
        "location": location,
        "temp_location": _ensure_trailing_slash(temp_location),
        "checkpoint_location": _ensure_trailing_slash(checkpoint_location),
        "job_name": _value(binding.get("job_name") or binding.get("dataflow_job_name"), f"cf-{_safe_table_suffix(topic)}-stream"),
        "template": {
            "name": "Kafka_to_BigQuery_Flex",
            "documentation": "https://docs.cloud.google.com/dataflow/docs/guides/templates/provided/kafka-to-bigquery",
        },
        "launch_options": launch_options,
        "parameters": parameters,
        "launch_command": [
            "gcloud",
            "dataflow",
            "flex-template",
            "run",
            "{{ dataflow_job_name }}",
            "--region",
            location,
            "--project",
            project_id,
            "--template-file-gcs-location",
            f"gs://dataflow-templates-{location}/latest/flex/Kafka_to_BigQuery_Flex",
            *_dataflow_launch_options_args({"launch_options": launch_options}),
            "--parameters",
            "{{ rendered_parameter_csv }}",
        ],
        "readback_commands": {
            "describe_job": [
                "gcloud",
                "dataflow",
                "jobs",
                "describe",
                "{{ dataflow_job_id }}",
                "--region",
                location,
                "--project",
                project_id,
                "--format=json",
            ],
            "count_output_table": _bigquery_count_command(output_table) or [],
            "count_dlq_table": _bigquery_count_command(output_deadletter_table) or [],
        },
        "evidence_required": [
            "Dataflow job id, state and region are captured for the ContractForge run id.",
            "Kafka starting offsets, ending offsets and committed offsets are captured or read back.",
            "BigQuery rows written, rejected rows and DLQ rows reconcile with stream evidence.",
            "No-input rerun proves checkpoint/consumer-group behavior for available-now semantics.",
        ],
        "non_claims": [
            "A continuous Dataflow job is not equivalent to ContractForge available-now until bounded catch-up/termination semantics are proven.",
            "Direct Pub/Sub-to-BigQuery subscriptions do not prove Kafka offset semantics.",
        ],
    }


def _dataflow_jdbc(source: dict[str, Any], env: GCPEnvironment) -> dict[str, Any]:
    source_type = _source_type(source)
    if "jdbc" not in source_type and source_type not in {"db2", "mariadb", "mysql", "oracle", "postgres", "redshift", "sqlserver"}:
        return {}
    binding = source.get("dataflow") if isinstance(source.get("dataflow"), dict) else {}
    output = source.get("output") if isinstance(source.get("output"), dict) else {}
    auth = source.get("auth") if isinstance(source.get("auth"), dict) else {}
    project_id = _value(binding.get("project_id") or binding.get("project") or env.project_id, "{{ parameter:gcp.project_id }}")
    location = _value(binding.get("location") or binding.get("region") or env.location, "{{ parameter:gcp.location }}")
    temp_location = _ensure_trailing_slash(
        _value(
            binding.get("temp_location") or binding.get("tempLocation"),
            f"gs://{_value(env.staging_bucket, '{{ parameter:gcp.staging_bucket }}')}/dataflow/temp/",
        )
    )
    output_table = _value(
        output.get("table") or output.get("output_table") or output.get("outputTable") or binding.get("output_table"),
        "{{ target:project:dataset.table }}",
    )
    parameters = {
        "driverJars": _csv_value(source.get("driver_jars") or binding.get("driver_jars") or binding.get("driverJars")),
        "driverClassName": _value(
            source.get("driver_class_name") or binding.get("driver_class_name") or binding.get("driverClassName"),
            _default_jdbc_driver(source_type),
        ),
        "connectionURL": _value(source.get("url") or source.get("connection_url") or binding.get("connection_url"), "{{ secret:gcp/jdbc_connection_url }}"),
        "outputTable": output_table,
        "bigQueryLoadingTemporaryDirectory": _value(
            binding.get("big_query_loading_temporary_directory")
            or binding.get("bigQueryLoadingTemporaryDirectory")
            or output.get("big_query_loading_temporary_directory"),
            f"{temp_location}bq-load/",
        ),
    }
    query = _value(source.get("query") or binding.get("query"), "")
    table = _value(source.get("table") or source.get("dbtable") or binding.get("table"), "")
    if query:
        parameters["query"] = query
    elif table:
        parameters["table"] = table
    username = auth.get("username_secret_id") or binding.get("username_secret_id") or auth.get("username")
    password = auth.get("password_secret_id") or binding.get("password_secret_id") or auth.get("password")
    if username:
        parameters["username"] = str(username)
    if password:
        parameters["password"] = str(password)
    optional_map = {
        "connectionProperties": source.get("connection_properties") or binding.get("connection_properties"),
        "useColumnAlias": binding.get("use_column_alias") or source.get("use_column_alias"),
        "isTruncate": binding.get("is_truncate") or source.get("is_truncate"),
        "partitionColumn": source.get("partition_column") or binding.get("partition_column"),
        "partitionColumnType": source.get("partition_column_type") or binding.get("partition_column_type"),
        "numPartitions": source.get("num_partitions") or binding.get("num_partitions"),
        "lowerBound": source.get("lower_bound") or binding.get("lower_bound"),
        "upperBound": source.get("upper_bound") or binding.get("upper_bound"),
        "fetchSize": source.get("fetch_size") or binding.get("fetch_size"),
        "createDisposition": output.get("create_disposition") or binding.get("create_disposition"),
        "bigQuerySchemaPath": output.get("schema_path") or binding.get("big_query_schema_path"),
        "outputDeadletterTable": output.get("deadletter_table") or output.get("dlq_table") or binding.get("output_deadletter_table"),
        "extraFilesToStage": _csv_value(source.get("extra_files_to_stage") or binding.get("extra_files_to_stage")),
    }
    for key, value in optional_map.items():
        if value not in (None, "", [], {}):
            parameters[key] = str(value).lower() if isinstance(value, bool) else str(value)
    parameters = {key: value for key, value in parameters.items() if value not in (None, "", [], {})}
    launch_options = {
        "network": str(binding.get("network") or "").strip(),
        "subnetwork": str(binding.get("subnetwork") or "").strip(),
        "service_account_email": str(
            binding.get("service_account_email") or binding.get("service_account") or env.service_account or ""
        ).strip(),
        "staging_location": str(binding.get("staging_location") or binding.get("stagingLocation") or "").strip(),
        "temp_location": temp_location,
        "disable_public_ips": _bool_value(binding.get("disable_public_ips") or binding.get("disablePublicIps"), False),
        "worker_zone": str(binding.get("worker_zone") or "").strip(),
        "worker_region": str(binding.get("worker_region") or "").strip(),
        "worker_machine_type": str(binding.get("worker_machine_type") or "").strip(),
        "num_workers": str(binding.get("num_workers") or "").strip(),
        "max_workers": str(binding.get("max_workers") or "").strip(),
    }
    launch_options = {key: value for key, value in launch_options.items() if value not in (None, "", False)}
    return {
        "kind": "contractforge.gcp.dataflow_jdbc_promotion_plan.v1",
        "status": "REVIEW_REQUIRED",
        "source_type": source_type,
        "runtime": "Google-provided Dataflow JDBC to BigQuery batch template.",
        "project_id": project_id,
        "location": location,
        "temp_location": temp_location,
        "job_name": _value(
            binding.get("job_name") or binding.get("dataflow_job_name"),
            f"cf-{_safe_table_suffix(_output_table_name(output_table))}-jdbc",
        ),
        "template": {
            "name": "Jdbc_to_BigQuery_Flex",
            "documentation": "https://docs.cloud.google.com/dataflow/docs/guides/templates/provided/jdbc-to-bigquery",
        },
        "launch_options": launch_options,
        "parameters": parameters,
        "launch_command": [
            "gcloud",
            "dataflow",
            "flex-template",
            "run",
            "{{ dataflow_job_name }}",
            "--region",
            location,
            "--project",
            project_id,
            "--template-file-gcs-location",
            f"gs://dataflow-templates-{location}/latest/flex/Jdbc_to_BigQuery_Flex",
            *_dataflow_launch_options_args({"launch_options": launch_options}),
            "--parameters",
            "{{ rendered_parameter_csv }}",
        ],
        "readback_commands": {
            "describe_job": [
                "gcloud",
                "dataflow",
                "jobs",
                "describe",
                "{{ dataflow_job_id }}",
                "--region",
                location,
                "--project",
                project_id,
                "--format=json",
            ],
            "count_output_table": _bigquery_count_command(output_table) or [],
        },
        "evidence_required": [
            "Dataflow job id, final state and region are captured for the ContractForge run id.",
            "JDBC driver, query/table, partition options and target table are captured without credentials.",
            "BigQuery output rows reconcile with downstream bronze-to-gold row-count and quality evidence.",
            "Network, credential and schema failure paths persist failed evidence without leaking secrets.",
        ],
        "non_claims": [
            "A Dataflow JDBC load alone is not full bronze-to-gold parity until downstream contracts run from the promoted table.",
            "Manual local JDBC extraction or file export is not acceptable promotion evidence.",
        ],
    }


def _source_type(source: dict[str, Any]) -> str:
    return str(source.get("type") or source.get("connector") or "").strip().lower()


def _value(value: object, default: str) -> str:
    text = "" if value is None else str(value).strip()
    return text or default


def _csv_value(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return "" if value is None else str(value).strip()


def _default_jdbc_driver(source_type: str) -> str:
    return {
        "sqlserver": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
        "postgres": "org.postgresql.Driver",
        "mysql": "com.mysql.cj.jdbc.Driver",
        "mariadb": "org.mariadb.jdbc.Driver",
        "oracle": "oracle.jdbc.OracleDriver",
    }.get(source_type, "{{ parameter:gcp.jdbc.driver_class_name }}")


def _bool_value(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _ensure_trailing_slash(path: str) -> str:
    return path if path.endswith("/") else f"{path}/"


def _bq_table_arg(*, table_name: str, project_id: str, dataset: str) -> str:
    parts = table_name.split(".")
    if len(parts) == 3:
        return f"{parts[0]}:{parts[1]}.{parts[2]}"
    if len(parts) == 2:
        return f"{project_id}:{parts[0]}.{parts[1]}"
    return f"{project_id}:{dataset}.{table_name}"


def _safe_table_suffix(path: str) -> str:
    parts = [part for part in path.rstrip("/").split("/") if part and not part.startswith("gs:")]
    base = parts[-1] if parts else "iceberg_source"
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in base)
    safe = "_".join(part for part in safe.split("_") if part)
    return safe or "iceberg_source"


def _dataflow_launch_command(dataflow: dict[str, Any]) -> list[str]:
    template = dataflow["template"]
    return [
        "gcloud",
        "dataflow",
        "flex-template",
        "run",
        str(dataflow["job_name"]),
        "--region",
        str(dataflow["location"]),
        "--project",
        str(dataflow["project_id"]),
        "--template-file-gcs-location",
        f"gs://dataflow-templates-{dataflow['location']}/latest/flex/{template['name']}",
        *_dataflow_launch_options_args(dataflow),
        "--parameters",
        "{{ rendered_parameter_csv }}",
        "--format=json",
    ]


def _run_dataflow_launch_command(dataflow: dict[str, Any], *, runner: Any | None = None) -> dict[str, Any]:
    command = _dataflow_launch_command(dataflow)
    if runner is not None:
        command = [item if item != "{{ rendered_parameter_csv }}" else _gcloud_parameters(dataflow["parameters"]) for item in command]
        return _run_command(command, runner=runner)

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as flags:
        flags.write(_dataflow_flags_file(dataflow))
        flags_path = flags.name
    try:
        command = ["gcloud", "dataflow", "flex-template", "run", str(dataflow["job_name"]), "--flags-file", flags_path, "--format=json"]
        result = _run_command(command, runner=runner)
        result["flags_file_used"] = True
        return result
    finally:
        try:
            os.remove(flags_path)
        except OSError:
            pass


def _dataflow_flags_file(dataflow: dict[str, Any]) -> str:
    lines = [
        f"--region: {dataflow['location']}",
        f"--project: {dataflow['project_id']}",
        f"--template-file-gcs-location: gs://dataflow-templates-{dataflow['location']}/latest/flex/{dataflow['template']['name']}",
        *_dataflow_launch_options_flags(dataflow),
        "--parameters:",
    ]
    for key, value in dataflow["parameters"].items():
        escaped = str(value).replace("'", "''")
        lines.append(f"  {key}: '{escaped}'")
    return "\n".join(lines) + "\n"


def _dataflow_launch_options_args(dataflow: dict[str, Any]) -> list[str]:
    options = dataflow.get("launch_options") if isinstance(dataflow.get("launch_options"), dict) else {}
    args: list[str] = []
    if options.get("enable_streaming_engine"):
        args.append("--enable-streaming-engine")
    if options.get("disable_public_ips"):
        args.append("--disable-public-ips")
    mapping = {
        "additional_pipeline_options": "--additional-pipeline-options",
        "network": "--network",
        "subnetwork": "--subnetwork",
        "service_account_email": "--service-account-email",
        "staging_location": "--staging-location",
        "temp_location": "--temp-location",
        "worker_zone": "--worker-zone",
        "worker_region": "--worker-region",
        "worker_machine_type": "--worker-machine-type",
        "num_workers": "--num-workers",
        "max_workers": "--max-workers",
    }
    for key, flag in mapping.items():
        value = str(options.get(key) or "").strip()
        if value:
            args.extend([flag, value])
    return args


def _dataflow_launch_options_flags(dataflow: dict[str, Any]) -> list[str]:
    options = dataflow.get("launch_options") if isinstance(dataflow.get("launch_options"), dict) else {}
    lines: list[str] = []
    if options.get("enable_streaming_engine"):
        lines.append("--enable-streaming-engine: true")
    if options.get("disable_public_ips"):
        lines.append("--disable-public-ips: true")
    mapping = {
        "additional_pipeline_options": "--additional-pipeline-options",
        "network": "--network",
        "subnetwork": "--subnetwork",
        "service_account_email": "--service-account-email",
        "staging_location": "--staging-location",
        "temp_location": "--temp-location",
        "worker_zone": "--worker-zone",
        "worker_region": "--worker-region",
        "worker_machine_type": "--worker-machine-type",
        "num_workers": "--num-workers",
        "max_workers": "--max-workers",
    }
    for key, flag in mapping.items():
        value = str(options.get(key) or "").strip()
        if value:
            lines.append(f"{flag}: {value}")
    return lines


def _dataflow_describe_command(dataflow: dict[str, Any], job_id: str) -> list[str]:
    return [
        "gcloud",
        "dataflow",
        "jobs",
        "describe",
        job_id,
        "--region",
        str(dataflow["location"]),
        "--project",
        str(dataflow["project_id"]),
        "--format=json",
    ]


def _gcloud_parameters(parameters: dict[str, Any]) -> str:
    parts = [f"{key}={value}" for key, value in parameters.items() if value not in (None, "")]
    return "^~^" + "~".join(parts)


def _dataflow_job_id(stdout: str) -> str:
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return ""
    if isinstance(payload.get("id"), str):
        return payload["id"]
    job = payload.get("job")
    if isinstance(job, dict) and isinstance(job.get("id"), str):
        return job["id"]
    return ""


def _bigquery_count_command(output_table_spec: str) -> list[str]:
    table = _table_from_output_spec(output_table_spec)
    if not table:
        return []
    return [
        "bq",
        "--format=json",
        "query",
        "--use_legacy_sql=false",
        f"SELECT COUNT(*) AS row_count FROM `{table}`",
    ]


def _table_from_output_spec(output_table_spec: str) -> str:
    if not output_table_spec or "{{" in output_table_spec:
        return ""
    if ":" in output_table_spec:
        project, rest = output_table_spec.split(":", 1)
        return f"{project}.{rest}"
    return output_table_spec


def _output_table_name(output_table_spec: str) -> str:
    table = _table_from_output_spec(output_table_spec) or output_table_spec
    return table.split(".")[-1]


def _bq_count_from_stdout(stdout: str) -> int | None:
    try:
        payload = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        return None
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        value = payload[0].get("row_count") or payload[0].get("f0_")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _run_command(command: list[str], *, runner: Any | None = None) -> dict[str, Any]:
    run = runner or subprocess.run
    if runner is None:
        command = _resolve_command(command)
    if any("{{" in item or "}}" in item for item in command):
        return {
            "status": "FAILED",
            "command": command,
            "returncode": 2,
            "stdout": "",
            "stderr": "Unresolved promotion command placeholder. Declare required source-promotion bindings before --execute.",
        }
    completed = run(command, capture_output=True, text=True)
    return {
        "status": "SUCCEEDED" if completed.returncode == 0 else "FAILED",
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _biglake_readback_assertions(registration: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    config = payload.get("biglakeConfiguration") if isinstance(payload.get("biglakeConfiguration"), dict) else {}
    expected_schema = _schema_names(registration.get("schema"))
    actual_schema = [
        str(field.get("name"))
        for field in (
            payload.get("schema", {}).get("fields", [])
            if isinstance(payload.get("schema"), dict)
            else []
        )
        if isinstance(field, dict) and field.get("name")
    ]
    return [
        {
            "name": "storage_uri",
            "expected": registration["source_storage_uri"],
            "actual": config.get("storageUri"),
            "passed": config.get("storageUri") == registration["source_storage_uri"],
        },
        {
            "name": "table_format",
            "expected": "ICEBERG",
            "actual": config.get("tableFormat"),
            "passed": config.get("tableFormat") == "ICEBERG",
        },
        {
            "name": "file_format",
            "expected": registration["table_options"]["file_format"],
            "actual": config.get("fileFormat"),
            "passed": config.get("fileFormat") == registration["table_options"]["file_format"],
        },
        {
            "name": "schema_fields",
            "expected": expected_schema,
            "actual": actual_schema,
            "passed": not expected_schema or actual_schema == expected_schema,
        },
    ]


def _schema_arg(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        parts = [
            f"{str(name).strip()}:{_normalize_type(str(data_type or 'STRING'))}"
            for name, data_type in value.items()
            if str(name).strip()
        ]
        if parts:
            return ",".join(parts)
    if isinstance(value, (list, tuple)):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                parts.append(f"{item.strip()}:STRING")
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("column") or item.get("field") or "").strip()
                if name:
                    parts.append(f"{name}:{_normalize_type(str(item.get('type') or item.get('data_type') or 'STRING'))}")
        if parts:
            return ",".join(parts)
    return "{{ parameter:gcp.biglake.schema }}"


def _schema_names(value: Any) -> list[str]:
    text = "" if value is None else str(value).strip()
    if not text or "{{" in text:
        return []
    names = []
    for field in text.split(","):
        name = field.split(":", 1)[0].strip()
        if name:
            names.append(name)
    return names


def _normalize_type(value: str) -> str:
    aliases = {"BOOL": "BOOLEAN", "FLOAT": "FLOAT64", "INTEGER": "INT64"}
    text = value.strip().upper()
    return aliases.get(text, text)


def _resolve_command(command: list[str]) -> list[str]:
    if command and command[0] == "bq":
        resolved = shutil.which("bq")
        if resolved:
            return [resolved, *command[1:]]
    if command and command[0] == "gcloud":
        resolved = shutil.which("gcloud")
        if resolved:
            return [resolved, *command[1:]]
    return command


__all__ = ["render_gcp_source_promotion_plan", "run_gcp_source_promotion"]
