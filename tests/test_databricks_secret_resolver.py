"""Databricks secret placeholder resolver — env-var override gate."""

from __future__ import annotations

import pytest

from contractforge_databricks.security.secrets import (
    ENV_OVERRIDE_FLAG,
    assert_no_inline_jdbc_secrets,
    contains_secret_placeholder,
    resolve_databricks_secret_placeholders,
    secret_placeholder_refs,
)


def test_env_override_is_ignored_when_flag_unset(monkeypatch) -> None:
    monkeypatch.delenv(ENV_OVERRIDE_FLAG, raising=False)
    monkeypatch.setenv("CONTRACTFORGE_SECRET_AWS_RDS_PASSWORD", "from-env")

    with pytest.raises(RuntimeError, match="Could not resolve dbutils"):
        resolve_databricks_secret_placeholders("{{ secret:aws/rds_password }}")


@pytest.mark.parametrize("flag_value", ["1", "true", "yes", "on", "True", "YES", "  on  "])
def test_env_override_honored_when_flag_truthy(monkeypatch, flag_value: str) -> None:
    monkeypatch.setenv(ENV_OVERRIDE_FLAG, flag_value)
    monkeypatch.setenv("CONTRACTFORGE_SECRET_AWS_RDS_PASSWORD", "from-env")

    assert (
        resolve_databricks_secret_placeholders("{{ secret:aws/rds_password }}")
        == "from-env"
    )


@pytest.mark.parametrize("flag_value", ["0", "false", "no", "off", "", "anything"])
def test_env_override_ignored_when_flag_falsy(monkeypatch, flag_value: str) -> None:
    monkeypatch.setenv(ENV_OVERRIDE_FLAG, flag_value)
    monkeypatch.setenv("CONTRACTFORGE_SECRET_AWS_RDS_PASSWORD", "from-env")

    with pytest.raises(RuntimeError, match="Could not resolve dbutils"):
        resolve_databricks_secret_placeholders("{{ secret:aws/rds_password }}")


def test_env_override_only_fires_for_existing_env_var(monkeypatch) -> None:
    """With the flag set but no matching env var, fallback to dbutils is exercised."""

    monkeypatch.setenv(ENV_OVERRIDE_FLAG, "1")
    monkeypatch.delenv("CONTRACTFORGE_SECRET_AWS_RDS_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="Could not resolve dbutils"):
        resolve_databricks_secret_placeholders("{{ secret:aws/rds_password }}")


def test_resolver_recurses_into_mappings_and_lists(monkeypatch) -> None:
    monkeypatch.setenv(ENV_OVERRIDE_FLAG, "1")
    monkeypatch.setenv("CONTRACTFORGE_SECRET_SCOPE_KEY1", "v1")
    monkeypatch.setenv("CONTRACTFORGE_SECRET_SCOPE_KEY2", "v2")

    resolved = resolve_databricks_secret_placeholders(
        {
            "outer": "{{ secret:scope/key1 }}",
            "options": {"nested": "prefix-{{ secret:scope/key2 }}-suffix"},
            "list_values": ["{{ secret:scope/key1 }}", "literal"],
        }
    )

    assert resolved["outer"] == "v1"
    assert resolved["options"]["nested"] == "prefix-v2-suffix"
    assert resolved["list_values"] == ["v1", "literal"]


def test_resolver_rejects_malformed_placeholder(monkeypatch) -> None:
    monkeypatch.setenv(ENV_OVERRIDE_FLAG, "1")

    with pytest.raises(ValueError, match="format \\{\\{ secret:scope/key \\}\\}"):
        resolve_databricks_secret_placeholders("{{ secret:no-slash }}")

    with pytest.raises(ValueError, match="non-empty scope"):
        resolve_databricks_secret_placeholders("{{ secret:/key }}")


def test_secret_placeholder_refs_and_detection() -> None:
    value = "jdbc://host?password={{ secret:scope/key }}&token={{ secret:other/token }}"

    assert contains_secret_placeholder({"nested": [value]}) is True
    assert secret_placeholder_refs(value) == (("scope", "key"), ("other", "token"))


def test_databricks_jdbc_secret_policy_rejects_inline_credentials() -> None:
    with pytest.raises(ValueError, match="JDBC 'password' must be provided via"):
        assert_no_inline_jdbc_secrets({"password": "raw-password"})

    with pytest.raises(ValueError, match="JDBC url embeds inline credentials"):
        assert_no_inline_jdbc_secrets({"url": "jdbc:postgresql://user:password@host/db"})


def test_databricks_jdbc_secret_policy_accepts_placeholders_and_rds_iam() -> None:
    assert_no_inline_jdbc_secrets({"password": "{{ secret:scope/password }}"})
    assert_no_inline_jdbc_secrets({"password": "{{rds_iam_token}}"})
