from __future__ import annotations

import pytest

from contractforge_aws.cli import main as aws_main
from contractforge_databricks.cli import main as databricks_main
from contractforge_fabric.cli import main as fabric_main
from contractforge_gcp.cli import main as gcp_main
from contractforge_snowflake.cli import main as snowflake_main


@pytest.mark.parametrize(
    ("main", "commands"),
    [
        (
            aws_main,
            {
                "plan",
                "render",
                "smoke",
                "deploy-project",
                "run-project",
                "sources",
                "stabilization-report",
                "cost-report",
                "performance-report",
            },
        ),
        (
            databricks_main,
            {"plan", "render", "deploy-project", "run-project", "sources", "stabilization-report", "cost-report"},
        ),
        (fabric_main, {"plan", "render", "smoke", "deploy-project", "run-project", "sources", "stabilization-report"}),
        (gcp_main, {"plan", "render", "smoke", "deploy-project", "run-project", "sources", "stabilization-report", "cost-report"}),
        (
            snowflake_main,
            {"plan", "render", "smoke", "deploy-project", "run-project", "sources", "stabilization-report", "cost-report"},
        ),
    ],
)
def test_adapter_cli_exposes_canonical_commands(main, commands, capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for command in commands:
        assert command in help_text


@pytest.mark.parametrize(
    ("main", "command", "flags"),
    [
        (aws_main, "plan", {"--environment"}),
        (databricks_main, "plan", {"--environment"}),
        (fabric_main, "plan", {"--environment"}),
        (gcp_main, "plan", {"--environment"}),
        (snowflake_main, "plan", {"--environment"}),
        (aws_main, "render", {"--environment"}),
        (databricks_main, "render", {"--environment", "--output-dir"}),
        (fabric_main, "render", {"--environment"}),
        (gcp_main, "render", {"--environment", "--output-dir"}),
        (snowflake_main, "render", {"--environment", "--output-dir"}),
        (
            gcp_main,
            "deploy-project",
            {
                "--environment",
                "--environment-key",
                "--render-orchestration",
                "--deploy-orchestration",
                "--run-orchestration",
                "--wait-orchestration",
            },
        ),
        (aws_main, "run-project", {"--environment", "--environment-key", "--dry-run", "--summary-only"}),
        (fabric_main, "run-project", {"--environment", "--environment-key", "--continue-on-failure", "--start-at"}),
        (gcp_main, "run-project", {"--environment", "--environment-key", "--continue-on-failure", "--start-at"}),
        (snowflake_main, "run-project", {"--environment", "--environment-key", "--dry-run", "--summary-only"}),
    ],
)
def test_adapter_cli_canonical_commands_expose_common_flags(main, command, flags, capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main([command, "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for flag in flags:
        assert flag in help_text
