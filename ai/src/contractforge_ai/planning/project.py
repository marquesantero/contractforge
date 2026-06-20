"""Natural-language project planning with deterministic review boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_ai.generators.targets import supported_project_targets
from contractforge_ai.connectors import connector_intent
from contractforge_ai.models import Assumption, EvidenceItem, RequiredDecision, Traceability, confidence_level
from contractforge_ai.planning.platforms import detect_platform_hints
from contractforge_ai.write_modes import canonical_write_mode

PlannerStatus = Literal["READY_FOR_REVIEW", "NEEDS_DECISIONS"]

_CONNECTOR_ALIASES: dict[str, tuple[str, ...]] = {
    "object_storage": ("file", "files", "volume", "folder", "object storage"),
    "table": ("registered table", "lakehouse table", "database table"),
    "delta_table": ("delta table", "delta lake"),
    "iceberg_table": ("iceberg table", "iceberg"),
    "sql": ("sql query", "source query"),
    "csv": ("csv", "csv file"),
    "json": ("json", "json file", "jsonl", "ndjson"),
    "parquet": ("parquet", "parquet file"),
    "avro": ("avro", "avro file"),
    "xml": ("xml", "xml file"),
    "incremental_files": ("incremental files", "new files", "file stream", "autoloader", "auto loader", "cloudfiles", "cloud files"),
    "http_file": ("http file", "https file", "download csv", "download json", "public url"),
    "rest_api": ("rest", "rest api", "api", "endpoint", "pagination"),
    "jdbc": ("jdbc",),
    "postgres": ("postgres", "postgresql", "rds postgres", "rds postgresql"),
    "mysql": ("mysql", "rds mysql"),
    "mariadb": ("mariadb", "maria db"),
    "sqlserver": ("sql server", "sqlserver", "mssql"),
    "oracle": ("oracle database", "oracle jdbc"),
    "redshift": ("redshift", "amazon redshift"),
    "db2": ("db2", "ibm db2"),
    "snowflake": ("snowflake",),
    "bigquery": ("bigquery", "big query"),
    "adls": ("adls", "azure data lake", "azure data lake storage", "abfs", "abfss"),
    "azure_blob": ("azure blob", "wasbs", "wasb", "blob storage"),
    "gcs": ("gcs", "google cloud storage", "gcp bucket"),
    "s3": ("s3", "s3a", "aws bucket", "bucket"),
    "sharepoint": ("sharepoint", "onedrive", "graph", "google drive"),
    "sftp": ("sftp", "ftp", "ssh file"),
    "eventhubs": ("event hub", "event hubs", "eventhub"),
    "kafka": ("kafka",),
    "salesforce": ("salesforce",),
    "appflow": ("appflow", "aws appflow"),
    "dms": ("dms", "aws dms"),
    "kinesis": ("kinesis", "aws kinesis"),
    "hubspot": ("hubspot",),
    "zendesk": ("zendesk",),
    "netsuite": ("netsuite",),
    "servicenow": ("servicenow", "service now"),
    "jira": ("jira",),
    "stripe": ("stripe",),
    "oracle_fusion": ("oracle fusion", "fusion cloud"),
}

_CONNECTOR_ALIAS_PRIORITY: dict[str, int] = {
    "appflow": 20,
    "dms": 20,
    "kinesis": 20,
    "lakeflow_connect": 20,
}

_MODES = (
    "snapshot_reconcile_soft_delete",
    "snapshot_soft_delete",
    "hash_diff_upsert",
    "scd1_hash_diff",
    "merge_current",
    "upsert",
    "scd1_upsert",
    "overwrite",
    "scd0_overwrite",
    "append",
    "scd0_append",
    "historical",
    "scd2_historical",
)

_MODE_ALIASES = {
    "snapshot_soft_delete": "snapshot_reconcile_soft_delete",
    "scd1_hash_diff": "hash_diff_upsert",
    "merge_current": "upsert",
    "scd1_upsert": "upsert",
    "scd0_overwrite": "overwrite",
    "scd0_append": "append",
    "scd2_historical": "historical",
}

_QUALITY_EXPRESSION_RESERVED_COLUMNS = {"be", "must", "should", "and", "or", "not"}

_LAYERS = ("bronze", "silver", "gold")

_TARGET_CONNECTOR_SUPPORT: dict[str, set[str]] = {
    "databricks-dab": {
        "adls",
        "azure_blob",
        "avro",
        "csv",
        "delta",
        "delta_share",
        "delta_table",
        "eventhubs_available_now",
        "eventhubs_bounded",
        "gcs",
        "http_file",
        "http_json",
        "incremental_files",
        "jdbc",
        "json",
        "jsonl",
        "kafka_available_now",
        "kafka_bounded",
        "native_passthrough",
        "ndjson",
        "object_storage",
        "orc",
        "parquet",
        "postgres",
        "rest_api",
        "s3",
        "sql",
        "table",
        "text",
        "view",
        "xml",
    },
    "aws-glue-iceberg": {
        "avro",
        "csv",
        "delta_share",
        "eventhubs_bounded",
        "gcs",
        "http_file",
        "http_json",
        "jdbc",
        "json",
        "jsonl",
        "kafka_bounded",
        "native_passthrough",
        "ndjson",
        "object_storage",
        "orc",
        "parquet",
        "postgres",
        "redshift",
        "rest_api",
        "s3",
        "sql",
        "table",
        "text",
        "xml",
    },
    "snowflake-sql-warehouse": {
        "csv",
        "http_file",
        "http_json",
        "jdbc",
        "json",
        "jsonl",
        "native_passthrough",
        "ndjson",
        "object_storage",
        "parquet",
        "postgres",
        "rest_api",
        "snowflake_jdbc",
        "sql",
        "table",
        "view",
    },
    "fabric-lakehouse": {
        "adls",
        "azure_blob",
        "avro",
        "csv",
        "delta",
        "delta_share",
        "delta_table",
        "eventhubs_bounded",
        "gcs",
        "http_file",
        "http_json",
        "jdbc",
        "json",
        "jsonl",
        "kafka_bounded",
        "native_passthrough",
        "ndjson",
        "object_storage",
        "orc",
        "parquet",
        "postgres",
        "rest_api",
        "s3",
        "sql",
        "sqlserver",
        "table",
        "text",
        "view",
        "xml",
    },
    "gcp-bigquery": {
        "avro",
        "bigquery",
        "bigquery_jdbc",
        "csv",
        "gcs",
        "http_file",
        "http_json",
        "json",
        "jsonl",
        "native_passthrough",
        "ndjson",
        "object_storage",
        "parquet",
        "rest_api",
        "sql",
        "table",
        "text",
        "view",
    },
}

_PLATFORM_TARGETS: dict[str, str] = {
    "databricks": "databricks-dab",
    "aws": "aws-glue-iceberg",
    "snowflake": "snowflake-sql-warehouse",
    "fabric": "fabric-lakehouse",
    "gcp": "gcp-bigquery",
}

_ADAPTER_TARGET_ORDER = ("databricks-dab", "aws-glue-iceberg", "snowflake-sql-warehouse", "fabric-lakehouse", "gcp-bigquery")


@dataclass(frozen=True)
class ProjectPlannerRequest:
    """Inputs for deterministic project planning from user intent."""

    intent: str
    schema_path: str | None = None
    default_catalog: str | None = None
    default_schema: str | None = None
    default_layer: str | None = None
    preferred_target: str | None = None


@dataclass(frozen=True)
class ProjectIntent:
    """Normalized intent extracted from natural language."""

    project_name: str | None = None
    connector: str | None = None
    source_system: str | None = None
    source_path: str | None = None
    target_catalog: str | None = None
    target_schema: str | None = None
    target_table: str | None = None
    layer: str | None = None
    mode: str | None = None
    schedule_cron: str | None = None
    schedule_timezone: str | None = None
    freshness: str | None = None
    latency_target: str | None = None
    governance: dict[str, Any] = field(default_factory=dict)
    portability_priority: str | None = None
    owner: str | None = None
    schema_path: str | None = None
    quality_rules: dict[str, Any] = field(default_factory=dict)
    operations: dict[str, Any] = field(default_factory=dict)
    dab_compute: dict[str, Any] = field(default_factory=dict)
    platform_hints: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "connector": self.connector,
            "source_system": self.source_system,
            "source_path": self.source_path,
            "target_catalog": self.target_catalog,
            "target_schema": self.target_schema,
            "target_table": self.target_table,
            "layer": self.layer,
            "mode": self.mode,
            "schedule_cron": self.schedule_cron,
            "schedule_timezone": self.schedule_timezone,
            "freshness": self.freshness,
            "latency_target": self.latency_target,
            "governance": self.governance,
            "portability_priority": self.portability_priority,
            "owner": self.owner,
            "schema_path": self.schema_path,
            "quality_rules": self.quality_rules,
            "operations": self.operations,
            "dab_compute": self.dab_compute,
            "platform_hints": self.platform_hints,
            "signals": self.signals,
            "missing_fields": self.missing_fields,
        }


@dataclass(frozen=True)
class ProjectRecommendation:
    """One recommended output target for a project plan."""

    target: str
    reason: str
    confidence: float
    command: str
    required_inputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "reason": self.reason,
            "confidence": self.confidence,
            "confidence_level": confidence_level(self.confidence),
            "command": self.command,
            "required_inputs": self.required_inputs,
        }

    def to_markdown(self) -> str:
        inputs = f" Missing: {', '.join(self.required_inputs)}." if self.required_inputs else ""
        return f"- `{self.target}` ({confidence_level(self.confidence)}): {self.reason}{inputs}\n  - Command: `{self.command}`"


@dataclass(frozen=True)
class ProjectPlannerResult:
    """Planner output with review boundary and explicit missing decisions."""

    status: PlannerStatus
    intent: ProjectIntent
    recommendations: list[ProjectRecommendation]
    assumptions: list[Assumption] = field(default_factory=list)
    decisions_required: list[RequiredDecision] = field(default_factory=list)
    traceability: Traceability = field(default_factory=Traceability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "intent": self.intent.to_dict(),
            "recommendations": [item.to_dict() for item in self.recommendations],
            "assumptions": [item.to_dict() for item in self.assumptions],
            "decisions_required": [item.to_dict() for item in self.decisions_required],
            "traceability": self.traceability.to_dict(),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Project Planning Result",
            "",
            f"- Status: `{self.status}`",
            f"- Connector: `{self.intent.connector or 'REVIEW_REQUIRED'}`",
            f"- Source: `{self.intent.source_path or 'REVIEW_REQUIRED'}`",
            f"- Target: `{_target_identifier(self.intent) or 'REVIEW_REQUIRED'}`",
            f"- Layer: `{self.intent.layer or 'REVIEW_REQUIRED'}`",
            f"- Mode: `{self.intent.mode or 'REVIEW_REQUIRED'}`",
            f"- Schedule: `{self.intent.schedule_cron or 'REVIEW_REQUIRED'}`",
            f"- Timezone: `{self.intent.schedule_timezone or 'REVIEW_REQUIRED'}`",
            "",
            "## Recommendations",
            *[item.to_markdown() for item in self.recommendations],
        ]
        if self.decisions_required:
            lines.extend(["", "## Decisions Required", *[item.to_markdown() for item in self.decisions_required]])
        if self.assumptions:
            lines.extend(["", "## Assumptions", *[item.to_markdown() for item in self.assumptions]])
        lines.extend(["", self.traceability.to_markdown()])
        return "\n".join(lines).rstrip() + "\n"


def plan_project_from_intent(request: ProjectPlannerRequest) -> ProjectPlannerResult:
    """Build a deterministic project plan from natural-language intent."""

    if not request.intent.strip():
        raise ValueError("Planner intent cannot be empty.")

    text = request.intent.strip()
    lowered = text.lower()
    signals: list[str] = []

    connector = _detect_connector(lowered, signals)
    layer = _detect_layer(lowered, request.default_layer, signals)
    mode = _detect_mode(lowered, layer, signals)
    target_catalog, target_schema, target_table = _detect_target(text, request)
    source_path = _detect_source_path(text, connector, signals)
    source_system = _detect_source_system(text, connector, source_path, signals)
    project_name = _detect_project_name(text, target_table)
    owner = _detect_owner(text)
    schedule_cron, schedule_timezone = _detect_schedule(text, lowered, signals)
    freshness, latency_target = _detect_freshness(text, lowered, signals)
    governance = _detect_governance(text, lowered, signals)
    platform_hints = detect_platform_hints(lowered, signals)
    portability_priority = _detect_portability_priority(lowered, platform_hints, signals)
    quality_rules = _detect_quality_rules(text)
    operations = _detect_operations(text, owner)
    dab_compute = _detect_dab_compute(text)

    missing_fields = _missing_fields(
        {
            "connector": connector,
            "source_path": source_path,
            "target_catalog": target_catalog,
            "target_schema": target_schema,
            "target_table": target_table,
            "schema_path": request.schema_path,
        }
    )

    intent = ProjectIntent(
        project_name=project_name,
        connector=connector,
        source_system=source_system,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        schedule_cron=schedule_cron,
        schedule_timezone=schedule_timezone,
        freshness=freshness,
        latency_target=latency_target,
        governance=governance,
        portability_priority=portability_priority,
        owner=owner,
        schema_path=request.schema_path,
        quality_rules=quality_rules,
        operations=operations,
        dab_compute=dab_compute,
        platform_hints=platform_hints,
        signals=signals,
        missing_fields=missing_fields,
    )

    decisions = _decisions_for(intent, request)
    assumptions = _assumptions_for(intent)
    recommendations = _recommendations_for(intent, request.preferred_target)
    confidence = _confidence(intent)
    status: PlannerStatus = "NEEDS_DECISIONS" if missing_fields or decisions else "READY_FOR_REVIEW"

    return ProjectPlannerResult(
        status=status,
        intent=intent,
        recommendations=recommendations,
        assumptions=assumptions,
        decisions_required=decisions,
        traceability=Traceability(
            confidence=confidence,
            evidence=[
                EvidenceItem(
                    source="user_intent",
                    reason="Parsed natural-language ingestion scenario into structured planning fields.",
                    value={"signals": signals, "missing_fields": missing_fields},
                    confidence=confidence,
                )
            ],
            assumptions=assumptions,
            decisions_required=decisions,
            review_required=True,
        ),
    )


def _detect_connector(lowered: str, signals: list[str]) -> str | None:
    if any(term in lowered for term in ("autoloader", "auto loader", "cloudfiles", "cloud files", "file stream", "incremental files", "new files")):
        return _connector_with_signal(
            "autoloader" if "auto" in lowered or "cloud" in lowered else "incremental_files",
            "file discovery wording",
            signals,
        )
    if "s3://" in lowered or "s3a://" in lowered:
        return _connector_with_signal("s3", "URI scheme", signals)
    if "abfs://" in lowered or "abfss://" in lowered:
        return _connector_with_signal("azure_blob", "URI scheme", signals)
    if ("http://" in lowered or "https://" in lowered) and any(term in lowered for term in ("rest", "api", "endpoint", "pagination")):
        return _connector_with_signal("rest_api", "HTTP API wording", signals)
    if "http://" in lowered or "https://" in lowered:
        return _connector_with_signal("http_file", "URI scheme", signals)
    matches: list[tuple[int, int, str, str]] = []
    for connector, aliases in _CONNECTOR_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                matches.append((_CONNECTOR_ALIAS_PRIORITY.get(connector, 0), len(alias), connector, alias))
    if not matches:
        return None
    _, _, connector, alias = sorted(matches, reverse=True)[0]
    return _connector_with_signal(connector, f"'{alias}'", signals)


def _connector_with_signal(name: str, source: str, signals: list[str]) -> str:
    intent = connector_intent(name)
    signals.append(f"{intent.to_signal()} from {source}")
    signals.append(f"connector_supported_by_core:{str(intent.supported_by_core).lower()}")
    if intent.recommendation:
        signals.append(f"connector_recommendation:{intent.recommendation}")
    return intent.connector


def _detect_layer(lowered: str, default_layer: str | None, signals: list[str]) -> str | None:
    for layer in _LAYERS:
        if re.search(rf"\b{layer}\b", lowered):
            signals.append(f"layer:{layer}")
            return layer
    if default_layer:
        signals.append(f"layer:{default_layer} from default")
        return default_layer
    return None


def _detect_mode(lowered: str, layer: str | None, signals: list[str]) -> str | None:
    normalized = lowered.replace("-", "_").replace(" ", "_")
    for mode in _MODES:
        if mode in normalized:
            public_mode = _MODE_ALIASES.get(mode, mode)
            signals.append(f"mode:{public_mode}")
            return public_mode
    if "type 2" in lowered or "history" in lowered or "historical" in lowered:
        signals.append("mode:historical from historical wording")
        return "historical"
    if "hash diff" in lowered or "hash-diff" in lowered:
        signals.append("mode:hash_diff_upsert from hash diff wording")
        return "hash_diff_upsert"
    if "upsert" in lowered or "merge" in lowered:
        signals.append("mode:upsert from merge/upsert wording")
        return "upsert"
    if "overwrite" in lowered or "replace" in lowered:
        signals.append("mode:overwrite from overwrite wording")
        return "overwrite"
    if "append" in lowered or "incremental" in lowered:
        signals.append("mode:append from append/incremental wording")
        return "append"
    if layer == "bronze":
        return "append"
    if layer == "silver":
        return "hash_diff_upsert"
    if layer == "gold":
        return "overwrite"
    return None


def _detect_target(text: str, request: ProjectPlannerRequest) -> tuple[str | None, str | None, str | None]:
    target_match = re.search(
        r"(?:target|to|into|table)\s+([A-Za-z_][\w-]*)\.([A-Za-z_][\w-]*)\.([A-Za-z_][\w-]*)",
        text,
        flags=re.IGNORECASE,
    )
    if target_match:
        return target_match.group(1), target_match.group(2), target_match.group(3)
    table_match = re.search(r"(?:target table|table)\s+([A-Za-z_][\w-]*)", text, flags=re.IGNORECASE)
    target_table = table_match.group(1) if table_match else None
    return request.default_catalog, request.default_schema, target_table


def _detect_source_path(text: str, connector: str | None, signals: list[str]) -> str | None:
    patterns = [
        r"(s3a?://[^\s,;]+)",
        r"(abfss?://[^\s,;]+)",
        r"(https?://[^\s,;]+)",
        r"(jdbc:[^\s,;]+)",
        r"(/Volumes/[^\s,;]+)",
        r"(dbfs:/[^\s,;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            signals.append("source_path:uri")
            return match.group(1).rstrip(".")
    from_match = re.search(r"(?:from|source)\s+([A-Za-z_][\w.-]*(?:/[^\s,;]+)?)", text, flags=re.IGNORECASE)
    if from_match and connector in {"snowflake_jdbc", "bigquery_jdbc", "jdbc", "native_passthrough", "postgres", "mysql", "sqlserver", "oracle"}:
        signals.append("source_path:logical-name")
        return from_match.group(1).rstrip(".")
    return None


def _detect_source_system(text: str, connector: str | None, source_path: str | None, signals: list[str]) -> str | None:
    explicit = re.search(r"(?:source system|system)\s*[:=]?\s*([A-Za-z0-9_.-]+)", text, flags=re.IGNORECASE)
    if explicit:
        signals.append("source_system:explicit")
        return explicit.group(1).rstrip(".")
    if connector in {"postgres", "mysql", "mariadb", "sqlserver", "oracle", "redshift", "db2", "snowflake_jdbc", "bigquery_jdbc"}:
        signals.append("source_system:connector")
        return connector
    if connector == "native_passthrough":
        match = re.search(r"\b(?:salesforce|workday|sap|sharepoint|stripe|oracle fusion)\b", text, flags=re.IGNORECASE)
        if match:
            signals.append("source_system:native_passthrough")
            return match.group(0).lower().replace(" ", "_")
    if source_path:
        provider = _source_system_from_path(source_path)
        if provider:
            signals.append("source_system:path-provider")
            return provider
    return None


def _detect_schedule(text: str, lowered: str, signals: list[str]) -> tuple[str | None, str | None]:
    explicit = re.search(r"\bcron(?:\s+definition)?\s*[:=]?\s*['\"]?([^'\"\n]+)", text, flags=re.IGNORECASE)
    if explicit:
        cron = _first_five_cron_fields(explicit.group(1))
        timezone = _detect_timezone(text, lowered)
        if cron:
            signals.append("schedule:cron")
            if timezone:
                signals.append(f"schedule_timezone:{timezone}")
            return cron, timezone

    daily = re.search(r"\bdaily(?:\s+at\s+(\d{1,2})(?::(\d{2}))?)?", lowered)
    if daily:
        hour = daily.group(1)
        minute = daily.group(2) or "0"
        timezone = _detect_timezone(text, lowered)
        if hour is not None:
            cron = f"{int(minute)} {int(hour)} * * *"
            signals.append("schedule:daily")
            if timezone:
                signals.append(f"schedule_timezone:{timezone}")
            return cron, timezone
        signals.append("schedule:daily_without_time")
        return None, timezone

    if re.search(r"\bhourly\b", lowered):
        timezone = _detect_timezone(text, lowered)
        signals.append("schedule:hourly")
        return "0 * * * *", timezone

    return None, None


def _detect_freshness(text: str, lowered: str, signals: list[str]) -> tuple[str | None, str | None]:
    latency = _detect_latency_target(text)
    if latency:
        signals.append("freshness:latency_target")
        signals.append(f"latency_target:{latency}")
        return "near_real_time", latency
    freshness_patterns = (
        ("real_time", ("real-time", "real time", "continuous")),
        ("near_real_time", ("near-real-time", "near real time", "available now", "available-now", "low latency")),
        ("batch", ("batch", "daily", "hourly", "scheduled")),
    )
    for freshness, terms in freshness_patterns:
        if any(term in lowered for term in terms):
            signals.append(f"freshness:{freshness}")
            return freshness, latency
    return None, None


def _detect_governance(text: str, lowered: str, signals: list[str]) -> dict[str, Any]:
    governance: dict[str, Any] = {}
    if re.search(r"\b(?:pii|personal data|sensitive)\b", lowered):
        governance["pii"] = True
    if re.search(r"\b(?:mask|masked|masking|column mask|column masking)\b", lowered):
        governance["column_masks_required"] = True
    if re.search(r"\b(?:row filter|row filters|row-level filter|row-level filters|rls|region filter|region filters)\b", lowered):
        governance["row_filters_required"] = True
    if re.search(r"\b(?:lineage|audit|evidence|control table|observability)\b", lowered):
        governance["evidence_required"] = True
    if governance:
        signals.append(f"governance:{','.join(sorted(governance))}")
    return governance


def _detect_portability_priority(lowered: str, platform_hints: list[str], signals: list[str]) -> str | None:
    if any(term in lowered for term in ("portable", "minimal difference", "minimal differences", "same contracts", "aws and databricks", "databricks and aws")):
        signals.append("portability_priority:high")
        return "high"
    if any(term in lowered for term in ("native performance", "platform native", "platform-specific", "platform specific")):
        signals.append("portability_priority:native_optimized")
        return "native_optimized"
    if len(platform_hints) > 1:
        signals.append("portability_priority:high")
        return "high"
    return None


def _source_system_from_path(source_path: str) -> str | None:
    path = source_path.lower()
    mappings = {
        "s3://": "s3",
        "s3a://": "s3",
        "abfs://": "adls",
        "abfss://": "adls",
        "gs://": "gcs",
        "http://": "http",
        "https://": "http",
        "jdbc:postgresql:": "postgres",
        "jdbc:mysql:": "mysql",
        "jdbc:sqlserver:": "sqlserver",
        "jdbc:oracle:": "oracle",
    }
    for prefix, system in mappings.items():
        if path.startswith(prefix):
            return system
    return None


def _first_five_cron_fields(value: str) -> str | None:
    fields = value.strip().split()
    return " ".join(fields[:5]) if len(fields) >= 5 else None


def _detect_timezone(text: str, lowered: str) -> str | None:
    explicit = re.search(r"\b(?:timezone|time zone|tz)\s*[:=]?\s*([A-Za-z_]+/[A-Za-z_]+(?:/[A-Za-z_]+)?)", text, flags=re.IGNORECASE)
    if explicit:
        return explicit.group(1)
    aliases = {
        "sao paulo": "America/Sao_Paulo",
        "são paulo": "America/Sao_Paulo",
        "fortaleza": "America/Fortaleza",
        "utc": "UTC",
        "new york": "America/New_York",
        "london": "Europe/London",
    }
    for alias, timezone in aliases.items():
        if alias in lowered:
            return timezone
    return None


def _detect_latency_target(text: str) -> str | None:
    match = re.search(r"\b(?:latency|freshness|sla)\s*(?:target)?\s*[:=]?\s*(\d+)\s*(minutes?|mins?|hours?|hrs?)\b", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"\bevery\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    unit = match.group(2).lower()
    normalized_unit = "minutes" if unit.startswith(("min", "minute")) else "hours"
    return f"{int(match.group(1))} {normalized_unit}"


def _detect_project_name(text: str, target_table: str | None) -> str | None:
    explicit_patterns = [
        r"(?:project|pipeline|flow)\s+(?:named|called)\s+['\"]?([A-Za-z][\w -]{2,80})['\"]?",
        r"(?:project_name|project name)\s*[:=]\s*['\"]?([A-Za-z][\w -]{2,80})['\"]?",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_project_name(match.group(1))
    if target_table:
        return target_table.replace("_", " ").title()
    return None


def _clean_project_name(value: str) -> str:
    return re.split(
        r"\s+(?:from|into|to|using|with|for)\s+",
        value.strip().rstrip("."),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()


def _detect_owner(text: str) -> str | None:
    match = re.search(r"(?:owner|technical owner)\s+([A-Za-z0-9_.@-]+)", text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _detect_operations(text: str, owner: str | None) -> dict[str, Any]:
    operations: dict[str, Any] = {}
    mappings = {
        "business_owner": r"(?:business owner)\s*[:=]?\s*([A-Za-z0-9_.@-]+)",
        "technical_owner": r"(?:technical owner)\s*[:=]?\s*([A-Za-z0-9_.@-]+)",
        "steward": r"(?:steward|data steward)\s*[:=]?\s*([A-Za-z0-9_.@-]+)",
        "support_group": r"(?:support group)\s*[:=]?\s*([A-Za-z0-9_.@-]+)",
        "escalation_group": r"(?:escalation group)\s*[:=]?\s*([A-Za-z0-9_.@-]+)",
        "expected_frequency": r"(?:expected frequency|frequency)\s*[:=]?\s*(daily|hourly|weekly|monthly)",
        "criticality": r"(?:criticality)\s*[:=]?\s*(low|medium|high|critical)",
        "runbook_url": r"(https?://[^\s,;]+)",
    }
    for key, pattern in mappings.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            operations[key] = match.group(1).rstrip(".")
    if owner and "technical_owner" not in operations:
        operations["technical_owner"] = owner
    sla = re.search(r"(?:freshness\s+)?sla\s*[:=]?\s*(\d+)\s*(?:minutes?|mins?|min)", text, flags=re.IGNORECASE)
    if not sla:
        sla = re.search(r"(?:freshness_sla_minutes)\s*[:=]\s*(\d+)", text, flags=re.IGNORECASE)
    if sla:
        operations["freshness_sla_minutes"] = int(sla.group(1))
    lowered = text.lower()
    if "alert on failure" in lowered:
        operations["alert_on_failure"] = True
    if "alert on quality failure" in lowered or "alert on quality fail" in lowered:
        operations["alert_on_quality_fail"] = True
    return operations


def _detect_quality_rules(text: str) -> dict[str, Any]:
    rules: dict[str, Any] = {}
    required = _columns_after_labels(text, ("required columns", "not null", "not_null", "mandatory columns"))
    if required:
        rules["not_null"] = required
    unique = _columns_after_labels(text, ("unique columns", "unique key", "unique"))
    if unique:
        rules["unique_key"] = unique
    accepted_values: dict[str, list[str]] = {}
    for match in re.finditer(
        r"([A-Za-z_][\w]*)\s+(?:accepted values|allowed values|values)\s*[:=]\s*([A-Za-z0-9_,\s.-]+)",
        text,
        flags=re.IGNORECASE,
    ):
        values = _split_values(match.group(2))
        if values:
            accepted_values[_safe_identifier(match.group(1))] = values
    if accepted_values:
        rules["accepted_values"] = accepted_values
    expressions = _quality_expressions(text)
    if expressions:
        rules["expressions"] = expressions
    return rules


def _columns_after_labels(text: str, labels: tuple[str, ...]) -> list[str]:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*[:=]?\s*([A-Za-z0-9_,\s.-]+)", text, flags=re.IGNORECASE)
    if not match:
        return []
    raw = match.group(1).split(".", 1)[0]
    raw = re.split(
        r"\b(?:unique key|unique columns|accepted values|allowed values|must be|should be|expression|expressions|severity|with|from|into|using)\b",
        raw,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return [_safe_identifier(item) for item in re.split(r"[,;\s]+", raw) if item.strip()]


def _quality_expressions(text: str) -> list[dict[str, Any]]:
    expressions: list[dict[str, Any]] = []
    severity = _detect_quality_severity(text)
    patterns = [
        (r"([A-Za-z_][\w]*)\s+must\s+be\s*(>=|<=|>|<|=)\s*([A-Za-z0-9_.-]+)", "must_be"),
        (r"([A-Za-z_][\w]*)\s+should\s+be\s*(>=|<=|>|<|=)\s*([A-Za-z0-9_.-]+)", "should_be"),
        (r"([A-Za-z_][\w]*)\s*(>=|<=|>|<|=)\s*([A-Za-z0-9_.-]+)", "expression"),
    ]
    seen: set[str] = set()
    for pattern, prefix in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            column = _safe_identifier(match.group(1))
            if column.lower() in _QUALITY_EXPRESSION_RESERVED_COLUMNS:
                continue
            operator = "==" if match.group(2) == "=" else match.group(2)
            value = match.group(3).rstrip(".")
            expression = f"{column} {operator} {value}"
            if expression in seen:
                continue
            seen.add(expression)
            expressions.append(
                {
                    "name": f"{column}_{prefix}_{_operator_name(operator)}_{_safe_identifier(value)}",
                    "expression": expression,
                    "severity": severity,
                }
            )
    return expressions


def _detect_quality_severity(text: str) -> str:
    match = re.search(r"(?:quality\s+)?severity\s*[:=]?\s*(warn|fail|abort|quarantine)", text, flags=re.IGNORECASE)
    if not match:
        return "abort"
    severity = match.group(1).lower()
    return "abort" if severity == "fail" else severity


def _detect_dab_compute(text: str) -> dict[str, Any]:
    lowered = text.lower()
    if "serverless" in lowered:
        return {"type": "serverless"}
    cluster_match = re.search(r"(?:existing cluster|cluster id|existing_cluster_id)\s*[:=]?\s*([A-Za-z0-9_.-]+)", text, flags=re.IGNORECASE)
    if cluster_match:
        return {"type": "existing_cluster", "existing_cluster_id": cluster_match.group(1)}
    if "job cluster" in lowered or "job_cluster" in lowered:
        return {"type": "job_cluster"}
    return {}


def detect_prompt_operations(text: str, owner: str | None = None) -> dict[str, Any]:
    """Extract explicit operations metadata from a prompt."""

    return _detect_operations(text, owner)


def detect_prompt_quality_rules(text: str) -> dict[str, Any]:
    """Extract explicit quality rules from a prompt."""

    return _detect_quality_rules(text)


def detect_prompt_dab_compute(text: str) -> dict[str, Any]:
    """Extract explicit Databricks Asset Bundle compute preference from a prompt."""

    return _detect_dab_compute(text)


def _split_values(raw: str) -> list[str]:
    raw = raw.split(".", 1)[0]
    raw = re.split(r"\b(?:required columns|final columns|gold final columns|must be|should be|with|from|into|using|severity)\b", raw, maxsplit=1, flags=re.IGNORECASE)[0]
    return [item.strip().strip("'\"").rstrip(".") for item in re.split(r"[,;]\s*|\s+", raw) if item.strip()]


def _operator_name(operator: str) -> str:
    return {
        ">=": "gte",
        "<=": "lte",
        ">": "gt",
        "<": "lt",
        "==": "eq",
    }.get(operator, "check")


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_")


def _missing_fields(values: dict[str, Any]) -> list[str]:
    return [key for key, value in values.items() if not value]


def _decisions_for(intent: ProjectIntent, request: ProjectPlannerRequest) -> list[RequiredDecision]:
    decisions: list[RequiredDecision] = []
    for field_name in intent.missing_fields:
        decisions.append(
            RequiredDecision(
                question=f"Provide {field_name}.",
                reason="The planner will not invent missing connector, schema, source or target values.",
                path=field_name,
            )
        )
    if canonical_write_mode(intent.mode or "") in {
        "scd1_upsert",
        "scd1_hash_diff",
        "scd2_historical",
        "snapshot_soft_delete",
    }:
        decisions.append(
            RequiredDecision(
                question="Confirm merge/hash/SCD keys.",
                reason="Merge-based modes require stable business keys and null-key validation.",
                path="merge_keys",
            )
        )
    if intent.schedule_cron and not intent.schedule_timezone:
        decisions.append(
            RequiredDecision(
                question="Confirm schedule timezone.",
                reason="Project schedules must use an explicit IANA timezone; the planner will not infer timezone from locale.",
                path="schedule.timezone",
            )
        )
    if any("schedule:daily_without_time" == signal for signal in intent.signals):
        decisions.append(
            RequiredDecision(
                question="Confirm daily schedule time and timezone.",
                reason="The prompt requested daily execution but did not provide a concrete cron time.",
                path="schedule.cron",
            )
        )
    if request.preferred_target and request.preferred_target not in _target_options():
        decisions.append(
            RequiredDecision(
                question=f"Choose a supported project target instead of {request.preferred_target!r}.",
                reason="Planner recommendations are limited to supported ContractForge AI project targets.",
                path="preferred_target",
                options=sorted(_target_options()),
            )
        )
    return decisions


def _assumptions_for(intent: ProjectIntent) -> list[Assumption]:
    assumptions = [
        Assumption(
            statement="Planner output is a review plan, not an instruction to write files or deploy resources.",
            confidence=0.95,
            review_required=True,
        )
    ]
    if intent.mode and intent.layer:
        assumptions.append(
            Assumption(
                statement=f"Write mode {intent.mode!r} is compatible with the inferred layer {intent.layer!r} only after key and quality review.",
                confidence=0.65,
                review_required=True,
            )
        )
    return assumptions


def _recommendations_for(intent: ProjectIntent, preferred_target: str | None) -> list[ProjectRecommendation]:
    candidates = [preferred_target] if preferred_target in _target_options() else _default_targets(intent)
    return [_recommendation(target, intent) for target in candidates]


def _default_targets(intent: ProjectIntent) -> list[str]:
    targets = ["contractforge-yaml"]
    requested_adapter_targets = [
        _PLATFORM_TARGETS[platform] for platform in intent.platform_hints if platform in _PLATFORM_TARGETS
    ]
    adapter_candidates = requested_adapter_targets or list(_ADAPTER_TARGET_ORDER)
    for target in adapter_candidates:
        if intent.connector in _TARGET_CONNECTOR_SUPPORT[target] and target not in targets:
            targets.append(target)
    if intent.layer == "gold":
        targets.append("dbt")
    targets.append("contractforge-python")
    if any("migration" in signal for signal in intent.signals):
        targets.append("classic-pyspark")
    return targets


def _recommendation(target: str, intent: ProjectIntent) -> ProjectRecommendation:
    required = intent.missing_fields.copy()
    base = _base_generate_command(target, intent)
    reasons = {
        "contractforge-yaml": "Best default for contract-first review, version control and governance separation.",
        "contractforge-python": "Useful when a thin Python entry point should validate contracts and call adapter planning/execution boundaries explicitly.",
        "databricks-dab": "Useful when the scenario should become a deployable Databricks job or bundle.",
        "aws-glue-iceberg": "Useful when the scenario should become an AWS Glue Spark and Iceberg project through the AWS adapter runtime.",
        "snowflake-sql-warehouse": "Useful when the scenario should become a Snowflake SQL warehouse project through the Snowflake adapter runtime.",
        "fabric-lakehouse": "Useful when the scenario should become a Microsoft Fabric Lakehouse project through the Fabric adapter runtime.",
        "gcp-bigquery": "Useful when the scenario should become a BigQuery project through the GCP adapter runtime.",
        "dbt": "Useful when downstream transformation ownership already uses dbt models and tests.",
        "classic-pyspark": "Useful for migration comparison, not preferred for governed production ingestion.",
    }
    confidence = 0.82 if target == "contractforge-yaml" else 0.68
    if required:
        confidence -= 0.15
    return ProjectRecommendation(
        target=target,
        reason=reasons[target],
        confidence=max(confidence, 0.35),
        command=base,
        required_inputs=required,
    )


def _base_generate_command(target: str, intent: ProjectIntent) -> str:
    args = [
        "contractforge-ai generate-project",
        f"--target {target}",
        f"--schema {intent.schema_path or '<schema-profile.json>'}",
        f"--project-name \"{intent.project_name or '<project-name>'}\"",
        f"--connector {intent.connector or '<connector>'}",
        f"--source-path {intent.source_path or '<source-path>'}",
        f"--target-catalog {intent.target_catalog or '<catalog>'}",
        f"--target-schema {intent.target_schema or '<schema>'}",
        f"--target-table {intent.target_table or '<table>'}",
        f"--layer {intent.layer or '<layer>'}",
    ]
    if intent.mode:
        args.append(f"--mode {intent.mode}")
    if intent.owner:
        args.append(f"--owner {intent.owner}")
    return " ".join(args)


def _confidence(intent: ProjectIntent) -> float:
    total = 8
    present = sum(
        1
        for value in (
            intent.project_name,
            intent.connector,
            intent.source_path,
            intent.target_catalog,
            intent.target_schema,
            intent.target_table,
            intent.layer,
            intent.mode,
        )
        if value
    )
    return max(0.35, min(0.90, present / total))


def _target_options() -> set[str]:
    return set(supported_project_targets())


def _target_identifier(intent: ProjectIntent) -> str | None:
    if intent.target_catalog and intent.target_schema and intent.target_table:
        return f"{intent.target_catalog}.{intent.target_schema}.{intent.target_table}"
    return None
