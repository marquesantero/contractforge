# Amazon RDS/Aurora JDBC with IAM Auth

This guide describes the validated path for reading Amazon RDS/Aurora through JDBC using `source.auth.type: rds_iam`.

Real validation performed:

- Runtime: Azure Databricks classic single-node.
- Cluster: `SINGLE_USER`, with PostgreSQL JDBC driver installed.
- Database: Amazon Aurora PostgreSQL 17.7.
- ContractForge: `2.6.5` and later.
- Result: `ingest()` with `connector: postgres`, `auth.type: rds_iam`, JDBC partitioning and `scd1_hash_diff` finished with `SUCCESS`.

## When to Use

Use `auth.type: rds_iam` when the source is Amazon RDS/Aurora with IAM database authentication enabled and you want to avoid a fixed database password in the contract.

Use `auth.type: basic` only when the database accepts traditional username/password authentication:

```yaml
source:
  auth:
    type: basic
    username: "{{ secret:scope/db_user }}"
    password: "{{ secret:scope/db_password }}"
```

## Prerequisites

- The RDS/Aurora endpoint must be reachable over TCP from the Databricks compute.
- The database JDBC driver must be installed on the cluster.
- The database user must exist and be authorized for IAM auth.
- The IAM principal used by ContractForge must have `rds-db:connect`.
- AWS credentials must be available in `source.auth`, Databricks Secrets, environment variables or the AWS credential provider chain when `credential_provider: default_chain` is used.

## JDBC Driver on Databricks

For PostgreSQL:

```text
org.postgresql:postgresql:42.7.4
```

On Unity Catalog `standard`/shared clusters, Maven libraries may require artifact allowlisting. If installation fails with an allowlist message, use one of these options:

- Ask the metastore admin to allowlist the Maven artifact.
- Use a `SINGLE_USER` cluster for controlled validation.

## PostgreSQL User

Example with a dedicated user:

```sql
CREATE USER contractforge_iam;
GRANT rds_iam TO contractforge_iam;
GRANT CONNECT ON DATABASE postgres TO contractforge_iam;
GRANT USAGE ON SCHEMA public TO contractforge_iam;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO contractforge_iam;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO contractforge_iam;
```

For quick validation, the master user may also work when authorized, but the recommended pattern is a dedicated user with minimum permissions.

## IAM Policy

The `rds-db:connect` resource uses the `DbiResourceId` or `DbClusterResourceId`, not the common cluster ARN.

For an Aurora cluster:

```bash
aws rds describe-db-clusters \
  --db-cluster-identifier <cluster-id> \
  --query "DBClusters[0].DbClusterResourceId" \
  --output text
```

Example policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "rds-db:connect",
      "Resource": "arn:aws:rds-db:us-east-1:123456789012:dbuser:cluster-ABCDEFGHIJKL/contractforge_iam"
    }
  ]
}
```

Attach the policy to the user or role used by the job.

## Secrets

Example Databricks secrets:

```bash
databricks secrets put-secret contractforge-aws rds_jdbc_url
databricks secrets put-secret contractforge-aws rds_username
databricks secrets put-secret contractforge-aws aws_access_key_id
databricks secrets put-secret contractforge-aws aws_secret_access_key
```

`aws_session_token` is optional. Declare it only when using valid temporary credentials. An expired STS token causes authentication failure.

## AWS Credential Provider Chain

When the runtime already provides AWS credentials through an instance profile, local profile, web identity, managed environment variable or another mechanism supported by `botocore`, use `credential_provider: default_chain`.

This mode requires `botocore` in the Python driver. Install the `contractforge[aws]` extra or make `botocore` available in the environment. ContractForge still generates the IAM token internally; `boto3` and AWS CLI are not required.

```yaml
source:
  type: connector
  connector: postgres
  options:
    url: "{{ secret:contractforge-aws/rds_jdbc_url }}"
    dbtable: public.orders
    driver: org.postgresql.Driver
  auth:
    type: rds_iam
    username: "{{ secret:contractforge-aws/rds_username }}"
    region: us-east-1
    credential_provider: default_chain
```

Connector credential priority:

1. Explicit credentials in `source.auth`.
2. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN` environment variables.
3. `credential_provider: default_chain`, when configured.

## YAML Contract

```yaml
source:
  type: connector
  connector: postgres
  options:
    url: "{{ secret:contractforge-aws/rds_jdbc_url }}"
    dbtable: public.orders
    driver: org.postgresql.Driver
    ssl: "true"
    sslmode: require
  auth:
    type: rds_iam
    username: "{{ secret:contractforge-aws/rds_username }}"
    region: us-east-1
    access_key_id: "{{ secret:contractforge-aws/aws_access_key_id }}"
    secret_access_key: "{{ secret:contractforge-aws/aws_secret_access_key }}"
    sslmode: require
  read:
    fetchsize: 1000
    partition_column: order_id
    lower_bound: 1
    upper_bound: 1000000
    num_partitions: 8

target:
  catalog: contractforge
  schema: bronze
  table: b_rds_orders

mode: scd1_hash_diff
hash_keys: [order_id]
quality_rules:
  not_null: [order_id]
  unique_key: [order_id]
```

## Python Contract

When using `ingest()` directly, pass `catalog` explicitly. A qualified `target_schema` does not replace `catalog`.

```python
from contractforge import ingest

result = ingest(
    catalog="contractforge",
    target_schema="bronze",
    target_table="b_rds_orders",
    ctrl_schema="ops",
    source={
        "type": "connector",
        "connector": "postgres",
        "options": {
            "url": "{{ secret:contractforge-aws/rds_jdbc_url }}",
            "dbtable": "public.orders",
            "driver": "org.postgresql.Driver",
            "ssl": "true",
            "sslmode": "require",
        },
        "auth": {
            "type": "rds_iam",
            "username": "{{ secret:contractforge-aws/rds_username }}",
            "region": "us-east-1",
            "access_key_id": "{{ secret:contractforge-aws/aws_access_key_id }}",
            "secret_access_key": "{{ secret:contractforge-aws/aws_secret_access_key }}",
            "sslmode": "require",
        },
        "read": {
            "fetchsize": 1000,
            "partition_column": "order_id",
            "lower_bound": 1,
            "upper_bound": 1000000,
            "num_partitions": 8,
        },
    },
    mode="scd1_hash_diff",
    hash_keys=["order_id"],
)
```

## Metrics

The result and `ctrl_ingestion_runs.source_metrics_json` record:

- `jdbc_auth_configured=true`
- `jdbc_auth_type=rds_iam`
- `jdbc_rds_iam_token_generated=true`
- `jdbc_rds_region=<region>`
- `jdbc_rds_iam_credential_source=explicit|env|default_chain`
- `jdbc_ssl_enabled=true`
- `partitioned_read=true|false`
- `fetchsize=<value>`

Tokens and secrets are redacted in metadata, lineage and control tables.

## Troubleshooting

`PAM authentication failed`

- The database user does not have `rds_iam`.
- The IAM principal does not have `rds-db:connect`.
- The token was generated for a different user, host, port or region.
- The `aws_session_token` expired.
- The database requires IAM auth and you tried `auth.type: basic`.

`No suitable driver` or `ClassNotFoundException`

- The JDBC driver is not installed on the cluster.
- On UC standard/shared clusters, Maven may be blocked by artifact allowlisting.

Timeout or `Connection refused`

- The Databricks runtime cannot reach the RDS endpoint.
- Check VPC routing, peering, Transit Gateway, PrivateLink/NLB, security groups, firewall rules or Aurora Express Internet Access Gateway.

`Catalog 'main' was not found`

- Pass `catalog` explicitly to `ingest()`.
- Do not depend on the default catalog in new workspaces.

`Metastore storage root URL does not exist`

- Do not try to create a new catalog without a managed location.
- Use an existing catalog or create the catalog through UI/SQL with `MANAGED LOCATION`.

## Current Limitations

- `credential_provider: default_chain` depends on `botocore` being installed and credentials actually being available in the Python driver.
- Network connectivity to RDS/Aurora remains outside the scope of the library.
