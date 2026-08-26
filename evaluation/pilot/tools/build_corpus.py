"""Build the frozen public corpus and separate provisional gold from author drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from wqeval.corpus import (
    case_has_registered_term,
    normalize_draft_record,
    split_annotated_cases,
    validate_annotated_case,
    validate_corpus_quotas,
)
from wqeval.strict_json import load_jsonl, loads


GENRES = ["technical", "executive", "personal", "marketing", "reference", "second_language"]
AUTHOR_PROFILES = [
    "domain_expert",
    "institutional_executive",
    "personal_author",
    "brand_marketer",
    "reference_editor",
    "second_language_professional",
]
FACT_TERMS = ("number", "quantity", "attribution", "modality", "negation", "date", "actor")
KEEP_TERMS = ("passive", "em_dash", "triad", "technical_term", "repetition", "fragment", "author_quirk")


def payload_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def payload_jsonl(records: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        for record in records
    ).encode("utf-8")


def write_atomic(path: Path, payload: bytes) -> None:
    """Publish one frozen artifact atomically and refuse every replacement."""

    if path.exists():
        raise FileExistsError(f"refusing to replace frozen corpus artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        os.unlink(temporary)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def publish_frozen_set(items: list[tuple[Path, bytes]]) -> None:
    """Preflight and publish a write-once artifact set, with manifest ordered last."""

    normalized = [(path.resolve(), payload) for path, payload in items]
    paths = [path for path, _ in normalized]
    if len(paths) != len(set(paths)):
        raise ValueError("frozen artifact set contains duplicate target paths")
    existing = [path for path in paths if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to publish over existing frozen artifact: {existing[0]}")

    created: list[tuple[Path, bytes]] = []
    try:
        for path, payload in normalized:
            write_atomic(path, payload)
            created.append((path, payload))
    except Exception:
        for path, payload in reversed(created):
            try:
                if path.read_bytes() == payload:
                    path.unlink()
            except FileNotFoundError:
                pass
        raise


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    project = arguments.project.resolve()
    native_map_document = loads((project / "taxonomy" / "native-map.json").read_bytes())
    if not isinstance(native_map_document, dict) or set(native_map_document) != {
        "schema_version",
        "status",
        "unknown_policy",
        "gold_issue_family_to_normalized",
    }:
        raise SystemExit("native-map schema is invalid")
    if native_map_document["schema_version"] != "1.0" or native_map_document["unknown_policy"] != "UNMAPPED":
        raise SystemExit("native-map version or unknown policy is invalid")
    native_map = native_map_document["gold_issue_family_to_normalized"]
    if not isinstance(native_map, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in native_map.items()):
        raise SystemExit("native-map entries are invalid")
    draft_paths = sorted((project / "corpus" / "drafts").glob("*.jsonl"))
    if not draft_paths:
        raise SystemExit("no draft JSONL files found")

    canonical: list[dict[str, Any]] = []
    repair_records: list[dict[str, Any]] = []
    for draft_path in draft_paths:
        for line_number, draft in enumerate(load_jsonl(draft_path), start=1):
            record, repairs = normalize_draft_record(draft)
            validate_annotated_case(record)
            canonical.append(record)
            repair_records.append(
                {
                    "case_id": record["case_id"],
                    "draft_file": draft_path.name,
                    "draft_line": line_number,
                    "repairs": repairs,
                }
            )
    case_ids = [record["case_id"] for record in canonical]
    if len(case_ids) != len(set(case_ids)):
        raise SystemExit("duplicate case_id across drafts")

    quota_summary = validate_corpus_quotas(
        canonical,
        {
            "total_cases": 90,
            "per_source_cases": 10,
            "per_source_change": 5,
            "per_source_keep": 5,
            "genres": GENRES,
            "min_per_genre": 12,
            "author_profiles": AUTHOR_PROFILES,
            "min_per_author_profile": 10,
        },
    )
    structured_count = sum(bool(record["protected_regions"]) for record in canonical)
    factual_count = sum(any(case_has_registered_term(record, term) for term in FACT_TERMS) for record in canonical)
    if structured_count < 18:
        raise SystemExit(f"structured case quota failed: expected at least 18, observed {structured_count}")
    if factual_count < 24:
        raise SystemExit(f"factual trap quota failed: expected at least 24, observed {factual_count}")
    factual_exposures = Counter()
    keep_exposures = Counter()
    for record in canonical:
        for term in FACT_TERMS:
            factual_exposures[term] += case_has_registered_term(record, term)
        for term in KEEP_TERMS:
            keep_exposures[term] += case_has_registered_term(record, term)
    missing_keep = {term: count for term, count in keep_exposures.items() if count < 2}
    if missing_keep:
        raise SystemExit(f"KEEP exposure quota failed: {missing_keep}")

    public_dev, public_test, gold_dev, gold_test = split_annotated_cases(canonical, dev_per_source_decision=1)
    if (len(public_dev), len(public_test), len(gold_dev), len(gold_test)) != (18, 72, 18, 72):
        raise SystemExit("unexpected dev/test split sizes")

    def scoring_records(gold_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        flattened: list[dict[str, Any]] = []
        for gold_record in gold_records:
            for finding in gold_record["gold_findings"]:
                family = finding["issue_family"]
                if family not in native_map:
                    raise SystemExit(f"unmapped gold issue family: {family}")
                operation = finding["allowed_operations"][0] if finding["allowed_operations"] else "preserve"
                flattened.append(
                    {
                        "schema_version": "1.0",
                        "case_id": gold_record["case_id"],
                        "finding_id": finding["finding_id"],
                        "start": finding["start"],
                        "end": finding["end"],
                        "span": finding["span"],
                        "decision": finding["decision"],
                        "problem_name": finding["problem_name"],
                        "system_issue_code": family,
                        "normalized_issue_code": native_map[family],
                        "context_explanation": finding["context_explanation"],
                        "severity": finding["severity"],
                        "suggested_operation": {
                            "operation_code": operation.casefold().replace(" ", "_"),
                            "instruction": operation,
                            "replacement": None,
                        },
                        "field_origin": "deterministic_adapter",
                    }
                )
        return sorted(flattened, key=lambda item: (item["case_id"], item["start"], item["end"], item["finding_id"]))

    outputs = {
        project / "private" / "gold" / "annotated.canonical.jsonl": payload_jsonl(sorted(canonical, key=lambda item: item["case_id"])),
        project / "private" / "gold" / "gold.dev.jsonl": payload_jsonl(gold_dev),
        project / "private" / "gold" / "gold.test.jsonl": payload_jsonl(gold_test),
        project / "private" / "gold" / "scoring.dev.jsonl": payload_jsonl(scoring_records(gold_dev)),
        project / "private" / "gold" / "scoring.test.jsonl": payload_jsonl(scoring_records(gold_test)),
        project / "corpus" / "cases.dev.jsonl": payload_jsonl(public_dev),
        project / "corpus" / "cases.test.jsonl": payload_jsonl(public_test),
        project / "corpus" / "normalization-ledger.jsonl": payload_jsonl(repair_records),
        project / "corpus" / "source-provenance.jsonl": payload_jsonl(
            [
                {"case_id": record["case_id"], "primary_source_id": record["primary_source_id"], "source_refs": record["source_refs"]}
                for record in sorted(canonical, key=lambda item: item["case_id"])
            ]
        ),
    }
    coverage = {
        "schema_version": "1.0",
        "status": "PROVISIONAL_GOLD_FROZEN_FOR_GENERATION",
        "quota_summary": quota_summary,
        "structured_cases": structured_count,
        "factual_trap_cases": factual_count,
        "factual_exposures": dict(sorted(factual_exposures.items())),
        "keep_control_exposures": dict(sorted(keep_exposures.items())),
        "dev_cases": len(public_dev),
        "test_cases": len(public_test),
        "normalization_repairs": sum(len(item["repairs"]) for item in repair_records),
        "operational_definitions": {
            "structured_case": "one or more exact protected regions in provisional gold",
            "factual_trap_case": "features, finding families, native labels, problem names, or proposition types name a registered factual trap",
        },
    }
    coverage_path = project / "corpus" / "coverage-matrix.json"
    outputs[coverage_path] = payload_json(coverage)
    freeze = {
        "schema_version": "1.0",
        "status": "frozen",
        "gold_status": "provisional_pending_human_adjudication",
        "files": [
            {
                "path": path.relative_to(project).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
            for path, payload in sorted(outputs.items(), key=lambda item: item[0])
        ],
    }
    freeze_path = project / "corpus" / "freeze-manifest.json"
    publish_frozen_set(
        [
            *sorted(outputs.items(), key=lambda item: item[0]),
            (freeze_path, payload_json(freeze)),
        ]
    )
    print(json.dumps({"cases": len(canonical), "dev": len(public_dev), "test": len(public_test), "files": len(outputs) + 1}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
