"""Models and deterministic contract factories for Snowflake smoke tests."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from contractforge_snowflake.naming import quote_identifier

_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")

CONTROL_TABLE_NAMES = (
    "ctrl_ingestion_runs",
    "ctrl_ingestion_errors",
    "ctrl_ingestion_quality",
    "ctrl_ingestion_quarantine",
    "ctrl_ingestion_schema_changes",
    "ctrl_ingestion_lineage",
    "ctrl_ingestion_explain",
    "ctrl_ingestion_metadata",
    "ctrl_ingestion_streams",
    "ctrl_ingestion_cost",
    "ctrl_ingestion_annotations",
    "ctrl_ingestion_access",
    "ctrl_ingestion_operations",
    "ctrl_ingestion_state",
    "ctrl_ingestion_locks",
)


@dataclass(frozen=True)
class SnowflakeSmokeConfig:
    database: str = "CONTRACTFORGE_TEST_DB"
    source_schema: str = "PUBLIC"
    target_schema: str = "PUBLIC"
    evidence_schema: str = "PUBLIC"
    table_prefix: str = "CF_SMOKE"
    warehouse: str = "COMPUTE_WH"
    role: str = "CONTRACTFORGE_INGEST_ROLE"
    connection: str | None = None
    output_dir: Path | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("database", self.database),
            ("source_schema", self.source_schema),
            ("target_schema", self.target_schema),
            ("evidence_schema", self.evidence_schema),
            ("table_prefix", self.table_prefix),
        ):
            if not _IDENTIFIER_RE.match(value):
                raise ValueError(f"Unsafe Snowflake smoke {label}: {value}")
        if not self.table_prefix.upper().startswith("CF_SMOKE"):
            raise ValueError("Snowflake smoke table_prefix must start with CF_SMOKE")

    @property
    def source_namespace(self) -> str:
        return f"{self.database}.{self.source_schema}"

    @property
    def target_namespace(self) -> dict[str, str]:
        return {"catalog": self.database, "schema": self.target_schema}

    def source_table(self, suffix: str) -> str:
        return f"{self.table_prefix}_{suffix}"

    def target_table(self, suffix: str) -> str:
        return f"{self.table_prefix}_{suffix}"

    def qualified_source(self, suffix: str) -> str:
        return _qualified_name(self.database, self.source_schema, self.source_table(suffix))

    def qualified_target(self, suffix: str) -> str:
        return _qualified_name(self.database, self.target_schema, self.target_table(suffix))

    def summary_config(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.output_dir is not None:
            payload["output_dir"] = str(self.output_dir)
        return payload


def environment_payload(config: SnowflakeSmokeConfig) -> dict[str, Any]:
    return {
        "name": "snowflake_minimal_smoke",
        "adapter": "snowflake",
        "evidence": {
            "database": config.database,
            "schema": config.evidence_schema,
            "create_database": False,
            "create_schema": False,
        },
        "parameters": {"snowflake": {"warehouse": config.warehouse, "role": config.role}},
    }


def bootstrap_skips(config: SnowflakeSmokeConfig) -> tuple[str, ...]:
    return (
        f"CREATE DATABASE IF NOT EXISTS {quote_identifier(config.database)}",
        f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(config.database)}.{quote_identifier(config.evidence_schema)}",
    )


def smoke_contracts(config: SnowflakeSmokeConfig) -> dict[str, dict[str, Any]]:
    orders_source = f"{config.source_namespace}.{config.source_table('ORDERS_SOURCE')}"
    quality_source = f"{config.source_namespace}.{config.source_table('QUALITY_SOURCE')}"
    customers_source = f"{config.source_namespace}.{config.source_table('CUSTOMERS_SOURCE')}"
    target = config.target_namespace
    return {
        "orders_append": {
            "source": {"type": "table", "table": orders_source},
            "target": {**target, "table": config.target_table("ORDERS_APPEND")},
            "layer": "bronze",
            "mode": "scd0_append",
            "schema_policy": "additive_only",
            "quality_rules": {
                "required_columns": ["ORDER_ID", "STATUS", "AMOUNT"],
                "not_null": ["ORDER_ID"],
                "accepted_values": {"STATUS": ["NEW", "PAID", "CANCELLED"]},
                "min_rows": 1,
            },
        },
        "orders_overwrite": {
            "source": {"type": "table", "table": orders_source},
            "target": {**target, "table": config.target_table("ORDERS_OVERWRITE")},
            "layer": "silver",
            "mode": "scd0_overwrite",
            "schema_policy": "permissive",
            "filter_expression": "AMOUNT >= 10",
            "transform": {
                "cast": {"AMOUNT": "NUMBER(10,2)"},
                "standardize": {"STATUS": {"trim": True, "lower": True}},
                "derive": {"AMOUNT_BAND": "CASE WHEN AMOUNT >= 20 THEN 'HIGH' ELSE 'LOW' END"},
            },
        },
        "orders_quarantine": {
            "source": {"type": "table", "table": quality_source},
            "target": {**target, "table": config.target_table("ORDERS_QUARANTINE")},
            "layer": "bronze",
            "mode": "scd0_append",
            "schema_policy": "additive_only",
            "quality_rules": {"not_null": ["ORDER_ID"]},
        },
        "customers_upsert": {
            "source": {"type": "table", "table": customers_source},
            "target": {**target, "table": config.target_table("CUSTOMERS_CURRENT")},
            "layer": "silver",
            "mode": "scd1_upsert",
            "merge_keys": ["CUSTOMER_ID"],
            "schema_policy": "additive_only",
            "transform": {
                "deduplicate": {
                    "keys": ["CUSTOMER_ID"],
                    "order_by": [{"column": "UPDATED_AT", "direction": "desc", "nulls": "last"}],
                }
            },
            "quality_rules": {
                "required_columns": ["CUSTOMER_ID", "EMAIL", "UPDATED_AT"],
                "not_null": ["CUSTOMER_ID"],
                "unique_key": ["CUSTOMER_ID"],
            },
        },
        "customers_hash_diff": {
            "source": {"type": "table", "table": customers_source},
            "target": {**target, "table": config.target_table("CUSTOMERS_HASHDIFF")},
            "layer": "silver",
            "mode": "scd1_hash_diff",
            "merge_keys": ["CUSTOMER_ID"],
            "hash_keys": ["LIFETIME_VALUE", "CUSTOMER_BAND"],
            "hash_exclude_columns": ["UPDATED_AT"],
            "schema_policy": "additive_only",
            "transform": {
                "deduplicate": {
                    "keys": ["CUSTOMER_ID"],
                    "order_by": [{"column": "UPDATED_AT", "direction": "desc", "nulls": "last"}],
                }
            },
        },
    }


def failure_contracts(config: SnowflakeSmokeConfig) -> dict[str, dict[str, Any]]:
    missing_source = f"{config.source_namespace}.{config.source_table('MISSING_SOURCE')}"
    orders_source = f"{config.source_namespace}.{config.source_table('ORDERS_SOURCE')}"
    target = config.target_namespace
    return {
        "missing_source": {
            "source": {"type": "table", "table": missing_source},
            "target": {**target, "table": config.target_table("MISSING_SOURCE_TARGET")},
            "layer": "bronze",
            "mode": "scd0_append",
            "schema_policy": "additive_only",
        },
        "quality_abort": {
            "source": {"type": "table", "table": orders_source},
            "target": {**target, "table": config.target_table("QUALITY_ABORT")},
            "layer": "bronze",
            "mode": "scd0_overwrite",
            "schema_policy": "permissive",
            "quality_rules": {"min_rows": 10},
        },
        "strict_schema": {
            "source": {"type": "table", "table": orders_source},
            "target": {**target, "table": config.target_table("STRICT_SCHEMA")},
            "layer": "bronze",
            "mode": "scd0_append",
            "schema_policy": "strict",
        },
    }


def setup_commands(config: SnowflakeSmokeConfig, *, execute_cleanup: bool = False) -> tuple[str, ...]:
    commands: list[str] = []
    if execute_cleanup:
        commands.extend(cleanup_commands(config))
    commands.extend(_schema_commands(config))
    commands.extend(
        (
            f"""
CREATE OR REPLACE TABLE {config.qualified_source("ORDERS_SOURCE")} (
  order_id NUMBER,
  status VARCHAR,
  amount FLOAT
)""".strip(),
            f"""
INSERT INTO {config.qualified_source("ORDERS_SOURCE")} (order_id, status, amount)
SELECT * FROM VALUES
  (1, 'NEW', 10.25),
  (2, 'PAID', 20.50),
  (3, 'CANCELLED', 5.00)""".strip(),
            f"""
CREATE OR REPLACE TABLE {config.qualified_source("QUALITY_SOURCE")} (
  order_id NUMBER,
  status VARCHAR,
  amount FLOAT
)""".strip(),
            f"""
INSERT INTO {config.qualified_source("QUALITY_SOURCE")} (order_id, status, amount)
SELECT * FROM VALUES
  (10, 'NEW', 12.00),
  (NULL, 'PAID', 15.00),
  (11, 'CANCELLED', 3.00)""".strip(),
            f"""
CREATE OR REPLACE TABLE {config.qualified_source("CUSTOMERS_SOURCE")} (
  customer_id NUMBER,
  name VARCHAR,
  email VARCHAR,
  updated_at TIMESTAMP_NTZ,
  lifetime_value FLOAT,
  customer_band VARCHAR
)""".strip(),
            f"""
INSERT INTO {config.qualified_source("CUSTOMERS_SOURCE")}
  (customer_id, name, email, updated_at, lifetime_value, customer_band)
SELECT * FROM VALUES
  (1, 'Ada', 'ada@example.com', '2026-06-04 10:00:00'::TIMESTAMP_NTZ, 1250.0, 'VIP'),
  (1, 'Ada New', 'ada.new@example.com', '2026-06-04 10:10:00'::TIMESTAMP_NTZ, 1300.0, 'VIP'),
  (2, 'Ben', 'ben@example.com', '2026-06-04 10:05:00'::TIMESTAMP_NTZ, 80.0, 'STANDARD')""".strip(),
            f"""
CREATE OR REPLACE TABLE {config.qualified_target("CUSTOMERS_CURRENT")} (
  customer_id NUMBER,
  name VARCHAR,
  updated_at TIMESTAMP_NTZ,
  lifetime_value FLOAT,
  customer_band VARCHAR
)""".strip(),
            f"""
INSERT INTO {config.qualified_target("CUSTOMERS_CURRENT")}
  (customer_id, name, updated_at, lifetime_value, customer_band)
SELECT 1, 'Ada Old', '2026-06-01 00:00:00'::TIMESTAMP_NTZ, 900.0, 'STANDARD'""".strip(),
            f"""
CREATE OR REPLACE TABLE {config.qualified_target("CUSTOMERS_HASHDIFF")} (
  customer_id NUMBER,
  name VARCHAR,
  email VARCHAR,
  updated_at TIMESTAMP_NTZ,
  lifetime_value FLOAT,
  customer_band VARCHAR
)""".strip(),
            f"""
INSERT INTO {config.qualified_target("CUSTOMERS_HASHDIFF")}
  (customer_id, name, email, updated_at, lifetime_value, customer_band)
SELECT 1, 'Ada Old', 'old@example.com', '2026-06-01 00:00:00'::TIMESTAMP_NTZ, 900.0, 'STANDARD'""".strip(),
            f"""
CREATE OR REPLACE TABLE {config.qualified_target("STRICT_SCHEMA")} (
  order_id NUMBER,
  status VARCHAR,
  amount FLOAT,
  legacy_col VARCHAR
)""".strip(),
        )
    )
    return tuple(commands)


def cleanup_commands(config: SnowflakeSmokeConfig) -> tuple[str, ...]:
    sources = (
        config.qualified_source("ORDERS_SOURCE"),
        config.qualified_source("QUALITY_SOURCE"),
        config.qualified_source("CUSTOMERS_SOURCE"),
    )
    targets = (
        config.qualified_target("ORDERS_APPEND"),
        config.qualified_target("ORDERS_OVERWRITE"),
        config.qualified_target("ORDERS_QUARANTINE"),
        config.qualified_target("CUSTOMERS_CURRENT"),
        config.qualified_target("CUSTOMERS_HASHDIFF"),
        config.qualified_target("MISSING_SOURCE_TARGET"),
        config.qualified_target("QUALITY_ABORT"),
        config.qualified_target("STRICT_SCHEMA"),
    )
    evidence_prefix = _qualified_schema(config.database, config.evidence_schema)
    return tuple(
        [f"DROP TABLE IF EXISTS {source}" for source in sources]
        + [f"DROP TABLE IF EXISTS {target}" for target in targets]
        + [f"DROP TABLE IF EXISTS {evidence_prefix}.{quote_identifier(name)}" for name in CONTROL_TABLE_NAMES]
    )


def target_count_queries(config: SnowflakeSmokeConfig) -> dict[str, str]:
    return {
        name: f"SELECT COUNT(*) FROM {config.qualified_target(suffix)}"
        for name, suffix in {
            "orders_append": "ORDERS_APPEND",
            "orders_overwrite": "ORDERS_OVERWRITE",
            "orders_quarantine": "ORDERS_QUARANTINE",
            "customers_current": "CUSTOMERS_CURRENT",
            "customers_hashdiff": "CUSTOMERS_HASHDIFF",
        }.items()
    }


def control_count_queries(config: SnowflakeSmokeConfig) -> dict[str, str]:
    evidence_prefix = _qualified_schema(config.database, config.evidence_schema)
    names = (
        "ctrl_ingestion_runs",
        "ctrl_ingestion_errors",
        "ctrl_ingestion_quality",
        "ctrl_ingestion_quarantine",
        "ctrl_ingestion_schema_changes",
        "ctrl_ingestion_state",
    )
    return {name: f"SELECT COUNT(*) FROM {evidence_prefix}.{quote_identifier(name)}" for name in names}


def _schema_commands(config: SnowflakeSmokeConfig) -> tuple[str, ...]:
    names = {
        config.source_schema: _qualified_schema(config.database, config.source_schema),
        config.target_schema: _qualified_schema(config.database, config.target_schema),
        config.evidence_schema: _qualified_schema(config.database, config.evidence_schema),
    }
    return tuple(f"CREATE SCHEMA IF NOT EXISTS {schema}" for name, schema in names.items() if name.upper() != "PUBLIC")


def _qualified_schema(database: str, schema: str) -> str:
    return f"{quote_identifier(database)}.{quote_identifier(schema)}"


def _qualified_name(database: str, schema: str, table: str) -> str:
    return f"{_qualified_schema(database, schema)}.{quote_identifier(table)}"
