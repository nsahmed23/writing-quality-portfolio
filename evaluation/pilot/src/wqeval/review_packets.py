"""Build blinded, hash-bound Stage 1 human-review packets."""

from __future__ import annotations

import copy
import hashlib
import json
import random
import re
from typing import Any

from .blinding import IdentityLeakError, assert_no_identity_leak, blind_review_records, build_blind_map
from .human_review import (
    HumanReviewIntegrityError,
    trusted_human_roster_sha256,
    verify_stage1_human_gold_review_artifact,
    verify_stage1_human_review_artifact,
)
from .roster_anchor import (
    HumanRosterAnchorError,
    human_roster_anchor_sha256,
    verify_human_roster_anchor,
)


class ReviewPacketError(ValueError):
    """Raised when a review packet cannot be built or verified safely."""


_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_DIAGNOSTIC_TEMPLATE_FIELDS = (
    "finding_valid",
    "span_valid",
    "problem_valid",
    "context_valid",
    "severity_valid",
    "operation_valid",
    "meaning_changed",
    "meaning_risk",
)
_GOLD_TEMPLATE_FIELDS = (
    "span_correct",
    "decision_correct",
    "label_correct",
    "severity_correct",
    "gold_complete",
)
_ARTIFACT_NAMES = (
    "diagnostic_public",
    "diagnostic_private",
    "diagnostic_reviewer_template",
    "diagnostic_adjudicator_template",
    "gold_public",
    "gold_private",
    "gold_reviewer_template",
    "gold_adjudicator_template",
)
_SOURCE_ARTIFACT_NAMES = (
    "diagnostic_public",
    "diagnostic_private",
    "gold_public",
    "gold_private",
)
_DERIVED_ARTIFACT_NAMES = tuple(
    name for name in _ARTIFACT_NAMES if name not in _SOURCE_ARTIFACT_NAMES
)
_BINDING_FIELDS = (
    "packet_id",
    "public_packet_sha256",
    "review_item_sha256",
)
_COUNT_FIELDS = {
    "cases",
    "gold_findings",
    "predictions",
    "diagnostic_review_items",
    "gold_review_items",
}
_MANIFEST_FIELDS = {
    "schema_version",
    "packet_kind",
    "packet_id",
    "seed",
    "run_id",
    "status",
    "human_roster_anchor_sha256",
    "evidence",
    "counts",
    "rating_contract",
    "source_artifact_sha256",
    "artifact_sha256",
}
_COMPLETED_SOURCE_MANIFEST_FIELDS = _MANIFEST_FIELDS - {"artifact_sha256"}
_RATING_CONTRACT = {
    "schema_version": "2.1",
    "contract_id": "stage1-bound-rating/2.1",
    "binding_fields": list(_BINDING_FIELDS),
    "diagnostic_verdict_fields": list(_DIAGNOSTIC_TEMPLATE_FIELDS),
    "gold_verdict_fields": list(_GOLD_TEMPLATE_FIELDS),
}


def _canonical_bytes(value: Any, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ReviewPacketError(f"{label} must be finite JSON data") from error


def _digest(value: Any, *, label: str) -> str:
    return hashlib.sha256(_canonical_bytes(value, label=label)).hexdigest()


def _nonempty_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewPacketError(f"{label} must be non-empty text")
    return value


def _validate_evidence(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ReviewPacketError("evidence must be a non-empty object")
    evidence: dict[str, str] = {}
    for key, digest in sorted(value.items()):
        key = _nonempty_text(key, label="evidence key")
        if not isinstance(digest, str) or _HEX_64.fullmatch(digest) is None:
            raise ReviewPacketError(f"evidence.{key} must be a lowercase SHA-256 digest")
        evidence[key] = digest
    return evidence


def _require_digest(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _HEX_64.fullmatch(value) is None:
        raise ReviewPacketError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _packet_identity_core(
    *,
    seed: int,
    run_id: str,
    human_roster_anchor_sha256: str,
    evidence: dict[str, str],
    counts: dict[str, int],
    source_artifact_sha256: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "packet_kind": "stage1_review_panel",
        "seed": seed,
        "run_id": run_id,
        "status": "PENDING_HUMAN_REVIEW",
        "human_roster_anchor_sha256": human_roster_anchor_sha256,
        "evidence": evidence,
        "counts": counts,
        "rating_contract": copy.deepcopy(_RATING_CONTRACT),
        "source_artifact_sha256": source_artifact_sha256,
    }


def _bound_template(
    *,
    packet_id: str | None,
    public_packet_sha256: str,
    review_item_id: str,
    review_item_sha256: str,
    verdict_fields: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "packet_id": packet_id,
        "public_packet_sha256": public_packet_sha256,
        "review_item_sha256": review_item_sha256,
        "review_item_id": review_item_id,
        "reviewer_id": None,
        **{field: None for field in verdict_fields},
    }


def _indexed_cases(cases: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(cases, list) or not cases:
        raise ReviewPacketError("cases must be a non-empty list")
    indexed: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(cases):
        if not isinstance(value, dict):
            raise ReviewPacketError(f"cases[{index}] must be an object")
        case_id = _nonempty_text(value.get("case_id"), label=f"cases[{index}].case_id")
        if case_id in indexed:
            raise ReviewPacketError(f"duplicate case_id: {case_id}")
        _canonical_bytes(value, label=f"cases[{index}]")
        indexed[case_id] = copy.deepcopy(value)
    return indexed


def _indexed_gold(
    gold_findings: Any,
    cases: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(gold_findings, list):
        raise ReviewPacketError("gold_findings must be a list")
    grouped: dict[str, list[dict[str, Any]]] = {case_id: [] for case_id in cases}
    identities: set[tuple[str, str]] = set()
    for index, value in enumerate(gold_findings):
        if not isinstance(value, dict):
            raise ReviewPacketError(f"gold_findings[{index}] must be an object")
        case_id = _nonempty_text(value.get("case_id"), label=f"gold_findings[{index}].case_id")
        finding_id = _nonempty_text(value.get("finding_id"), label=f"gold_findings[{index}].finding_id")
        if case_id not in cases:
            raise ReviewPacketError(f"gold finding is unbound to a case: {case_id}:{finding_id}")
        identity = (case_id, finding_id)
        if identity in identities:
            raise ReviewPacketError(f"duplicate gold finding: {case_id}:{finding_id}")
        identities.add(identity)
        _canonical_bytes(value, label=f"gold_findings[{index}]")
        grouped[case_id].append(copy.deepcopy(value))
    for values in grouped.values():
        values.sort(key=lambda item: str(item["finding_id"]))
    return grouped


def _indexed_predictions(
    predictions: Any,
    cases: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(predictions, list):
        raise ReviewPacketError("predictions must be a list")
    indexed: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    systems: set[str] = set()
    for index, value in enumerate(predictions):
        if not isinstance(value, dict):
            raise ReviewPacketError(f"predictions[{index}] must be an object")
        system_id = _nonempty_text(value.get("system_id"), label=f"predictions[{index}].system_id")
        case_id = _nonempty_text(value.get("case_id"), label=f"predictions[{index}].case_id")
        finding_id = _nonempty_text(value.get("finding_id"), label=f"predictions[{index}].finding_id")
        run_number = value.get("run_number")
        if isinstance(run_number, bool) or not isinstance(run_number, int) or run_number < 1:
            raise ReviewPacketError(f"predictions[{index}].run_number is invalid")
        if case_id not in cases:
            raise ReviewPacketError(f"prediction is unbound to a case: {case_id}:{finding_id}")
        if value.get("decision") not in {"CHANGE", "KEEP"}:
            raise ReviewPacketError(f"predictions[{index}].decision is invalid")
        identity = (system_id, run_number, case_id, finding_id)
        if identity in indexed:
            raise ReviewPacketError(
                f"duplicate prediction: {system_id}:{run_number}:{case_id}:{finding_id}"
            )
        _canonical_bytes(value, label=f"predictions[{index}]")
        indexed[identity] = copy.deepcopy(value)
        systems.add(system_id)
    ordered = [indexed[key] for key in sorted(indexed)]
    return ordered, sorted(systems)


def _prediction_payload_sha256(values: list[dict[str, Any]]) -> str:
    payload = b"".join(
        _canonical_bytes(value, label="system prediction") + b"\n"
        for value in values
    )
    return hashlib.sha256(payload).hexdigest()


def _system_prediction_bindings(
    predictions: list[dict[str, Any]],
    supplied: Any,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, prediction in enumerate(predictions):
        if not isinstance(prediction, dict):
            raise ReviewPacketError(f"predictions[{index}] must be an object")
        system_id = _nonempty_text(
            prediction.get("system_id"),
            label=f"predictions[{index}].system_id",
        )
        grouped.setdefault(system_id, []).append(prediction)
    # A supplied digest binds the exact VerifiedStage1Evaluation JSONL order.
    # The standalone path has no detached ordering authority, so it canonicalizes.
    digest_groups = grouped
    if supplied is None:
        digest_groups = {
            system_id: sorted(
                values,
                key=lambda item: (
                    int(item.get("run_number", 0)),
                    str(item.get("case_id", "")),
                    str(item.get("finding_id", "")),
                ),
            )
            for system_id, values in grouped.items()
        }
    derived = {
        system_id: {
            "system_id": system_id,
            "prediction_count": len(values),
            "change_count": sum(item.get("decision") == "CHANGE" for item in values),
            "predictions_sha256": _prediction_payload_sha256(values),
        }
        for system_id, values in digest_groups.items()
    }
    if supplied is None:
        return [derived[key] for key in sorted(derived)]
    if not isinstance(supplied, list) or not supplied:
        raise ReviewPacketError("system_prediction_bindings must be a non-empty list")
    indexed: dict[str, dict[str, Any]] = {}
    expected_fields = {
        "system_id",
        "prediction_count",
        "change_count",
        "predictions_sha256",
    }
    for index, value in enumerate(supplied):
        if not isinstance(value, dict) or set(value) != expected_fields:
            raise ReviewPacketError(f"system_prediction_bindings[{index}] fields are invalid")
        system_id = _nonempty_text(
            value["system_id"],
            label=f"system_prediction_bindings[{index}].system_id",
        )
        if system_id in indexed:
            raise ReviewPacketError(f"duplicate system prediction binding: {system_id}")
        for field in ("prediction_count", "change_count"):
            count = value[field]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ReviewPacketError(
                    f"system_prediction_bindings[{index}].{field} is invalid"
                )
        if value["change_count"] > value["prediction_count"]:
            raise ReviewPacketError("system change_count cannot exceed prediction_count")
        _require_digest(
            value["predictions_sha256"],
            label=f"system_prediction_bindings[{index}].predictions_sha256",
        )
        indexed[system_id] = copy.deepcopy(value)
    if not set(derived).issubset(indexed):
        raise ReviewPacketError("system prediction bindings omit an observed system")
    for system_id, observed in derived.items():
        if indexed[system_id] != observed:
            raise ReviewPacketError(f"system prediction binding mismatch: {system_id}")
    empty_sha256 = hashlib.sha256(b"").hexdigest()
    for system_id in set(indexed) - set(derived):
        value = indexed[system_id]
        if (
            value["prediction_count"] != 0
            or value["change_count"] != 0
            or value["predictions_sha256"] != empty_sha256
        ):
            raise ReviewPacketError(
                f"unobserved system prediction binding must describe an empty payload: {system_id}"
            )
    return [indexed[key] for key in sorted(indexed)]


def _diagnostic_packets(
    cases: dict[str, dict[str, Any]],
    predictions: list[dict[str, Any]],
    systems: list[str],
    system_bindings: list[dict[str, Any]],
    *,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    changes = [prediction for prediction in predictions if prediction["decision"] == "CHANGE"]
    mapping = build_blind_map(systems, seed=seed)
    try:
        blinded, crosswalk = blind_review_records(
            changes,
            mapping,
            seed=seed,
            include_system_alias=False,
        )
    except (IdentityLeakError, ValueError) as error:
        raise ReviewPacketError(str(error)) from error

    originals = {
        (
            item["system_id"],
            item["run_number"],
            item["case_id"],
            item["finding_id"],
        ): item
        for item in changes
    }
    crosswalk_by_item = {item["review_item_id"]: item for item in crosswalk}
    public_items: list[dict[str, Any]] = []
    private_items: list[dict[str, Any]] = []
    for blinded_prediction in blinded:
        prediction = copy.deepcopy(blinded_prediction)
        review_item_id = prediction.pop("review_item_id")
        prediction.pop("system_alias", None)
        case_id = _nonempty_text(prediction.get("case_id"), label="blinded prediction case_id")
        public_items.append(
            {
                "review_item_id": review_item_id,
                "case": copy.deepcopy(cases[case_id]),
                "prediction": prediction,
            }
        )

        crosswalk_item = crosswalk_by_item[review_item_id]
        identity = (
            crosswalk_item["system_id"],
            crosswalk_item["run_number"],
            crosswalk_item["case_id"],
            crosswalk_item["finding_id"],
        )
        original = copy.deepcopy(originals[identity])
        private_items.append(
            {
                "review_item_id": review_item_id,
                "prediction": original,
                "prediction_sha256": _digest(original, label=f"prediction {review_item_id}"),
            }
        )

    public = {
        "schema_version": "2.0",
        "packet_kind": "stage1_diagnostic_review",
        "instructions": (
            "Judge the proposed finding against the supplied case. Do not infer authorship. "
            "Check the exact span, named problem, contextual explanation, severity, suggested "
            "operation, and whether applying the operation could alter factual meaning. "
            "finding_valid must equal span_valid AND problem_valid AND context_valid AND "
            "severity_valid AND operation_valid. meaning_changed must be true if and only if "
            "meaning_risk is not none. meaning_risk must be exactly one of: none, low, medium, "
            "high, critical."
        ),
        "review_items": public_items,
    }
    try:
        assert_no_identity_leak(public, systems)
    except IdentityLeakError as error:
        raise ReviewPacketError(str(error)) from error

    public_packet_sha256 = _digest(public, label="diagnostic public packet")
    public_item_sha256 = {
        item["review_item_id"]: _digest(
            item,
            label=f"diagnostic public item {item['review_item_id']}",
        )
        for item in public_items
    }
    for item in private_items:
        item["review_item_sha256"] = public_item_sha256[item["review_item_id"]]
    private_items.sort(key=lambda item: item["review_item_id"])
    private = {
        "schema_version": "2.0",
        "packet_kind": "stage1_diagnostic_private_crosswalk",
        "public_packet_sha256": public_packet_sha256,
        "total_prediction_count": len(predictions),
        "system_bindings": copy.deepcopy(system_bindings),
        "review_items": private_items,
    }
    template = [
        _bound_template(
            packet_id=None,
            public_packet_sha256=public_packet_sha256,
            review_item_id=item["review_item_id"],
            review_item_sha256=item["review_item_sha256"],
            verdict_fields=_DIAGNOSTIC_TEMPLATE_FIELDS,
        )
        for item in private_items
    ]
    return public, private, template, copy.deepcopy(template)


def _gold_packets(
    cases: dict[str, dict[str, Any]],
    gold_by_case: dict[str, list[dict[str, Any]]],
    *,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    case_ids = sorted(cases)
    item_ids = [f"Gold-{index:06d}" for index in range(1, len(case_ids) + 1)]
    random.Random(seed + 2).shuffle(item_ids)
    item_id_by_case = dict(zip(case_ids, item_ids, strict=True))
    public_items = [
        {
            "review_item_id": item_id_by_case[case_id],
            "case": copy.deepcopy(cases[case_id]),
            "gold_findings": copy.deepcopy(gold_by_case[case_id]),
        }
        for case_id in case_ids
    ]
    random.Random(seed + 3).shuffle(public_items)
    private_items = []
    for item in sorted(public_items, key=lambda value: value["review_item_id"]):
        bound = {
            "case": copy.deepcopy(item["case"]),
            "gold_findings": copy.deepcopy(item["gold_findings"]),
        }
        private_items.append(
            {
                "review_item_id": item["review_item_id"],
                **bound,
                "bound_evidence_sha256": _digest(bound, label=f"gold {item['review_item_id']}"),
            }
        )
    public = {
        "schema_version": "2.0",
        "packet_kind": "stage1_gold_review",
        "instructions": (
            "Review every case, including cases with no proposed gold findings. Check span, "
            "CHANGE or KEEP decision, problem label, severity, and whether the proposed gold is complete."
        ),
        "review_items": public_items,
    }
    public_packet_sha256 = _digest(public, label="gold public packet")
    public_item_sha256 = {
        item["review_item_id"]: _digest(
            item,
            label=f"gold public item {item['review_item_id']}",
        )
        for item in public_items
    }
    for item in private_items:
        item["review_item_sha256"] = public_item_sha256[item["review_item_id"]]
    private = {
        "schema_version": "2.0",
        "packet_kind": "stage1_gold_private_crosswalk",
        "public_packet_sha256": public_packet_sha256,
        "review_items": private_items,
    }
    template = [
        _bound_template(
            packet_id=None,
            public_packet_sha256=public_packet_sha256,
            review_item_id=item["review_item_id"],
            review_item_sha256=item["review_item_sha256"],
            verdict_fields=_GOLD_TEMPLATE_FIELDS,
        )
        for item in private_items
    ]
    return public, private, template, copy.deepcopy(template)


def build_stage1_review_packets(
    cases: list[dict[str, Any]],
    gold_findings: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    seed: int,
    evidence: dict[str, str],
    human_roster_anchor: dict[str, Any],
    expected_run_id: str,
    system_prediction_bindings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return deterministic public packets, private crosswalks, and blank forms."""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ReviewPacketError("seed must be an integer")
    evidence = _validate_evidence(evidence)
    run_id = _nonempty_text(expected_run_id, label="expected_run_id")
    panel_report_sha256 = evidence.get("panel_report_canonical_sha256")
    if panel_report_sha256 is None:
        raise ReviewPacketError(
            "evidence.panel_report_canonical_sha256 is required for roster anchoring"
        )
    if evidence.get("scoring_protocol_amendment_sha256") is None:
        raise ReviewPacketError(
            "evidence.scoring_protocol_amendment_sha256 is required for review packets"
        )
    try:
        verified_roster_anchor = verify_human_roster_anchor(
            human_roster_anchor,
            expected_source_panel_report_sha256=panel_report_sha256,
            expected_run_id=run_id,
        )
    except HumanRosterAnchorError as error:
        raise ReviewPacketError(str(error)) from error
    roster_anchor_sha256 = human_roster_anchor_sha256(verified_roster_anchor)
    system_bindings = _system_prediction_bindings(predictions, system_prediction_bindings)
    indexed_cases = _indexed_cases(cases)
    indexed_gold = _indexed_gold(gold_findings, indexed_cases)
    indexed_predictions, systems = _indexed_predictions(predictions, indexed_cases)
    diagnostic_public, diagnostic_private, diagnostic_template, diagnostic_adjudicator = (
        _diagnostic_packets(
            indexed_cases,
            indexed_predictions,
            systems,
            system_bindings,
            seed=seed,
        )
    )
    gold_public, gold_private, gold_template, gold_adjudicator = _gold_packets(
        indexed_cases,
        indexed_gold,
        seed=seed,
    )
    bundle: dict[str, Any] = {
        "diagnostic_public": diagnostic_public,
        "diagnostic_private": diagnostic_private,
        "gold_public": gold_public,
        "gold_private": gold_private,
    }
    counts = {
        "cases": len(indexed_cases),
        "gold_findings": sum(len(values) for values in indexed_gold.values()),
        "predictions": len(indexed_predictions),
        "diagnostic_review_items": len(diagnostic_private["review_items"]),
        "gold_review_items": len(gold_private["review_items"]),
    }
    source_hashes = {
        name: _digest(bundle[name], label=name)
        for name in _SOURCE_ARTIFACT_NAMES
    }
    packet_id = _digest(
        _packet_identity_core(
            seed=seed,
            run_id=run_id,
            human_roster_anchor_sha256=roster_anchor_sha256,
            evidence=evidence,
            counts=counts,
            source_artifact_sha256=source_hashes,
        ),
        label="packet identity",
    )
    for template in (
        diagnostic_template,
        diagnostic_adjudicator,
        gold_template,
        gold_adjudicator,
    ):
        for item in template:
            item["packet_id"] = packet_id
    bundle.update(
        {
            "diagnostic_reviewer_template": diagnostic_template,
            "diagnostic_adjudicator_template": diagnostic_adjudicator,
            "gold_reviewer_template": gold_template,
            "gold_adjudicator_template": gold_adjudicator,
        }
    )
    artifact_hashes = {
        name: _digest(bundle[name], label=name)
        for name in _ARTIFACT_NAMES
    }
    bundle["manifest"] = {
        "schema_version": "2.0",
        "packet_kind": "stage1_review_panel",
        "packet_id": packet_id,
        "seed": seed,
        "run_id": run_id,
        "status": "PENDING_HUMAN_REVIEW",
        "human_roster_anchor_sha256": roster_anchor_sha256,
        "evidence": evidence,
        "counts": counts,
        "rating_contract": copy.deepcopy(_RATING_CONTRACT),
        "source_artifact_sha256": source_hashes,
        "artifact_sha256": artifact_hashes,
    }
    return bundle


def _public_item_bindings(
    public: Any,
    *,
    packet_kind: str,
    label: str,
) -> tuple[str, dict[str, str]]:
    if (
        not isinstance(public, dict)
        or set(public) != {"schema_version", "packet_kind", "instructions", "review_items"}
        or public["schema_version"] != "2.0"
        or public["packet_kind"] != packet_kind
        or not isinstance(public["instructions"], str)
        or not public["instructions"].strip()
        or not isinstance(public["review_items"], list)
    ):
        raise ReviewPacketError(f"{label} public packet is invalid")
    bindings: dict[str, str] = {}
    for index, item in enumerate(public["review_items"]):
        if not isinstance(item, dict):
            raise ReviewPacketError(f"{label} public review_items[{index}] is invalid")
        review_item_id = _nonempty_text(
            item.get("review_item_id"),
            label=f"{label} public review_items[{index}].review_item_id",
        )
        if review_item_id in bindings:
            raise ReviewPacketError(f"duplicate {label} public review item: {review_item_id}")
        bindings[review_item_id] = _digest(
            item,
            label=f"{label} public review item {review_item_id}",
        )
    return _digest(public, label=f"{label} public packet"), bindings


def _verify_private_packet(
    private: Any,
    *,
    label: str,
    public_packet_sha256: str,
    public_bindings: dict[str, str],
) -> tuple[int, dict[str, dict[str, Any]]]:
    if label == "diagnostic":
        expected_fields = {
            "schema_version",
            "packet_kind",
            "public_packet_sha256",
            "total_prediction_count",
            "system_bindings",
            "review_items",
        }
        expected_kind = "stage1_diagnostic_private_crosswalk"
    else:
        expected_fields = {
            "schema_version",
            "packet_kind",
            "public_packet_sha256",
            "review_items",
        }
        expected_kind = "stage1_gold_private_crosswalk"
    if (
        not isinstance(private, dict)
        or set(private) != expected_fields
        or private["schema_version"] != "2.0"
        or private["packet_kind"] != expected_kind
        or private["public_packet_sha256"] != public_packet_sha256
        or not isinstance(private["review_items"], list)
    ):
        raise ReviewPacketError(f"{label} private packet is invalid")
    if label == "diagnostic":
        total_predictions = private["total_prediction_count"]
        if (
            isinstance(total_predictions, bool)
            or not isinstance(total_predictions, int)
            or total_predictions < len(private["review_items"])
        ):
            raise ReviewPacketError("diagnostic total_prediction_count is invalid")
        raw_system_bindings = private["system_bindings"]
        if not isinstance(raw_system_bindings, list) or not raw_system_bindings:
            raise ReviewPacketError("diagnostic system_bindings are invalid")
        system_bindings: dict[str, dict[str, Any]] = {}
        binding_fields = {
            "system_id",
            "prediction_count",
            "change_count",
            "predictions_sha256",
        }
        for index, binding in enumerate(raw_system_bindings):
            if not isinstance(binding, dict) or set(binding) != binding_fields:
                raise ReviewPacketError(
                    f"diagnostic system_bindings[{index}] fields are invalid"
                )
            system_id = _nonempty_text(
                binding["system_id"],
                label=f"diagnostic system_bindings[{index}].system_id",
            )
            if system_id in system_bindings:
                raise ReviewPacketError(f"duplicate diagnostic system binding: {system_id}")
            for field in ("prediction_count", "change_count"):
                value = binding[field]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ReviewPacketError(
                        f"diagnostic system_bindings[{index}].{field} is invalid"
                    )
            if binding["change_count"] > binding["prediction_count"]:
                raise ReviewPacketError("diagnostic system change_count exceeds prediction_count")
            _require_digest(
                binding["predictions_sha256"],
                label=f"diagnostic system_bindings[{index}].predictions_sha256",
            )
            system_bindings[system_id] = copy.deepcopy(binding)
        if sum(value["prediction_count"] for value in system_bindings.values()) != total_predictions:
            raise ReviewPacketError("diagnostic system prediction counts do not match total")
    else:
        total_predictions = 0
        system_bindings = {}

    private_ids: set[str] = set()
    observed_changes: dict[str, int] = {}
    for index, item in enumerate(private["review_items"]):
        if not isinstance(item, dict):
            raise ReviewPacketError(f"{label} private review_items[{index}] is invalid")
        review_item_id = _nonempty_text(
            item.get("review_item_id"),
            label=f"{label} private review_items[{index}].review_item_id",
        )
        if review_item_id in private_ids:
            raise ReviewPacketError(f"duplicate {label} private review item: {review_item_id}")
        private_ids.add(review_item_id)
        if item.get("review_item_sha256") != public_bindings.get(review_item_id):
            raise ReviewPacketError(f"{label} review item binding mismatch: {review_item_id}")
        if label == "diagnostic":
            if set(item) != {
                "review_item_id",
                "review_item_sha256",
                "prediction",
                "prediction_sha256",
            }:
                raise ReviewPacketError(f"diagnostic private item fields are invalid: {review_item_id}")
            if item["prediction_sha256"] != _digest(
                item["prediction"],
                label=f"diagnostic private prediction {review_item_id}",
            ):
                raise ReviewPacketError(f"diagnostic prediction binding mismatch: {review_item_id}")
            prediction = item["prediction"]
            if not isinstance(prediction, dict) or prediction.get("decision") != "CHANGE":
                raise ReviewPacketError(
                    f"diagnostic private item is not a CHANGE prediction: {review_item_id}"
                )
            system_id = _nonempty_text(
                prediction.get("system_id"),
                label=f"diagnostic private prediction {review_item_id}.system_id",
            )
            if system_id not in system_bindings:
                raise ReviewPacketError(
                    f"diagnostic private prediction has no system binding: {system_id}"
                )
            observed_changes[system_id] = observed_changes.get(system_id, 0) + 1
        else:
            if set(item) != {
                "review_item_id",
                "review_item_sha256",
                "case",
                "gold_findings",
                "bound_evidence_sha256",
            }:
                raise ReviewPacketError(f"gold private item fields are invalid: {review_item_id}")
            bound = {"case": item["case"], "gold_findings": item["gold_findings"]}
            if item["bound_evidence_sha256"] != _digest(
                bound,
                label=f"gold private evidence {review_item_id}",
            ):
                raise ReviewPacketError(f"gold evidence binding mismatch: {review_item_id}")
    if private_ids != set(public_bindings):
        raise ReviewPacketError(f"{label} public and private review item sets differ")
    if label == "diagnostic":
        for system_id, binding in system_bindings.items():
            if observed_changes.get(system_id, 0) != binding["change_count"]:
                raise ReviewPacketError(
                    f"diagnostic change count does not match system binding: {system_id}"
                )
    return total_predictions, system_bindings


def _verify_blank_templates(
    values: Any,
    *,
    label: str,
    packet_id: str,
    public_packet_sha256: str,
    public_bindings: dict[str, str],
    verdict_fields: tuple[str, ...],
) -> None:
    if not isinstance(values, list) or len(values) != len(public_bindings):
        raise ReviewPacketError(f"{label} template count is invalid")
    expected_fields = {
        *_BINDING_FIELDS,
        "review_item_id",
        "reviewer_id",
        *verdict_fields,
    }
    observed_ids: set[str] = set()
    for index, item in enumerate(values):
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise ReviewPacketError(f"{label} template fields are invalid")
        review_item_id = _nonempty_text(
            item["review_item_id"],
            label=f"{label}[{index}].review_item_id",
        )
        if review_item_id in observed_ids:
            raise ReviewPacketError(f"duplicate {label} template item: {review_item_id}")
        observed_ids.add(review_item_id)
        if (
            item["packet_id"] != packet_id
            or item["public_packet_sha256"] != public_packet_sha256
            or item["review_item_sha256"] != public_bindings.get(review_item_id)
        ):
            raise ReviewPacketError(f"{label} template binding mismatch: {review_item_id}")
        if item["reviewer_id"] is not None or any(item[field] is not None for field in verdict_fields):
            raise ReviewPacketError(f"{label} template must contain blank rating fields")
    if observed_ids != set(public_bindings):
        raise ReviewPacketError(f"{label} template item set is incomplete")


def _verify_bundle(
    bundle: Any,
    *,
    expected_packet_id: str,
) -> dict[str, Any]:
    detached_packet_id = _require_digest(expected_packet_id, label="expected packet_id")
    if not isinstance(bundle, dict) or set(bundle) != {*_ARTIFACT_NAMES, "manifest"}:
        raise ReviewPacketError("review packet bundle fields are invalid")
    manifest = bundle["manifest"]
    if (
        not isinstance(manifest, dict)
        or set(manifest) != _MANIFEST_FIELDS
        or manifest["schema_version"] != "2.0"
        or manifest["packet_kind"] != "stage1_review_panel"
        or manifest["status"] != "PENDING_HUMAN_REVIEW"
        or manifest["rating_contract"] != _RATING_CONTRACT
    ):
        raise ReviewPacketError("review packet manifest is invalid")
    if manifest["packet_id"] != detached_packet_id:
        raise ReviewPacketError("review packet does not match the detached expected packet_id")
    seed = manifest["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ReviewPacketError("review packet seed is invalid")
    run_id = _nonempty_text(manifest["run_id"], label="review packet run_id")
    roster_anchor_sha256 = _require_digest(
        manifest["human_roster_anchor_sha256"],
        label="review packet human roster anchor",
    )
    evidence = _validate_evidence(manifest["evidence"])
    counts = manifest["counts"]
    if not isinstance(counts, dict) or set(counts) != _COUNT_FIELDS:
        raise ReviewPacketError("review packet counts are invalid")
    for key, value in counts.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ReviewPacketError(f"review packet counts.{key} is invalid")

    source_hashes = manifest["source_artifact_sha256"]
    if not isinstance(source_hashes, dict) or set(source_hashes) != set(_SOURCE_ARTIFACT_NAMES):
        raise ReviewPacketError("review packet source artifact hashes are invalid")
    expected_hashes = manifest["artifact_sha256"]
    if not isinstance(expected_hashes, dict) or set(expected_hashes) != set(_ARTIFACT_NAMES):
        raise ReviewPacketError("review packet artifact hashes are invalid")
    for name in _ARTIFACT_NAMES:
        observed = _digest(bundle[name], label=name)
        if expected_hashes[name] != observed:
            raise ReviewPacketError(f"review packet artifact hash mismatch: {name}")
        if name in _SOURCE_ARTIFACT_NAMES and source_hashes[name] != observed:
            raise ReviewPacketError(f"review packet source artifact hash mismatch: {name}")

    expected_identity = _digest(
        _packet_identity_core(
            seed=seed,
            run_id=run_id,
            human_roster_anchor_sha256=roster_anchor_sha256,
            evidence=evidence,
            counts=counts,
            source_artifact_sha256=source_hashes,
        ),
        label="packet identity",
    )
    if manifest["packet_id"] != expected_identity:
        raise ReviewPacketError("review packet identity mismatch")

    diagnostic_public_sha, diagnostic_bindings = _public_item_bindings(
        bundle["diagnostic_public"],
        packet_kind="stage1_diagnostic_review",
        label="diagnostic",
    )
    total_predictions, _ = _verify_private_packet(
        bundle["diagnostic_private"],
        label="diagnostic",
        public_packet_sha256=diagnostic_public_sha,
        public_bindings=diagnostic_bindings,
    )
    gold_public_sha, gold_bindings = _public_item_bindings(
        bundle["gold_public"],
        packet_kind="stage1_gold_review",
        label="gold",
    )
    _verify_private_packet(
        bundle["gold_private"],
        label="gold",
        public_packet_sha256=gold_public_sha,
        public_bindings=gold_bindings,
    )
    expected_counts = {
        "cases": len(bundle["gold_private"]["review_items"]),
        "gold_findings": sum(
            len(item["gold_findings"])
            for item in bundle["gold_private"]["review_items"]
        ),
        "predictions": total_predictions,
        "diagnostic_review_items": len(diagnostic_bindings),
        "gold_review_items": len(gold_bindings),
    }
    if counts != expected_counts:
        raise ReviewPacketError("review packet counts do not match source artifacts")

    for name in ("diagnostic_reviewer_template", "diagnostic_adjudicator_template"):
        _verify_blank_templates(
            bundle[name],
            label=name,
            packet_id=detached_packet_id,
            public_packet_sha256=diagnostic_public_sha,
            public_bindings=diagnostic_bindings,
            verdict_fields=_DIAGNOSTIC_TEMPLATE_FIELDS,
        )
    for name in ("gold_reviewer_template", "gold_adjudicator_template"):
        _verify_blank_templates(
            bundle[name],
            label=name,
            packet_id=detached_packet_id,
            public_packet_sha256=gold_public_sha,
            public_bindings=gold_bindings,
            verdict_fields=_GOLD_TEMPLATE_FIELDS,
        )
    return bundle


def _verify_completed_manifest(
    manifest: Any,
    *,
    expected_packet_id: str,
) -> dict[str, Any]:
    detached_packet_id = _require_digest(expected_packet_id, label="expected packet_id")
    if (
        not isinstance(manifest, dict)
        or set(manifest) != _COMPLETED_SOURCE_MANIFEST_FIELDS
        or manifest["schema_version"] != "2.0"
        or manifest["packet_kind"] != "stage1_review_panel"
        or manifest["status"] != "PENDING_HUMAN_REVIEW"
        or manifest["rating_contract"] != _RATING_CONTRACT
        or manifest["packet_id"] != detached_packet_id
    ):
        raise ReviewPacketError("completed review source manifest is invalid")
    seed = manifest["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ReviewPacketError("completed review source seed is invalid")
    run_id = _nonempty_text(
        manifest["run_id"],
        label="completed review source run_id",
    )
    roster_anchor_sha256 = _require_digest(
        manifest["human_roster_anchor_sha256"],
        label="completed review human roster anchor",
    )
    evidence = _validate_evidence(manifest["evidence"])
    counts = manifest["counts"]
    if not isinstance(counts, dict) or set(counts) != _COUNT_FIELDS:
        raise ReviewPacketError("completed review source counts are invalid")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in counts.values()
    ):
        raise ReviewPacketError("completed review source counts are invalid")
    source_hashes = manifest["source_artifact_sha256"]
    if (
        not isinstance(source_hashes, dict)
        or set(source_hashes) != set(_SOURCE_ARTIFACT_NAMES)
    ):
        raise ReviewPacketError("completed review source hashes are invalid")
    for label, value in source_hashes.items():
        _require_digest(value, label=f"completed review source hash {label}")
    expected_identity = _digest(
        _packet_identity_core(
            seed=seed,
            run_id=run_id,
            human_roster_anchor_sha256=roster_anchor_sha256,
            evidence=evidence,
            counts=counts,
            source_artifact_sha256=source_hashes,
        ),
        label="completed review packet identity",
    )
    if expected_identity != detached_packet_id:
        raise ReviewPacketError("completed review source manifest identity mismatch")
    return manifest


def _completed_source_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in manifest.items()
        if key in _COMPLETED_SOURCE_MANIFEST_FIELDS
    }


def _roster_from_packet_anchor(
    human_roster_anchor: dict[str, Any] | None,
    manifest: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve roster trust only from the digest frozen into the packet manifest."""

    if human_roster_anchor is None:
        return None, None
    panel_report_sha256 = manifest["evidence"].get("panel_report_canonical_sha256")
    if panel_report_sha256 is None:
        raise ReviewPacketError(
            "completed review source manifest lacks a panel report roster binding"
        )
    try:
        verified_anchor = verify_human_roster_anchor(
            human_roster_anchor,
            expected_sha256=manifest["human_roster_anchor_sha256"],
            expected_source_panel_report_sha256=panel_report_sha256,
            expected_run_id=manifest["run_id"],
        )
    except HumanRosterAnchorError as error:
        raise ReviewPacketError(str(error)) from error
    roster = verified_anchor["human_roster"]
    return roster, trusted_human_roster_sha256(roster)


def _strip_and_verify_bound_ratings(
    values: Any,
    *,
    label: str,
    packet_id: str,
    public_packet_sha256: str,
    public_bindings: dict[str, str],
    verdict_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        raise ReviewPacketError(f"{label} must be a list")
    expected_fields = {
        *_BINDING_FIELDS,
        "review_item_id",
        "reviewer_id",
        *verdict_fields,
    }
    stripped: list[dict[str, Any]] = []
    for index, item in enumerate(values):
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise ReviewPacketError(f"{label}[{index}] fields are invalid")
        review_item_id = _nonempty_text(
            item["review_item_id"],
            label=f"{label}[{index}].review_item_id",
        )
        if (
            item["packet_id"] != packet_id
            or item["public_packet_sha256"] != public_packet_sha256
            or item["review_item_sha256"] != public_bindings.get(review_item_id)
        ):
            raise ReviewPacketError(f"{label}[{index}] packet or review item binding mismatch")
        stripped.append(
            {
                "review_item_id": review_item_id,
                "reviewer_id": item["reviewer_id"],
                **{field: item[field] for field in verdict_fields},
            }
        )
    return stripped


def verify_completed_diagnostic_review_artifact(
    artifact: Any,
    *,
    expected_packet_id: str,
    system_id: str | None = None,
    expected_predictions_sha256: str | None = None,
    human_roster_anchor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify a completed panel packet and optionally project one system's ratings."""

    expected_fields = {
        "schema_version",
        "artifact_kind",
        "status",
        "source_manifest",
        "public_packet",
        "private_packet",
        "reviewers",
        "adjudicator",
        "reviews",
        "adjudications",
    }
    if (
        not isinstance(artifact, dict)
        or set(artifact) != expected_fields
        or artifact["schema_version"] != "2.0"
        or artifact["artifact_kind"] != "stage1_completed_diagnostic_review"
        or artifact["status"] != "COMPLETE"
    ):
        raise ReviewPacketError("completed diagnostic review artifact is invalid")
    manifest = _verify_completed_manifest(
        artifact["source_manifest"],
        expected_packet_id=expected_packet_id,
    )
    trusted_human_roster, expected_human_roster_sha256 = _roster_from_packet_anchor(
        human_roster_anchor,
        manifest,
    )
    public_sha256, public_bindings = _public_item_bindings(
        artifact["public_packet"],
        packet_kind="stage1_diagnostic_review",
        label="diagnostic",
    )
    if public_sha256 != manifest["source_artifact_sha256"]["diagnostic_public"]:
        raise ReviewPacketError("completed diagnostic public packet hash mismatch")
    total_predictions, system_bindings = _verify_private_packet(
        artifact["private_packet"],
        label="diagnostic",
        public_packet_sha256=public_sha256,
        public_bindings=public_bindings,
    )
    if _digest(
        artifact["private_packet"],
        label="completed diagnostic private packet",
    ) != manifest["source_artifact_sha256"]["diagnostic_private"]:
        raise ReviewPacketError("completed diagnostic private packet hash mismatch")
    if total_predictions != manifest["counts"]["predictions"]:
        raise ReviewPacketError("completed diagnostic prediction count mismatch")
    reviews = _strip_and_verify_bound_ratings(
        artifact["reviews"],
        label="diagnostic reviews",
        packet_id=expected_packet_id,
        public_packet_sha256=public_sha256,
        public_bindings=public_bindings,
        verdict_fields=_DIAGNOSTIC_TEMPLATE_FIELDS,
    )
    adjudications = _strip_and_verify_bound_ratings(
        artifact["adjudications"],
        label="diagnostic adjudications",
        packet_id=expected_packet_id,
        public_packet_sha256=public_sha256,
        public_bindings=public_bindings,
        verdict_fields=_DIAGNOSTIC_TEMPLATE_FIELDS,
    )
    all_private_items = artifact["private_packet"]["review_items"]

    def legacy_artifact(private_items: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        selected_ids = {item["review_item_id"] for item in private_items}
        legacy_items = [
            {
                "review_item_id": item["review_item_id"],
                "prediction": copy.deepcopy(item["prediction"]),
            }
            for item in private_items
        ]
        return {
            "schema_version": "1.0",
            "reviewers": copy.deepcopy(artifact["reviewers"]),
            "adjudicator": copy.deepcopy(artifact["adjudicator"]),
            "review_items": legacy_items,
            "reviews": [item for item in reviews if item["review_item_id"] in selected_ids],
            "adjudications": [
                item for item in adjudications if item["review_item_id"] in selected_ids
            ],
        }, [copy.deepcopy(item["prediction"]) for item in private_items]

    full_legacy, full_predictions = legacy_artifact(all_private_items)
    try:
        full_metrics = verify_stage1_human_review_artifact(
            full_legacy,
            full_predictions,
            trusted_human_roster=trusted_human_roster,
            expected_human_roster_sha256=expected_human_roster_sha256,
        )
    except HumanReviewIntegrityError as error:
        raise ReviewPacketError(str(error)) from error

    if system_id is None:
        if expected_predictions_sha256 is not None:
            raise ReviewPacketError(
                "expected_predictions_sha256 requires a system_id projection"
            )
        private_items = all_private_items
        metrics = full_metrics
        bound_predictions_sha256 = None
    else:
        system_id = _nonempty_text(system_id, label="system_id")
        expected_digest = _require_digest(
            expected_predictions_sha256,
            label="expected predictions_sha256",
        )
        binding = system_bindings.get(system_id)
        if binding is None:
            raise ReviewPacketError(f"system_id is not registered in the review packet: {system_id}")
        if binding["predictions_sha256"] != expected_digest:
            raise ReviewPacketError(
                f"review packet prediction binding mismatch for system: {system_id}"
            )
        private_items = [
            item
            for item in all_private_items
            if item["prediction"].get("system_id") == system_id
        ]
        subset_legacy, subset_predictions = legacy_artifact(private_items)
        try:
            metrics = verify_stage1_human_review_artifact(
                subset_legacy,
                subset_predictions,
                trusted_human_roster=trusted_human_roster,
                expected_human_roster_sha256=expected_human_roster_sha256,
            )
        except HumanReviewIntegrityError as error:
            raise ReviewPacketError(str(error)) from error
        bound_predictions_sha256 = binding["predictions_sha256"]

    return {
        **metrics,
        "packet_id": expected_packet_id,
        "public_packet_sha256": public_sha256,
        "system_id": system_id,
        "predictions_sha256": bound_predictions_sha256,
        "reviewed_prediction_count": len(private_items),
    }


def verify_completed_gold_review_artifact(
    artifact: Any,
    *,
    expected_packet_id: str,
    human_roster_anchor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify a completed gold packet from its retained public and private evidence."""

    expected_fields = {
        "schema_version",
        "artifact_kind",
        "status",
        "source_manifest",
        "public_packet",
        "private_packet",
        "reviewers",
        "adjudicator",
        "reviews",
        "adjudications",
    }
    if (
        not isinstance(artifact, dict)
        or set(artifact) != expected_fields
        or artifact["schema_version"] != "2.0"
        or artifact["artifact_kind"] != "stage1_completed_gold_review"
        or artifact["status"] != "COMPLETE"
    ):
        raise ReviewPacketError("completed gold review artifact is invalid")
    manifest = _verify_completed_manifest(
        artifact["source_manifest"],
        expected_packet_id=expected_packet_id,
    )
    trusted_human_roster, expected_human_roster_sha256 = _roster_from_packet_anchor(
        human_roster_anchor,
        manifest,
    )
    public_sha256, public_bindings = _public_item_bindings(
        artifact["public_packet"],
        packet_kind="stage1_gold_review",
        label="gold",
    )
    if public_sha256 != manifest["source_artifact_sha256"]["gold_public"]:
        raise ReviewPacketError("completed gold public packet hash mismatch")
    _verify_private_packet(
        artifact["private_packet"],
        label="gold",
        public_packet_sha256=public_sha256,
        public_bindings=public_bindings,
    )
    if _digest(
        artifact["private_packet"],
        label="completed gold private packet",
    ) != manifest["source_artifact_sha256"]["gold_private"]:
        raise ReviewPacketError("completed gold private packet hash mismatch")
    reviews = _strip_and_verify_bound_ratings(
        artifact["reviews"],
        label="gold reviews",
        packet_id=expected_packet_id,
        public_packet_sha256=public_sha256,
        public_bindings=public_bindings,
        verdict_fields=_GOLD_TEMPLATE_FIELDS,
    )
    adjudications = _strip_and_verify_bound_ratings(
        artifact["adjudications"],
        label="gold adjudications",
        packet_id=expected_packet_id,
        public_packet_sha256=public_sha256,
        public_bindings=public_bindings,
        verdict_fields=_GOLD_TEMPLATE_FIELDS,
    )
    private_items = artifact["private_packet"]["review_items"]
    legacy_items = [
        {
            "review_item_id": item["review_item_id"],
            "case": copy.deepcopy(item["case"]),
            "gold_findings": copy.deepcopy(item["gold_findings"]),
        }
        for item in private_items
    ]
    legacy = {
        "schema_version": "1.0",
        "reviewers": copy.deepcopy(artifact["reviewers"]),
        "adjudicator": copy.deepcopy(artifact["adjudicator"]),
        "review_items": legacy_items,
        "reviews": reviews,
        "adjudications": adjudications,
    }
    cases = [copy.deepcopy(item["case"]) for item in private_items]
    gold_findings = [
        copy.deepcopy(finding)
        for item in private_items
        for finding in item["gold_findings"]
    ]
    try:
        metrics = verify_stage1_human_gold_review_artifact(
            legacy,
            cases,
            gold_findings,
            trusted_human_roster=trusted_human_roster,
            expected_human_roster_sha256=expected_human_roster_sha256,
        )
    except HumanReviewIntegrityError as error:
        raise ReviewPacketError(str(error)) from error
    return {
        **metrics,
        "packet_id": expected_packet_id,
        "public_packet_sha256": public_sha256,
    }


def assemble_diagnostic_review_artifact(
    bundle: dict[str, Any],
    *,
    expected_packet_id: str,
    human_roster_anchor: dict[str, Any],
    reviewers: list[dict[str, Any]],
    adjudicator: dict[str, Any],
    reviews: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build and verify one evidence-preserving completed diagnostic panel."""

    bundle = _verify_bundle(bundle, expected_packet_id=expected_packet_id)
    artifact = {
        "schema_version": "2.0",
        "artifact_kind": "stage1_completed_diagnostic_review",
        "status": "COMPLETE",
        "source_manifest": _completed_source_manifest(bundle["manifest"]),
        "public_packet": copy.deepcopy(bundle["diagnostic_public"]),
        "private_packet": copy.deepcopy(bundle["diagnostic_private"]),
        "reviewers": copy.deepcopy(reviewers),
        "adjudicator": copy.deepcopy(adjudicator),
        "reviews": copy.deepcopy(reviews),
        "adjudications": copy.deepcopy(adjudications),
    }
    verify_completed_diagnostic_review_artifact(
        artifact,
        expected_packet_id=expected_packet_id,
        human_roster_anchor=human_roster_anchor,
    )
    return artifact


def assemble_gold_review_artifact(
    bundle: dict[str, Any],
    *,
    expected_packet_id: str,
    human_roster_anchor: dict[str, Any],
    reviewers: list[dict[str, Any]],
    adjudicator: dict[str, Any],
    reviews: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build and verify one evidence-preserving completed gold panel."""

    bundle = _verify_bundle(bundle, expected_packet_id=expected_packet_id)
    artifact = {
        "schema_version": "2.0",
        "artifact_kind": "stage1_completed_gold_review",
        "status": "COMPLETE",
        "source_manifest": _completed_source_manifest(bundle["manifest"]),
        "public_packet": copy.deepcopy(bundle["gold_public"]),
        "private_packet": copy.deepcopy(bundle["gold_private"]),
        "reviewers": copy.deepcopy(reviewers),
        "adjudicator": copy.deepcopy(adjudicator),
        "reviews": copy.deepcopy(reviews),
        "adjudications": copy.deepcopy(adjudications),
    }
    verify_completed_gold_review_artifact(
        artifact,
        expected_packet_id=expected_packet_id,
        human_roster_anchor=human_roster_anchor,
    )
    return artifact
