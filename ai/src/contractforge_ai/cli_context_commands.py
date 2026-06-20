"""Context command handlers for the ContractForge AI CLI."""

from __future__ import annotations

import json

from contractforge_ai.cli_output import _print_text_knowledge_results, _print_text_task_routing
from contractforge_ai.context.knowledge import (
    build_knowledge_index,
    load_knowledge_index,
    query_knowledge_index,
    save_knowledge_index,
)
from contractforge_ai.intelligence import TaskRouteRequest, route_task
from contractforge_ai.reports import render_guided_project_review


def _handle_knowledge_build_command(args) -> int:
    index = build_knowledge_index(args.paths, root=args.root, max_chars=args.max_chars)
    save_knowledge_index(index, args.output)
    payload = {
        "status": "BUILT",
        "output": args.output,
        "root_paths": list(index.root_paths),
        "chunks": len(index.chunks),
    }
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Knowledge index built: {args.output}")
        print(f"Chunks: {len(index.chunks)}")
    return 0


def _handle_knowledge_query_command(args) -> int:
    index = load_knowledge_index(args.index)
    results = query_knowledge_index(index, args.query, limit=args.limit)
    payload = {"query": args.query, "results": [result.to_dict() for result in results]}
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_text_knowledge_results(results)
    return 0


KNOWLEDGE_COMMAND_HANDLERS = {
    "build": _handle_knowledge_build_command,
    "query": _handle_knowledge_query_command,
}


def _handle_knowledge_index_command(args) -> int:
    return KNOWLEDGE_COMMAND_HANDLERS[args.knowledge_command](args)


def _handle_route_task_command(args) -> int:
    index = load_knowledge_index(args.knowledge_index) if args.knowledge_index else None
    result = route_task(
        TaskRouteRequest(
            intent=args.intent,
            task_hint=args.task_hint,
            knowledge_index=index,
            context_limit=args.context_limit,
            prefer_http_only=args.prefer_http_only,
            prefer_databricks_boundary=args.prefer_databricks_boundary,
            require_strict_schema=True if args.require_strict_schema else None,
        )
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(render_guided_project_review(result).markdown)
    elif args.format == "html":
        print(render_guided_project_review(result).html)
    else:
        _print_text_task_routing(result)
    return 0


CONTEXT_COMMAND_HANDLERS = {
    "knowledge-index": _handle_knowledge_index_command,
    "route-task": _handle_route_task_command,
}
