"""USGS GeoJSON REST medallion project shared by Databricks and AWS tests."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

PlatformName = Literal["databricks", "aws"]

USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
USGS_FEED_SCHEMA = """
STRUCT<
  type: STRING,
  metadata: STRUCT<
    generated: BIGINT,
    url: STRING,
    title: STRING,
    status: BIGINT,
    api: STRING,
    count: BIGINT
  >,
  bbox: ARRAY<DOUBLE>,
  features: ARRAY<STRUCT<
    type: STRING,
    id: STRING,
    properties: STRUCT<
      mag: DOUBLE,
      place: STRING,
      time: BIGINT,
      updated: BIGINT,
      tz: BIGINT,
      url: STRING,
      detail: STRING,
      felt: BIGINT,
      cdi: DOUBLE,
      mmi: DOUBLE,
      alert: STRING,
      status: STRING,
      tsunami: BIGINT,
      sig: BIGINT,
      net: STRING,
      code: STRING,
      ids: STRING,
      sources: STRING,
      types: STRING,
      nst: BIGINT,
      dmin: DOUBLE,
      rms: DOUBLE,
      gap: DOUBLE,
      magType: STRING,
      type: STRING,
      title: STRING
    >,
    geometry: STRUCT<
      type: STRING,
      coordinates: ARRAY<DOUBLE>
    >
  >>
>
""".strip()


@dataclass(frozen=True)
class USGSMedallionStep:
    name: str
    layer: str
    description: str
    contract: dict[str, Any]


def platform_contracts(
    platform: PlatformName,
    *,
    target_catalog: str,
    project_prefix: str = "cf_usgs_rest",
    aws_warehouse: str | None = None,
) -> tuple[USGSMedallionStep, ...]:
    """Return the USGS medallion contracts bound to one runtime platform."""

    bronze_schema = f"{project_prefix}_bronze"
    silver_schema = f"{project_prefix}_silver"
    gold_schema = f"{project_prefix}_gold"
    bronze_table = _table_name(platform, target_catalog, bronze_schema, "b_usgs_earthquake_geojson")
    silver_table = _table_name(platform, target_catalog, silver_schema, "s_usgs_earthquake_events")
    common_extension = _platform_extension(platform, aws_warehouse=aws_warehouse)
    return (
        USGSMedallionStep(
            name="bronze_usgs_geojson",
            layer="bronze",
            description="Raw bounded REST pull of the USGS GeoJSON feed.",
            contract=_with_extension(_bronze_contract(target_catalog, bronze_schema), common_extension),
        ),
        USGSMedallionStep(
            name="silver_usgs_events",
            layer="silver",
            description="Explode and normalize GeoJSON features into current earthquake events.",
            contract=_with_extension(_silver_contract(target_catalog, silver_schema, bronze_table), common_extension),
        ),
        USGSMedallionStep(
            name="gold_usgs_daily_summary",
            layer="gold",
            description="Daily earthquake activity mart.",
            contract=_with_extension(_daily_gold_contract(target_catalog, gold_schema, silver_table), common_extension),
        ),
        USGSMedallionStep(
            name="gold_usgs_magnitude_bands",
            layer="gold",
            description="Magnitude band mart by event type.",
            contract=_with_extension(_band_gold_contract(target_catalog, gold_schema, silver_table), common_extension),
        ),
    )


def platform_environment(
    platform: PlatformName,
    *,
    project_prefix: str = "cf_usgs_rest",
    aws_region: str = "us-east-1",
    aws_role_arn: str | None = None,
    core_wheel_s3_uri: str | None = None,
) -> dict[str, Any]:
    if platform == "databricks":
        return {
            "name": "usgs_rest_databricks",
            "adapter": "databricks",
            "evidence": {"catalog": "workspace", "schema": f"{project_prefix}_ops"},
            "parameters": {"databricks": {"runtime": "serverless"}},
        }
    dependencies: dict[str, Any] = {"additional_python_modules": "pydantic>=2.7,eval-type-backport,PyYAML>=6"}
    if core_wheel_s3_uri:
        dependencies["extra_py_files"] = core_wheel_s3_uri
    return {
        "name": "usgs_rest_aws",
        "adapter": "aws",
        "evidence": {"database": f"contractforge_{project_prefix}_ops"},
        "parameters": {
            "aws": {
                "region": aws_region,
                "dependencies": dependencies,
                "glue_job": {
                    "role_arn": aws_role_arn or "arn:aws:iam::123456789012:role/ContractForgeGlueSmokeRole",
                    "worker_type": "G.1X",
                    "number_of_workers": 2,
                    "timeout_minutes": 15,
                    "max_retries": 0,
                },
            }
        },
    }


def portability_report(*, project_prefix: str = "cf_usgs_rest") -> dict[str, Any]:
    """Summarize the intended platform differences for the USGS project."""

    databricks = platform_contracts("databricks", target_catalog="workspace", project_prefix=project_prefix)
    aws = platform_contracts(
        "aws",
        target_catalog="contractforge",
        project_prefix=project_prefix,
        aws_warehouse="s3://contractforge-example/warehouse/",
    )
    return {
        "kind": "contractforge_usgs_rest_medallion_portability",
        "feed": USGS_FEED_URL,
        "steps": [
            {
                "name": dbx.name,
                "portable_intent_equal": _portable_signature(dbx.contract) == _portable_signature(aws_step.contract),
                "allowed_differences": _allowed_delta(dbx.contract, aws_step.contract),
            }
            for dbx, aws_step in zip(databricks, aws)
        ],
    }


def write_project_contracts(
    root: str | Path,
    platform: PlatformName,
    *,
    target_catalog: str,
    project_prefix: str = "cf_usgs_rest",
    aws_warehouse: str | None = None,
) -> dict[str, str]:
    """Write one platform-bound split-contract project to disk."""

    root_path = Path(root)
    written: dict[str, str] = {}
    for step in platform_contracts(
        platform,
        target_catalog=target_catalog,
        project_prefix=project_prefix,
        aws_warehouse=aws_warehouse,
    ):
        layer_dir = root_path / "contracts" / step.layer / step.name
        layer_dir.mkdir(parents=True, exist_ok=True)
        path = layer_dir / f"{step.name}.ingestion.json"
        path.write_text(json.dumps(step.contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written[step.name] = str(path)
    return written


def _bronze_contract(target_catalog: str, target_schema: str) -> dict[str, Any]:
    return {
        "source": {
            "type": "rest_api",
            "name": "usgs_earthquake_2_5_day_geojson",
            "system": "usgs",
            "request": {
                "url": USGS_FEED_URL,
                "method": "GET",
                "headers": {
                    "Accept": "application/geo+json, application/json",
                    "User-Agent": "ContractForge real ingestion test",
                },
            },
            "response": {"mode": "raw", "raw_column": "raw_response"},
            "limits": {
                "timeout_seconds": 60,
                "retry_attempts": 3,
                "retry_backoff_seconds": 2,
                "max_page_bytes": 10485760,
                "max_total_bytes": 10485760,
                "max_records": 1,
            },
        },
        "target": {"catalog": target_catalog, "schema": target_schema, "table": "b_usgs_earthquake_geojson"},
        "layer": "bronze",
        "mode": "scd0_overwrite",
        "schema_policy": "permissive",
        "quality_rules": {
            "required_columns": ["raw_response", "response_page_number"],
            "not_null": ["raw_response"],
            "unique_key": ["response_page_number"],
        },
        "annotations": {
            "table": {
                "description": "Raw USGS Earthquake GeoJSON feed response.",
                "tags": {"domain": "geospatial", "provider": "usgs", "source_format": "geojson"},
            },
            "columns": {
                "raw_response": {"description": "Raw GeoJSON FeatureCollection response body."},
                "response_page_number": {"description": "REST connector page number."},
            },
        },
    }


def _silver_contract(target_catalog: str, target_schema: str, bronze_table: str) -> dict[str, Any]:
    return {
        "source": {
            "type": "table",
            "system": "usgs",
            "table": bronze_table,
            "read": {"source_complete": True},
        },
        "target": {"catalog": target_catalog, "schema": target_schema, "table": "s_usgs_earthquake_events"},
        "layer": "silver",
        "mode": "scd0_overwrite",
        "schema_policy": "additive_only",
        "select_columns": ["raw_response", "response_page_number"],
        "schemas": {"usgs_geojson_feed": USGS_FEED_SCHEMA},
        "transform": {
            "shape": {
                "parse_json": [{"column": "raw_response", "alias": "payload", "schema_ref": "usgs_geojson_feed"}],
                "arrays": [{"path": "payload.features", "mode": "explode_outer", "alias": "feature"}],
                "columns": {
                    "payload.metadata.generated": {"alias": "feed_generated_epoch_ms", "cast": "BIGINT"},
                    "payload.metadata.title": {"alias": "feed_title", "cast": "STRING"},
                    "payload.metadata.count": {"alias": "feed_event_count", "cast": "BIGINT"},
                    "payload.metadata.api": {"alias": "feed_api_version", "cast": "STRING"},
                    "payload.bbox": {"alias": "feed_bbox"},
                    "feature.id": {"alias": "earthquake_id", "cast": "STRING"},
                    "feature.type": {"alias": "geojson_feature_type", "cast": "STRING"},
                    "feature.properties.title": {"alias": "event_title", "cast": "STRING"},
                    "feature.properties.place": {"alias": "place", "cast": "STRING"},
                    "feature.properties.mag": {"alias": "magnitude", "cast": "DOUBLE"},
                    "feature.properties.magType": {"alias": "magnitude_type", "cast": "STRING"},
                    "feature.properties.time": {"alias": "event_epoch_ms", "cast": "BIGINT"},
                    "feature.properties.updated": {"alias": "updated_epoch_ms", "cast": "BIGINT"},
                    "feature.properties.status": {"alias": "event_status", "cast": "STRING"},
                    "feature.properties.type": {"alias": "event_type", "cast": "STRING"},
                    "feature.properties.alert": {"alias": "alert_level", "cast": "STRING"},
                    "feature.properties.tsunami": {"alias": "tsunami_flag", "cast": "INT"},
                    "feature.properties.sig": {"alias": "significance", "cast": "BIGINT"},
                    "feature.properties.net": {"alias": "network", "cast": "STRING"},
                    "feature.properties.code": {"alias": "network_event_code", "cast": "STRING"},
                    "feature.properties.url": {"alias": "event_url", "cast": "STRING"},
                    "feature.properties.detail": {"alias": "detail_url", "cast": "STRING"},
                    "feature.properties.felt": {"alias": "felt_reports", "cast": "BIGINT"},
                    "feature.properties.cdi": {"alias": "community_intensity", "cast": "DOUBLE"},
                    "feature.properties.mmi": {"alias": "instrumental_intensity", "cast": "DOUBLE"},
                    "feature.geometry.type": {"alias": "geometry_type", "cast": "STRING"},
                    "feature.geometry.coordinates": {"alias": "coordinates"},
                    "longitude": {"alias": "longitude", "expression": "CAST(feature.geometry.coordinates[0] AS DOUBLE)"},
                    "latitude": {"alias": "latitude", "expression": "CAST(feature.geometry.coordinates[1] AS DOUBLE)"},
                    "depth_km": {"alias": "depth_km", "expression": "CAST(feature.geometry.coordinates[2] AS DOUBLE)"},
                },
            },
            "standardize": {
                "event_status": {"trim": True, "lower": True, "empty_as_null": True},
                "event_type": {"trim": True, "lower": True, "empty_as_null": True},
                "magnitude_type": {"trim": True, "lower": True, "empty_as_null": True},
                "alert_level": {"trim": True, "lower": True, "empty_as_null": True},
                "network": {"trim": True, "lower": True},
            },
            "derive": {
                "event_time": "CAST(from_unixtime(event_epoch_ms / 1000) AS TIMESTAMP)",
                "updated_at": "CAST(from_unixtime(updated_epoch_ms / 1000) AS TIMESTAMP)",
                "feed_generated_at": "CAST(from_unixtime(feed_generated_epoch_ms / 1000) AS TIMESTAMP)",
                "event_date": "to_date(CAST(from_unixtime(event_epoch_ms / 1000) AS TIMESTAMP))",
                "magnitude_band": (
                    "CASE WHEN magnitude IS NULL THEN 'unknown' WHEN magnitude < 3 THEN 'minor' "
                    "WHEN magnitude < 5 THEN 'light' WHEN magnitude < 7 THEN 'strong' ELSE 'major' END"
                ),
                "is_tsunami_related": "tsunami_flag = 1",
                "normalized_at_utc": "CURRENT_TIMESTAMP()",
            },
            "deduplicate": {
                "keys": ["earthquake_id"],
                "order_by": [
                    {"column": "updated_at", "direction": "desc", "nulls": "last"},
                    {"column": "feed_generated_at", "direction": "desc", "nulls": "last"},
                ],
            },
        },
        "filter_expression": "earthquake_id IS NOT NULL",
        "quality_rules": {
            "not_null": ["earthquake_id", "event_time", "latitude", "longitude"],
            "unique_key": ["earthquake_id"],
            "expressions": [
                {
                    "name": "valid_geojson_point",
                    "expression": "geometry_type = 'Point'",
                    "severity": "warn",
                    "message": "USGS summary feeds should expose point geometries.",
                },
                {
                    "name": "valid_coordinates",
                    "expression": "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180",
                    "severity": "abort",
                    "message": "Coordinates must be valid WGS84 latitude/longitude.",
                },
                {
                    "name": "reasonable_depth",
                    "expression": "depth_km IS NULL OR depth_km BETWEEN -20 AND 800",
                    "severity": "warn",
                    "message": "Earthquake depth is outside the expected operational range.",
                },
                {
                    "name": "non_negative_magnitude",
                    "expression": "magnitude IS NULL OR magnitude >= 0",
                    "severity": "warn",
                    "message": "Magnitude should not be negative for normal earthquake events.",
                },
            ],
        },
        "annotations": {
            "table": {
                "description": "Current normalized earthquake events parsed from the USGS GeoJSON feed.",
                "tags": {"domain": "geospatial", "provider": "usgs", "layer": "silver"},
            },
            "columns": {
                "earthquake_id": {"description": "Stable USGS earthquake event identifier."},
                "magnitude": {"description": "Event magnitude from USGS summary properties."},
                "latitude": {"description": "Latitude extracted from GeoJSON coordinates."},
                "longitude": {"description": "Longitude extracted from GeoJSON coordinates."},
                "depth_km": {"description": "Depth in kilometers extracted from GeoJSON coordinates."},
            },
        },
    }


def _daily_gold_contract(target_catalog: str, target_schema: str, silver_table: str) -> dict[str, Any]:
    return {
        "source": {
            "type": "sql",
            "system": "usgs_curated",
            "name": "usgs_earthquake_daily_summary",
            "query": f"""
SELECT
  event_date,
  COUNT(*) AS earthquake_count,
  SUM(CASE WHEN is_tsunami_related THEN 1 ELSE 0 END) AS tsunami_related_count,
  AVG(magnitude) AS avg_magnitude,
  MAX(magnitude) AS max_magnitude,
  AVG(depth_km) AS avg_depth_km,
  COUNT(DISTINCT network) AS reporting_networks,
  MAX(updated_at) AS last_event_update_at,
  CURRENT_TIMESTAMP() AS computed_at_utc
FROM {silver_table}
WHERE event_date IS NOT NULL
GROUP BY event_date
""".strip(),
            "read": {"source_complete": True},
        },
        "target": {"catalog": target_catalog, "schema": target_schema, "table": "g_usgs_earthquake_daily_summary"},
        "layer": "gold",
        "mode": "scd0_overwrite",
        "schema_policy": "additive_only",
        "quality_rules": {
            "not_null": ["event_date"],
            "expressions": [
                {
                    "name": "positive_daily_count",
                    "expression": "earthquake_count > 0",
                    "severity": "abort",
                    "message": "Daily summary rows must represent at least one earthquake.",
                }
            ],
        },
    }


def _band_gold_contract(target_catalog: str, target_schema: str, silver_table: str) -> dict[str, Any]:
    return {
        "source": {
            "type": "sql",
            "system": "usgs_curated",
            "name": "usgs_earthquake_magnitude_bands",
            "query": f"""
SELECT
  magnitude_band,
  event_type,
  COUNT(*) AS event_count,
  MIN(magnitude) AS min_magnitude,
  AVG(magnitude) AS avg_magnitude,
  MAX(magnitude) AS max_magnitude,
  MIN(event_time) AS first_event_time,
  MAX(event_time) AS latest_event_time,
  CURRENT_TIMESTAMP() AS computed_at_utc
FROM {silver_table}
GROUP BY magnitude_band, event_type
""".strip(),
            "read": {"source_complete": True},
        },
        "target": {"catalog": target_catalog, "schema": target_schema, "table": "g_usgs_earthquake_magnitude_bands"},
        "layer": "gold",
        "mode": "scd0_overwrite",
        "schema_policy": "additive_only",
        "quality_rules": {
            "not_null": ["magnitude_band"],
            "expressions": [
                {
                    "name": "positive_band_count",
                    "expression": "event_count > 0",
                    "severity": "abort",
                    "message": "Magnitude-band summary rows must represent at least one event.",
                }
            ],
        },
    }


def _with_extension(contract: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
    if not extension:
        return contract
    updated = deepcopy(contract)
    updated["extensions"] = deepcopy(extension)
    return updated


def _platform_extension(platform: PlatformName, *, aws_warehouse: str | None) -> dict[str, Any]:
    if platform == "databricks":
        return {"databricks": {"delta_properties": {"delta.enableChangeDataFeed": "true"}}}
    extension: dict[str, Any] = {"aws": {}}
    if aws_warehouse:
        extension["aws"]["iceberg"] = {"warehouse": aws_warehouse}
    return extension


def _table_name(platform: PlatformName, catalog: str, schema: str, table: str) -> str:
    if platform == "aws":
        return f"glue_catalog.{_safe_name(f'{catalog}_{schema}')}.{_safe_name(table)}"
    return f"{catalog}.{schema}.{table}"


def _portable_signature(contract: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(contract)
    normalized.pop("extensions", None)
    target = normalized.get("target")
    if isinstance(target, dict):
        target["catalog"] = "${target_catalog}"
    source = normalized.get("source")
    if isinstance(source, dict):
        if source.get("table"):
            source["table"] = "${source_table}"
        if source.get("query"):
            source["query"] = _normalize_query(str(source["query"]))
    return normalized


def _allowed_delta(databricks: dict[str, Any], aws: dict[str, Any]) -> dict[str, Any]:
    return {
        "databricks": _delta(databricks),
        "aws": _delta(aws),
    }


def _delta(contract: dict[str, Any]) -> dict[str, Any]:
    source = contract.get("source") if isinstance(contract.get("source"), dict) else {}
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    return {
        "target_catalog": target.get("catalog"),
        "source_table": source.get("table"),
        "source_query_tables": _query_tables(str(source.get("query") or "")),
        "extensions": contract.get("extensions") or {},
    }


def _normalize_query(query: str) -> str:
    tables = _query_tables(query)
    normalized = query
    for table in tables:
        normalized = normalized.replace(table, "${source_table}")
    return normalized


def _query_tables(query: str) -> tuple[str, ...]:
    tokens = query.replace("\n", " ").split()
    tables = []
    for idx, token in enumerate(tokens[:-1]):
        if token.upper() in {"FROM", "JOIN"}:
            tables.append(tokens[idx + 1].rstrip(","))
    return tuple(tables)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char == "_" else "_" for char in value).strip("_") or "contractforge"
