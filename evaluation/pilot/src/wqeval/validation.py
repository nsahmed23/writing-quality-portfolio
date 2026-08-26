"""Strict validation for cases, findings, rewrites, and review assignments."""

from __future__ import annotations

import hashlib
import copy
import re
from typing import Any

from .rewrite import apply_edits


class ValidationError(ValueError):
    """Raised when an evaluation record violates its contract."""


GENRES = {"technical", "executive", "personal", "marketing", "reference", "second_language"}
SEVERITIES = {"none", "low", "medium", "high", "critical"}
DECISIONS = {"CHANGE", "KEEP"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _require_object(record: Any, name: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValidationError(f"{name} must be an object")
    return record


def _exact_keys(record: dict[str, Any], required: set[str], optional: set[str], name: str) -> None:
    missing = required - record.keys()
    unknown = record.keys() - required - optional
    if missing:
        raise ValidationError(f"{name} missing fields: {sorted(missing)}")
    if unknown:
        raise ValidationError(f"{name} has unknown fields: {sorted(unknown)}")


def _text(value: Any, name: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValidationError(f"{name} must be non-empty text")
    return value


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} must be an integer")
    return value


def _record_id(value: Any, name: str) -> str:
    text = _text(value, name)
    if not ID_PATTERN.fullmatch(text):
        raise ValidationError(f"{name} is unsafe or too long")
    return text


def _validate_region(region: Any, source: str, index: int) -> None:
    item = _require_object(region, f"protected region {index}")
    legacy = {"kind", "start", "end", "text"}
    production = {"region_id", "type", "start", "end", "span", "policy"}
    if set(item) == legacy:
        kind = _text(item["kind"], "protected region kind")
        span = item["text"]
    elif set(item) == production:
        _record_id(item["region_id"], "protected region id")
        kind = _text(item["type"], "protected region type")
        span = item["span"]
        if item["policy"] not in {"exact", "layout_only"}:
            raise ValidationError("protected region policy must be exact or layout_only")
    else:
        raise ValidationError("protected region fields do not match a supported schema")
    start = _integer(item["start"], "protected region start")
    end = _integer(item["end"], "protected region end")
    if not kind or start < 0 or end <= start or end > len(source):
        raise ValidationError("protected region offsets are invalid")
    if not isinstance(span, str) or source[start:end] != span:
        raise ValidationError("protected region text does not match its offsets")


def validate_case(record: Any) -> None:
    item = _require_object(record, "case")
    required = {"schema_version", "case_id", "text", "genre", "author_type", "protected_regions"}
    optional = {
        "split",
        "offset_unit",
        "artifact_type",
        "task_context",
        "author_profile",
    }
    _exact_keys(item, required, optional, "case")
    if item["schema_version"] != "1.0":
        raise ValidationError("unsupported case schema_version")
    _record_id(item["case_id"], "case_id")
    source = _text(item["text"], "case text", empty=True)
    if item["genre"] not in GENRES:
        raise ValidationError("unsupported genre")
    _text(item["author_type"], "author_type")
    if "author_profile" in item and item["author_profile"] not in {
        "domain_expert",
        "institutional_executive",
        "personal_author",
        "brand_marketer",
        "reference_editor",
        "second_language_professional",
    }:
        raise ValidationError("unsupported author_profile")
    if not isinstance(item["protected_regions"], list):
        raise ValidationError("protected_regions must be a list")
    for index, region in enumerate(item["protected_regions"]):
        _validate_region(region, source, index)
    if "offset_unit" in item and item["offset_unit"] != "unicode_codepoint":
        raise ValidationError("offset_unit must be unicode_codepoint")


def validate_finding(record: Any, source_case: dict[str, Any]) -> None:
    item = _require_object(record, "finding")
    legacy_required = {
        "schema_version",
        "case_id",
        "finding_id",
        "span",
        "problem_code",
        "problem",
        "context",
        "severity",
        "suggested_operation",
        "decision",
    }
    production_required = {
        "schema_version",
        "case_id",
        "finding_id",
        "start",
        "end",
        "span",
        "problem_name",
        "system_issue_code",
        "normalized_issue_code",
        "context_explanation",
        "severity",
        "suggested_operation",
        "decision",
        "field_origin",
    }
    keys = set(item)
    if keys == legacy_required:
        span_object = _require_object(item["span"], "finding span")
        _exact_keys(span_object, {"start", "end", "text"}, set(), "finding span")
        start = _integer(span_object["start"], "span start")
        end = _integer(span_object["end"], "span end")
        span_text = span_object["text"]
        _text(item["problem_code"], "problem_code")
        _text(item["problem"], "problem")
        _text(item["context"], "context")
        _text(item["suggested_operation"], "suggested_operation")
    elif keys in (production_required, production_required | {"system_id", "run_number"}):
        start = _integer(item["start"], "span start")
        end = _integer(item["end"], "span end")
        span_text = item["span"]
        _text(item["problem_name"], "problem_name")
        _text(item["system_issue_code"], "system_issue_code")
        _text(item["normalized_issue_code"], "normalized_issue_code")
        _text(item["context_explanation"], "context_explanation")
        if item["field_origin"] not in {"authored", "deterministic_adapter", "model_adapter"}:
            raise ValidationError("invalid field_origin")
        operation = _require_object(item["suggested_operation"], "suggested_operation")
        _exact_keys(operation, {"operation_code", "instruction", "replacement"}, set(), "suggested_operation")
        _text(operation["operation_code"], "operation_code")
        _text(operation["instruction"], "operation instruction")
        if operation["replacement"] is not None and not isinstance(operation["replacement"], str):
            raise ValidationError("operation replacement must be text or null")
        if "system_id" in item:
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", _text(item["system_id"], "system_id")):
                raise ValidationError("system_id is unsafe")
            run_number = _integer(item["run_number"], "run_number")
            if run_number < 1:
                raise ValidationError("run_number must be positive")
    else:
        raise ValidationError("finding fields do not match a supported schema")
    if item["schema_version"] != "1.0":
        raise ValidationError("unsupported finding schema_version")
    _record_id(item["case_id"], "case_id")
    _record_id(item["finding_id"], "finding_id")
    if item["case_id"] != source_case.get("case_id"):
        raise ValidationError("finding case_id does not match source case")
    source = source_case.get("text")
    if not isinstance(source, str) or start < 0 or end <= start or end > len(source):
        raise ValidationError("finding offsets are invalid")
    if not isinstance(span_text, str) or source[start:end] != span_text:
        raise ValidationError("finding span does not match source offsets")
    if item["severity"] not in SEVERITIES:
        raise ValidationError("invalid severity")
    if item["decision"] not in DECISIONS:
        raise ValidationError("invalid decision")


def validate_rewrite(record: Any, source_case: dict[str, Any]) -> None:
    item = _require_object(record, "rewrite")
    required = {"schema_version", "case_id", "source_sha256", "revised_text", "edits"}
    _exact_keys(item, required, set(), "rewrite")
    if item["schema_version"] != "1.0":
        raise ValidationError("unsupported rewrite schema_version")
    if item["case_id"] != source_case.get("case_id"):
        raise ValidationError("rewrite case_id does not match source case")
    source = source_case.get("text")
    if not isinstance(source, str):
        raise ValidationError("source case has no text")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if item["source_sha256"] != digest:
        raise ValidationError("source_sha256 does not match source text")
    if not isinstance(item["revised_text"], str) or not isinstance(item["edits"], list):
        raise ValidationError("revised_text and edits have invalid types")
    for index, edit in enumerate(item["edits"]):
        edit_item = _require_object(edit, f"edit {index}")
        _exact_keys(edit_item, {"start", "end", "replacement", "finding_id"}, set(), f"edit {index}")
        _record_id(edit_item["finding_id"], "finding_id")
    try:
        reconstructed = apply_edits(source, item["edits"])
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if reconstructed != item["revised_text"]:
        raise ValidationError("declared edits do not reconstruct revised_text")


def validate_review_assignment(record: Any) -> None:
    item = _require_object(record, "review assignment")
    _exact_keys(item, {"item_id", "generator_id", "reviewer_id", "human"}, set(), "review assignment")
    _record_id(item["item_id"], "item_id")
    generator = _text(item["generator_id"], "generator_id")
    reviewer = _text(item["reviewer_id"], "reviewer_id")
    if item["human"] is not True:
        raise ValidationError("human review assignment must explicitly identify a real human")
    if generator.casefold() == reviewer.casefold():
        raise ValidationError("a generator cannot review its own output")


def validate_diagnostic_output(
    record: Any,
    source_case: dict[str, Any],
    *,
    allowed_normalized_codes: set[str] | None = None,
) -> None:
    item = _require_object(record, "diagnostic output")
    _exact_keys(item, {"schema_version", "case_id", "case_decision", "findings"}, set(), "diagnostic output")
    if item["schema_version"] != "1.0":
        raise ValidationError("unsupported diagnostic output schema_version")
    if item["case_id"] != source_case.get("case_id"):
        raise ValidationError("diagnostic output case_id does not match source case")
    if item["case_decision"] not in DECISIONS:
        raise ValidationError("diagnostic case_decision must be CHANGE or KEEP")
    if not isinstance(item["findings"], list):
        raise ValidationError("diagnostic findings must be a list")
    finding_ids: set[str] = set()
    has_change = False
    nested_finding_fields = {
        "finding_id",
        "start",
        "end",
        "span",
        "problem_name",
        "system_issue_code",
        "normalized_issue_code",
        "context_explanation",
        "severity",
        "suggested_operation",
        "decision",
        "field_origin",
    }
    for finding in item["findings"]:
        if not isinstance(finding, dict):
            raise ValidationError("diagnostic finding must be an object")
        if set(finding) != nested_finding_fields:
            raise ValidationError("diagnostic finding fields do not match the common envelope")
        enriched_finding = {
            **finding,
            "schema_version": item["schema_version"],
            "case_id": item["case_id"],
        }
        validate_finding(enriched_finding, source_case)
        if finding["decision"] == "KEEP":
            operation = finding["suggested_operation"]
            if operation["operation_code"] != "preserve" or operation["replacement"] is not None:
                raise ValidationError("KEEP findings must use operation_code preserve with a null replacement")
        normalized_code = finding["normalized_issue_code"]
        if (
            allowed_normalized_codes is not None
            and normalized_code != "UNMAPPED"
            and normalized_code not in allowed_normalized_codes
        ):
            raise ValidationError("normalized_issue_code is outside the frozen public vocabulary")
        finding_id = finding["finding_id"]
        if finding_id in finding_ids:
            raise ValidationError("diagnostic output has duplicate finding_id")
        finding_ids.add(finding_id)
        has_change = has_change or finding["decision"] == "CHANGE"
    if (item["case_decision"] == "CHANGE") != has_change:
        raise ValidationError("diagnostic case_decision is inconsistent with findings")


def validate_diagnostic_output_set(
    records: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    *,
    allowed_normalized_codes: set[str] | None = None,
) -> None:
    case_by_id = {item["case_id"]: item for item in cases}
    if len(case_by_id) != len(cases):
        raise ValidationError("source case IDs must be unique")
    seen: set[str] = set()
    for record in records:
        case_id = record.get("case_id") if isinstance(record, dict) else None
        if case_id not in case_by_id:
            raise ValidationError(f"diagnostic output references unknown case: {case_id}")
        if case_id in seen:
            raise ValidationError(f"duplicate diagnostic case output: {case_id}")
        validate_diagnostic_output(
            record,
            case_by_id[case_id],
            allowed_normalized_codes=allowed_normalized_codes,
        )
        seen.add(case_id)
    missing = sorted(set(case_by_id) - seen)
    if missing:
        raise ValidationError(f"diagnostic output is missing cases: {missing}")


def flatten_diagnostic_outputs(
    records: list[dict[str, Any]], *, system_id: str, run_number: int
) -> list[dict[str, Any]]:
    if not isinstance(system_id, str) or not system_id:
        raise ValidationError("system_id must be non-empty text")
    if isinstance(run_number, bool) or not isinstance(run_number, int) or run_number < 1:
        raise ValidationError("run_number must be a positive integer")
    flattened: list[dict[str, Any]] = []
    for record in records:
        for finding in record.get("findings", []):
            item = copy.deepcopy(finding)
            item["schema_version"] = record["schema_version"]
            item["case_id"] = record["case_id"]
            item["system_id"] = system_id
            item["run_number"] = run_number
            flattened.append(item)
    return flattened
