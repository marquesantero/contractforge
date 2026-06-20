# Security

ContractForge Core defines secure semantics; adapters implement platform-specific credential, governance and persistence behavior.

## Core Security Rules

- Do not store secrets in contracts.
- Use placeholders or adapter-native secret references.
- Redact source options, URLs, headers, JDBC properties and error payloads before evidence persistence.
- Keep platform SDKs out of `contractforge_core`.
- Treat access contracts as intent until an adapter proves native equivalence.

## Secrets

Contracts should refer to secrets indirectly:

```yaml
source:
  type: jdbc
  jdbc:
    url: "{{ secret:erp/postgres_url }}"
    table: public.orders
  auth:
    method: basic
    username: "{{ secret:erp/user }}"
    password: "{{ secret:erp/password }}"
```

The core should validate shape and redact values. The adapter resolves placeholders using the platform-approved mechanism.

Adapter security policy:

- Databricks resolves `{{ secret:scope/key }}` through `dbutils.secrets` at runtime. Environment-variable override is disabled by default and only honored when `CONTRACTFORGE_ALLOW_SECRET_ENV_OVERRIDE=1`.
- Databricks JDBC sources reject inline `password`/`sfpassword` values and JDBC URLs containing `user:password@host`. Use secret placeholders or adapter-owned authentication such as RDS IAM.
- AWS rendered Glue artifacts must not contain real credentials. JDBC secrets are rendered as AWS Secrets Manager lookups in the generated Glue script, and inline JDBC credentials are rejected before artifact publication.
- Fabric rendered notebook artifacts resolve authenticated bounded HTTP/REST
  placeholders through Azure Key Vault with
  `notebookutils.credentials.getSecret`. The contract uses
  `{{ secret:scope/key }}`, and the Fabric environment maps the scope with
  `secrets.vault_url` or `secrets.scopes.<scope>`. Inline HTTP/REST credentials
  remain review-blocked.

## Adapter Credential Boundaries

Examples:

- Databricks: secret scopes, Unity Catalog External Locations, Volumes, Connections.
- AWS: IAM roles, Lake Formation, Secrets Manager, Glue connections.
- Fabric: Azure Key Vault, workspace connections and managed identities.
- Snowflake: secrets, integrations, roles and warehouses.

These mechanisms belong in adapter docs and adapter code, not in the core planner.

## Governance

Access contracts may include grants, row filters and column masks. These are not universally equivalent.

Adapters must return `REVIEW_REQUIRED` when:

- security inheritance differs;
- mask/filter semantics differ;
- policy evaluation context differs;
- destructive drift remediation is requested;
- permissions are insufficient to inspect or apply the policy.

## Evidence Redaction

Evidence must be useful without leaking credentials.

Redact:

- passwords;
- tokens;
- authorization headers;
- signed URLs;
- JDBC credentials;
- platform client configuration;
- exception traces containing secret material.

Keep:

- source type;
- redacted endpoint host when safe;
- connector family;
- capability evidence;
- runtime type;
- non-secret options relevant to reproducibility.
