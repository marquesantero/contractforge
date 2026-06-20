"""Optional adapter-aware validation for ContractForge AI."""

from contractforge_ai.adapter_validation.models import AdapterPlanningOutcome, AdapterValidationStatus
from contractforge_ai.adapter_validation.registry import AdapterPlannerSpec, adapter_planner_spec, known_adapter_names
from contractforge_ai.adapter_validation.validation import validate_contract_with_adapter

__all__ = [
    "AdapterPlannerSpec",
    "AdapterPlanningOutcome",
    "AdapterValidationStatus",
    "adapter_planner_spec",
    "known_adapter_names",
    "validate_contract_with_adapter",
]
