"""Canonical corpus validation, draft normalization, quota checks, and gold separation."""

from __future__ import annotations

import copy
import re
from collections import Counter
from typing import Any


class CorpusError(ValueError):
    """Raised when corpus data violates the preregistered contract."""


SOURCE_ALIASES = {
    "soundshuman": "S-001",
    "stop-slop": "S-002",
    "no-ai-slop": "S-003",
    "humanizer": "S-004",
    "slopkit": "S-005",
    "anti-ai-slop-writing": "S-006",
    "avoid-ai-writing": "S-007",
    "kami-anti-patterns": "S-008",
    "kami-writing": "S-009",
}
GENRES = {"technical", "executive", "personal", "marketing", "reference", "second_language"}
DECISIONS = {"CHANGE", "KEEP"}
SEVERITIES = {"none", "low", "medium", "high", "critical"}
AUTHOR_PROFILES = {
    "domain_expert",
    "institutional_executive",
    "personal_author",
    "brand_marketer",
    "reference_editor",
    "second_language_professional",
}


def case_has_registered_term(record: dict[str, Any], term: str) -> bool:
    """Match a registered tag as a token, never as a substring of another word."""

    if not isinstance(term, str) or not term:
        raise CorpusError("registered term must be non-empty text")
    labels = list(record.get("features", []))
    labels.extend(finding.get("issue_family", "") for finding in record.get("gold_findings", []))
    labels.extend(finding.get("source_native_label", "") for finding in record.get("gold_findings", []))
    labels.extend(finding.get("problem_name", "") for finding in record.get("gold_findings", []))
    labels.extend(proposition.get("type", "") for proposition in record.get("propositions", []))
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(term.casefold())}(?![a-z0-9])")
    return any(isinstance(label, str) and pattern.search(label.casefold()) for label in labels)


def _source_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CorpusError("primary_source_id must be non-empty text")
    normalized = value.strip()
    return SOURCE_ALIASES.get(normalized.casefold(), normalized)


def _genre(value: Any) -> str:
    if not isinstance(value, str):
        raise CorpusError("genre must be text")
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {"secondlanguage": "second_language", "esl": "second_language"}
    return aliases.get(normalized, normalized)


def _author_profile(author_type: Any, genre: str) -> str:
    if not isinstance(author_type, str):
        raise CorpusError("author_type must be text")
    lowered = author_type.casefold()
    if "second_language" in lowered or "bilingual" in lowered or genre == "second_language":
        return "second_language_professional"
    if genre == "marketing" or any(token in lowered for token in ("marketer", "marketing", "growth", "brand")):
        return "brand_marketer"
    if genre == "personal" or any(token in lowered for token in ("essayist", "memoirist", "individual_author")):
        return "personal_author"
    if genre == "executive" or any(token in lowered for token in ("executive", "manager", "director", "lead", "commander", "founder")):
        return "institutional_executive"
    if genre == "reference" or any(token in lowered for token in ("editor", "writer", "documentation", "policy", "legal", "clerk", "reporter", "educator", "maintainer")):
        return "reference_editor"
    return "domain_expert"


def normalize_draft_record(record: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize known pre-freeze authoring variants and return an explicit repair ledger."""

    if not isinstance(record, dict):
        raise CorpusError("draft record must be an object")
    item = copy.deepcopy(record)
    repairs: list[str] = []
    primary = _source_id(item.get("primary_source_id"))
    if primary != item.get("primary_source_id"):
        repairs.append("normalized primary_source_id")
    item["primary_source_id"] = primary
    normalized_genre = _genre(item.get("genre"))
    if normalized_genre != item.get("genre"):
        repairs.append("normalized genre")
    item["genre"] = normalized_genre
    expected_profile = _author_profile(item.get("author_type"), normalized_genre)
    if item.get("author_profile") != expected_profile:
        repairs.append("added or normalized author_profile")
    item["author_profile"] = expected_profile

    refs = item.get("source_refs")
    if not isinstance(refs, list):
        raise CorpusError("source_refs must be a list")
    normalized_refs: list[dict[str, Any]] = []
    for index, ref in enumerate(refs, start=1):
        if not isinstance(ref, dict):
            raise CorpusError("source reference must be an object")
        canonical_ref_keys = {"source_id", "commit", "path", "lines", "derivation"}
        unknown_ref_keys = sorted(set(ref) - canonical_ref_keys)
        if unknown_ref_keys:
            repairs.append(f"source_ref {index}: removed unknown fields {unknown_ref_keys}")
        normalized_source_id = _source_id(ref.get("source_id", primary))
        normalized_ref = {
            "source_id": normalized_source_id,
            "commit": ref.get("commit"),
            "path": ref.get("path"),
            "lines": ref.get("lines"),
            "derivation": ref.get("derivation"),
        }
        if "source_id" not in ref:
            repairs.append(f"source_ref {index}: added source_id")
        elif normalized_source_id != ref["source_id"]:
            repairs.append(f"source_ref {index}: normalized source_id")
        if "lines" not in ref:
            repairs.append(f"source_ref {index}: added null lines")
        normalized_refs.append(normalized_ref)
    item["source_refs"] = normalized_refs

    findings = item.get("gold_findings")
    if not isinstance(findings, list):
        raise CorpusError("gold_findings must be a list")
    normalized_findings: list[dict[str, Any]] = []
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            raise CorpusError("gold finding must be an object")
        finding_item = copy.deepcopy(finding)
        if "finding_id" not in finding_item:
            finding_item["finding_id"] = f"{item.get('case_id')}-F{index:02d}"
            repairs.append(f"finding {index}: added finding_id")
        if "issue_family" not in finding_item and "normalized_issue_family" in finding_item:
            finding_item["issue_family"] = finding_item.pop("normalized_issue_family")
            repairs.append(f"finding {index}: normalized issue_family key")
        if "source_native_label" not in finding_item:
            finding_item["source_native_label"] = "UNMAPPED_NATIVE"
            repairs.append(f"finding {index}: added source_native_label")
        normalized_findings.append(finding_item)
    item["gold_findings"] = normalized_findings

    propositions = item.get("propositions", [])
    if not isinstance(propositions, list):
        raise CorpusError("propositions must be a list")
    normalized_propositions: list[dict[str, Any]] = []
    for index, proposition in enumerate(propositions, start=1):
        if isinstance(proposition, str):
            normalized = {
                "proposition_id": f"{item.get('case_id')}-P{index:02d}",
                "type": "claim",
                "text": proposition,
                "criticality": "high",
            }
            repairs.append(f"proposition {index}: normalized string record")
        elif isinstance(proposition, dict):
            canonical_keys = {"proposition_id", "type", "text", "criticality"}
            if set(proposition) == canonical_keys:
                normalized = copy.deepcopy(proposition)
            else:
                text = proposition.get("text", proposition.get("statement"))
                normalized = {
                    "proposition_id": proposition.get("proposition_id", f"{item.get('case_id')}-P{index:02d}"),
                    "type": proposition.get("type", proposition.get("kind", "claim")),
                    "text": text,
                    "criticality": proposition.get("criticality", "high"),
                }
                repairs.append(f"proposition {index}: normalized object record")
        else:
            raise CorpusError("proposition must be text or an object")
        normalized_propositions.append(normalized)
    item["propositions"] = normalized_propositions

    voice = item.get("voice_signals", [])
    if not isinstance(voice, list):
        raise CorpusError("voice_signals must be a list")
    normalized_voice: list[dict[str, Any]] = []
    for index, signal in enumerate(voice, start=1):
        if isinstance(signal, str):
            normalized_signal = {
                "signal_id": f"{item.get('case_id')}-V{index:02d}",
                "description": signal,
                "protected": True,
            }
            repairs.append(f"voice signal {index}: normalized string record")
        elif isinstance(signal, dict):
            normalized_signal = {
                "signal_id": signal.get("signal_id", f"{item.get('case_id')}-V{index:02d}"),
                "description": signal.get("description"),
                "protected": signal.get("protected", True),
            }
            if set(signal) != {"signal_id", "description", "protected"}:
                repairs.append(f"voice signal {index}: normalized object record")
        else:
            raise CorpusError("voice signal must be text or an object")
        normalized_voice.append(normalized_signal)
    item["voice_signals"] = normalized_voice

    regions = item.get("protected_regions", [])
    if not isinstance(regions, list):
        raise CorpusError("protected_regions must be a list")
    normalized_regions: list[dict[str, Any]] = []
    for index, region in enumerate(regions, start=1):
        if not isinstance(region, dict):
            raise CorpusError("protected region must be an object")
        if set(region) == {"region_id", "start", "end", "span", "type", "policy"}:
            normalized_region = copy.deepcopy(region)
        else:
            normalized_region = {
                "region_id": region.get("region_id", f"{item.get('case_id')}-R{index:02d}"),
                "start": region.get("start"),
                "end": region.get("end"),
                "span": region.get("span", region.get("text")),
                "type": region.get("type", region.get("kind")),
                "policy": region.get("policy", "exact"),
            }
            repairs.append(f"protected region {index}: normalized record")
        normalized_regions.append(normalized_region)
    item["protected_regions"] = normalized_regions
    return item, repairs


def _nonempty_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CorpusError(f"{name} must be non-empty text")
    return value


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CorpusError(f"{name} must be an integer")
    return value


def validate_annotated_case(record: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "case_id",
        "primary_source_id",
        "source_refs",
        "text",
        "offset_unit",
        "genre",
        "author_type",
        "author_profile",
        "artifact_type",
        "features",
        "case_decision",
        "gold_findings",
        "propositions",
        "voice_signals",
        "protected_regions",
        "provisional_gold",
    }
    if not isinstance(record, dict) or set(record) != required:
        missing = sorted(required - set(record)) if isinstance(record, dict) else sorted(required)
        extra = sorted(set(record) - required) if isinstance(record, dict) else []
        raise CorpusError(f"annotated case fields mismatch; missing={missing}, extra={extra}")
    if record["schema_version"] != "1.0" or record["offset_unit"] != "unicode_codepoint":
        raise CorpusError("unsupported schema version or offset unit")
    case_id = _nonempty_text(record["case_id"], "case_id")
    primary = _source_id(record["primary_source_id"])
    if primary != record["primary_source_id"] or primary not in {f"S-{index:03d}" for index in range(1, 10)}:
        raise CorpusError("primary_source_id must be canonical S-001 through S-009")
    source = record["text"]
    if not isinstance(source, str):
        raise CorpusError("text must be a string")
    if record["genre"] not in GENRES:
        raise CorpusError("unsupported genre")
    _nonempty_text(record["author_type"], "author_type")
    if record["author_profile"] not in AUTHOR_PROFILES:
        raise CorpusError("unsupported author_profile")
    _nonempty_text(record["artifact_type"], "artifact_type")
    if not isinstance(record["features"], list) or not all(isinstance(item, str) for item in record["features"]):
        raise CorpusError("features must be a list of strings")
    if record["case_decision"] not in DECISIONS:
        raise CorpusError("case_decision must be CHANGE or KEEP")
    if record["provisional_gold"] is not True:
        raise CorpusError("pre-adjudication corpus must set provisional_gold true")

    if not isinstance(record["source_refs"], list) or not record["source_refs"]:
        raise CorpusError("source_refs must be a non-empty list")
    referenced_sources: set[str] = set()
    for ref in record["source_refs"]:
        if not isinstance(ref, dict) or set(ref) != {"source_id", "commit", "path", "lines", "derivation"}:
            raise CorpusError("source reference fields are invalid")
        referenced_sources.add(_source_id(ref["source_id"]))
        commit = _nonempty_text(ref["commit"], "source commit")
        if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit.casefold()):
            raise CorpusError("source commit must be a 40-character hexadecimal hash")
        _nonempty_text(ref["path"], "source path")
        if ref["lines"] is not None and not isinstance(ref["lines"], str):
            raise CorpusError("source lines must be text or null")
        _nonempty_text(ref["derivation"], "source derivation")
    if primary not in referenced_sources:
        raise CorpusError("primary source is absent from source_refs")

    findings = record["gold_findings"]
    if not isinstance(findings, list) or not findings:
        raise CorpusError("gold_findings must be a non-empty list")
    finding_ids: set[str] = set()
    has_change = False
    for finding in findings:
        required_finding = {
            "finding_id",
            "start",
            "end",
            "span",
            "decision",
            "issue_family",
            "source_native_label",
            "problem_name",
            "severity",
            "context_explanation",
            "allowed_operations",
            "forbidden_changes",
            "importance",
        }
        if not isinstance(finding, dict) or set(finding) != required_finding:
            raise CorpusError("gold finding fields are invalid")
        finding_id = _nonempty_text(finding["finding_id"], "finding_id")
        if finding_id in finding_ids:
            raise CorpusError(f"duplicate finding_id in {case_id}")
        finding_ids.add(finding_id)
        start = _integer(finding["start"], "finding start")
        end = _integer(finding["end"], "finding end")
        if start < 0 or end <= start or end > len(source) or source[start:end] != finding["span"]:
            raise CorpusError(f"finding span mismatch in {case_id}")
        if finding["decision"] not in DECISIONS or finding["severity"] not in SEVERITIES:
            raise CorpusError("invalid finding decision or severity")
        has_change = has_change or finding["decision"] == "CHANGE"
        for key in ("issue_family", "source_native_label", "problem_name", "context_explanation", "importance"):
            _nonempty_text(finding[key], key)
        for key in ("allowed_operations", "forbidden_changes"):
            if not isinstance(finding[key], list) or not all(isinstance(value, str) and value for value in finding[key]):
                raise CorpusError(f"{key} must be a non-empty-string list")
    if (record["case_decision"] == "CHANGE") != has_change:
        raise CorpusError("case_decision is inconsistent with gold findings")

    for proposition in record["propositions"]:
        if not isinstance(proposition, dict) or set(proposition) != {"proposition_id", "type", "text", "criticality"}:
            raise CorpusError("proposition fields are invalid")
        for key in ("proposition_id", "type", "text", "criticality"):
            _nonempty_text(proposition[key], f"proposition {key}")
    for signal in record["voice_signals"]:
        if not isinstance(signal, dict) or set(signal) != {"signal_id", "description", "protected"}:
            raise CorpusError("voice signal fields are invalid")
        _nonempty_text(signal["signal_id"], "signal_id")
        _nonempty_text(signal["description"], "voice description")
        if not isinstance(signal["protected"], bool):
            raise CorpusError("voice protected must be boolean")
    for region in record["protected_regions"]:
        if not isinstance(region, dict) or set(region) != {"region_id", "start", "end", "span", "type", "policy"}:
            raise CorpusError("protected region fields are invalid")
        start = _integer(region["start"], "protected region start")
        end = _integer(region["end"], "protected region end")
        if start < 0 or end <= start or end > len(source) or source[start:end] != region["span"]:
            raise CorpusError(f"protected region span mismatch in {case_id}")
        if region["policy"] not in {"exact", "layout_only"}:
            raise CorpusError("invalid protected region policy")


def split_annotated_cases(
    records: list[dict[str, Any]], *, dev_per_source_decision: int = 1
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    for record in records:
        validate_annotated_case(record)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault((record["primary_source_id"], record["case_decision"]), []).append(record)
    dev_ids: set[str] = set()
    for group in grouped.values():
        selected = sorted(group, key=lambda item: item["case_id"])[:dev_per_source_decision]
        dev_ids.update(item["case_id"] for item in selected)

    public_dev: list[dict[str, Any]] = []
    public_test: list[dict[str, Any]] = []
    gold_dev: list[dict[str, Any]] = []
    gold_test: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: item["case_id"]):
        split = "dev" if record["case_id"] in dev_ids else "test"
        public = {
            "schema_version": record["schema_version"],
            "case_id": record["case_id"],
            "split": split,
            "text": record["text"],
            "offset_unit": record["offset_unit"],
            "genre": record["genre"],
            "author_type": record["author_type"],
            "author_profile": record["author_profile"],
            "artifact_type": record["artifact_type"],
            "protected_regions": [],
        }
        gold = {
            "schema_version": record["schema_version"],
            "case_id": record["case_id"],
            "split": split,
            "case_decision": record["case_decision"],
            "gold_findings": record["gold_findings"],
            "propositions": record["propositions"],
            "voice_signals": record["voice_signals"],
            "protected_regions": record["protected_regions"],
            "provisional_gold": record["provisional_gold"],
        }
        if split == "dev":
            public_dev.append(public)
            gold_dev.append(gold)
        else:
            public_test.append(public)
            gold_test.append(gold)
    return public_dev, public_test, gold_dev, gold_test


def validate_corpus_quotas(records: list[dict[str, Any]], quotas: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    expected_total = quotas.get("total_cases")
    if expected_total is not None and len(records) != expected_total:
        errors.append(f"total_cases expected {expected_total}, observed {len(records)}")
    source_counts = Counter(item["primary_source_id"] for item in records)
    decision_counts = Counter((item["primary_source_id"], item["case_decision"]) for item in records)
    per_source = quotas.get("per_source_cases")
    per_change = quotas.get("per_source_change")
    per_keep = quotas.get("per_source_keep")
    for source in sorted(source_counts):
        if per_source is not None and source_counts[source] != per_source:
            errors.append(f"source {source} expected {per_source}, observed {source_counts[source]}")
        if per_change is not None and decision_counts[(source, "CHANGE")] != per_change:
            errors.append(f"source {source} CHANGE expected {per_change}, observed {decision_counts[(source, 'CHANGE')]}")
        if per_keep is not None and decision_counts[(source, "KEEP")] != per_keep:
            errors.append(f"source {source} KEEP expected {per_keep}, observed {decision_counts[(source, 'KEEP')]}")
    genre_counts = Counter(item["genre"] for item in records)
    for genre in quotas.get("genres", []):
        minimum = quotas.get("min_per_genre", 0)
        if genre_counts[genre] < minimum:
            errors.append(f"genre {genre} expected at least {minimum}, observed {genre_counts[genre]}")
    profile_counts = Counter(item["author_profile"] for item in records)
    for profile in quotas.get("author_profiles", []):
        minimum = quotas.get("min_per_author_profile", 0)
        if profile_counts[profile] < minimum:
            errors.append(f"author_profile {profile} expected at least {minimum}, observed {profile_counts[profile]}")
    if errors:
        raise CorpusError("; ".join(errors))
    return {
        "total_cases": len(records),
        "by_source": dict(sorted(source_counts.items())),
        "by_decision": {f"{source}:{decision}": count for (source, decision), count in sorted(decision_counts.items())},
        "by_genre": dict(sorted(genre_counts.items())),
        "by_author_profile": dict(sorted(profile_counts.items())),
    }
