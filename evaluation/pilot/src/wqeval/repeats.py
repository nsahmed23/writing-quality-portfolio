"""Aggregation for independent repeated Stage 1 runs."""

from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
from typing import Any

from .corpus_evidence import VerifiedScoringCorpus
from .reconciliation import VerifiedStage1Run, reconcile_stage1_outputs
from .scoring import exact_finding_key, score_stage1
from .validation import validate_case, validate_finding


def _mean_defined(values: list[float | None]) -> float | None:
    defined = [value for value in values if value is not None]
    return sum(defined) / len(defined) if defined else None


def _range_defined(values: list[float | None]) -> dict[str, float] | None:
    defined = [value for value in values if value is not None]
    return {"min": min(defined), "max": max(defined)} if defined else None


def _index_case_panel(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for source_case in records:
        validate_case(source_case)
        case_id = source_case["case_id"]
        if case_id in indexed:
            raise ValueError(f"duplicate case in frozen panel: {case_id}")
        indexed[case_id] = source_case
    return indexed


def aggregate_stage1_runs(
    corpus: VerifiedScoringCorpus,
    *,
    run_root: str | Path,
    expected_output_evidence_sha256: str,
    system_id: str,
    expected_runs: int,
) -> dict[str, Any]:
    """Score each run separately and report exact finding stability.

    ``pass_at_1`` uses the preregistered first run. ``pass_at_3_any`` is the
    share of gold CHANGE finding occurrences detected in at least one run, and
    ``pass_power_3`` is the share detected in every run. The names retain the
    protocol terminology even when ``expected_runs`` is used for validation.
    Predictions are never pooled for ordinary precision or false-positive
    counts.
    """

    if not isinstance(corpus, VerifiedScoringCorpus):
        raise TypeError("corpus must be a VerifiedScoringCorpus")
    corpus.assert_verified()
    gold = list(corpus.gold)
    if isinstance(expected_runs, bool) or not isinstance(expected_runs, int) or expected_runs < 1:
        raise ValueError("expected_runs must be a positive integer")
    if not isinstance(system_id, str) or not system_id:
        raise ValueError("system_id must be non-empty text")
    expected_panel = set(range(1, expected_runs + 1))
    reconciliation = reconcile_stage1_outputs(
        run_root,
        expected_output_evidence_sha256=expected_output_evidence_sha256,
    )
    selected = [run for run in reconciliation["runs"] if run.system_id == system_id]
    verified_runs: dict[int, VerifiedStage1Run] = {}
    for run in selected:
        if run.run_number in verified_runs:
            raise ValueError("repeated scoring has a duplicate verified run")
        verified_runs[run.run_number] = run
    if set(verified_runs) != expected_panel:
        raise ValueError("repeated scoring requires the exact run panel")

    ordered_evidence = [verified_runs[number] for number in sorted(verified_runs)]
    first_cases = list(ordered_evidence[0].cases)
    case_by_id = _index_case_panel(first_cases)
    if case_by_id != _index_case_panel(list(corpus.cases)):
        raise ValueError("repeated scoring case panel differs from the verified corpus")
    for evidence in ordered_evidence[1:]:
        if _index_case_panel(list(evidence.cases)) != case_by_id:
            raise ValueError("repeated scoring requires an identical verified case panel")
    cases = [case_by_id[case_id] for case_id in sorted(case_by_id)]
    for gold_finding in gold:
        case_id = gold_finding.get("case_id")
        if case_id not in case_by_id:
            raise ValueError(f"gold finding references unknown case: {case_id}")
        validate_finding(gold_finding, case_by_id[case_id])

    per_run: dict[str, dict[str, Any]] = {}
    match_counters: dict[int, Counter[tuple[str, int, int, str]]] = {}
    invalid_run_numbers: list[int] = []
    for run_number in sorted(verified_runs):
        evidence = verified_runs[run_number]
        if evidence.system_id != system_id or evidence.run_number != run_number:
            raise ValueError("verified run evidence identity is invalid")
        if _index_case_panel(list(evidence.cases)) != case_by_id:
            raise ValueError("verified run case panel changed during scoring")
        if evidence.status == "invalid":
            if (
                evidence.record_count != 0
                or evidence.normalized_payload is not None
                or evidence.normalized_sha256 is not None
                or evidence.normalized_byte_count is not None
                or not isinstance(evidence.error_type, str)
                or not isinstance(evidence.error_message, str)
            ):
                raise ValueError("verified invalid run evidence is inconsistent")
            invalid_run_numbers.append(run_number)
            per_run[str(run_number)] = {
                "status": "invalid",
                "error_type": evidence.error_type,
                "error_message": evidence.error_message,
            }
            match_counters[run_number] = Counter()
            continue
        if evidence.status != "valid":
            raise ValueError("verified run evidence status is invalid")
        if evidence.record_count != len(cases):
            raise ValueError("verified run record_count does not match the frozen case panel")
        if (
            evidence.normalized_payload is None
            or evidence.normalized_byte_count is None
            or evidence.normalized_sha256 is None
            or len(evidence.normalized_payload) != evidence.normalized_byte_count
            or hashlib.sha256(evidence.normalized_payload).hexdigest() != evidence.normalized_sha256
        ):
            raise ValueError("verified run normalized payload no longer matches its receipt")
        predictions = list(evidence.predictions)
        for prediction in predictions:
            case_id = prediction.get("case_id")
            if case_id not in case_by_id:
                raise ValueError(f"prediction references unknown case: {case_id}")
            if prediction.get("run_number") != run_number:
                raise ValueError("prediction run_number does not match its run panel")
            if prediction.get("system_id") != system_id:
                raise ValueError("prediction system_id does not match the requested system")
            validate_finding(prediction, case_by_id[case_id])
        per_run[str(run_number)] = {
            "status": "valid",
            **score_stage1(cases, gold, predictions),
        }
        match_counters[run_number] = Counter(
            exact_finding_key(item) for item in predictions if item.get("decision") == "CHANGE"
        )

    gold_counter = Counter(exact_finding_key(item) for item in gold if item.get("decision") == "CHANGE")
    gold_occurrences = [
        (key, occurrence)
        for key in sorted(gold_counter, key=lambda value: tuple(str(part) for part in value))
        for occurrence in range(1, gold_counter[key] + 1)
    ]
    if invalid_run_numbers:
        pass_at_1 = None
        pass_at_3_any = None
        pass_power_3 = None
        undefined = "one or more runs failed schema validation"
    elif gold_occurrences:
        first_matches = sum(match_counters[1][key] >= occurrence for key, occurrence in gold_occurrences)
        any_matches = sum(
            any(match_counters[run][key] >= occurrence for run in expected_panel)
            for key, occurrence in gold_occurrences
        )
        all_matches = sum(
            all(match_counters[run][key] >= occurrence for run in expected_panel)
            for key, occurrence in gold_occurrences
        )
        denominator = len(gold_occurrences)
        pass_at_1 = first_matches / denominator
        pass_at_3_any = any_matches / denominator
        pass_power_3 = all_matches / denominator
        undefined = None
    else:
        pass_at_1 = None
        pass_at_3_any = None
        pass_power_3 = None
        undefined = "no gold CHANGE findings"

    precisions = [
        per_run[str(run)].get("precision")
        for run in sorted(expected_panel)
    ]
    recalls = [
        per_run[str(run)].get("recall")
        for run in sorted(expected_panel)
    ]
    return {
        "system_id": system_id,
        "output_evidence_sha256": expected_output_evidence_sha256,
        "expected_runs": expected_runs,
        "run_numbers": sorted(expected_panel),
        "valid_run_numbers": sorted(expected_panel - set(invalid_run_numbers)),
        "invalid_run_numbers": invalid_run_numbers,
        "schema_compliance_rate": (expected_runs - len(invalid_run_numbers)) / expected_runs,
        "gold_change_findings": len(gold_occurrences),
        "pass_at_1": pass_at_1,
        "pass_at_3_any": pass_at_3_any,
        "pass_power_3": pass_power_3,
        "undefined_repeat_metrics": undefined,
        "mean_exact_precision": _mean_defined(precisions),
        "mean_exact_recall": _mean_defined(recalls),
        "precision_defined_run_count": sum(value is not None for value in precisions),
        "precision_undefined_run_count": sum(value is None for value in precisions),
        "recall_defined_run_count": sum(value is not None for value in recalls),
        "recall_undefined_run_count": sum(value is None for value in recalls),
        "exact_precision_range": _range_defined(precisions),
        "exact_recall_range": _range_defined(recalls),
        "verified_runs": {
            str(run): {
                "job_id": verified_runs[run].job_id,
                "system_id": verified_runs[run].system_id,
                "run_number": verified_runs[run].run_number,
                "status": verified_runs[run].status,
                "record_count": verified_runs[run].record_count,
                "raw_sha256": verified_runs[run].raw_sha256,
                "normalized_sha256": verified_runs[run].normalized_sha256,
                "normalized_byte_count": verified_runs[run].normalized_byte_count,
            }
            for run in sorted(expected_panel)
        },
        "per_run": per_run,
    }
