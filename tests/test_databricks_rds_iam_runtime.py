"""RDS IAM token materialization in the Databricks adapter runtime."""

from __future__ import annotations

import datetime as dt
import sys
from types import SimpleNamespace

import pytest

from contractforge_core.connectors import generate_rds_iam_auth_token, jdbc_common_options
from contractforge_databricks.sources.rds_iam_runtime import (
    RDS_IAM_TOKEN_PLACEHOLDER,
    _TOKEN_CACHE,
    _cache_key,
    materialize_rds_iam_options,
)


def _jdbc_source(auth: dict) -> dict:
    return {
        "type": "connector",
        "connector": "postgres",
        "options": {
            "url": "jdbc:postgresql://demo.cluster-xyz.us-east-1.rds.amazonaws.com:5432/orders",
            "dbtable": "public.orders",
            "driver": "org.postgresql.Driver",
        },
        "auth": auth,
    }


def test_materialize_rds_iam_options_replaces_placeholder_with_real_token() -> None:
    source = _jdbc_source(
        {
            "type": "rds_iam",
            "username": "app_user",
            "region": "us-east-1",
            "access_key_id": "AKIAEXAMPLE",
            "secret_access_key": "secret-example",
        }
    )
    options = jdbc_common_options(source)

    assert options["password"] == RDS_IAM_TOKEN_PLACEHOLDER

    materialized = materialize_rds_iam_options(options, auth=source["auth"])

    assert materialized["password"] != RDS_IAM_TOKEN_PLACEHOLDER
    assert materialized["password"].startswith("demo.cluster-xyz.us-east-1.rds.amazonaws.com:5432/?")
    # metadata flags scrubbed before the options leave the adapter
    assert "contractforge.rdsIamHost" not in materialized
    assert "contractforge.rdsIamPort" not in materialized
    assert "contractforge.rdsIamRegion" not in materialized
    # the rest of the JDBC options are preserved unchanged
    assert materialized["user"] == "app_user"
    assert materialized["ssl"] == "true"
    assert materialized["dbtable"] == "public.orders"


def test_materialize_rds_iam_options_passes_through_non_iam_options() -> None:
    source = _jdbc_source({"type": "basic", "username": "alice", "password": "secret"})
    options = jdbc_common_options(source)

    materialized = materialize_rds_iam_options(options, auth=source["auth"])

    assert materialized == options
    # No contractforge.rdsIam* keys were ever emitted, so removal is a no-op.


def test_materialize_rds_iam_options_requires_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _jdbc_source(
        {
            "type": "rds_iam",
            "username": "app_user",
            "region": "us-east-1",
        }
    )
    options = jdbc_common_options(source)

    _TOKEN_CACHE.clear()
    monkeypatch.setitem(sys.modules, "boto3", None)
    with pytest.raises(ValueError, match="source.auth.access_key_id/source.auth.secret_access_key"):
        materialize_rds_iam_options(options, auth=source["auth"])


def test_materialize_rds_iam_options_uses_boto3_default_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class FakeRdsClient:
        def generate_db_auth_token(self, **kwargs):
            calls.append(kwargs)
            return "boto3-generated-token"

    class FakeSession:
        def __init__(self, *, region_name: str):
            self.region_name = region_name

        def client(self, service_name: str, *, region_name: str):
            assert service_name == "rds"
            assert region_name == "us-east-1"
            return FakeRdsClient()

    _TOKEN_CACHE.clear()
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(Session=FakeSession))
    source = _jdbc_source({"type": "rds_iam", "username": "app_user", "region": "us-east-1"})
    options = jdbc_common_options(source)

    materialized = materialize_rds_iam_options(options, auth=source["auth"])

    assert materialized["password"] == "boto3-generated-token"
    assert calls == [
        {
            "DBHostname": "demo.cluster-xyz.us-east-1.rds.amazonaws.com",
            "Port": 5432,
            "DBUsername": "app_user",
            "Region": "us-east-1",
        }
    ]


def test_materialize_rds_iam_options_caches_boto3_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class FakeRdsClient:
        def generate_db_auth_token(self, **kwargs):
            calls.append(kwargs)
            return f"token-{len(calls)}"

    class FakeSession:
        def __init__(self, *, region_name: str):
            self.region_name = region_name

        def client(self, service_name: str, *, region_name: str):
            return FakeRdsClient()

    _TOKEN_CACHE.clear()
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(Session=FakeSession))
    source = _jdbc_source({"type": "rds_iam", "username": "app_user", "region": "us-east-1"})
    options = jdbc_common_options(source)

    first = materialize_rds_iam_options(options, auth=source["auth"])
    second = materialize_rds_iam_options(options, auth=source["auth"])

    assert first["password"] == "token-1"
    assert second["password"] == "token-1"
    assert len(calls) == 1


def test_materialize_rds_iam_options_uses_session_token_when_provided() -> None:
    _TOKEN_CACHE.clear()
    source = _jdbc_source(
        {
            "type": "rds_iam",
            "username": "app_user",
            "region": "us-east-1",
            "access_key_id": "AKIAEXAMPLE",
            "secret_access_key": "secret-example",
            "session_token": "session-token-value",
        }
    )
    options = jdbc_common_options(source)
    materialized = materialize_rds_iam_options(options, auth=source["auth"])

    assert "X-Amz-Security-Token" in materialized["password"]
    cache_keys = tuple(_TOKEN_CACHE)
    assert cache_keys
    assert all("AKIAEXAMPLE" not in key for key in cache_keys)
    assert all("secret-example" not in key for key in cache_keys)
    assert all("session-token-value" not in key for key in cache_keys)


def test_rds_iam_cache_key_hashes_components_incrementally(monkeypatch: pytest.MonkeyPatch) -> None:
    updates: list[bytes] = []

    class FakeDigest:
        def update(self, value: bytes) -> None:
            updates.append(value)

        def hexdigest(self) -> str:
            return "digest"

    monkeypatch.setattr(
        "contractforge_databricks.sources.rds_iam_runtime.hashlib.sha256",
        lambda: FakeDigest(),
    )

    assert (
        _cache_key(
            host="db.example.com",
            port=5432,
            region="us-east-1",
            username="app_user",
            access_key="AKIAEXAMPLE",
            secret_key="secret-example",
            session_token="session-token-value",
        )
        == "digest"
    )

    joined_material = b"\x1f".join(
        (
            b"db.example.com",
            b"5432",
            b"us-east-1",
            b"app_user",
            b"AKIAEXAMPLE",
            b"secret-example",
            b"session-token-value",
        )
    )
    assert joined_material not in updates
    assert updates.count(b"\x1f") == 7


def test_materialize_rds_iam_options_matches_core_token_generation() -> None:
    # The runtime helper uses the wall clock. Compare the stable endpoint and
    # SigV4 shape against a core-generated token for the current date.
    now = dt.datetime.now(dt.timezone.utc)
    expected = generate_rds_iam_auth_token(
        host="demo.cluster-xyz.us-east-1.rds.amazonaws.com",
        port=5432,
        region="us-east-1",
        username="app_user",
        access_key="AKIAEXAMPLE",
        secret_key="secret-example",
        now=now,
    )

    source = _jdbc_source(
        {
            "type": "rds_iam",
            "username": "app_user",
            "region": "us-east-1",
            "access_key_id": "AKIAEXAMPLE",
            "secret_access_key": "secret-example",
        }
    )
    options = jdbc_common_options(source)
    materialized = materialize_rds_iam_options(options, auth=source["auth"])

    assert materialized["password"].startswith("demo.cluster-xyz.us-east-1.rds.amazonaws.com:5432/?")
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in materialized["password"]
    assert f"%2F{now.strftime('%Y%m%d')}%2Fus-east-1%2Frds-db%2Faws4_request" in materialized["password"]
    assert expected.split("&X-Amz-Date=", 1)[0].split("%2Frds-db%2Faws4_request", 1)[0] in materialized["password"]
