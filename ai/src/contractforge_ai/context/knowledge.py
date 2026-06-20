"""Local knowledge indexing and retrieval for ContractForge AI."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from contractforge_ai.context.redaction import redact_secrets

SUPPORTED_EXTENSIONS = {".md", ".mdx", ".yaml", ".yml", ".json", ".py", ".sql", ".txt"}
DEFAULT_MAX_CHARS = 1800
TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")
TOKEN_PART_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class KnowledgeChunk:
    """A retrievable source-referenced context chunk."""

    id: str
    source_path: str
    source_type: str
    heading: str | None
    start_line: int
    end_line: int
    text: str
    tokens: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class KnowledgeIndex:
    """A deterministic local knowledge index."""

    version: int
    root_paths: tuple[str, ...]
    chunks: tuple[KnowledgeChunk, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "root_paths": list(self.root_paths),
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KnowledgeIndex":
        chunks = tuple(
            KnowledgeChunk(
                id=str(item["id"]),
                source_path=str(item["source_path"]),
                source_type=str(item["source_type"]),
                heading=item.get("heading"),
                start_line=int(item["start_line"]),
                end_line=int(item["end_line"]),
                text=str(item["text"]),
                tokens=tuple(str(token) for token in item.get("tokens", [])),
            )
            for item in payload.get("chunks", [])
        )
        return cls(
            version=int(payload.get("version", 1)),
            root_paths=tuple(str(path) for path in payload.get("root_paths", [])),
            chunks=chunks,
        )


@dataclass(frozen=True)
class KnowledgeSearchResult:
    """A ranked retrieval result with citation details."""

    chunk_id: str
    score: float
    source_path: str
    source_type: str
    heading: str | None
    start_line: int
    end_line: int
    excerpt: str
    matched_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_knowledge_index(
    paths: list[str | Path],
    *,
    root: str | Path | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> KnowledgeIndex:
    """Build a deterministic lexical index from local documentation/context paths."""

    root_path = Path(root).resolve() if root is not None else None
    source_files = _discover_files(paths)
    chunks: list[KnowledgeChunk] = []
    for source_file in source_files:
        try:
            raw = source_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = source_file.read_text(encoding="utf-8", errors="ignore")
        redacted = _redact_text(raw)
        source_path = _render_source_path(source_file, root_path)
        chunks.extend(_chunk_document(source_path, source_file.suffix.lower(), redacted, max_chars=max_chars))
    return KnowledgeIndex(
        version=1,
        root_paths=tuple(str(Path(path)) for path in paths),
        chunks=tuple(chunks),
    )


def query_knowledge_index(index: KnowledgeIndex, query: str, *, limit: int = 5) -> list[KnowledgeSearchResult]:
    """Return ranked lexical matches from a knowledge index."""

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    query_counts = Counter(query_tokens)
    doc_freq = _document_frequency(index.chunks)
    total_docs = max(len(index.chunks), 1)
    results: list[KnowledgeSearchResult] = []
    for chunk in index.chunks:
        chunk_counts = Counter(chunk.tokens)
        score = 0.0
        matched: list[str] = []
        for token, query_count in query_counts.items():
            term_count = chunk_counts.get(token, 0)
            if term_count == 0:
                continue
            matched.append(token)
            idf = math.log((1 + total_docs) / (1 + doc_freq.get(token, 0))) + 1
            score += query_count * term_count * idf
        if score <= 0:
            continue
        normalized = score / max(len(chunk.tokens), 1) ** 0.5
        results.append(
            KnowledgeSearchResult(
                chunk_id=chunk.id,
                score=round(normalized, 6),
                source_path=chunk.source_path,
                source_type=chunk.source_type,
                heading=chunk.heading,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                excerpt=_excerpt(chunk.text),
                matched_terms=tuple(sorted(set(matched))),
            )
        )
    return sorted(results, key=lambda item: (-item.score, item.source_path, item.start_line))[:limit]


def save_knowledge_index(index: KnowledgeIndex, path: str | Path) -> None:
    """Write a knowledge index as JSON."""

    Path(path).write_text(json.dumps(index.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def load_knowledge_index(path: str | Path) -> KnowledgeIndex:
    """Load a knowledge index JSON file."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Knowledge index must be a JSON object.")
    return KnowledgeIndex.from_dict(payload)


def _discover_files(paths: list[str | Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        candidate = Path(path)
        if candidate.is_dir():
            for item in sorted(candidate.rglob("*")):
                if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(item)
        elif candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(candidate)
    return sorted(dict.fromkeys(files))


def _chunk_document(source_path: str, suffix: str, text: str, *, max_chars: int) -> list[KnowledgeChunk]:
    source_type = _source_type(suffix)
    if source_type == "markdown" and len(text) > max_chars:
        sections = _markdown_sections(text)
    else:
        sections = [(None, 1, len(text.splitlines()) or 1, text.strip())]
    chunks: list[KnowledgeChunk] = []
    for heading, start_line, end_line, section_text in sections:
        if not section_text:
            continue
        for part_index, part in enumerate(_split_text(section_text, max_chars=max_chars)):
            chunk_id = f"{source_path}:{start_line}:{part_index}"
            chunks.append(
                KnowledgeChunk(
                    id=chunk_id,
                    source_path=source_path,
                    source_type=source_type,
                    heading=heading,
                    start_line=start_line,
                    end_line=end_line,
                    text=part,
                    tokens=tuple(_tokenize(" ".join(value for value in [heading or "", part] if value))),
                )
            )
    return chunks


def _markdown_sections(text: str) -> list[tuple[str | None, int, int, str]]:
    lines = text.splitlines()
    sections: list[tuple[str | None, int, int, str]] = []
    current_heading: str | None = None
    current_start = 1
    buffer: list[str] = []
    for index, line in enumerate(lines, start=1):
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading and buffer:
            sections.append((current_heading, current_start, index - 1, "\n".join(buffer).strip()))
            buffer = []
            current_start = index
        if heading:
            current_heading = heading.group(2).strip()
        buffer.append(line)
    if buffer:
        sections.append((current_heading, current_start, len(lines) or 1, "\n".join(buffer).strip()))
    return sections


def _split_text(text: str, *, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph.strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = paragraph.strip()
        while len(current) > max_chars:
            chunks.append(current[:max_chars].strip())
            current = current[max_chars:].strip()
    if current:
        chunks.append(current)
    return chunks


def _document_frequency(chunks: tuple[KnowledgeChunk, ...]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for chunk in chunks:
        counts.update(set(chunk.tokens))
    return dict(counts)


def _tokenize(value: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(value):
        normalized = raw.lower()
        if len(normalized) > 1:
            tokens.append(normalized)
        for part in TOKEN_PART_RE.findall(raw):
            normalized_part = part.lower()
            if len(normalized_part) > 1 and normalized_part != normalized:
                tokens.append(normalized_part)
    return tokens


def _source_type(suffix: str) -> str:
    if suffix in {".md", ".mdx"}:
        return "markdown"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".json":
        return "json"
    if suffix == ".py":
        return "python"
    if suffix == ".sql":
        return "sql"
    return "text"


def _render_source_path(path: Path, root: Path | None) -> str:
    resolved = path.resolve()
    if root is not None:
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def _redact_text(text: str) -> str:
    redacted = redact_secrets({"content": text})
    return str(redacted["content"])


def _excerpt(text: str, *, max_chars: int = 420) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."
