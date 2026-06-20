# Connection YAML Reference

Connection YAML files define reusable connector defaults. They are loaded by
the core before semantic planning, then merged with the ingestion contract's
`source` block.

Use connection files for shared source configuration:

- endpoint, URL and driver;
- authentication shape and secret references;
- source system label;
- common read defaults such as `fetchsize`.

Keep dataset-specific semantics in the ingestion contract:

- table or query;
- partition bounds;
- watermark;
- source completeness;
- target, mode, quality, governance and access policy.

## Project Inventory

`project.yaml` can list reusable connection files:

```yaml
connections:
  supabase_postgres: connections/supabase.yaml
```

This is inventory and documentation. It does not apply a connection by itself.
An ingestion contract applies a connection with `source.type: connection`.

## Connection File

```yaml
type: connector
connector: postgres
system: supabase_inventory_demo
options:
  url: "{{ secret:supabase/jdbc_url }}"
  driver: org.postgresql.Driver
auth:
  type: username_password
  username: "{{ secret:supabase/user }}"
  password: "{{ secret:supabase/password }}"
read:
  fetchsize: 10000
```

## Ingestion Override

```yaml
source:
  type: connection
  connection_path: project://connections/supabase.yaml
  table: public.products
  read:
    fetchsize: 20000
    partition_column: product_id
    lower_bound: 1
    upper_bound: 100000
    num_partitions: 8
```

Merge rule:

| Location | Role |
| --- | --- |
| Connection YAML | Shared defaults. |
| Ingestion `source` | Dataset-specific overrides. These values win. |

The resolved source passed to adapters is equivalent to:

```yaml
type: connector
connector: postgres
system: supabase_inventory_demo
options:
  url: "{{ secret:supabase/jdbc_url }}"
  driver: org.postgresql.Driver
auth:
  type: username_password
  username: "{{ secret:supabase/user }}"
  password: "{{ secret:supabase/password }}"
read:
  fetchsize: 20000
  partition_column: product_id
  lower_bound: 1
  upper_bound: 100000
  num_partitions: 8
table: public.products
connection: project://connections/supabase.yaml
```

`read.fetchsize` is `20000` because the ingestion contract overrides the global
default. Other nested `read` values are added by deep merge.

## Path Rules

Use `project://connections/...` for centralized project connection files.
Same-bundle relative paths are allowed only when they stay under the ingestion
bundle directory. Absolute paths and `..` traversal are rejected.

Adapters must not re-read connection YAML files. They receive the resolved
source payload from the core and record the effective connector metadata in
evidence.
