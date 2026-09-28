"""Strict local ingestion of proposed findings, without a quality judgment."""

import hashlib
import json
import math

from .anchors import AnchorError, resolve_anchor


_REQUIRED = frozenset({"native_label", "quote", "explanation"})
_OPTIONAL = frozenset({"occurrence", "left_context", "right_context"})


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("nonfinite JSON number")
    return parsed


def _reject_constant(value):
    raise ValueError("nonfinite JSON constant")


def _validate_json_value(value, depth=0):
    """Reject escaped lone surrogates and unreasonable structural depth."""
    if depth > 128:
        raise ValueError("JSON nesting exceeds 128 levels")
    if isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, list):
        for element in value:
            _validate_json_value(element, depth + 1)
    elif isinstance(value, dict):
        for key, element in value.items():
            key.encode("utf-8")
            _validate_json_value(element, depth + 1)


def _valid_finding(item, text):
    if not isinstance(item, dict) or not _REQUIRED <= item.keys():
        raise AnchorError("INVALID_FINDING")
    if item.keys() - (_REQUIRED | _OPTIONAL):
        raise AnchorError("UNKNOWN_FIELD")
    if any(not isinstance(item[key], str) or not item[key].strip() for key in _REQUIRED):
        raise AnchorError("INVALID_FINDING")

    options = {key: item[key] for key in _OPTIONAL if key in item}
    # Explicit JSON null is not the same as an omitted optional field.
    if "occurrence" in options and (type(options["occurrence"]) is not int or options["occurrence"] < 1):
        raise AnchorError("INVALID_OCCURRENCE")
    if any(key in options and not isinstance(options[key], str)
           for key in ("left_context", "right_context")):
        raise AnchorError("INVALID_CONTEXT")
    start, end = resolve_anchor(text, item["quote"], **options)
    return start, end


def ingest_response(case_id: str, text: str, response_bytes: bytes) -> dict:
    """Validate JSON and anchor independent findings to the supplied case text.

    Malformed JSON/envelopes set ``response_error`` and contain no findings;
    malformed individual findings use ``rejected_findings`` instead. The raw
    response hash is calculated before parsing and preserves exact input bytes.
    """
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a nonblank string")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if type(response_bytes) is not bytes:
        raise ValueError("response_bytes must be bytes")
    try:
        text_bytes = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("text must encode as UTF-8") from exc

    output = {
        "status": "development_only",
        "case_id": case_id,
        "text_sha256": hashlib.sha256(text_bytes).hexdigest(),
        "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
        "accepted_findings": [],
        "rejected_findings": [],
        "response_error": None,
    }
    try:
        parsed = json.loads(response_bytes.decode("utf-8"),
                            object_pairs_hook=_unique_pairs,
                            parse_constant=_reject_constant,
                            parse_float=_finite_float)
        _validate_json_value(parsed)
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError):
        output["response_error"] = "INVALID_JSON"
        return output
    if not isinstance(parsed, dict) or parsed.keys() != {"findings"} or not isinstance(parsed["findings"], list):
        output["response_error"] = "INVALID_ENVELOPE"
        return output

    seen = set()
    for index, item in enumerate(parsed["findings"]):
        try:
            start, end = _valid_finding(item, text)
        except AnchorError as exc:
            output["rejected_findings"].append({"index": index, "code": exc.reason})
            continue
        duplicate_key = (start, end, item["native_label"], item["quote"], item["explanation"])
        if duplicate_key in seen:
            output["rejected_findings"].append({"index": index, "code": "DUPLICATE_FINDING"})
            continue
        seen.add(duplicate_key)
        output["accepted_findings"].append({"index": index, **item, "start": start, "end": end})
    return output
