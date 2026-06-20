"""CLI handlers for prompt evaluation commands."""

from __future__ import annotations

import json

from contractforge_ai.cli_output import (
    _print_text_prompt_eval_results,
    _print_text_prompt_templates,
)
from contractforge_ai.evaluation import evaluate_prompt_cases, list_prompt_templates


def _handle_eval_prompts_command(args) -> int:
    if args.list_templates:
        templates = list_prompt_templates()
        if args.format == "json":
            print(json.dumps({"templates": [template.to_dict() for template in templates]}, indent=2, ensure_ascii=False))
        else:
            _print_text_prompt_templates(templates)
        return 0
    results = evaluate_prompt_cases()
    if args.format == "json":
        print(json.dumps({"results": [result.to_dict() for result in results]}, indent=2, ensure_ascii=False))
    else:
        _print_text_prompt_eval_results(results)
    return 1 if any(result.status == "FAIL" for result in results) else 0


PROMPT_EVALUATION_COMMAND_HANDLERS = {
    "eval-prompts": _handle_eval_prompts_command,
}
