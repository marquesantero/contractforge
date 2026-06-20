from contractforge_ai.context.redaction import redact_secrets


def test_redacts_secret_keys_and_secret_templates():
    payload = {
        "source": {
            "auth": {
                "api_key": "plain-value",
                "client_secret": "{{ secret:scope/client_secret }}",
            },
            "path": "s3://bucket/path",
        }
    }

    redacted = redact_secrets(payload)

    assert redacted["source"]["auth"]["api_key"] == "[REDACTED]"
    assert redacted["source"]["auth"]["client_secret"] == "[REDACTED]"
    assert redacted["source"]["path"] == "s3://bucket/path"


def test_redacts_secret_template_inside_non_secret_field():
    payload = {"url": "https://example.com?token={{ secret:scope/token }}"}

    redacted = redact_secrets(payload)

    assert redacted["url"] == "https://example.com?token=[REDACTED_SECRET_REF]"


def test_redacts_inline_secret_assignments_in_strings():
    payload = {"intent": "Use token=secret-token and password:plain-password for this test."}

    redacted = redact_secrets(payload)

    assert "secret-token" not in redacted["intent"]
    assert "plain-password" not in redacted["intent"]
    assert "token=[REDACTED]" in redacted["intent"]
    assert "password:[REDACTED]" in redacted["intent"]


def test_redacts_bearer_headers_and_openai_style_keys_in_error_strings():
    payload = {
        "warning": (
            "Invalid header value b'Bearer sk-proj_abc1234567890XYZABCDEF\\r\\n' "
            "while calling provider."
        )
    }

    redacted = redact_secrets(payload)

    assert "sk-proj" not in redacted["warning"]
    assert "\\r\\n" not in redacted["warning"]
    assert "Bearer [REDACTED]" in redacted["warning"]
