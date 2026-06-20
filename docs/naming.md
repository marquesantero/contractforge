# Naming

Naming has two separate concerns:

1. physical data identifiers declared by the contract;
2. generated artifact names created by adapters.

## Physical Targets

Physical target identifiers are user-owned:

```yaml
target:
  catalog: main
  schema: silver
  table: orders
```

The core should not rewrite these names to match a platform convention. Adapters may validate whether the target shape is legal for the platform.

## Logical Layer

`layer` is semantic metadata:

```yaml
layer: silver
```

It may influence generated artifact names, tags or review output, but it should not silently replace `target.schema`.

## Generated Names

Adapters may use core naming helpers to derive:

- bundle names;
- job names;
- task keys;
- review artifact names;
- evidence artifact names;
- staging names when needed.

Generated names must be deterministic and reviewable.

## Adapter Safety

Adapters should:

- quote identifiers using platform-specific rules;
- avoid changing physical targets silently;
- document naming constraints;
- produce review warnings for invalid or risky target names;
- keep generated names separate from contract-owned physical identifiers.
