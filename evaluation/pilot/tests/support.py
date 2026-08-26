from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


def case(
    case_id: str = "C001",
    text: str = "The API failed.",
    *,
    genre: str = "technical",
    author_type: str = "professional",
    author_profile: str | None = None,
    protected_regions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profiles = {
        "technical": "domain_expert",
        "executive": "institutional_executive",
        "personal": "personal_author",
        "marketing": "brand_marketer",
        "reference": "reference_editor",
        "second_language": "second_language_professional",
    }
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "text": text,
        "genre": genre,
        "author_type": author_type,
        "author_profile": author_profile or profiles.get(genre, "domain_expert"),
        "protected_regions": protected_regions or [],
    }


def finding(
    case_id: str = "C001",
    finding_id: str = "F001",
    *,
    start: int = 0,
    end: int = 3,
    span_text: str = "The",
    problem_code: str = "vague_reference",
    decision: str = "CHANGE",
    severity: str = "medium",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "finding_id": finding_id,
        "span": {"start": start, "end": end, "text": span_text},
        "problem_code": problem_code,
        "problem": problem_code.replace("_", " ").title(),
        "context": "The named issue is present in this context.",
        "severity": severity,
        "suggested_operation": "Replace the vague reference with its named subject.",
        "decision": decision,
    }


def human_review_artifact(
    predictions: list[dict[str, Any]],
    *,
    changed_finding_ids: set[str] | None = None,
    critical_finding_ids: set[str] | None = None,
) -> dict[str, Any]:
    changed = changed_finding_ids or set()
    critical = critical_finding_ids or set()
    review_items = [
        {"review_item_id": f"Item-{index:06d}", "prediction": copy.deepcopy(prediction)}
        for index, prediction in enumerate(
            (item for item in predictions if item["decision"] == "CHANGE"),
            start=1,
        )
    ]
    reviews = [
        {
            "review_item_id": item["review_item_id"],
            "reviewer_id": reviewer_id,
            "finding_valid": True,
            "span_valid": True,
            "problem_valid": True,
            "context_valid": True,
            "severity_valid": True,
            "operation_valid": True,
            "meaning_changed": False,
            "meaning_risk": "none",
        }
        for reviewer_id in ("human-a", "human-b")
        for item in review_items
    ]
    adjudications = []
    for item in review_items:
        finding_id = item["prediction"]["finding_id"]
        meaning_changed = finding_id in changed
        adjudications.append(
            {
                "review_item_id": item["review_item_id"],
                "reviewer_id": "human-c",
                "finding_valid": True,
                "span_valid": True,
                "problem_valid": True,
                "context_valid": True,
                "severity_valid": True,
                "operation_valid": True,
                "meaning_changed": meaning_changed,
                "meaning_risk": (
                    "critical"
                    if finding_id in critical
                    else "high"
                    if meaning_changed
                    else "none"
                ),
            }
        )
    return {
        "schema_version": "1.0",
        "reviewers": [
            {"reviewer_id": "human-a", "actor_type": "human", "human": True},
            {"reviewer_id": "human-b", "actor_type": "human", "human": True},
        ],
        "adjudicator": {"reviewer_id": "human-c", "actor_type": "human", "human": True},
        "review_items": review_items,
        "reviews": reviews,
        "adjudications": adjudications,
    }


def trusted_human_roster() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "status": "CONFIRMED",
        "attestation_kind": "real_human_identity",
        "reviewer_ids": ["human-a", "human-b"],
        "adjudicator_id": "human-c",
        "attested_by": "test-fixture-authority",
        "attestation_source": "unit-test detached fixture",
        "real_humans_confirmed": True,
    }


def human_gold_review_artifact(
    cases: list[dict[str, Any]],
    gold_findings: list[dict[str, Any]],
    *,
    approved: bool = True,
) -> dict[str, Any]:
    findings_by_case: dict[str, list[dict[str, Any]]] = {
        item["case_id"]: [] for item in cases
    }
    for finding in gold_findings:
        findings_by_case[finding["case_id"]].append(copy.deepcopy(finding))
    review_items = [
        {
            "review_item_id": f"Gold-{index:06d}",
            "case": copy.deepcopy(case_item),
            "gold_findings": findings_by_case[case_item["case_id"]],
        }
        for index, case_item in enumerate(cases, start=1)
    ]
    reviews = [
        {
            "review_item_id": item["review_item_id"],
            "reviewer_id": reviewer_id,
            "span_correct": True,
            "decision_correct": True,
            "label_correct": True,
            "severity_correct": True,
            "gold_complete": True,
        }
        for reviewer_id in ("human-a", "human-b")
        for item in review_items
    ]
    adjudications = [
        {
            "review_item_id": item["review_item_id"],
            "reviewer_id": "human-c",
            "span_correct": True,
            "decision_correct": True,
            "label_correct": True,
            "severity_correct": True,
            "gold_complete": approved,
        }
        for item in review_items
    ]
    return {
        "schema_version": "1.0",
        "reviewers": [
            {"reviewer_id": "human-a", "actor_type": "human", "human": True},
            {"reviewer_id": "human-b", "actor_type": "human", "human": True},
        ],
        "adjudicator": {"reviewer_id": "human-c", "actor_type": "human", "human": True},
        "review_items": review_items,
        "reviews": reviews,
        "adjudications": adjudications,
    }


def rewrite(
    source: str,
    revised: str,
    edits: list[dict[str, Any]],
    *,
    case_id: str = "C001",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "revised_text": revised,
        "edits": edits,
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
        newline="\n",
    )


def verified_scoring_corpus(
    root: Path,
    cases: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    *,
    split: str = "test",
):
    from wqeval.corpus_evidence import verify_frozen_scoring_corpus

    cases_path = root / "corpus" / f"cases.{split}.jsonl"
    gold_path = root / "private" / "gold" / f"scoring.{split}.jsonl"
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(cases_path, cases)
    write_jsonl(gold_path, gold)
    entries = []
    for relative, path in (
        (f"corpus/cases.{split}.jsonl", cases_path),
        (f"private/gold/scoring.{split}.jsonl", gold_path),
    ):
        payload = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    manifest = {
        "schema_version": "1.0",
        "status": "frozen",
        "gold_status": "provisional_pending_human_adjudication",
        "files": entries,
    }
    manifest_path = root / "corpus" / "freeze-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return verify_frozen_scoring_corpus(
        root,
        expected_freeze_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        split=split,
    )
