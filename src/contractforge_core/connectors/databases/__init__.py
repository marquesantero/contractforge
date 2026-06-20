"""Facade for database connector families."""

from contractforge_core.connectors.databases.jdbc import (
    JDBC_CONNECTORS,
    generate_rds_iam_auth_token,
    infer_aws_region_from_rds_host,
    jdbc_common_options,
    parse_jdbc_host_port,
    rds_iam_review_options,
    validate_jdbc_source,
)

__all__ = [
    "JDBC_CONNECTORS",
    "generate_rds_iam_auth_token",
    "infer_aws_region_from_rds_host",
    "jdbc_common_options",
    "parse_jdbc_host_port",
    "rds_iam_review_options",
    "validate_jdbc_source",
]
