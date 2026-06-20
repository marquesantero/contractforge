# Shape Suggestions

`contractforge-ai suggest-shape` inspects nested JSON samples and creates a draft ContractForge `shape` block.

The command is deterministic. It does not call a model provider and does not mutate files.

## Basic Usage

```bash
contractforge-ai suggest-shape --sample sample.json --format yaml
```

Input:

```json
{
  "id": "evt-1",
  "properties": {
    "mag": 2.1,
    "place": "10 km S",
    "time": 1710000000000
  },
  "geometry": {
    "type": "Point",
    "coordinates": [-122.1, 37.1, 10.0]
  }
}
```

Possible output:

```yaml
shape:
  select:
    - path: id
      alias: id
    - path: properties.mag
      alias: properties_mag
    - path: properties.place
      alias: properties_place
    - path: properties.time
      alias: properties_time
    - path: geometry.type
      alias: geometry_type
  flatten:
    - path: properties
      prefix: properties
    - path: geometry
      prefix: geometry
  explode:
    - path: geometry.coordinates
      mode: outer
      alias: geometry_coordinates
      requires_review: true
  notes:
    - Generated from a sample payload. Review before applying.
    - Explode operations are marked requires_review because they can change row cardinality.
```

## Arrays of Structs

For arrays such as:

```json
{
  "order_id": "1",
  "items": [
    {"sku": "A", "quantity": 2},
    {"sku": "B", "quantity": 1}
  ]
}
```

The generator emits an explode candidate and decision notes. You must decide the target grain:

- one row per order;
- one row per item;
- separate child table for items;
- aggregate item information before writing.

## Cardinality Rule

Any operation that changes row count must be explicit. The generator marks array explosions with `requires_review` and emits warnings so the user validates row counts before applying the shape.

## JSON Output

Use JSON when tooling needs discovered paths, warnings and decisions:

```bash
contractforge-ai suggest-shape --sample sample.json --format json
```

The response includes:

- `shape`: draft ContractForge shape config;
- `python_example`: executable starter Python call with the generated shape represented as a dictionary;
- `decisions_required`: human decisions before applying;
- `warnings`: safety notes;
- `discovered_paths`: primitive, struct and array paths found in the sample.

The Python example is intended to compile as-is after replacing placeholders such as `source={...}` with a real ContractForge source definition. It keeps the generated shape as `shape = {...}` and passes it with `shape=shape`, instead of embedding YAML text inside Python.

## Limits

The generator uses a sample payload. It cannot guarantee complete schema coverage if optional fields do not appear in the sample. For production contracts, compare output with source documentation or a larger profiling sample.

