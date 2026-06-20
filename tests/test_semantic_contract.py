from dataclasses import FrozenInstanceError

import pytest

from contractforge_core.semantic import SemanticContract, SourceIntent, TargetIntent, WriteIntent


def test_semantic_contract_is_immutable() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="bronze"),
        write=WriteIntent(mode="scd0_append"),
    )

    with pytest.raises(FrozenInstanceError):
        contract.target = TargetIntent(name="orders_new", layer="bronze")
