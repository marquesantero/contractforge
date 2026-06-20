from pathlib import Path

from contractforge_ai.reviewers.contract import review_contract


def test_review_flags_hash_diff_without_keys(tmp_path: Path):
    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: json
  path: /tmp/orders
target:
  catalog: main
  schema: silver
  table: orders
mode: scd1_hash_diff
""",
        encoding="utf-8",
    )

    result = review_contract(contract)

    assert result.status == "FAIL"
    assert result.risk == "critical"
    assert any(finding.code == "write.keys.missing" for finding in result.findings)
    assert any(finding.code == "source.json.schema.missing" for finding in result.findings)
    assert result.traceability.review_required is True
    assert result.findings[0].evidence


def test_review_passes_minimal_safe_append_contract(tmp_path: Path):
    contract = tmp_path / "safe.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: csv
  path: /tmp/orders.csv
  read:
    schema: "order_id STRING, amount DOUBLE"
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
quality_rules:
  not_null: [order_id]
annotations:
  table:
    description: Orders landing table
operations:
  technical_owner: data-engineering
""",
        encoding="utf-8",
    )

    result = review_contract(contract)

    assert result.status == "PASS"
    assert result.findings == []
    assert result.traceability.confidence == 1.0
    assert result.traceability.review_required is False


def test_review_flags_autoloader_without_checkpoint(tmp_path: Path):
    contract = tmp_path / "auto.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: autoloader
  format: csv
  path: /Volumes/main/landing/orders
  read:
    schema: "order_id STRING"
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
quality_rules:
  not_null: [order_id]
annotations:
  table:
    description: Orders
operations:
  technical_owner: data-engineering
""",
        encoding="utf-8",
    )

    result = review_contract(contract)

    assert result.status == "FAIL"
    assert any(finding.code == "autoloader.checkpoint.missing" for finding in result.findings)
    assert any(finding.code == "autoloader.schema_location.missing" for finding in result.findings)


def test_bundle_review_loads_sibling_annotations_and_operations(tmp_path: Path):
    contract = tmp_path / "b_orders.ingestion.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: csv
  path: /tmp/orders.csv
  read:
    schema: "order_id STRING, amount DOUBLE"
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
quality_rules:
  not_null: [order_id]
""",
        encoding="utf-8",
    )
    (tmp_path / "b_orders.annotations.yaml").write_text(
        """
annotations:
  table:
    description: Orders landing table
  columns:
    order_id:
      description: Source order identifier
""",
        encoding="utf-8",
    )
    (tmp_path / "b_orders.operations.yaml").write_text(
        """
operations:
  technical_owner: data-engineering
  criticality: medium
""",
        encoding="utf-8",
    )

    standalone = review_contract(contract)
    bundled = review_contract(contract, bundle=True)

    assert any(finding.code == "annotations.missing" for finding in standalone.findings)
    assert any(finding.code == "operations.missing" for finding in standalone.findings)
    assert bundled.status == "PASS"
    assert bundled.findings == []
    assert bundled.traceability.evidence[0].value["bundle_review"] is True
    assert bundled.traceability.evidence[0].value["annotations_loaded"] is True
    assert bundled.traceability.evidence[0].value["operations_loaded"] is True


def test_bundle_review_distinguishes_missing_sibling_metadata(tmp_path: Path):
    contract = tmp_path / "b_orders.ingestion.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: csv
  path: /tmp/orders.csv
  read:
    schema: "order_id STRING"
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
quality_rules:
  not_null: [order_id]
""",
        encoding="utf-8",
    )

    result = review_contract(contract, bundle=True)

    assert result.status == "WARN"
    assert any(finding.code == "annotations.sibling.missing" for finding in result.findings)
    assert any(finding.code == "operations.sibling.missing" for finding in result.findings)
    assert not any(finding.code == "annotations.missing" for finding in result.findings)
    assert not any(finding.code == "operations.missing" for finding in result.findings)
