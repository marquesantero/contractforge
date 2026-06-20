"""Render RDS IAM JDBC auth for AWS Glue scripts.

The core's ``rds_iam_review_options`` writes a placeholder password
(``{{rds_iam_token}}``) plus ``contractforge.rdsIamHost / Port / Region``
metadata options for ``source.auth.type='rds_iam'``. The AWS adapter renders a
static Glue script, so it emits a runtime ``_cf_rds_iam_token(...)`` call (boto3
``rds.generate_db_auth_token``) and strips the metadata options. The token is
generated when the job runs and never reaches the published artifact.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contractforge_aws.security import RDS_IAM_TOKEN_PLACEHOLDER, is_rds_iam_options

_HOST_OPTION = "contractforge.rdsIamHost"
_PORT_OPTION = "contractforge.rdsIamPort"
_REGION_OPTION = "contractforge.rdsIamRegion"
_METADATA_OPTIONS = (_HOST_OPTION, _PORT_OPTION, _REGION_OPTION)

__all__ = [
    "RDS_IAM_TOKEN_PLACEHOLDER",
    "is_rds_iam_options",
    "render_rds_iam_token_helper",
    "split_rds_iam_options",
]


def split_rds_iam_options(options: Mapping[str, Any]) -> tuple[dict[str, str], str]:
    """Return ``(render_options, password_expression)`` for an RDS IAM source.

    The returned options drop the placeholder password and the
    ``contractforge.rdsIam*`` metadata; the password expression is a runtime
    ``_cf_rds_iam_token(...)`` call built from that metadata and the JDBC user.
    """

    cleaned = {str(key): str(value) for key, value in options.items()}
    host = cleaned.pop(_HOST_OPTION, "")
    port = cleaned.pop(_PORT_OPTION, "")
    region = cleaned.pop(_REGION_OPTION, "")
    cleaned.pop("password", None)
    username = cleaned.get("user", "")
    if not host or not port or not region:
        raise ValueError(
            "RDS IAM JDBC rendering requires contractforge.rdsIamHost, contractforge.rdsIamPort and "
            "contractforge.rdsIamRegion (produced by the core for source.auth.type='rds_iam')"
        )
    if not username:
        raise ValueError("RDS IAM JDBC rendering requires a JDBC user (source.auth.username)")
    expression = f"_cf_rds_iam_token({host!r}, {int(port)}, {region!r}, {username!r})"
    return cleaned, expression


def render_rds_iam_token_helper() -> str:
    """Render the Glue-runtime ``_cf_rds_iam_token`` helper definition."""

    return "\n".join(
        [
            "_CF_RDS_CLIENT = None",
            "",
            "",
            "def _cf_rds_iam_token(host, port, region, username):",
            '    """Generate an RDS IAM auth token at Glue job runtime."""',
            "    global _CF_RDS_CLIENT",
            "    if _CF_RDS_CLIENT is None:",
            "        _CF_RDS_CLIENT = boto3.client('rds', region_name=region)",
            "    return _CF_RDS_CLIENT.generate_db_auth_token(",
            "        DBHostname=host, Port=port, DBUsername=username, Region=region",
            "    )",
            "",
        ]
    )
