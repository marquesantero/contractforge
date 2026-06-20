from contractforge_core.contracts import classify_source_type


def test_incremental_files_is_portable_builtin() -> None:
    classification = classify_source_type("incremental_files")

    assert classification.portability == "PORTABLE_BUILTIN"
    assert classification.adapter is None


def test_xml_file_source_is_portable_builtin() -> None:
    classification = classify_source_type("xml")

    assert classification.portability == "PORTABLE_BUILTIN"


def test_non_portable_source_type_does_not_name_an_adapter() -> None:
    classification = classify_source_type("autoloader")

    assert classification.portability == "UNSUPPORTED"
    assert classification.adapter is None


def test_bounded_streams_are_not_continuous_streaming() -> None:
    classification = classify_source_type("kafka_bounded")

    assert classification.portability == "BOUNDED_STREAM"
    assert "Bounded" in classification.reason


def test_available_now_streams_are_checkpointed_stream_catchup() -> None:
    classification = classify_source_type("kafka_available_now")

    assert classification.portability == "AVAILABLE_NOW_STREAM"
    assert "Checkpointed" in classification.reason
    assert classification.adapter is None


def test_native_passthrough_is_first_class() -> None:
    classification = classify_source_type("native_passthrough")

    assert classification.portability == "NATIVE_PASSTHROUGH"


def test_odata_is_not_a_portable_builtin() -> None:
    classification = classify_source_type("odata")

    assert classification.portability == "UNSUPPORTED"
