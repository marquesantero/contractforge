from contractforge_core.execution import WriteStrategy


def test_core_write_strategy_executable_and_serializes() -> None:
    strategy = WriteStrategy(
        kind="contractforge_algorithm",
        engine="generic_merge",
        reason="fallback algorithm",
        blockers=("capability",),
        warnings=("review",),
    )

    assert strategy.executable
    assert strategy.as_dict() == {
        "kind": "contractforge_algorithm",
        "engine": "generic_merge",
        "reason": "fallback algorithm",
        "blockers": ["capability"],
        "warnings": ["review"],
    }


def test_core_write_strategy_unsupported_is_not_executable() -> None:
    assert not WriteStrategy(kind="unsupported", engine="none", reason="missing merge").executable
