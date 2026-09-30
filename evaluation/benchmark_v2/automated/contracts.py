"""Strict JSON contracts for suites and rubrics."""

import json
import math
import unicodedata
from pathlib import Path

SPLITS = ("calibration", "development", "test")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"nonfinite JSON value: {value}")


def _clean_unicode(value):
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif isinstance(value, list):
        for item in value:
            _clean_unicode(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _clean_unicode(key)
            _clean_unicode(item)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite number")
    return value


def strict_json(raw: bytes) -> object:
    """Read one UTF-8 JSON value with no duplicate keys or invalid Unicode."""
    if not isinstance(raw, bytes):
        raise ValueError("JSON input must be bytes")
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"),
                           object_pairs_hook=_unique_pairs,
                           parse_constant=_invalid_constant)
        return _clean_unicode(value)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc


def _object(value, required, optional=(), label="object"):
    if not isinstance(value, dict) or set(value) - (set(required) | set(optional)) or set(required) - set(value):
        raise ValueError(f"invalid {label} fields")


def _nonblank(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonblank")


def _strings(value, label):
    if not isinstance(value, list) or any(not isinstance(s, str) for s in value):
        raise ValueError(f"{label} must be a string array")


def case_fingerprint(case):
    # Reversed presentation is the same underlying pair. Normalize cosmetic
    # whitespace and Unicode to catch copies disguised as distinct documents.
    def canonical(s):
        return " ".join(unicodedata.normalize("NFC", s).split())
    return (canonical(case["prompt"]), canonical(case["context"]),
            tuple(sorted((canonical(case["a"]), canonical(case["b"])))))


def validate_suite(value) -> dict:
    _clean_unicode(value)
    _object(value, ("schema_version", "name", "cases"), label="suite")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("unsupported suite schema")
    _nonblank(value["name"], "suite name")
    if not isinstance(value["cases"], list) or not value["cases"]:
        raise ValueError("suite needs cases")
    seen_ids, document_splits, fingerprints = set(), {}, {}
    document_clusters, cluster_splits = {}, {}
    for case in value["cases"]:
        _object(case, ("id", "document_id", "split", "lane", "prompt", "context",
                       "a", "b", "expected", "checks", "provenance"), ("cluster_id",), label="case")
        for key in ("id", "document_id", "prompt", "a", "b"):
            _nonblank(case[key], key)
        if "cluster_id" in case:
            _nonblank(case["cluster_id"], "cluster_id")
        if not isinstance(case["context"], str):
            raise ValueError("context must be a string")
        if case["id"] in seen_ids:
            raise ValueError("duplicate case id")
        seen_ids.add(case["id"])
        if case["split"] not in SPLITS or case["lane"] not in ("editing", "communication"):
            raise ValueError("invalid split or lane")
        if case["expected"] not in ("a", "b", "tie", "both_bad", None):
            raise ValueError("invalid expected winner")
        doc = case["document_id"]
        if doc in document_splits and document_splits[doc] != case["split"]:
            raise ValueError("document reused across splits")
        document_splits[doc] = case["split"]
        # A cluster groups documents that must stay on one side of a split (for
        # example every reply in one thread). Present versus absent counts as
        # different, so a document is clustered in every case or in none.
        cluster = case.get("cluster_id")
        if doc in document_clusters and document_clusters[doc] != cluster:
            raise ValueError("document assigned to more than one cluster")
        document_clusters[doc] = cluster
        if cluster is not None and cluster_splits.setdefault(cluster, case["split"]) != case["split"]:
            raise ValueError("cluster spans splits")
        fingerprint = case_fingerprint(case)
        if fingerprint in fingerprints and fingerprints[fingerprint] != doc:
            raise ValueError("copied pair assigned to another document id")
        fingerprints[fingerprint] = doc
        checks = case["checks"]
        _object(checks, (), ("required", "forbidden", "max_words", "exact"), label="checks")
        for key in ("required", "forbidden"):
            if key in checks:
                _strings(checks[key], key)
                if any(not s for s in checks[key]):
                    raise ValueError(f"{key} contains empty string")
        if "max_words" in checks and (type(checks["max_words"]) is not int or checks["max_words"] < 1):
            raise ValueError("max_words must be positive integer")
        if "exact" in checks and not isinstance(checks["exact"], str):
            raise ValueError("exact must be string")
        provenance = case["provenance"]
        _object(provenance, ("kind", "source", "license"), ("note",), label="provenance")
        if provenance["kind"] not in ("synthetic_control", "published_reference"):
            raise ValueError("invalid provenance kind")
        for key in ("source", "license"):
            _nonblank(provenance[key], key)
        if "note" in provenance and not isinstance(provenance["note"], str):
            raise ValueError("provenance note must be string")
        if provenance["kind"] == "published_reference" and case["expected"] is not None:
            raise ValueError("published reference cannot have expected winner")
    return value


def validate_rubric(value) -> dict:
    _clean_unicode(value)
    _object(value, ("schema_version", "id", "criteria"), label="rubric")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("unsupported rubric schema")
    _nonblank(value["id"], "rubric id")
    criteria = value["criteria"]
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 8:
        raise ValueError("rubric requires one to eight criteria")
    ids = set()
    for criterion in criteria:
        _object(criterion, ("id", "description"), label="criterion")
        _nonblank(criterion["id"], "criterion id")
        _nonblank(criterion["description"], "criterion description")
        if criterion["id"] in ids:
            raise ValueError("duplicate criterion id")
        ids.add(criterion["id"])
    if sum(len(c["description"]) for c in criteria) > 6000:
        raise ValueError("rubric descriptions exceed 6000 characters")
    return value


def load_suite(path) -> dict:
    return validate_suite(strict_json(Path(path).read_bytes()))


def load_rubric(path) -> dict:
    return validate_rubric(strict_json(Path(path).read_bytes()))
