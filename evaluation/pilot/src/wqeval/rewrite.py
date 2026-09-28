"""Deterministic edit reconstruction and protected-region checks."""

from __future__ import annotations

import re
from typing import Any


_LAYOUT_CONTENT = re.compile(r"\w+", flags=re.UNICODE)


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def apply_edits(source: str, edits: list[dict[str, Any]]) -> str:
    """Apply non-overlapping edits against source Unicode code-point offsets."""

    if not isinstance(source, str) or not isinstance(edits, list):
        raise ValueError("source must be text and edits must be a list")
    normalized: list[tuple[int, int, str]] = []
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            raise ValueError(f"edit {index} must be an object")
        start = _integer(edit.get("start"), f"edit {index} start")
        end = _integer(edit.get("end"), f"edit {index} end")
        replacement = edit.get("replacement")
        if not isinstance(replacement, str):
            raise ValueError(f"edit {index} replacement must be text")
        if start < 0 or end < start or end > len(source):
            raise ValueError(f"edit {index} is outside the source")
        normalized.append((start, end, replacement))
    by_start = sorted(normalized, key=lambda item: (item[0], item[1]))
    for left, right in zip(by_start, by_start[1:]):
        if right[0] < left[1] or (left[0] == left[1] == right[0] == right[1]):
            raise ValueError("edits overlap or have an ambiguous shared insertion point")
    result = source
    for start, end, replacement in reversed(by_start):
        result = result[:start] + replacement + result[end:]
    return result


def _edit_changes_source(source: str, edit: dict[str, Any]) -> bool:
    return edit["replacement"] != source[edit["start"] : edit["end"]]


def _edit_touches_region(edit: dict[str, Any], region_start: int, region_end: int) -> bool:
    edit_start = edit["start"]
    edit_end = edit["end"]
    if edit_start == edit_end:
        return region_start <= edit_start <= region_end
    return edit_start < region_end and edit_end > region_start


def _layout_signature(text: str) -> str:
    """Preserve structural punctuation and spacing while abstracting word content."""

    return _LAYOUT_CONTENT.sub("<content>", text)


def _layout_region_changed(
    source: str,
    edits: list[dict[str, Any]],
    region_start: int,
    region_end: int,
) -> bool:
    local_edits: list[dict[str, Any]] = []
    for edit in edits:
        if not _edit_changes_source(source, edit):
            continue
        edit_start = edit["start"]
        edit_end = edit["end"]
        if not _edit_touches_region(edit, region_start, region_end):
            continue
        if edit_start == edit_end and edit_start in {region_start, region_end}:
            return True
        if edit_start < region_start or edit_end > region_end:
            return True
        local_edits.append(
            {
                "start": edit_start - region_start,
                "end": edit_end - region_start,
                "replacement": edit["replacement"],
            }
        )

    if not local_edits:
        return False
    original = source[region_start:region_end]
    revised = apply_edits(original, local_edits)
    return _layout_signature(original) != _layout_signature(revised)


def protected_region_violations(source_case: dict[str, Any], rewrite: dict[str, Any]) -> list[dict[str, Any]]:
    """Return protected regions whose declared policy is violated."""

    source = source_case.get("text")
    edits = rewrite.get("edits", [])
    reconstructed = apply_edits(source, edits)
    if rewrite.get("revised_text") != reconstructed:
        raise ValueError("rewrite revised_text does not match the declared edits")

    violations: list[dict[str, Any]] = []
    for region in source_case.get("protected_regions", []):
        region_start = region["start"]
        region_end = region["end"]
        policy = region.get("policy", "exact")
        if policy == "exact":
            violated = any(
                _edit_changes_source(source, edit)
                and _edit_touches_region(edit, region_start, region_end)
                for edit in edits
            )
        elif policy == "layout_only":
            violated = _layout_region_changed(source, edits, region_start, region_end)
        else:
            raise ValueError(f"unsupported protected region policy: {policy!r}")
        if violated:
            violations.append(dict(region))
    return violations
