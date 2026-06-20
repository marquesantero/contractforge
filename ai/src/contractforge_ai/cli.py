"""Command line interface for ContractForge AI."""

from __future__ import annotations

import sys

from contractforge_ai.cli_parser import build_parser
from contractforge_ai.cli_context_commands import CONTEXT_COMMAND_HANDLERS
from contractforge_ai.cli_generation_helpers import GENERATION_HELPER_COMMAND_HANDLERS
from contractforge_ai.cli_onboarding_commands import ONBOARDING_COMMAND_HANDLERS
from contractforge_ai.cli_prompt_evaluation import PROMPT_EVALUATION_COMMAND_HANDLERS
from contractforge_ai.cli_project_generation import PROJECT_GENERATION_COMMAND_HANDLERS
from contractforge_ai.cli_validation_commands import VALIDATION_COMMAND_HANDLERS
from contractforge_ai.cli_workflows import WORKFLOW_COMMAND_HANDLERS
from contractforge_ai.context import collect_databricks_run_evidence


COMMAND_GROUPS = (
    (WORKFLOW_COMMAND_HANDLERS, True),
    (CONTEXT_COMMAND_HANDLERS, False),
    (GENERATION_HELPER_COMMAND_HANDLERS, False),
    (PROJECT_GENERATION_COMMAND_HANDLERS, False),
    (ONBOARDING_COMMAND_HANDLERS, False),
    (PROMPT_EVALUATION_COMMAND_HANDLERS, False),
    (VALIDATION_COMMAND_HANDLERS, True),
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    for handlers, passes_parser in COMMAND_GROUPS:
        handler = handlers.get(args.command)
        if handler is not None:
            return handler(args, parser) if passes_parser else handler(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

