from __future__ import annotations

import json

import pytest

from contractforge_core.contracts import compose_contract_sections, contract_metadata_warnings, load_contract_bundle


def test_compose_split_contract_sections_into_semantic_bundle() -> None:
    bundle = compose_contract_sections(
        ingestion={
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
        },
        annotations={
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "table": {"description": "Curated orders"},
            "columns": {"order_id": {"description": "Business order id"}},
        },
        operations={
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "criticality": "high",
            "owners": ["sales-ops"],
        },
        access={
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "grants": [{"principal": "data-readers", "privileges": ["SELECT"]}],
        },
        environment={
            "name": "prod",
            "adapter": "databricks",
            "evidence": {"catalog": "audit", "schema": "ops"},
        },
    )

    assert bundle.semantic.write.mode == "scd1_upsert"
    assert bundle.semantic.governance is not None
    assert bundle.semantic.governance.annotations is not None
    assert bundle.semantic.governance.access is not None
    assert bundle.semantic.operations is not None
    assert bundle.semantic.operations.metadata is not None
    assert bundle.environment is not None
    assert bundle.environment["name"] == "prod"
    assert bundle.environment["adapter"] == "databricks"
    assert bundle.environment["evidence"] == {"catalog": "audit", "schema": "ops"}
    assert "environment" not in bundle.contract


def test_compose_contract_sections_rejects_target_mismatch() -> None:
    with pytest.raises(ValueError, match="annotations.target.table"):
        compose_contract_sections(
            ingestion={
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            },
            annotations={
                "target": {"catalog": "main", "schema": "silver", "table": "customers"},
                "table_comment": "Wrong target",
            },
        )


def test_split_section_target_requires_canonical_ingestion_target() -> None:
    with pytest.raises(ValueError, match="ingestion.target"):
        compose_contract_sections(
            ingestion={
                "source": {"type": "table", "table": "main.raw.orders"},
            },
            annotations={
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
                "table": {"description": "Orders"},
            },
        )


def test_environment_section_cannot_contain_semantic_fields() -> None:
    with pytest.raises(ValueError, match="environment"):
        compose_contract_sections(
            ingestion={
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            },
            environment={"name": "prod", "adapter": "databricks", "source": {"type": "table"}},
        )


def test_load_contract_bundle_supports_json_yml_metadata_and_environment(tmp_path) -> None:
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.json").write_text(
        json.dumps(
            {
                "_metadata": {"contract_version": "1.0.0"},
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
                "mode": "scd1_upsert",
                "merge_keys": ["order_id"],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "orders.annotations.yml").write_text(
        "_metadata:\n  contract_version: 1.1.0\ntable:\n  description: Orders\n",
        encoding="utf-8",
    )
    (tmp_path / "orders.environment.yaml").write_text(
        "name: prod\nadapter: databricks\nevidence:\n  schema: ops\n",
        encoding="utf-8",
    )

    bundle = load_contract_bundle(base)

    assert bundle.semantic.write.mode == "scd1_upsert"
    assert bundle.environment is not None
    assert bundle.environment["name"] == "prod"
    assert bundle.environment["adapter"] == "databricks"
    assert bundle.environment["evidence"] == {"schema": "ops"}
    assert bundle.metadata["ingestion"]["contract_version"] == "1.0.0"
    assert set(bundle.metadata["paths"]) == {"ingestion", "annotations", "environment"}
    assert bundle.metadata["warnings"]["items"]


def test_load_contract_bundle_resolves_connection_source_yaml(tmp_path) -> None:
    connections = tmp_path / "connections"
    connections.mkdir()
    (connections / "supabase.yaml").write_text(
        """
type: connector
connector: postgres
system: supabase
options:
  url: "{{ secret:contractforge/supabase-jdbc-url }}"
  driver: org.postgresql.Driver
read:
  fetchsize: 1000
auth:
  type: basic
  username: "{{ secret:contractforge/supabase-user }}"
  password: "{{ secret:contractforge/supabase-password }}"
""".lstrip(),
        encoding="utf-8",
    )
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.yaml").write_text(
        """
source:
  type: connection
  connection_path: connections/supabase.yaml
  table: public.orders
  read:
    partition_column: order_id
    lower_bound: 1
    upper_bound: 1000
    num_partitions: 4
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )

    bundle = load_contract_bundle(base)

    source = bundle.contract["source"]
    assert source["type"] == "connector"
    assert source["connector"] == "postgres"
    assert source["system"] == "supabase"
    assert source["connection"] == "connections/supabase.yaml"
    assert source["table"] == "public.orders"
    assert source["options"]["driver"] == "org.postgresql.Driver"
    assert source["read"]["fetchsize"] == 1000
    assert source["read"]["partition_column"] == "order_id"
    assert bundle.semantic.source.kind == "connector:postgres"


def test_load_contract_bundle_resolves_project_connection_source_yaml(tmp_path) -> None:
    (tmp_path / "project.yaml").write_text("name: demo\n", encoding="utf-8")
    connections = tmp_path / "connections"
    connections.mkdir()
    (connections / "supabase.yaml").write_text(
        """
type: connector
connector: postgres
system: supabase
options:
  url: "{{ secret:contractforge/supabase-jdbc-url }}"
  driver: org.postgresql.Driver
read:
  fetchsize: 1000
auth:
  type: basic
  username: "{{ secret:contractforge/supabase-user }}"
  password: "{{ secret:contractforge/supabase-password }}"
""".lstrip(),
        encoding="utf-8",
    )
    dataset = tmp_path / "contracts" / "bronze" / "orders"
    dataset.mkdir(parents=True)
    base = dataset / "orders"
    (dataset / "orders.ingestion.yaml").write_text(
        """
source:
  type: connection
  connection_path: project://connections/supabase.yaml
  table: public.orders
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )

    bundle = load_contract_bundle(base)

    source = bundle.contract["source"]
    assert source["connector"] == "postgres"
    assert source["connection"] == "project://connections/supabase.yaml"
    assert source["table"] == "public.orders"


def test_load_contract_bundle_requires_connection_path_for_connection_source(tmp_path) -> None:
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.yaml").write_text(
        """
source:
  type: connection
  table: public.orders
target:
  catalog: main
  schema: bronze
  table: orders
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="connection_path"):
        load_contract_bundle(base)


@pytest.mark.parametrize(
    "bad_ref",
    [
        "/etc/passwd",
        "C:/Windows/System32/drivers/etc/hosts",
        "../../escape.yaml",
        "../sibling.yaml",
        "connections/../../../../etc/passwd",
    ],
)
def test_load_contract_bundle_rejects_connection_path_escapes_bundle_dir(tmp_path, bad_ref: str) -> None:
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.yaml").write_text(
        f"""
source:
  type: connection
  connection_path: {bad_ref}
target:
  catalog: main
  schema: bronze
  table: orders
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="connection_path"):
        load_contract_bundle(base)


def test_load_contract_bundle_rejects_operations_section_envelope(tmp_path) -> None:
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.yaml").write_text(
        """
source:
  type: table
  table: main.raw.orders
target:
  catalog: main
  schema: silver
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "orders.operations.yaml").write_text(
        """
operations:
  business_owner: sales
  technical_owner: data-platform
  criticality: high
  expected_frequency: daily
  owners: [data-platform]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="operations.yaml must declare fields at the document root"):
        load_contract_bundle(base)


def test_load_contract_bundle_accepts_bare_operations_section(tmp_path) -> None:
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.yaml").write_text(
        """
source:
  type: table
  table: main.raw.orders
target:
  catalog: main
  schema: silver
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "orders.operations.yaml").write_text(
        """
business_owner: sales
technical_owner: data-platform
criticality: high
expected_frequency: daily
owners: [data-platform]
""".lstrip(),
        encoding="utf-8",
    )

    bundle = load_contract_bundle(base)

    assert bundle.semantic.operations is not None
    assert bundle.semantic.operations.metadata["ownership"]["business_owner"] == "sales"
    assert bundle.semantic.operations.metadata["criticality"] == "high"


def test_contract_metadata_warnings_detect_version_drift() -> None:
    warnings = contract_metadata_warnings(
        {"ingestion": {"contract_version": "1.0.0"}, "annotations": {"contract_version": "2.0.0"}}
    )

    assert any("major version" in warning for warning in warnings)
