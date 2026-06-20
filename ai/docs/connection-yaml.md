# Connection YAML

Connection YAML files define reusable source defaults. They are resolved by the core bundle loader before adapter planning.

## Example

```yaml
# connections/supabase.yaml
type: connector
connector: postgres
system: supabase_inventory
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

The ingestion contract references it:

```yaml
source:
  type: connection
  connection_path: project://connections/supabase.yaml
  table: public.products
  read:
    fetchsize: 20000
```

## Override Precedence

Connection YAML is loaded first. Ingestion `source` is merged on top. Therefore:

- connection `read.fetchsize: 10000`
- ingestion `read.fetchsize: 20000`

resolves to `read.fetchsize: 20000`.

This is deliberate. Global connector defaults should never hide dataset-specific table, query, partition, watermark or read behavior.

## Security

- Prefer `project://connections/...`.
- Same-bundle relative paths must stay inside the bundle directory.
- Absolute paths and `..` traversal are rejected.
- AI must never generate raw secret values.
