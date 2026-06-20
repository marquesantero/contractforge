"""Gap planning for intent-first project synthesis."""

from __future__ import annotations

from contractforge_ai.agentic.models import GapAction, GapPlan, IntentSpec, Layer, ProjectState
from contractforge_ai.models import RequiredDecision


def plan_project_gaps(intent: IntentSpec, state: ProjectState) -> GapPlan:
    """Compare desired intent and current project state."""

    actions: list[GapAction] = []
    warnings = list(state.warnings)
    decisions = list(intent.decisions_required)
    previous_table: str | None = None

    for layer in intent.requested_layers:
        existing = state.contract_for_layer(layer)
        if existing is not None:
            actions.append(
                GapAction(
                    action="preserve",
                    layer=layer,
                    reason="An existing contract for this layer was found and will not be regenerated.",
                    existing_contract=existing.path,
                    source_table=existing.full_target_name,
                )
            )
            previous_table = existing.full_target_name
            continue

        actions.append(
            GapAction(
                action="generate",
                layer=layer,
                reason="No existing contract for this requested layer was found.",
                source_table=previous_table,
            )
        )
        previous_table = _planned_target(intent, layer)

    if not intent.source and not state.layers:
        decisions.append(
            RequiredDecision(
                question="Confirm the source table or path for the first generated layer.",
                reason="No existing project context or source reference was available.",
                path="source",
            )
        )
    if not actions:
        warnings.append("No generation actions were required for the requested layers.")
    return GapPlan(actions=actions, decisions_required=decisions, warnings=warnings)


def _planned_target(intent: IntentSpec, layer: Layer) -> str:
    return f"{intent.catalog}.{layer}.{_layer_table(layer, intent.base_name)}"


def _layer_table(layer: Layer, base_name: str) -> str:
    prefix = {"bronze": "b", "silver": "s", "gold": "g"}[layer]
    clean = base_name.removeprefix("b_").removeprefix("s_").removeprefix("g_")
    return clean if clean.startswith(f"{prefix}_") else f"{prefix}_{clean}"
