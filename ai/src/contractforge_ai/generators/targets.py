"""Project generation target metadata."""

from __future__ import annotations

from dataclasses import dataclass

PROJECT_TARGETS = (
    "contractforge-yaml",
    "contractforge-python",
    "databricks-dab",
    "aws-glue-iceberg",
    "snowflake-sql-warehouse",
    "fabric-lakehouse",
    "gcp-bigquery",
    "dbt",
    "classic-pyspark",
)


@dataclass(frozen=True)
class ProjectTargetSpecBinding:
    """Map an enriched specification field into a target generation kwarg."""

    spec_field: str
    kwarg: str


PROJECT_TARGET_SPEC_BINDINGS: dict[str, tuple[ProjectTargetSpecBinding, ...]] = {
    "databricks-dab": (ProjectTargetSpecBinding(spec_field="dab_compute", kwarg="compute"),),
}


def supported_project_targets() -> tuple[str, ...]:
    """Return supported project generation targets in stable CLI order."""

    return PROJECT_TARGETS


def project_target_spec_bindings(target: str) -> tuple[ProjectTargetSpecBinding, ...]:
    """Return target-specific enriched-spec bindings for project generation."""

    return PROJECT_TARGET_SPEC_BINDINGS.get(target, ())
