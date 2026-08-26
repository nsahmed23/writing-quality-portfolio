"""Strict UTF-8 JSON and JSONL readers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class StrictJsonError(ValueError):
    """Raised when input is not one unambiguous standards-compliant JSON value."""


MAX_JSON_NESTING = 128


def _enforce_nesting_depth(document: str, *, maximum: int = MAX_JSON_NESTING) -> None:
    """Bound structural depth without treating brackets inside strings as syntax."""

    depth = 0
    in_string = False
    escaped = False
    for character in document:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > maximum:
                raise StrictJsonError(f"JSON nesting exceeds the maximum depth of {maximum}")
        elif character in "]}":
            depth = max(0, depth - 1)


def _reject_constant(value: str) -> None:
    raise StrictJsonError(f"non-finite JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _validate_value(value: Any) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise StrictJsonError("JSON strings must contain Unicode scalar values")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise StrictJsonError("non-finite JSON number is forbidden")
    elif isinstance(value, list):
        for item in value:
            _validate_value(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_value(key)
            _validate_value(item)


def loads(document: str | bytes) -> Any:
    """Parse exactly one strict JSON value and reject ambiguous extensions."""

    if isinstance(document, bytes):
        try:
            document = document.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise StrictJsonError("input is not valid UTF-8") from exc
    if not isinstance(document, str):
        raise StrictJsonError("JSON input must be text or bytes")
    if not document.strip():
        raise StrictJsonError("JSON input is empty")
    _enforce_nesting_depth(document)
    try:
        value = json.loads(
            document,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        _validate_value(value)
        return value
    except StrictJsonError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError, RecursionError) as exc:
        raise StrictJsonError(str(exc)) from exc


def loads_jsonl(document: str | bytes, *, source_name: str = "<jsonl>") -> list[dict[str, Any]]:
    """Parse JSONL using only LF or CRLF record separators."""

    if isinstance(document, bytes):
        try:
            text = document.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise StrictJsonError(f"{source_name}: input is not valid UTF-8") from exc
    elif isinstance(document, str):
        text = document
    else:
        raise StrictJsonError("JSONL input must be text or bytes")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        raise StrictJsonError(f"{source_name}: JSONL input is empty")
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line[:-1] if raw_line.endswith("\r") else raw_line
        if "\r" in line:
            raise StrictJsonError(f"{source_name}:{line_number}: CR is only allowed in a CRLF separator")
        if not line.strip():
            raise StrictJsonError(f"{source_name}:{line_number}: blank JSONL line")
        try:
            value = loads(line)
        except StrictJsonError as exc:
            raise StrictJsonError(f"{source_name}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise StrictJsonError(f"{source_name}:{line_number}: each JSONL record must be an object")
        records.append(value)
    return records


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load an object-per-line UTF-8 JSONL file without blank records."""

    source = Path(path)
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise StrictJsonError(f"{source}: unable to read JSONL input") from exc
    return loads_jsonl(payload, source_name=str(source))
