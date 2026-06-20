from contractforge_core.capabilities import CapabilityEvidence, NativeCapability, capability


def test_core_native_capability_evidence_serializes_without_none_value() -> None:
    evidence = CapabilityEvidence(source="runtime", message="detected")

    assert evidence.as_dict() == {"source": "runtime", "message": "detected"}


def test_core_native_capability_serializes_support_state() -> None:
    capability = NativeCapability(
        name="merge",
        status="supported",
        reason="runtime supports merge",
        requires=("table_api",),
        evidence=(CapabilityEvidence("runtime", "ok", "true"),),
    )

    assert capability.supported
    assert capability.as_dict()["requires"] == ["table_api"]
    assert capability.as_dict()["evidence"] == [{"source": "runtime", "message": "ok", "value": "true"}]


def test_core_capability_factory() -> None:
    item = capability("merge", "unsupported", "missing merge", requires=("merge",))

    assert item.name == "merge"
    assert not item.supported
    assert item.requires == ("merge",)
