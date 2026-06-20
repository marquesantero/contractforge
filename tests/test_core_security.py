from contractforge_core.security import redact_text, redact_value


def test_core_redact_text_removes_common_secret_patterns() -> None:
    raw = "\n".join(
        [
            "password=abc123",
            "Authorization: Bearer token-value",
            "Authorization: Basic base64-value",
            "jdbc:postgresql://user:pass@host/db",
            "https://host/path?access_token=abc&x-amz-signature=def",
            "client_secret: super-secret",
            "{{ secret:scope/key }}",
            "-----BEGIN PRIVATE KEY-----raw-----END PRIVATE KEY-----",
        ]
    )

    redacted = redact_text(raw)

    assert "abc123" not in redacted
    assert "token-value" not in redacted
    assert "base64-value" not in redacted
    assert "pass@host" not in redacted
    assert "access_token=abc" not in redacted
    assert "x-amz-signature=def" not in redacted
    assert "super-secret" not in redacted
    assert "scope/key" not in redacted
    assert "raw" not in redacted
    assert "***REDACTED***" in redacted


def test_core_redact_value_redacts_nested_sensitive_keys_and_strings() -> None:
    value = redact_value({"auth": {"secret_scope": "prod"}, "url": "jdbc:x://u:p@h/db?token=abc"})

    assert value["auth"]["secret_scope"] == "***REDACTED***"
    assert "token=***REDACTED***" in value["url"]
