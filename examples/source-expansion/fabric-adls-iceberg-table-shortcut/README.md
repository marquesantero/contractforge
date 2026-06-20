# Fabric ADLS Iceberg Table Shortcut Source Smoke

This project is a focused `F11` source-expansion smoke for an Azure Data Lake
Storage Gen2-backed Iceberg table shortcut in Fabric.

The project is contract-only: `project.fabric_setup.shortcuts` creates the
native Fabric `Tables` shortcut before execution, and the ingestion contract
reads `source.type: iceberg_table` without notebook workaround code.
