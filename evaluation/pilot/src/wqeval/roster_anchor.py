"""Immutable pre-review binding for a declared real-human review panel.

The anchor makes later roster substitution detectable. It cannot prove that a
named person exists or performed the review. That identity claim remains an
external user attestation and is the trust root for the human-review gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .human_review import HumanReviewIntegrityError, validate_trusted_human_roster
from .strict_json import loads


class HumanRosterAnchorError(ValueError):
    """Raised when a pre-review roster anchor is malformed or misbound."""


_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_ANCHOR_FIELDS = {
    "schema_version",
    "anchor_kind",
    "status",
    "run_id",
    "source_panel_report_sha256",
    "human_roster",
}


def _require_digest(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _HEX_64.fullmatch(value) is None:
        raise HumanRosterAnchorError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HumanRosterAnchorError(f"{label} must be non-empty text")
    return value


def _canonical_panel_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise HumanRosterAnchorError("source panel report must be finite JSON data") from error


def panel_report_sha256(report: Any) -> str:
    """Return the canonical digest used by ``VerifiedStage1Panel`` reports."""

    return hashlib.sha256(_canonical_panel_bytes(report)).hexdigest()


def encode_human_roster_anchor(anchor: Any) -> bytes:
    """Encode an anchor in its one canonical on-disk representation."""

    try:
        return (
            json.dumps(
                anchor,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise HumanRosterAnchorError("human roster anchor must be finite JSON data") from error


def human_roster_anchor_sha256(anchor: Any) -> str:
    """Return the digest later frozen into the review packet identity."""

    return hashlib.sha256(encode_human_roster_anchor(anchor)).hexdigest()


def build_human_roster_anchor(
    *,
    human_roster: dict[str, Any],
    run_id: str,
    source_panel_report_sha256: str,
) -> dict[str, Any]:
    """Create an exact, private roster anchor before any form is distributed."""

    try:
        roster = validate_trusted_human_roster(human_roster)
    except HumanReviewIntegrityError as error:
        raise HumanRosterAnchorError(str(error)) from error
    anchor = {
        "schema_version": "1.0",
        "anchor_kind": "stage1_human_roster_pre_review",
        "status": "FROZEN_PRE_REVIEW",
        "run_id": _require_text(run_id, label="run_id"),
        "source_panel_report_sha256": _require_digest(
            source_panel_report_sha256,
            label="source_panel_report_sha256",
        ),
        "human_roster": roster,
    }
    return verify_human_roster_anchor(anchor)


def verify_human_roster_anchor(
    anchor: Any,
    *,
    expected_sha256: str | None = None,
    expected_source_panel_report_sha256: str | None = None,
    expected_run_id: str | None = None,
) -> dict[str, Any]:
    """Validate an anchor and any independently derived bindings."""

    if not isinstance(anchor, dict) or set(anchor) != _ANCHOR_FIELDS:
        raise HumanRosterAnchorError("human roster anchor fields are invalid")
    if (
        anchor["schema_version"] != "1.0"
        or anchor["anchor_kind"] != "stage1_human_roster_pre_review"
        or anchor["status"] != "FROZEN_PRE_REVIEW"
    ):
        raise HumanRosterAnchorError("human roster anchor identity is invalid")
    run_id = _require_text(anchor["run_id"], label="human roster anchor.run_id")
    panel_sha256 = _require_digest(
        anchor["source_panel_report_sha256"],
        label="human roster anchor.source_panel_report_sha256",
    )
    try:
        validate_trusted_human_roster(anchor["human_roster"])
    except HumanReviewIntegrityError as error:
        raise HumanRosterAnchorError(str(error)) from error
    payload = encode_human_roster_anchor(anchor)
    snapshot = loads(payload)
    if not isinstance(snapshot, dict):
        raise HumanRosterAnchorError("human roster anchor must be an object")
    if expected_sha256 is not None:
        expected = _require_digest(expected_sha256, label="expected human roster anchor")
        if hashlib.sha256(payload).hexdigest() != expected:
            raise HumanRosterAnchorError(
                "human roster anchor does not match the packet-bound SHA-256"
            )
    if expected_source_panel_report_sha256 is not None:
        expected_panel = _require_digest(
            expected_source_panel_report_sha256,
            label="expected source panel report",
        )
        if panel_sha256 != expected_panel:
            raise HumanRosterAnchorError(
                "human roster anchor is bound to a different source panel report"
            )
    if expected_run_id is not None and run_id != _require_text(
        expected_run_id,
        label="expected run_id",
    ):
        raise HumanRosterAnchorError("human roster anchor is bound to a different run_id")
    return snapshot

