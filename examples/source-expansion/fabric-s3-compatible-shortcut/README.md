# Fabric S3-Compatible Shortcut Source Smoke

This project is a focused `F11` source-expansion smoke for native Fabric
S3-compatible shortcut-backed CSV reads.

The project is contract-only: `project.fabric_setup.shortcuts` creates the
native Fabric shortcut before execution, and the ingestion contract reads the
Lakehouse `Files/...` shortcut path without notebook workaround code.
