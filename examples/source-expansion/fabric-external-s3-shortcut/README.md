# Fabric External Amazon S3 Shortcut Source Smoke

This project is a focused `F11` source-expansion smoke for native Fabric
external shortcut creation against Amazon S3.

The project-level `fabric_setup.shortcuts` block creates the Fabric shortcut
with a Fabric AmazonS3 cloud connection. The contracts themselves only read the
resulting Lakehouse Files shortcut path and validate target/control-table
evidence.
