"""Provider-backed translation for rendered reports."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from contractforge_ai.providers import GenerationOptions, ModelProvider, ProviderExecutionError
from contractforge_ai.reports import RenderedReport


@dataclass(frozen=True)
class TranslationSegment:
    """A report text segment that can be translated safely."""

    segment_id: str
    text: str


def should_translate_report(language: str | None, provider: ModelProvider | None) -> bool:
    """Return whether a report should be translated with a real model provider."""

    if _is_english(language) or provider is None:
        return False
    return getattr(provider, "name", None) != "offline"


def translate_report(
    report: RenderedReport,
    *,
    language: str | None,
    provider: ModelProvider | None,
) -> RenderedReport:
    """Translate report prose after the canonical English report is rendered.

    Labels, status values, paths, code blocks, identifiers and technical tokens remain
    in English. Translation is intentionally provider-backed so arbitrary languages
    do not require deterministic catalogs inside the package.
    """

    if not should_translate_report(language, provider):
        return report
    assert provider is not None
    target_language = str(language).strip()
    try:
        return RenderedReport(
            markdown=_translate_markdown(
                report.markdown,
                language=target_language,
                provider=provider,
            ),
            html=_translate_html(
                report.html,
                language=target_language,
                provider=provider,
            ),
        )
    except ProviderExecutionError:
        raise
    except Exception as exc:  # pragma: no cover - defensive for provider adapters.
        raise ProviderExecutionError(f"report translation failed: {exc}") from exc


def _translate_markdown(
    markdown: str,
    *,
    language: str,
    provider: ModelProvider,
) -> str:
    lines = markdown.splitlines(keepends=True)
    segments: list[TranslationSegment] = []
    replacements: dict[int, str] = {}
    in_fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not _is_translatable_text(stripped) or _is_markdown_label_line(stripped):
            continue
        segment_id = f"m{len(segments)}"
        segments.append(TranslationSegment(segment_id=segment_id, text=stripped))
        replacements[index] = segment_id
    translated = _translate_segments(segments, language=language, provider=provider, content_format="Markdown")
    for index, segment_id in replacements.items():
        original = lines[index]
        prefix = original[: len(original) - len(original.lstrip())]
        suffix = "\n" if original.endswith("\n") else ""
        lines[index] = f"{prefix}{translated[segment_id]}{suffix}"
    return "".join(lines)


def _translate_html(
    document: str,
    *,
    language: str,
    provider: ModelProvider,
) -> str:
    parser = _HtmlSegmentExtractor()
    parser.feed(document)
    parser.close()
    translated = _translate_segments(parser.segments, language=language, provider=provider, content_format="HTML")
    return parser.render(translated)


def _translate_segments(
    segments: list[TranslationSegment],
    *,
    language: str,
    provider: ModelProvider,
    content_format: str,
) -> dict[str, str]:
    if not segments:
        return {}
    system = (
        "You translate ContractForge AI reports after they have been generated in English. "
        "Translate only the provided narrative text segments to the requested language. "
        "Do not translate status values, identifiers, file paths, command names, metrics, code-like tokens or product names. "
        "Return JSON only, using the same segment ids."
    )
    payload = {"segments": [{"id": item.segment_id, "text": item.text} for item in segments]}
    prompt = (
        f"Target language: {language}\n"
        f"Document format: {content_format}\n\n"
        "Return this exact JSON shape: {\"translations\":[{\"id\":\"...\",\"text\":\"...\"}]}.\n"
        "Translate the text values in this JSON payload:\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    raw = provider.complete(
        prompt,
        system=system,
        options=GenerationOptions(temperature=0.0),
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderExecutionError("report translation provider returned invalid JSON") from exc
    translations = data.get("translations") if isinstance(data, dict) else None
    if not isinstance(translations, list):
        raise ProviderExecutionError("report translation provider returned JSON without translations list")
    translated = {item.segment_id: item.text for item in segments}
    expected = set(translated)
    for item in translations:
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("id") or "")
        if segment_id in expected and isinstance(item.get("text"), str):
            translated[segment_id] = item["text"]
    return translated


def _is_english(language: str | None) -> bool:
    normalized = (language or "en").strip().lower().replace("_", "-")
    return normalized in {"", "en"} or normalized.startswith("en-")


def _is_translatable_text(value: str) -> bool:
    text = value.strip()
    if len(text) < 12:
        return False
    if text.lower() in _TECHNICAL_VALUES:
        return False
    if not re.search(r"\s", text) and re.search(r"[_./:\\-]", text):
        return False
    if not re.search(r"[A-Za-z]", text):
        return False
    if text.startswith(("{", "}", "[", "]", "<", "|")):
        return False
    if re.fullmatch(r"[A-Z0-9_ .:/\\|=-]+", text):
        return False
    without_inline_code = re.sub(r"`[^`]+`", "", text).strip()
    if without_inline_code and not re.search(r"[A-Za-z]{3,}", without_inline_code):
        return False
    if not without_inline_code:
        return False
    return True


_TECHNICAL_VALUES = {
    "accepted",
    "approve",
    "block",
    "critical",
    "fail",
    "failed",
    "high",
    "ignored",
    "invalid",
    "low",
    "medium",
    "needs_decisions",
    "not_run",
    "pass",
    "ready",
    "rejected",
    "requires_review",
    "review_required",
    "success",
    "unsafe",
    "warn",
    "warning",
}


def _is_markdown_label_line(value: str) -> bool:
    text = value.strip()
    if text.startswith("#"):
        return True
    if text.startswith("|"):
        return True
    if re.match(r"^- [A-Z][A-Za-z /_-]{1,40}:", text):
        return True
    return False


class _HtmlSegmentExtractor(HTMLParser):
    _skip_tags = {"style", "script", "pre", "code", "kbd", "samp", "svg"}
    _translatable_tags = {"p", "li", "td", "div"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.segments: list[TranslationSegment] = []
        self._tag_stack: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        self.parts.append(self.get_starttag_text() or _start_tag(tag, attrs))
        self._tag_stack.append(tag.lower())
        if tag.lower() in self._skip_tags:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        normalized = tag.lower()
        if normalized in self._skip_tags and self._skip_depth:
            self._skip_depth -= 1
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.parts.append(self.get_starttag_text() or _start_tag(tag, attrs, startend=True))

    def handle_data(self, data: str) -> None:
        current = self._tag_stack[-1] if self._tag_stack else ""
        if self._skip_depth or current not in self._translatable_tags or not _is_translatable_text(data):
            self.parts.append(data)
            return
        segment_id = f"h{len(self.segments)}"
        self.segments.append(TranslationSegment(segment_id=segment_id, text=data.strip()))
        self.parts.append(f"%%CF_TRANSLATION_{segment_id}%%")

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def render(self, translations: dict[str, str]) -> str:
        document = "".join(self.parts)
        for segment_id, text in translations.items():
            document = document.replace(f"%%CF_TRANSLATION_{segment_id}%%", html.escape(text, quote=False))
        return document


def _start_tag(tag: str, attrs, *, startend: bool = False) -> str:
    rendered_attrs = "".join(f' {name}="{html.escape(str(value), quote=True)}"' for name, value in attrs)
    suffix = " /" if startend else ""
    return f"<{tag}{rendered_attrs}{suffix}>"
