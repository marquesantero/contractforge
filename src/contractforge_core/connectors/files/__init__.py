"""Facade for the file and object-storage connector family."""

from contractforge_core.connectors.files.files import (
    FILE_SOURCE_TYPES,
    OBJECT_STORAGE_TYPES,
    file_reader_options,
    file_source_format,
    is_file_source,
    normalize_file_format,
    object_storage_provider,
)

__all__ = [
    "FILE_SOURCE_TYPES",
    "OBJECT_STORAGE_TYPES",
    "file_reader_options",
    "file_source_format",
    "is_file_source",
    "normalize_file_format",
    "object_storage_provider",
]
