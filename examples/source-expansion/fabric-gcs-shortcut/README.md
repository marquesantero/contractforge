# Fabric GCS shortcut source smoke

This project is a focused `F11` source-expansion smoke for Google Cloud
Storage shortcut-backed CSV reads in Fabric.

The project is contract-only: `project.fabric_setup.shortcuts` creates the
native Fabric shortcut before execution, and the ingestion contract reads the
Lakehouse `Files/...` shortcut path without notebook workaround code.
