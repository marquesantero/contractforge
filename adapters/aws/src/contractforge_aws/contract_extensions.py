"""AWS contract extension accessors and guardrails."""

from __future__ import annotations

from typing import Any

from contractforge_core.planner import PlanningWarning

AWS_EXTENSION_FIELDS = frozenset(
    {
        "dependencies",
        "dqdl",
        "glue_job",
        "iceberg",
        "job_bookmarks",
        "lake_formation",
        "native_passthrough",
    }
)

AWS_EXTENSION_MAP_FIELDS = AWS_EXTENSION_FIELDS

AWS_EXTENSION_NESTED_FIELDS = {
    "dependencies": frozenset(
        {
            "additional_python_modules",
            "extra_jars",
            "extra_py_files",
            "jars",
            "py_files",
            "python_modules",
        }
    ),
    "glue_job": frozenset(
        {
            "default_arguments",
            "description",
            "enable_job_bookmark",
            "glue_version",
            "max_retries",
            "name",
            "number_of_workers",
            "role_arn",
            "script_s3_uri",
            "spark_conf",
            "timeout_minutes",
            "worker_type",
        }
    ),
    "iceberg": frozenset({"table_properties", "warehouse"}),
    "job_bookmarks": frozenset({"enable_job_bookmark", "enabled"}),
}


def aws_extensions(contract: Any) -> dict[str, Any]:
    """Return the adapter-owned ``extensions.aws`` map."""

    extensions = getattr(contract, "extensions", None)
    if not isinstance(extensions, dict):
        return {}
    value = extensions.get("aws")
    return dict(value) if isinstance(value, dict) else {}


def aws_extension_warnings(contract: Any) -> tuple[PlanningWarning, ...]:
    """Return warnings for AWS extension keys the adapter will ignore."""

    extensions = aws_extensions(contract)
    unknown = sorted(set(extensions) - AWS_EXTENSION_FIELDS)
    unknown_warnings = tuple(
        PlanningWarning(
            code="AWS_UNKNOWN_EXTENSION",
            message=(
                f"extensions.aws.{name} is not a recognized AWS adapter extension "
                "and will not be honored by planning, rendering or runtime execution."
            ),
        )
        for name in unknown
    )
    shape_warnings = tuple(
        PlanningWarning(
            code="AWS_EXTENSION_SHAPE_IGNORED",
            message=f"extensions.aws.{name} must be a map; the declared value will not be honored.",
        )
        for name in sorted(AWS_EXTENSION_MAP_FIELDS)
        if name in extensions and not isinstance(extensions[name], dict)
    )
    nested_warnings = tuple(
        PlanningWarning(
            code="AWS_UNKNOWN_EXTENSION_FIELD",
            message=(
                f"extensions.aws.{section}.{name} is not a recognized AWS adapter extension field "
                "and will not be honored by planning, rendering or runtime execution."
            ),
        )
        for section, allowed in sorted(AWS_EXTENSION_NESTED_FIELDS.items())
        if isinstance(extensions.get(section), dict)
        for name in sorted(set(extensions[section]) - allowed)
    )
    return unknown_warnings + shape_warnings + nested_warnings
