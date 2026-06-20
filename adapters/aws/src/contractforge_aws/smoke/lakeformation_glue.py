"""Glue Spark read checks for the Lake Formation consumer matrix."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from contractforge_core.security import redact_value


@dataclass(frozen=True)
class GlueReadValidationConfig:
    region: str
    database: str
    table: str
    script_s3_uri: str | None
    allowed_role_arn: str | None
    denied_role_arn: str | None
    allowed_job_name: str = "cf-lf-glue-allowed-read"
    denied_job_name: str = "cf-lf-glue-denied-read"
    temp_dir: str | None = None
    warehouse_s3_uri: str | None = None
    worker_type: str = "G.1X"
    number_of_workers: int = 2
    timeout_minutes: int = 10
    poll_interval_seconds: float = 20.0
    max_wait_seconds: float = 900.0


def read_check_script() -> str:
    return "\n".join(
        [
            "from awsglue.context import GlueContext",
            "from awsglue.job import Job",
            "from awsglue.utils import getResolvedOptions",
            "from pyspark.context import SparkContext",
            "import sys",
            "",
            "args = getResolvedOptions(sys.argv, ['JOB_NAME', 'DATABASE', 'TABLE'])",
            "sc = SparkContext.getOrCreate()",
            "glue_context = GlueContext(sc)",
            "spark = glue_context.spark_session",
            "job = Job(glue_context)",
            "job.init(args['JOB_NAME'], args)",
            "spark.conf.set('spark.sql.catalog.glue_catalog', 'org.apache.iceberg.spark.SparkCatalog')",
            "spark.conf.set('spark.sql.catalog.glue_catalog.catalog-impl', 'org.apache.iceberg.aws.glue.GlueCatalog')",
            "spark.conf.set('spark.sql.catalog.glue_catalog.io-impl', 'org.apache.iceberg.aws.s3.S3FileIO')",
            "rows = spark.sql(f\"SELECT COUNT(*) AS c FROM glue_catalog.{args['DATABASE']}.{args['TABLE']}\").collect()",
            "print(f\"CONTRACTFORGE_LF_GLUE_READ_COUNT={rows[0]['c'] if rows else 'UNKNOWN'}\")",
            "job.commit()",
            "",
        ]
    )


def validate_glue_reads(boto3: Any, config: GlueReadValidationConfig) -> dict[str, Any]:
    if not config.script_s3_uri:
        return _pending(config, "Glue read validation requires --glue-script-s3-uri.")
    glue = boto3.client("glue", region_name=config.region)
    cases = {
        "allowed_role_count": _run_case(glue, config, role_arn=config.allowed_role_arn, job_name=config.allowed_job_name, expect_success=True),
        "denied_role_count": _run_case(glue, config, role_arn=config.denied_role_arn, job_name=config.denied_job_name, expect_success=False),
    }
    pending = [
        case.get("reason")
        for case in cases.values()
        if case.get("status") == "READ_VALIDATION_PENDING" and case.get("reason")
    ]
    failures = [case for case in cases.values() if case.get("status") == "FAIL"]
    status = "FAIL" if failures else "READ_VALIDATION_PENDING" if pending else "PASS"
    return {"status": status, "config": asdict(config), "cases": cases, "pending": pending}


def _pending(config: GlueReadValidationConfig, reason: str) -> dict[str, Any]:
    return {"status": "READ_VALIDATION_PENDING", "config": asdict(config), "cases": {}, "pending": [reason]}


def _run_case(glue: Any, config: GlueReadValidationConfig, *, role_arn: str | None, job_name: str, expect_success: bool) -> dict[str, Any]:
    if not role_arn:
        return {"status": "READ_VALIDATION_PENDING", "reason": "No Glue role ARN provided for this read case."}
    try:
        _create_or_update_job(glue, config, role_arn=role_arn, job_name=job_name)
        response = glue.start_job_run(JobName=job_name, Arguments={"--DATABASE": config.database, "--TABLE": config.table})
        run_id = str(response["JobRunId"])
        run = _wait_for_run(glue, config, job_name=job_name, run_id=run_id)
        return _result_from_run(run, job_name=job_name, run_id=run_id, expect_success=expect_success)
    except Exception as exc:  # pragma: no cover - live AWS diagnostic path
        return _exception_result(exc, expect_success=expect_success)


def _create_or_update_job(glue: Any, config: GlueReadValidationConfig, *, role_arn: str, job_name: str) -> None:
    payload = _job_payload(config, role_arn)
    try:
        glue.get_job(JobName=job_name)
    except Exception as exc:
        if _is_not_found(exc):
            glue.create_job(Name=job_name, **payload)
            return
        raise
    glue.update_job(JobName=job_name, JobUpdate=payload)


def _job_payload(config: GlueReadValidationConfig, role_arn: str) -> dict[str, Any]:
    spark_conf = ["spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"]
    if config.warehouse_s3_uri:
        spark_conf.append(f"spark.sql.catalog.glue_catalog.warehouse={config.warehouse_s3_uri}")
    args = {
        "--conf": " --conf ".join(spark_conf),
        "--datalake-formats": "iceberg",
        "--enable-glue-datacatalog": "true",
        "--job-language": "python",
        "--job-bookmark-option": "job-bookmark-disable",
    }
    if config.temp_dir:
        args["--TempDir"] = config.temp_dir
    return {
        "Role": role_arn,
        "Description": "ContractForge Lake Formation Glue Spark read validation.",
        "Command": {"Name": "glueetl", "ScriptLocation": config.script_s3_uri, "PythonVersion": "3"},
        "DefaultArguments": args,
        "GlueVersion": "4.0",
        "WorkerType": config.worker_type,
        "NumberOfWorkers": config.number_of_workers,
        "Timeout": config.timeout_minutes,
        "MaxRetries": 0,
    }


def _wait_for_run(glue: Any, config: GlueReadValidationConfig, *, job_name: str, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + config.max_wait_seconds
    while True:
        run = glue.get_job_run(JobName=job_name, RunId=run_id).get("JobRun", {})
        if run.get("JobRunState") in {"SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT", "ERROR"}:
            return run
        if time.monotonic() >= deadline:
            run.setdefault("JobRunState", "TIMEOUT")
            run.setdefault("ErrorMessage", "Timed out waiting for Glue job.")
            return run
        time.sleep(config.poll_interval_seconds)


def _result_from_run(run: dict[str, Any], *, job_name: str, run_id: str, expect_success: bool) -> dict[str, Any]:
    state = run.get("JobRunState")
    error = redact_value(run.get("ErrorMessage") or run.get("StateDetail"))
    if state == "SUCCEEDED" and expect_success:
        return {"status": "PASS", "job_name": job_name, "run_id": run_id, "state": state}
    if state != "SUCCEEDED" and not expect_success:
        return {"status": "PASS", "job_name": job_name, "run_id": run_id, "state": state, "expected_failure": True, "reason": error}
    status = "FAIL"
    reason = "Denied Glue role succeeded; Lake Formation isolation was not proven." if state == "SUCCEEDED" else error
    return {"status": status, "job_name": job_name, "run_id": run_id, "state": state, "reason": reason}


def _exception_result(exc: Exception, *, expect_success: bool) -> dict[str, Any]:
    reason = redact_value(str(exc))
    status = "FAIL" if expect_success else "PASS"
    payload = {"status": status, "error_type": type(exc).__name__, "reason": reason}
    if not expect_success:
        payload["expected_failure"] = True
    return payload


def _is_not_found(exc: Exception) -> bool:
    return getattr(exc, "response", {}).get("Error", {}).get("Code") in {"EntityNotFoundException", "EntityNotFound"}


__all__ = ["GlueReadValidationConfig", "read_check_script", "validate_glue_reads"]
