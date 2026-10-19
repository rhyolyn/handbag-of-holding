"""Opening-frontmatter parsing and normalized Markdown identity rendering."""

from __future__ import annotations

from collections.abc import Mapping

import yaml


def parse_opening_frontmatter(text: str) -> tuple[Mapping[object, object], str] | None:
    """Parse YAML only when the first Markdown line opens a frontmatter block."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    closing_index = _closing_fence_index(lines)
    if closing_index is None:
        return None
    data = yaml.safe_load("".join(lines[1:closing_index]))
    if not isinstance(data, dict):
        return None
    return data, "".join(lines[closing_index + 1 :])


def render_normalized_markdown(frontmatter: Mapping[object, object], body: str) -> str:
    """Render frontmatter with deterministic key order and normalized line endings."""
    yaml_text = yaml.safe_dump(dict(frontmatter), allow_unicode=True, sort_keys=True)
    return f"---\n{yaml_text}---\n{_normalize_line_endings(body)}"


def _closing_fence_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index
    return None


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
