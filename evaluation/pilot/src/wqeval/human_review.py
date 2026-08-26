"""Strict validation for blinded Stage 1 human-review artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class HumanReviewIntegrityError(ValueError):
    """Raised when a Stage 1 human-review artifact is not independently verifiable."""


_ARTIFACT_FIELDS = {
    "schema_version",
    "reviewers",
    "adjudicator",
    "review_items",
    "reviews",
    "adjudications",
}
_ACTOR_FIELDS = {"reviewer_id", "actor_type", "human"}
_ITEM_FIELDS = {"review_item_id", "prediction"}
_DIAGNOSTIC_COMPONENT_FIELDS = (
    "span_valid",
    "problem_valid",
    "context_valid",
    "severity_valid",
    "operation_valid",
)
_DIAGNOSTIC_VERDICT_FIELDS = (
    "finding_valid",
    *_DIAGNOSTIC_COMPONENT_FIELDS,
)
_RATING_FIELDS = {
    "review_item_id",
    "reviewer_id",
    *_DIAGNOSTIC_VERDICT_FIELDS,
    "meaning_changed",
    "meaning_risk",
}
_GOLD_ITEM_FIELDS = {"review_item_id", "case", "gold_findings"}
_GOLD_RATING_FIELDS = {
    "review_item_id",
    "reviewer_id",
    "span_correct",
    "decision_correct",
    "label_correct",
    "severity_correct",
    "gold_complete",
}
_MEANING_RISKS = {"none", "low", "medium", "high", "critical"}
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_ROSTER_FIELDS = {
    "schema_version",
    "status",
    "attestation_kind",
    "reviewer_ids",
    "adjudicator_id",
    "attested_by",
    "attestation_source",
    "real_humans_confirmed",
}


def _require_exact_fields(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise HumanReviewIntegrityError(f"{label} fields are invalid")
    return value


def _require_nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HumanReviewIntegrityError(f"{label} must be non-empty text")
    return value


def _canonical_json(value: Any, label: str) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise HumanReviewIntegrityError(f"{label} must be finite JSON data") from error


def validate_trusted_human_roster(roster: Any) -> dict[str, Any]:
    """Validate the declared panel identities without claiming they are real people.

    The attestation fields are an external trust root. This function proves only
    that the document is complete, internally consistent, and safe to bind into
    a pre-review anchor.
    """

    roster = _require_exact_fields(roster, _ROSTER_FIELDS, "trusted human roster")
    if (
        roster["schema_version"] != "1.0"
        or roster["status"] != "CONFIRMED"
        or roster["attestation_kind"] != "real_human_identity"
        or type(roster["real_humans_confirmed"]) is not bool
        or roster["real_humans_confirmed"] is not True
    ):
        raise HumanReviewIntegrityError("trusted human roster attestation is invalid")
    _require_nonempty_text(roster["attested_by"], "trusted human roster.attested_by")
    _require_nonempty_text(
        roster["attestation_source"],
        "trusted human roster.attestation_source",
    )
    reviewer_ids = roster["reviewer_ids"]
    if (
        not isinstance(reviewer_ids, list)
        or len(reviewer_ids) != 2
        or any(not isinstance(value, str) or not value.strip() for value in reviewer_ids)
        or len({value.casefold() for value in reviewer_ids}) != 2
    ):
        raise HumanReviewIntegrityError("trusted human roster reviewers are invalid")
    adjudicator_id = _require_nonempty_text(
        roster["adjudicator_id"],
        "trusted human roster.adjudicator_id",
    )
    if adjudicator_id.casefold() in {value.casefold() for value in reviewer_ids}:
        raise HumanReviewIntegrityError(
            "trusted human roster adjudicator must be separate from both reviewers"
        )
    _canonical_json(roster, "trusted human roster")
    return json.loads(_canonical_json(roster, "trusted human roster"))


def trusted_human_roster_sha256(roster: dict[str, Any]) -> str:
    """Return the detached digest callers must preserve before accepting reviews."""

    return hashlib.sha256(
        _canonical_json(roster, "trusted human roster").encode("utf-8")
    ).hexdigest()


def _verify_trusted_human_roster(
    roster: Any,
    expected_sha256: Any,
    *,
    reviewer_ids: list[str],
    adjudicator_id: str,
) -> bool:
    if roster is None and expected_sha256 is None:
        return False
    if roster is None or expected_sha256 is None:
        raise HumanReviewIntegrityError(
            "trusted human roster and its detached SHA-256 must be supplied together"
        )
    if not isinstance(expected_sha256, str) or _HEX_64.fullmatch(expected_sha256) is None:
        raise HumanReviewIntegrityError("expected human roster SHA-256 is invalid")
    roster = validate_trusted_human_roster(roster)
    roster_reviewers = roster["reviewer_ids"]
    if (
        {value.casefold() for value in roster_reviewers}
        != {value.casefold() for value in reviewer_ids}
    ):
        raise HumanReviewIntegrityError("trusted human roster reviewers do not match the panel")
    roster_adjudicator = _require_nonempty_text(
        roster["adjudicator_id"],
        "trusted human roster.adjudicator_id",
    )
    if roster_adjudicator.casefold() != adjudicator_id.casefold():
        raise HumanReviewIntegrityError("trusted human roster adjudicator does not match the panel")
    if trusted_human_roster_sha256(roster) != expected_sha256:
        raise HumanReviewIntegrityError("trusted human roster does not match its detached SHA-256")
    return True


def _validate_human_actor(value: Any, label: str) -> str:
    actor = _require_exact_fields(value, _ACTOR_FIELDS, label)
    reviewer_id = _require_nonempty_text(actor["reviewer_id"], f"{label}.reviewer_id")
    if actor["actor_type"] != "human":
        raise HumanReviewIntegrityError(f"{label} must declare actor_type human")
    if type(actor["human"]) is not bool or actor["human"] is not True:
        raise HumanReviewIntegrityError(f"{label}.human must be the boolean true")
    return reviewer_id


def _validate_rating(
    value: Any,
    label: str,
) -> tuple[str, str, dict[str, bool], bool, str]:
    rating = _require_exact_fields(value, _RATING_FIELDS, label)
    review_item_id = _require_nonempty_text(rating["review_item_id"], f"{label}.review_item_id")
    reviewer_id = _require_nonempty_text(rating["reviewer_id"], f"{label}.reviewer_id")
    verdicts: dict[str, bool] = {}
    for field in sorted(_DIAGNOSTIC_VERDICT_FIELDS):
        verdict = rating[field]
        if type(verdict) is not bool:
            raise HumanReviewIntegrityError(f"{label}.{field} must be a boolean")
        verdicts[field] = verdict
    if verdicts["finding_valid"] != all(
        verdicts[field] for field in _DIAGNOSTIC_COMPONENT_FIELDS
    ):
        raise HumanReviewIntegrityError(
            f"{label}.finding_valid must summarize all diagnostic components"
        )
    meaning_changed = rating["meaning_changed"]
    if type(meaning_changed) is not bool:
        raise HumanReviewIntegrityError(f"{label}.meaning_changed must be a boolean")
    meaning_risk = rating["meaning_risk"]
    if meaning_risk not in _MEANING_RISKS:
        raise HumanReviewIntegrityError(f"{label}.meaning_risk is invalid")
    if meaning_changed != (meaning_risk != "none"):
        raise HumanReviewIntegrityError(
            f"{label}.meaning_changed and meaning_risk contradict each other"
        )
    return review_item_id, reviewer_id, verdicts, meaning_changed, meaning_risk


def _binary_agreement(
    left: list[bool],
    right: list[bool],
) -> tuple[float | None, float | None]:
    if not left or len(left) != len(right):
        return None, None
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    expected = sum(
        (left.count(label) / len(left)) * (right.count(label) / len(right))
        for label in (False, True)
    )
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)
    return observed, kappa


def _validate_gold_rating(value: Any, label: str) -> tuple[str, str, dict[str, bool]]:
    rating = _require_exact_fields(value, _GOLD_RATING_FIELDS, label)
    review_item_id = _require_nonempty_text(rating["review_item_id"], f"{label}.review_item_id")
    reviewer_id = _require_nonempty_text(rating["reviewer_id"], f"{label}.reviewer_id")
    verdicts: dict[str, bool] = {}
    for field in sorted(_GOLD_RATING_FIELDS - {"review_item_id", "reviewer_id"}):
        value = rating[field]
        if type(value) is not bool:
            raise HumanReviewIntegrityError(f"{label}.{field} must be a boolean")
        verdicts[field] = value
    return review_item_id, reviewer_id, verdicts


def _verify_human_panel(artifact: dict[str, Any]) -> tuple[list[str], str]:
    reviewers = artifact["reviewers"]
    if not isinstance(reviewers, list) or len(reviewers) != 2:
        raise HumanReviewIntegrityError("exactly two independent human reviewers are required")
    reviewer_ids = [
        _validate_human_actor(actor, f"reviewers[{index}]")
        for index, actor in enumerate(reviewers)
    ]
    normalized_reviewer_ids = [reviewer_id.casefold() for reviewer_id in reviewer_ids]
    if len(set(normalized_reviewer_ids)) != 2:
        raise HumanReviewIntegrityError("human reviewer identities must be unique")

    adjudicator_id = _validate_human_actor(artifact["adjudicator"], "adjudicator")
    if adjudicator_id.casefold() in normalized_reviewer_ids:
        raise HumanReviewIntegrityError("the human adjudicator must be separate from both reviewers")
    return reviewer_ids, adjudicator_id


def verify_stage1_human_review_artifact(
    artifact: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    trusted_human_roster: dict[str, Any] | None = None,
    expected_human_roster_sha256: str | None = None,
) -> dict[str, Any]:
    """Verify complete independent panels and return adjudicated meaning metrics."""

    artifact = _require_exact_fields(artifact, _ARTIFACT_FIELDS, "human review artifact")
    if artifact["schema_version"] != "1.0":
        raise HumanReviewIntegrityError("human review artifact schema_version must be 1.0")
    if not isinstance(predictions, list):
        raise HumanReviewIntegrityError("predictions must be a list")

    reviewer_ids, adjudicator_id = _verify_human_panel(artifact)
    human_identity_attested = _verify_trusted_human_roster(
        trusted_human_roster,
        expected_human_roster_sha256,
        reviewer_ids=reviewer_ids,
        adjudicator_id=adjudicator_id,
    )
    normalized_reviewer_ids = [reviewer_id.casefold() for reviewer_id in reviewer_ids]

    expected_predictions: dict[tuple[str | None, int | None, str, str], str] = {}
    generator_ids: set[str] = set()
    for index, prediction in enumerate(predictions):
        if not isinstance(prediction, dict):
            raise HumanReviewIntegrityError(f"predictions[{index}] must be an object")
        decision = prediction.get("decision")
        if decision not in {"CHANGE", "KEEP"}:
            raise HumanReviewIntegrityError(f"predictions[{index}].decision is invalid")
        case_id = _require_nonempty_text(prediction.get("case_id"), f"predictions[{index}].case_id")
        finding_id = _require_nonempty_text(prediction.get("finding_id"), f"predictions[{index}].finding_id")
        system_id = prediction.get("system_id", prediction.get("generator_id"))
        if system_id is not None and (not isinstance(system_id, str) or not system_id):
            raise HumanReviewIntegrityError(f"predictions[{index}].system identity is invalid")
        run_number = prediction.get("run_number")
        if run_number is not None and (
            isinstance(run_number, bool) or not isinstance(run_number, int) or run_number < 1
        ):
            raise HumanReviewIntegrityError(f"predictions[{index}].run_number is invalid")
        key = (system_id, run_number, case_id, finding_id)
        if key in expected_predictions:
            raise HumanReviewIntegrityError(
                f"duplicate prediction finding identity: {system_id}:{run_number}:{case_id}:{finding_id}"
            )
        canonical = _canonical_json(prediction, f"predictions[{index}]")
        if decision == "CHANGE":
            expected_predictions[key] = canonical
        for identity_field in ("generator_id", "system_id"):
            generator_id = prediction.get(identity_field)
            if isinstance(generator_id, str) and generator_id:
                generator_ids.add(generator_id.casefold())

    human_ids = set(normalized_reviewer_ids) | {adjudicator_id.casefold()}
    if human_ids & generator_ids:
        raise HumanReviewIntegrityError("a prediction generator cannot serve as reviewer or adjudicator")

    review_items = artifact["review_items"]
    if not isinstance(review_items, list):
        raise HumanReviewIntegrityError("review_items must be a list")
    item_ids: set[str] = set()
    normalized_item_ids: set[str] = set()
    bound_predictions: set[tuple[str | None, int | None, str, str]] = set()
    for index, value in enumerate(review_items):
        item = _require_exact_fields(value, _ITEM_FIELDS, f"review_items[{index}]")
        item_id = _require_nonempty_text(item["review_item_id"], f"review_items[{index}].review_item_id")
        if item_id.casefold() in normalized_item_ids:
            raise HumanReviewIntegrityError(f"duplicate review_item_id: {item_id}")
        item_ids.add(item_id)
        normalized_item_ids.add(item_id.casefold())

        prediction = item["prediction"]
        if not isinstance(prediction, dict) or prediction.get("decision") != "CHANGE":
            raise HumanReviewIntegrityError(f"review_items[{index}] must bind a CHANGE prediction")
        case_id = _require_nonempty_text(prediction.get("case_id"), f"review_items[{index}].prediction.case_id")
        finding_id = _require_nonempty_text(
            prediction.get("finding_id"),
            f"review_items[{index}].prediction.finding_id",
        )
        system_id = prediction.get("system_id", prediction.get("generator_id"))
        run_number = prediction.get("run_number")
        key = (system_id, run_number, case_id, finding_id)
        expected = expected_predictions.get(key)
        if expected is None or _canonical_json(prediction, f"review_items[{index}].prediction") != expected:
            raise HumanReviewIntegrityError(f"review item is not bound to preserved prediction: {case_id}:{finding_id}")
        if key in bound_predictions:
            raise HumanReviewIntegrityError(f"prediction is bound more than once: {case_id}:{finding_id}")
        bound_predictions.add(key)
    if bound_predictions != set(expected_predictions):
        raise HumanReviewIntegrityError("review_items must bind every CHANGE prediction exactly once")

    reviews = artifact["reviews"]
    if not isinstance(reviews, list):
        raise HumanReviewIntegrityError("reviews must be a list")
    observed_review_pairs: set[tuple[str, str]] = set()
    reviewer_id_set = set(reviewer_ids)
    finding_valid_by_reviewer: dict[str, dict[str, bool]] = {
        reviewer_id: {} for reviewer_id in reviewer_ids
    }
    for index, value in enumerate(reviews):
        item_id, reviewer_id, verdicts, _, _ = _validate_rating(value, f"reviews[{index}]")
        if item_id not in item_ids:
            raise HumanReviewIntegrityError(f"review is unbound to a review item: {item_id}")
        if reviewer_id not in reviewer_id_set:
            raise HumanReviewIntegrityError(f"review is assigned to an undeclared reviewer: {reviewer_id}")
        pair = (reviewer_id, item_id)
        if pair in observed_review_pairs:
            raise HumanReviewIntegrityError(f"duplicate review: {reviewer_id}:{item_id}")
        observed_review_pairs.add(pair)
        finding_valid_by_reviewer[reviewer_id][item_id] = verdicts["finding_valid"]
    expected_review_pairs = {(reviewer_id, item_id) for reviewer_id in reviewer_ids for item_id in item_ids}
    if observed_review_pairs != expected_review_pairs:
        raise HumanReviewIntegrityError("both reviewers must review every item exactly once")

    adjudications = artifact["adjudications"]
    if not isinstance(adjudications, list):
        raise HumanReviewIntegrityError("adjudications must be a list")
    observed_adjudications: set[str] = set()
    changed_count = 0
    critical_count = 0
    complete_accepted_count = 0
    component_accepted_counts = {
        field: 0 for field in _DIAGNOSTIC_VERDICT_FIELDS
    }
    for index, value in enumerate(adjudications):
        item_id, reviewer_id, verdicts, meaning_changed, meaning_risk = _validate_rating(
            value,
            f"adjudications[{index}]",
        )
        if item_id not in item_ids:
            raise HumanReviewIntegrityError(f"adjudication is unbound to a review item: {item_id}")
        if reviewer_id != adjudicator_id:
            raise HumanReviewIntegrityError("adjudication must be authored by the declared adjudicator")
        if item_id in observed_adjudications:
            raise HumanReviewIntegrityError(f"duplicate adjudication: {item_id}")
        observed_adjudications.add(item_id)
        changed_count += meaning_changed
        critical_count += meaning_changed and meaning_risk == "critical"
        complete_accepted_count += all(
            verdicts[field] for field in _DIAGNOSTIC_VERDICT_FIELDS
        )
        for field in _DIAGNOSTIC_VERDICT_FIELDS:
            component_accepted_counts[field] += verdicts[field]
    if observed_adjudications != item_ids:
        raise HumanReviewIntegrityError("the adjudicator must adjudicate every item exactly once")

    reviewed_count = len(item_ids)
    ordered_items = sorted(item_ids)
    left = [finding_valid_by_reviewer[reviewer_ids[0]][item_id] for item_id in ordered_items]
    right = [finding_valid_by_reviewer[reviewer_ids[1]][item_id] for item_id in ordered_items]
    agreement, kappa = _binary_agreement(left, right)
    complete_acceptance_rate = (
        complete_accepted_count / reviewed_count if reviewed_count else None
    )
    component_acceptance_rates = {
        field: accepted / reviewed_count if reviewed_count else None
        for field, accepted in component_accepted_counts.items()
    }
    return {
        "review_structure_verified": True,
        "human_identity_attested": human_identity_attested,
        "human_review_verified": human_identity_attested,
        "human_adjudicated": human_identity_attested,
        "meaning_reviewed_suggestions": reviewed_count,
        "diagnostic_meaning_change_rate": changed_count / reviewed_count if reviewed_count else None,
        "critical_meaning_risk": critical_count,
        "human_complete_acceptance_rate": complete_acceptance_rate,
        "human_finding_acceptance_rate": complete_acceptance_rate,
        "human_component_acceptance_rates": component_acceptance_rates,
        "human_reviewer_finding_valid_agreement": agreement,
        "human_reviewer_finding_valid_kappa": kappa,
    }


def verify_stage1_human_gold_review_artifact(
    artifact: dict[str, Any],
    cases: list[dict[str, Any]],
    gold_findings: list[dict[str, Any]],
    *,
    trusted_human_roster: dict[str, Any] | None = None,
    expected_human_roster_sha256: str | None = None,
) -> dict[str, Any]:
    """Verify that two humans and a separate adjudicator approved every gold finding."""

    artifact = _require_exact_fields(artifact, _ARTIFACT_FIELDS, "human gold review artifact")
    if artifact["schema_version"] != "1.0":
        raise HumanReviewIntegrityError("human gold review artifact schema_version must be 1.0")
    if not isinstance(cases, list) or not cases:
        raise HumanReviewIntegrityError("cases must be a non-empty list")
    if not isinstance(gold_findings, list):
        raise HumanReviewIntegrityError("gold_findings must be a list")

    reviewer_ids, adjudicator_id = _verify_human_panel(artifact)
    human_identity_attested = _verify_trusted_human_roster(
        trusted_human_roster,
        expected_human_roster_sha256,
        reviewer_ids=reviewer_ids,
        adjudicator_id=adjudicator_id,
    )
    expected_cases: dict[str, str] = {}
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise HumanReviewIntegrityError(f"cases[{index}] must be an object")
        case_id = _require_nonempty_text(case.get("case_id"), f"cases[{index}].case_id")
        if case_id in expected_cases:
            raise HumanReviewIntegrityError(f"duplicate case identity: {case_id}")
        expected_cases[case_id] = _canonical_json(case, f"cases[{index}]")

    expected_gold: dict[tuple[str, str], str] = {}
    expected_gold_by_case: dict[str, dict[str, str]] = {
        case_id: {} for case_id in expected_cases
    }
    for index, finding in enumerate(gold_findings):
        if not isinstance(finding, dict):
            raise HumanReviewIntegrityError(f"gold_findings[{index}] must be an object")
        case_id = _require_nonempty_text(finding.get("case_id"), f"gold_findings[{index}].case_id")
        finding_id = _require_nonempty_text(
            finding.get("finding_id"),
            f"gold_findings[{index}].finding_id",
        )
        key = (case_id, finding_id)
        if case_id not in expected_cases:
            raise HumanReviewIntegrityError(f"gold finding refers to an unknown case: {case_id}:{finding_id}")
        if key in expected_gold:
            raise HumanReviewIntegrityError(f"duplicate gold finding identity: {case_id}:{finding_id}")
        canonical = _canonical_json(finding, f"gold_findings[{index}]")
        expected_gold[key] = canonical
        expected_gold_by_case[case_id][finding_id] = canonical

    review_items = artifact["review_items"]
    if not isinstance(review_items, list):
        raise HumanReviewIntegrityError("review_items must be a list")
    item_ids: set[str] = set()
    normalized_item_ids: set[str] = set()
    bound_cases: set[str] = set()
    bound_gold: set[tuple[str, str]] = set()
    for index, value in enumerate(review_items):
        item = _require_exact_fields(value, _GOLD_ITEM_FIELDS, f"review_items[{index}]")
        item_id = _require_nonempty_text(item["review_item_id"], f"review_items[{index}].review_item_id")
        if item_id.casefold() in normalized_item_ids:
            raise HumanReviewIntegrityError(f"duplicate review_item_id: {item_id}")
        item_ids.add(item_id)
        normalized_item_ids.add(item_id.casefold())

        case = item["case"]
        if not isinstance(case, dict):
            raise HumanReviewIntegrityError(f"review_items[{index}].case must be an object")
        case_id = _require_nonempty_text(case.get("case_id"), f"review_items[{index}].case.case_id")
        expected_case = expected_cases.get(case_id)
        if expected_case is None or _canonical_json(case, f"review_items[{index}].case") != expected_case:
            raise HumanReviewIntegrityError(f"review item is not bound to a preserved case: {case_id}")
        if case_id in bound_cases:
            raise HumanReviewIntegrityError(f"case is bound more than once: {case_id}")
        bound_cases.add(case_id)

        findings = item["gold_findings"]
        if not isinstance(findings, list):
            raise HumanReviewIntegrityError(f"review_items[{index}].gold_findings must be a list")
        observed_for_case: dict[str, str] = {}
        for finding_index, finding in enumerate(findings):
            label = f"review_items[{index}].gold_findings[{finding_index}]"
            if not isinstance(finding, dict):
                raise HumanReviewIntegrityError(f"{label} must be an object")
            finding_case_id = _require_nonempty_text(finding.get("case_id"), f"{label}.case_id")
            finding_id = _require_nonempty_text(finding.get("finding_id"), f"{label}.finding_id")
            if finding_case_id != case_id:
                raise HumanReviewIntegrityError(f"{label} belongs to a different case")
            if finding_id in observed_for_case:
                raise HumanReviewIntegrityError(f"duplicate gold finding in review item: {case_id}:{finding_id}")
            canonical = _canonical_json(finding, label)
            expected = expected_gold_by_case[case_id].get(finding_id)
            if expected is None or canonical != expected:
                raise HumanReviewIntegrityError(
                    f"review item is not bound to preserved gold: {case_id}:{finding_id}"
                )
            observed_for_case[finding_id] = canonical
            bound_gold.add((case_id, finding_id))
        if observed_for_case != expected_gold_by_case[case_id]:
            raise HumanReviewIntegrityError(f"review item does not contain the complete gold for case: {case_id}")
    if bound_cases != set(expected_cases):
        raise HumanReviewIntegrityError("review_items must bind every case exactly once")
    if bound_gold != set(expected_gold):
        raise HumanReviewIntegrityError("review_items must bind every gold finding exactly once")

    reviews = artifact["reviews"]
    if not isinstance(reviews, list):
        raise HumanReviewIntegrityError("reviews must be a list")
    reviewer_id_set = set(reviewer_ids)
    observed_review_pairs: set[tuple[str, str]] = set()
    completeness_by_reviewer: dict[str, dict[str, bool]] = {
        reviewer_id: {} for reviewer_id in reviewer_ids
    }
    for index, value in enumerate(reviews):
        item_id, reviewer_id, verdicts = _validate_gold_rating(value, f"reviews[{index}]")
        if item_id not in item_ids:
            raise HumanReviewIntegrityError(f"review is unbound to a review item: {item_id}")
        if reviewer_id not in reviewer_id_set:
            raise HumanReviewIntegrityError(f"review is assigned to an undeclared reviewer: {reviewer_id}")
        pair = (reviewer_id, item_id)
        if pair in observed_review_pairs:
            raise HumanReviewIntegrityError(f"duplicate review: {reviewer_id}:{item_id}")
        observed_review_pairs.add(pair)
        completeness_by_reviewer[reviewer_id][item_id] = verdicts["gold_complete"]
    expected_review_pairs = {(reviewer_id, item_id) for reviewer_id in reviewer_ids for item_id in item_ids}
    if observed_review_pairs != expected_review_pairs:
        raise HumanReviewIntegrityError("both reviewers must review every gold item exactly once")

    adjudications = artifact["adjudications"]
    if not isinstance(adjudications, list):
        raise HumanReviewIntegrityError("adjudications must be a list")
    observed_adjudications: set[str] = set()
    approved = True
    for index, value in enumerate(adjudications):
        item_id, reviewer_id, verdicts = _validate_gold_rating(value, f"adjudications[{index}]")
        if item_id not in item_ids:
            raise HumanReviewIntegrityError(f"adjudication is unbound to a review item: {item_id}")
        if reviewer_id != adjudicator_id:
            raise HumanReviewIntegrityError("adjudication must be authored by the declared adjudicator")
        if item_id in observed_adjudications:
            raise HumanReviewIntegrityError(f"duplicate adjudication: {item_id}")
        observed_adjudications.add(item_id)
        approved = approved and all(verdicts.values())
    if observed_adjudications != item_ids:
        raise HumanReviewIntegrityError("the adjudicator must adjudicate every gold item exactly once")

    ordered_items = sorted(item_ids)
    left = [completeness_by_reviewer[reviewer_ids[0]][item_id] for item_id in ordered_items]
    right = [completeness_by_reviewer[reviewer_ids[1]][item_id] for item_id in ordered_items]
    agreement, kappa = _binary_agreement(left, right)

    return {
        "gold_review_structure_verified": True,
        "human_identity_attested": human_identity_attested,
        "human_gold_review_verified": human_identity_attested,
        "human_gold_adjudicated": human_identity_attested,
        "human_gold_approved": approved,
        "human_gold_reviewed_cases": len(item_ids),
        "human_gold_reviewed_findings": len(expected_gold),
        "human_gold_reviewer_completeness_agreement": agreement,
        "human_gold_reviewer_completeness_kappa": kappa,
    }
