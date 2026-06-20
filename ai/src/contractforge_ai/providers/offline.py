"""Offline provider used for tests and deterministic local workflows."""

from __future__ import annotations

from contractforge_ai.providers.base import GenerationOptions


class OfflineProvider:
    """Provider that returns a stable response without network calls."""

    name = "offline"

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        options: GenerationOptions | None = None,
    ) -> str:
        del prompt, system, options
        return "No model provider configured. Deterministic review findings were returned."
