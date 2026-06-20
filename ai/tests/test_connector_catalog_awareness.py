from __future__ import annotations

import contractforge_ai
from contractforge_ai.connectors import connector_aliases, connector_intent, connector_message, supported_connector_names


def test_supported_connector_names_match_core_catalog_examples():
    names = set(supported_connector_names())

    assert {
        "incremental_files",
        "kafka_bounded",
        "kafka_available_now",
        "eventhubs_bounded",
        "eventhubs_available_now",
        "native_passthrough",
        "rest_api",
        "snowflake_jdbc",
    } <= names


def test_core_supported_connector_has_catalog_message():
    intent = connector_intent("postgres")

    assert intent.connector == "postgres"
    assert intent.display_name == "PostgreSQL JDBC"
    assert intent.family == "jdbc"
    assert intent.required_fields == ("url",)
    assert intent.supported_by_core is True
    assert intent.portability == "PORTABLE_BUILTIN"
    assert "Supported by ContractForge Core" in (intent.recommendation or "")


def test_databricks_autoloader_maps_to_portable_incremental_files():
    intent = connector_intent("autoloader")

    assert intent.connector == "incremental_files"
    assert intent.adapter == "databricks"
    assert intent.supported_by_core is True
    assert "Databricks-specific" in (intent.recommendation or "")
    assert "`incremental_files`" in intent.to_message()


def test_stream_aliases_map_to_bounded_or_available_now_core_sources():
    assert connector_intent("kafka").connector == "kafka_bounded"
    assert connector_intent("event hubs").connector == "eventhubs_bounded"
    assert connector_intent("kafka_available_now").connector == "kafka_available_now"
    assert connector_intent("aws kinesis").connector == "native_passthrough"
    assert connector_intent("aws kinesis").adapter == "aws"


def test_vendor_and_legacy_protocols_map_to_native_passthrough():
    for name in ("salesforce", "sap_odata", "sharepoint", "sftp", "mongodb", "appflow", "dms", "hubspot"):
        intent = connector_intent(name)
        assert intent.connector == "native_passthrough"
        assert intent.supported_by_core is True
        assert "native_passthrough" in (intent.recommendation or "")


def test_connector_aliases_include_core_names_and_common_terms():
    aliases = connector_aliases()

    assert aliases["postgres"] == "postgres"
    assert aliases["autoloader"] == "incremental_files"
    assert aliases["snowflake"] == "snowflake_jdbc"
    assert aliases["event_hubs"] == "eventhubs_bounded"
    assert aliases["azure_data_lake"] == "adls"
    assert aliases["google_cloud_storage"] == "gcs"
    assert aliases["appflow"] == "native_passthrough"


def test_connector_alias_targets_are_supported_by_core():
    supported = set(supported_connector_names())

    assert all(target in supported for target in connector_aliases().values())


def test_connector_message_states_core_support_and_required_fields():
    message = connector_message("http json file")

    assert "`http_json`" in message
    assert "supported by ContractForge Core" in message
    assert "Required fields: request.url" in message


def test_unknown_connector_message_is_explicitly_unsupported():
    intent = connector_intent("custom mainframe spool")

    assert intent.connector == "custom_mainframe_spool"
    assert intent.supported_by_core is False
    assert "Unsupported by ContractForge Core" in (intent.recommendation or "")
    assert "unsupported by ContractForge Core" in intent.to_message()


def test_connector_helpers_are_public_ai_api():
    assert contractforge_ai.connector_intent("autoloader").connector == "incremental_files"
    assert "`incremental_files`" in contractforge_ai.connector_message("cloudFiles")
    assert "postgres" in contractforge_ai.supported_connector_names()
