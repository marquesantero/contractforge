import json

from contractforge_core.cli import main


def test_core_cli_validate_contract_file(tmp_path, capsys) -> None:
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "source": {"type": "table", "table": "raw.orders"},
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
                "mode": "upsert",
                "merge_keys": ["order_id"],
            }
        ),
        encoding="utf-8",
    )

    assert main(["validate", str(contract), "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "SUCCESS"
    assert payload["items"][0]["mode"] == "upsert"


def test_core_cli_validate_project_discovers_split_bundle(tmp_path, capsys) -> None:
    output = tmp_path / "contracts" / "silver" / "s_orders"
    assert (
        main(
            [
                "init",
                "--output",
                str(output),
                "--source",
                "raw.orders",
                "--target-table",
                "orders",
                "--catalog",
                "main",
                "--target-schema",
                "silver",
                "--adapter",
                "databricks",
                "--mode",
                "upsert",
                "--merge-keys",
                "order_id",
                "--indent",
                "0",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["validate-project", str(tmp_path), "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "SUCCESS"
    assert payload["items"][0]["kind"] == "bundle"
    assert payload["items"][0]["target"] == "orders"


def test_core_cli_validate_project_ignores_project_connections_and_generated_metadata(tmp_path, capsys) -> None:
    project = tmp_path / "project.yaml"
    connection = tmp_path / "connections" / "supabase.yaml"
    generated = tmp_path / ".databricks" / "bundle" / "dev" / "deployment.json"
    contract = tmp_path / "contracts" / "silver" / "s_orders" / "s_orders.ingestion.yaml"
    connection.parent.mkdir(parents=True)
    generated.parent.mkdir(parents=True)
    contract.parent.mkdir(parents=True)
    project.write_text("name: demo\nsource_system: legacy_project_metadata\n", encoding="utf-8")
    connection.write_text("source:\n  type: jdbc\n  url: jdbc:postgresql://host/db\n", encoding="utf-8")
    generated.write_text(json.dumps({"version": 1, "files": []}), encoding="utf-8")
    contract.write_text(
        """
source:
  type: table
  ref: bronze.orders
target:
  catalog: main
  schema: silver
  table: orders
mode: overwrite
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["validate-project", str(tmp_path), "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "SUCCESS"
    assert payload["total"] == 1
    assert payload["items"][0]["path"].endswith("s_orders.ingestion.yaml")


def test_core_cli_schema_includes_environment(capsys) -> None:
    assert main(["schema", "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert "contract" in payload
    assert "environment" in payload
    assert "execution" in payload
    props = payload["contract"]["properties"]
    assert "execution" in props
    assert "idempotency_policy" in props
    assert "watermark_columns" in props
    assert "column_mapping" in props


def test_core_cli_connectors_doctor_reports_portable_and_unsupported(capsys) -> None:
    assert main(["connectors", "doctor", "incremental_files", "autoloader", "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)
    statuses = {item["name"]: item["status"] for item in payload["items"]}

    assert statuses["incremental_files"] == "SUCCESS"
    assert statuses["autoloader"] == "FAILED"


def test_core_cli_validate_rejects_incomplete_executable_source(tmp_path, capsys) -> None:
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "source": {"type": "connector", "connector": "rest_api"},
                "target": {"table": "orders"},
                "mode": "append",
            }
        ),
        encoding="utf-8",
    )

    assert main(["validate", str(contract), "--indent", "0"]) == 1

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "FAILED"
    assert "source.request.url" in payload["items"][0]["error"]


def test_core_cli_validate_accepts_custom_source_connector(tmp_path, capsys) -> None:
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "source": {"type": "connector", "connector": "custom_crm_source", "name": "crm_accounts"},
                "target": {"table": "accounts"},
                "mode": "append",
            }
        ),
        encoding="utf-8",
    )

    assert main(["validate", str(contract), "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "SUCCESS"
