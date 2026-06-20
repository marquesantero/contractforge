"""Security helpers for the AWS adapter (redaction and secret resolution)."""

from contractforge_core.security import REDACTED, redact_text, redact_value
from contractforge_aws.security.http_safety import ALLOW_PRIVATE_FLAG, validate_http_target
from contractforge_aws.security.secrets import (
    RDS_IAM_TOKEN_PLACEHOLDER,
    SECRET_PLACEHOLDER_RE,
    assert_no_inline_jdbc_secrets,
    contains_secret_placeholder,
    is_rds_iam_options,
    render_secret_aware_literal,
    render_secret_resolver_helper,
    secret_placeholder_refs,
)
from contractforge_aws.security.source_policy import validate_source_security

__all__ = [
    "REDACTED",
    "ALLOW_PRIVATE_FLAG",
    "RDS_IAM_TOKEN_PLACEHOLDER",
    "SECRET_PLACEHOLDER_RE",
    "assert_no_inline_jdbc_secrets",
    "contains_secret_placeholder",
    "is_rds_iam_options",
    "redact_text",
    "redact_value",
    "render_secret_aware_literal",
    "render_secret_resolver_helper",
    "secret_placeholder_refs",
    "validate_http_target",
    "validate_source_security",
]
