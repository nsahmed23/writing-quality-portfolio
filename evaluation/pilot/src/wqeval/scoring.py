"""Deterministic Stage 1, agreement, fact, and Stage 2 metrics."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
import math
import re
from typing import Any, Iterable

from .human_review import verify_stage1_human_review_artifact


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def exact_finding_key(finding: dict[str, Any]) -> tuple[str, int, int, str]:
    """Return the preregistered exact key, excluding finding identity and severity."""

    span = finding.get("span")
    if isinstance(span, dict):
        start, end = span.get("start"), span.get("end")
    else:
        start, end = finding.get("start"), finding.get("end")
    problem = finding.get("problem_code", finding.get("normalized_issue_code"))
    return finding.get("case_id"), start, end, problem


def _counts_for_cases(
    case_ids: set[str],
    gold_changes: list[dict[str, Any]],
    prediction_changes: list[dict[str, Any]],
) -> tuple[int, int, int]:
    gold_counter = Counter(exact_finding_key(item) for item in gold_changes if item.get("case_id") in case_ids)
    prediction_counter = Counter(
        exact_finding_key(item) for item in prediction_changes if item.get("case_id") in case_ids
    )
    true_positives = sum((gold_counter & prediction_counter).values())
    false_positives = sum(prediction_counter.values()) - true_positives
    false_negatives = sum(gold_counter.values()) - true_positives
    return true_positives, false_positives, false_negatives


def _finding_coordinates(finding: dict[str, Any]) -> tuple[str, int, int, str]:
    span = finding.get("span")
    if isinstance(span, dict):
        start, end = span.get("start"), span.get("end")
    else:
        start, end = finding.get("start"), finding.get("end")
    problem = finding.get("problem_code", finding.get("normalized_issue_code"))
    return finding.get("case_id"), start, end, problem


def _overlap_counts(
    gold_changes: list[dict[str, Any]], prediction_changes: list[dict[str, Any]]
) -> tuple[int, int, int]:
    gold_groups: defaultdict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    prediction_groups: defaultdict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for item in gold_changes:
        case_id, start, end, problem = _finding_coordinates(item)
        if isinstance(start, int) and isinstance(end, int):
            gold_groups[(case_id, problem)].append((start, end))
    for item in prediction_changes:
        case_id, start, end, problem = _finding_coordinates(item)
        if isinstance(start, int) and isinstance(end, int):
            prediction_groups[(case_id, problem)].append((start, end))

    true_positives = 0
    for key, predicted_spans in prediction_groups.items():
        gold_spans = gold_groups.get(key, [])
        edges = [
            [
                gold_index
                for gold_index, (gold_start, gold_end) in enumerate(gold_spans)
                if max(start, gold_start) < min(end, gold_end)
            ]
            for start, end in predicted_spans
        ]
        matched_gold: dict[int, int] = {}

        def assign(prediction_index: int, visited: set[int]) -> bool:
            for gold_index in edges[prediction_index]:
                if gold_index in visited:
                    continue
                visited.add(gold_index)
                previous = matched_gold.get(gold_index)
                if previous is None or assign(previous, visited):
                    matched_gold[gold_index] = prediction_index
                    return True
            return False

        true_positives += sum(assign(index, set()) for index in range(len(predicted_spans)))
    return (
        true_positives,
        len(prediction_changes) - true_positives,
        len(gold_changes) - true_positives,
    )


def _metric_bundle(tp: int, fp: int, fn: int) -> dict[str, Any]:
    undefined: dict[str, str] = {}
    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    if precision is None:
        undefined["precision"] = "no predicted CHANGE findings"
    if recall is None:
        undefined["recall"] = "no gold CHANGE findings"
    if precision is None or recall is None or precision + recall == 0:
        f1 = None
        undefined["f1"] = "precision or recall is undefined or both are zero"
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "undefined_metrics": undefined,
    }


def score_stage1(
    cases: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    meaning_reviews: list[dict[str, Any]] | None = None,
    human_review_artifact: dict[str, Any] | None = None,
    trusted_human_roster: dict[str, Any] | None = None,
    expected_human_roster_sha256: str | None = None,
) -> dict[str, Any]:
    """Score exact CHANGE findings and contextual KEEP controls."""

    case_by_id = {item["case_id"]: item for item in cases}
    gold_changes = [item for item in gold if item.get("decision") == "CHANGE"]
    gold_keeps = [item for item in gold if item.get("decision") == "KEEP"]
    prediction_changes = [item for item in predictions if item.get("decision") == "CHANGE"]
    prediction_keeps = [item for item in predictions if item.get("decision") == "KEEP"]

    all_case_ids = set(case_by_id)
    tp, fp, fn = _counts_for_cases(all_case_ids, gold_changes, prediction_changes)
    matched_keep = Counter(exact_finding_key(item) for item in gold_keeps) & Counter(
        exact_finding_key(item) for item in prediction_keeps
    )
    explicit_keep_matches = sum(matched_keep.values())
    metrics = _metric_bundle(tp, fp, fn)
    metrics["positive_opportunities"] = len(gold_changes)
    metrics["keep_opportunities"] = len(gold_keeps)
    metrics["explicit_keep_matches"] = explicit_keep_matches
    metrics["false_discovery_proportion"] = _safe_ratio(fp, tp + fp)
    metrics["exact_span_accuracy"] = _safe_ratio(tp, tp + fp + fn)
    overlap_tp, overlap_fp, overlap_fn = _overlap_counts(gold_changes, prediction_changes)
    metrics["overlap_sensitivity"] = _metric_bundle(overlap_tp, overlap_fp, overlap_fn)

    gold_by_case: defaultdict[str, Counter] = defaultdict(Counter)
    predictions_by_case: defaultdict[str, Counter] = defaultdict(Counter)
    for finding in gold_changes:
        gold_by_case[finding.get("case_id")][exact_finding_key(finding)] += 1
    for finding in prediction_changes:
        predictions_by_case[finding.get("case_id")][exact_finding_key(finding)] += 1
    per_case_bundles = []
    for case_id in sorted(all_case_ids):
        ctp = sum((gold_by_case[case_id] & predictions_by_case[case_id]).values())
        cfp = sum(predictions_by_case[case_id].values()) - ctp
        cfn = sum(gold_by_case[case_id].values()) - ctp
        per_case_bundles.append(_metric_bundle(ctp, cfp, cfn))
    defined_precision = [item["precision"] for item in per_case_bundles if item["precision"] is not None]
    defined_recall = [item["recall"] for item in per_case_bundles if item["recall"] is not None]
    defined_f1 = [item["f1"] for item in per_case_bundles if item["f1"] is not None]
    metrics["macro_precision"] = _mean(defined_precision)
    metrics["macro_recall"] = _mean(defined_recall)
    metrics["macro_f1"] = _mean(defined_f1)
    metrics["macro_defined_case_counts"] = {
        "precision": len(defined_precision),
        "recall": len(defined_recall),
        "f1": len(defined_f1),
    }
    word_count = sum(len(re.findall(r"\b\w+\b", str(item.get("text", "")), flags=re.UNICODE)) for item in cases)
    metrics["word_count"] = word_count
    metrics["false_findings_per_1000_words"] = _safe_ratio(fp * 1000, word_count)

    matched_change = Counter(exact_finding_key(item) for item in gold_changes) & Counter(
        exact_finding_key(item) for item in prediction_changes
    )
    important_misses = 0
    for item in gold_changes:
        key = exact_finding_key(item)
        if item.get("severity") in {"high", "critical"} and matched_change[key] == 0:
            important_misses += 1
        elif matched_change[key] > 0:
            matched_change[key] -= 1
    metrics["important_issues_missed"] = important_misses
    critical_gold = [item for item in gold_changes if item.get("severity") == "critical"]
    critical_matches = Counter(exact_finding_key(item) for item in critical_gold) & Counter(
        exact_finding_key(item) for item in prediction_changes
    )
    critical_matched_count = sum(critical_matches.values())
    metrics["critical_issues"] = len(critical_gold)
    metrics["critical_issues_missed"] = len(critical_gold) - critical_matched_count
    metrics["critical_miss_rate"] = _safe_ratio(metrics["critical_issues_missed"], len(critical_gold))

    gold_change_cases = {item["case_id"] for item in gold_changes}
    clean_case_ids = all_case_ids - gold_change_cases
    predicted_change_cases = {item["case_id"] for item in prediction_changes}
    clean_false_cases = len(clean_case_ids & predicted_change_cases)
    metrics["clean_control_case_false_positive_rate"] = _safe_ratio(clean_false_cases, len(clean_case_ids))
    keep_false_positives = 0
    for keep in gold_keeps:
        keep_case, keep_start, keep_end, _ = _finding_coordinates(keep)
        attacked = any(
            prediction.get("case_id") == keep_case
            and max(keep_start, _finding_coordinates(prediction)[1])
            < min(keep_end, _finding_coordinates(prediction)[2])
            for prediction in prediction_changes
        )
        keep_false_positives += attacked
    metrics["keep_false_positive_count"] = keep_false_positives
    metrics["keep_accuracy"] = _safe_ratio(len(gold_keeps) - keep_false_positives, len(gold_keeps))
    metrics["explicit_keep_recognition_rate"] = _safe_ratio(explicit_keep_matches, len(gold_keeps))

    by_genre: dict[str, Any] = {}
    by_author: dict[str, Any] = {}
    by_profile: dict[str, Any] = {}
    genres: defaultdict[str, set[str]] = defaultdict(set)
    authors: defaultdict[str, set[str]] = defaultdict(set)
    profiles: defaultdict[str, set[str]] = defaultdict(set)
    for item in cases:
        genres[item["genre"]].add(item["case_id"])
        authors[item["author_type"]].add(item["case_id"])
        if "author_profile" in item:
            profiles[item["author_profile"]].add(item["case_id"])
    for name, identifiers in sorted(genres.items()):
        stp, sfp, sfn = _counts_for_cases(identifiers, gold_changes, prediction_changes)
        bundle = _metric_bundle(stp, sfp, sfn)
        bundle["case_count"] = len(identifiers)
        bundle["positive_opportunities"] = sum(item.get("case_id") in identifiers for item in gold_changes)
        bundle["keep_opportunities"] = sum(item.get("case_id") in identifiers for item in gold_keeps)
        by_genre[name] = bundle
    for name, identifiers in sorted(authors.items()):
        stp, sfp, sfn = _counts_for_cases(identifiers, gold_changes, prediction_changes)
        bundle = _metric_bundle(stp, sfp, sfn)
        bundle["case_count"] = len(identifiers)
        bundle["positive_opportunities"] = sum(item.get("case_id") in identifiers for item in gold_changes)
        bundle["keep_opportunities"] = sum(item.get("case_id") in identifiers for item in gold_keeps)
        by_author[name] = bundle
    metrics["by_genre"] = by_genre
    metrics["by_author_type"] = by_author
    for name, identifiers in sorted(profiles.items()):
        stp, sfp, sfn = _counts_for_cases(identifiers, gold_changes, prediction_changes)
        bundle = _metric_bundle(stp, sfp, sfn)
        bundle["case_count"] = len(identifiers)
        bundle["positive_opportunities"] = sum(item.get("case_id") in identifiers for item in gold_changes)
        bundle["keep_opportunities"] = sum(item.get("case_id") in identifiers for item in gold_keeps)
        by_profile[name] = bundle
    metrics["by_author_profile"] = by_profile

    if meaning_reviews is not None:
        raise ValueError("flat meaning_reviews are unverified; supply a bound human_review_artifact")
    if human_review_artifact is None:
        metrics.update(
            {
                "human_review_verified": False,
                "human_adjudicated": False,
                "human_identity_attested": False,
                "review_structure_verified": False,
                "meaning_reviewed_suggestions": 0,
                "diagnostic_meaning_change_rate": None,
                "critical_meaning_risk": None,
            }
        )
    else:
        metrics.update(
            verify_stage1_human_review_artifact(
                human_review_artifact,
                predictions,
                trusted_human_roster=trusted_human_roster,
                expected_human_roster_sha256=expected_human_roster_sha256,
            )
        )
    return metrics


def percent_agreement(left: list[Any], right: list[Any]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("ratings must be equal-length non-empty lists")
    return sum(a == b for a, b in zip(left, right)) / len(left)


def cohen_kappa(left: list[Any], right: list[Any]) -> float | None:
    if len(left) != len(right) or not left:
        raise ValueError("ratings must be equal-length non-empty lists")
    observed = percent_agreement(left, right)
    labels = set(left) | set(right)
    expected = sum((left.count(label) / len(left)) * (right.count(label) / len(right)) for label in labels)
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


def agreement_summary(ratings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(ratings, dict) or len(ratings) != 2:
        raise ValueError("agreement requires exactly two reviewer panels")
    reviewer_ids = list(ratings)
    if any(not isinstance(reviewer_id, str) or not reviewer_id.strip() for reviewer_id in reviewer_ids):
        raise ValueError("reviewer IDs must be non-empty text")
    if len({reviewer_id.casefold() for reviewer_id in reviewer_ids}) != 2:
        raise ValueError("reviewer IDs must be unique")
    if any(not isinstance(items, dict) or not items for items in ratings.values()):
        raise ValueError("reviewer panels must be non-empty objects")
    item_sets = [set(items) for items in ratings.values()]
    if any(items != item_sets[0] for items in item_sets[1:]):
        raise ValueError("agreement requires complete reviewer panels over identical item sets")
    pairs: list[dict[str, Any]] = []
    for left_id, right_id in combinations(sorted(ratings), 2):
        common = sorted(set(ratings[left_id]) & set(ratings[right_id]))
        if not common:
            continue
        left = [ratings[left_id][item] for item in common]
        right = [ratings[right_id][item] for item in common]
        kappa = cohen_kappa(left, right)
        pair = {
            "reviewer_a": left_id,
            "reviewer_b": right_id,
            "common_items": len(common),
            "percent_agreement": percent_agreement(left, right),
            "cohen_kappa": kappa,
        }
        if kappa is None:
            pair["cohen_kappa_undefined_reason"] = "expected agreement is 1, so the kappa denominator is zero"
        pairs.append(pair)
    return {"pair_count": len(pairs), "pairs": pairs}


def compare_fact_ledgers(expected: list[dict[str, Any]], observed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def index(records: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
        if not isinstance(records, list):
            raise ValueError(f"{name} fact ledger must be a list")
        indexed: dict[str, dict[str, Any]] = {}
        for item in records:
            if not isinstance(item, dict) or set(item) != {"fact_id", "kind", "value"}:
                raise ValueError(f"{name} fact record fields are invalid")
            fact_id = item["fact_id"]
            kind = item["kind"]
            if not isinstance(fact_id, str) or not fact_id or not isinstance(kind, str) or not kind:
                raise ValueError(f"{name} fact identity and kind must be non-empty text")
            if fact_id in indexed:
                raise ValueError(f"{name} fact ledger has duplicate fact_id: {fact_id}")
            indexed[fact_id] = item
        return indexed

    expected_by_id = index(expected, "expected")
    observed_by_id = index(observed, "observed")
    violations: list[dict[str, Any]] = []
    for fact_id in sorted(expected_by_id.keys() | observed_by_id.keys()):
        before = expected_by_id.get(fact_id)
        after = observed_by_id.get(fact_id)
        if before is None:
            violations.append({"fact_id": fact_id, "kind": after.get("kind"), "status": "unexpected", "observed": after})
        elif after is None:
            violations.append({"fact_id": fact_id, "kind": before.get("kind"), "status": "missing", "expected": before})
        elif before.get("kind") != after.get("kind") or before.get("value") != after.get("value"):
            violations.append(
                {
                    "fact_id": fact_id,
                    "kind": before.get("kind"),
                    "status": "changed",
                    "expected": before,
                    "observed": after,
                }
            )
    return violations


def _mean(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return sum(materialized) / len(materialized) if materialized else None


def score_stage2(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    expected_fields = {
        "case_id",
        "generator_id",
        "run_number",
        "rewrite_sha256",
        "reviewer_id",
        "human",
        "semantic_preserved",
        "voice_retained",
        "unnecessary_edits",
        "total_edits",
        "protected_violations",
        "clarity_delta",
        "reader_preference",
        "problem_reduced",
    }
    identities: set[tuple[str, str, str, int]] = set()
    for index, item in enumerate(outcomes):
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise ValueError(f"Stage 2 outcomes[{index}] fields are invalid")
        identifiers: dict[str, str] = {}
        for field in ("case_id", "generator_id", "reviewer_id"):
            value = item[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Stage 2 outcomes[{index}].{field} must be non-empty text")
            identifiers[field] = value
        if item.get("human") is not True:
            raise ValueError("Stage 2 outcomes must explicitly identify a real human reviewer")
        if identifiers["generator_id"].casefold() == identifiers["reviewer_id"].casefold():
            raise ValueError("a generator cannot review its own rewrite")
        run_number = item["run_number"]
        if isinstance(run_number, bool) or not isinstance(run_number, int) or run_number < 1:
            raise ValueError(f"Stage 2 outcomes[{index}].run_number must be a positive integer")
        rewrite_sha256 = item["rewrite_sha256"]
        if not isinstance(rewrite_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", rewrite_sha256) is None:
            raise ValueError(f"Stage 2 outcomes[{index}].rewrite_sha256 is invalid")
        identity = (
            identifiers["case_id"],
            identifiers["generator_id"].casefold(),
            identifiers["reviewer_id"].casefold(),
            run_number,
        )
        if identity in identities:
            raise ValueError("duplicate Stage 2 outcome rating")
        identities.add(identity)
        for field in ("semantic_preserved", "voice_retained", "problem_reduced"):
            if type(item[field]) is not bool:
                raise ValueError(f"Stage 2 outcomes[{index}].{field} must be a boolean")
        unnecessary = item.get("unnecessary_edits")
        total = item.get("total_edits")
        if isinstance(unnecessary, bool) or isinstance(total, bool) or not isinstance(unnecessary, int) or not isinstance(total, int):
            raise ValueError("edit counts must be integers")
        if unnecessary < 0 or total < 0 or unnecessary > total:
            raise ValueError("unnecessary edits cannot exceed total edits")
        protected = item["protected_violations"]
        if isinstance(protected, bool) or not isinstance(protected, int) or protected < 0:
            raise ValueError("protected_violations must be a nonnegative integer")
        clarity = item["clarity_delta"]
        if (
            isinstance(clarity, bool)
            or not isinstance(clarity, (int, float))
            or not math.isfinite(clarity)
        ):
            raise ValueError("clarity_delta must be a finite number")
        if item["reader_preference"] not in {"revised", "source", "tie"}:
            raise ValueError("reader_preference must be revised, source, or tie")
    count = len(outcomes)
    total_edits = sum(item["total_edits"] for item in outcomes)
    unnecessary_edits = sum(item["unnecessary_edits"] for item in outcomes)
    return {
        "case_count": count,
        "semantic_preservation_rate": _safe_ratio(sum(item.get("semantic_preserved") is True for item in outcomes), count),
        "voice_retention_rate": _safe_ratio(sum(item.get("voice_retained") is True for item in outcomes), count),
        "unnecessary_edit_rate": _safe_ratio(unnecessary_edits, total_edits),
        "protected_region_integrity_rate": _safe_ratio(sum(item.get("protected_violations") == 0 for item in outcomes), count),
        "mean_clarity_delta": _mean(float(item["clarity_delta"]) for item in outcomes),
        "reader_preference_rate": _safe_ratio(sum(item.get("reader_preference") == "revised" for item in outcomes), count),
        "specific_problem_reduction_rate": _safe_ratio(sum(item.get("problem_reduced") is True for item in outcomes), count),
    }
