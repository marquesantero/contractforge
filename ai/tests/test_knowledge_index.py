import json
from pathlib import Path

from contractforge_ai.context.knowledge import (
    build_knowledge_index,
    load_knowledge_index,
    query_knowledge_index,
    save_knowledge_index,
)


def test_build_knowledge_index_chunks_markdown_with_citations(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "connectors.md").write_text(
        """
# Connectors

Use the Azure Blob connector for ADLS paths and SAS token tests.

## Serverless

Serverless should prefer External Locations for object storage access.
""".strip(),
        encoding="utf-8",
    )

    index = build_knowledge_index([docs], root=tmp_path)
    results = query_knowledge_index(index, "azure blob external locations", limit=2)

    assert index.chunks
    assert results
    assert results[0].source_path == "docs/connectors.md"
    assert results[0].start_line >= 1
    assert "azure" in results[0].matched_terms
    assert "External Locations" in " ".join(result.excerpt for result in results)


def test_knowledge_index_redacts_secret_like_values(tmp_path: Path):
    context = tmp_path / "context.yaml"
    context.write_text(
        """
source:
  connector: snowflake
  auth:
    password: plain-secret-value
""".strip(),
        encoding="utf-8",
    )

    index = build_knowledge_index([context])

    assert "plain-secret-value" not in index.chunks[0].text
    assert "[REDACTED]" in index.chunks[0].text


def test_knowledge_index_round_trips_json(tmp_path: Path):
    doc = tmp_path / "contract.json"
    output = tmp_path / "index.json"
    doc.write_text(json.dumps({"mode": "scd1_hash_diff", "merge_keys": ["order_id"]}), encoding="utf-8")

    index = build_knowledge_index([doc])
    save_knowledge_index(index, output)
    loaded = load_knowledge_index(output)

    assert loaded.to_dict() == index.to_dict()
    assert query_knowledge_index(loaded, "hash diff merge keys")
