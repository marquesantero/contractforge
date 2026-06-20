# Fabric Iceberg Table Shortcut Source Smoke

This project is a focused `F11` source-expansion smoke for an external Iceberg
table folder stored in Amazon S3 and exposed through a Fabric Lakehouse table
shortcut.

The project-level `fabric_setup.shortcuts` block creates the shortcut directly
under `Tables`, pointing at a valid Iceberg folder with `metadata/` and `data/`.
The contract itself reads `source.type: iceberg_table` from the reflected
Lakehouse table and validates target/control-table evidence.
