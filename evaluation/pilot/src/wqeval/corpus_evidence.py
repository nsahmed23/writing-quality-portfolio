"""Detached-hash verification for the frozen Stage 1 scoring corpus."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re
from typing import Any

from .storage import PathSafetyError, RawStore, TamperError
from .strict_json import StrictJsonError, loads, loads_jsonl
from .validation import ValidationError, validate_case, validate_finding


_HEX_256 = re.compile(r"[0-9a-f]{64}")
_MANIFEST_FIELDS = {"schema_version", "status", "gold_status", "files"}
_REF_FIELDS = {"path", "sha256", "bytes"}
_ATTESTATION = object()


class CorpusEvidenceError(RuntimeError):
    """Raised when frozen cases or gold do not match their detached authority."""


@dataclass(frozen=True)
class VerifiedScoringCorpus:
    freeze_manifest_sha256: str
    cases_sha256: str
    gold_sha256: str
    split: str
    gold_status: str
    cases_payload: bytes
    gold_payload: bytes
    _attestation: object = field(repr=False, compare=False)

    def assert_verified(self) -> None:
        if self._attestation is not _ATTESTATION:
            raise CorpusEvidenceError("corpus evidence was not created by the detached verifier")
        if hashlib.sha256(self.cases_payload).hexdigest() != self.cases_sha256:
            raise CorpusEvidenceError("verified cases payload changed")
        if hashlib.sha256(self.gold_payload).hexdigest() != self.gold_sha256:
            raise CorpusEvidenceError("verified gold payload changed")

    @property
    def cases(self) -> tuple[dict[str, Any], ...]:
        self.assert_verified()
        return tuple(loads_jsonl(self.cases_payload, source_name=f"verified cases {self.split}"))

    @property
    def gold(self) -> tuple[dict[str, Any], ...]:
        self.assert_verified()
        return tuple(loads_jsonl(self.gold_payload, source_name=f"verified gold {self.split}"))


def _digest(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or _HEX_256.fullmatch(value) is None:
        raise CorpusEvidenceError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _read_fixed(
    store: RawStore,
    relative_path: str,
    *,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
    maximum_bytes: int,
) -> bytes:
    normalized, target = store._target(relative_path)
    metadata = target.lstat()
    if metadata.st_size > maximum_bytes:
        raise CorpusEvidenceError(f"corpus artifact exceeds {maximum_bytes} bytes: {normalized}")
    payload = store._read_regular_file(target, maximum_bytes=maximum_bytes)
    if expected_bytes is not None and len(payload) != expected_bytes:
        raise CorpusEvidenceError(f"corpus artifact byte count is inconsistent: {normalized}")
    if expected_sha256 is not None and hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise CorpusEvidenceError(f"corpus artifact SHA-256 is inconsistent: {normalized}")
    return payload


def _reference(value: Any, *, expected_path: str) -> tuple[str, int]:
    if not isinstance(value, dict) or set(value) != _REF_FIELDS or value.get("path") != expected_path:
        raise CorpusEvidenceError(f"freeze manifest lacks the exact registered file: {expected_path}")
    digest = _digest(value["sha256"], name=f"{expected_path} reference")
    byte_count = value["bytes"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
        raise CorpusEvidenceError(f"{expected_path} reference byte count is invalid")
    return digest, byte_count


def verify_frozen_scoring_corpus(
    project_root: str | Path,
    *,
    expected_freeze_manifest_sha256: str,
    split: str,
    maximum_artifact_bytes: int = 50_000_000,
) -> VerifiedScoringCorpus:
    """Verify one fixed public-case and private-scoring pair from the frozen manifest."""

    if split not in {"dev", "test"}:
        raise CorpusEvidenceError("split must be dev or test")
    if (
        isinstance(maximum_artifact_bytes, bool)
        or not isinstance(maximum_artifact_bytes, int)
        or maximum_artifact_bytes < 1
    ):
        raise CorpusEvidenceError("maximum_artifact_bytes must be a positive integer")
    expected_manifest_sha = _digest(
        expected_freeze_manifest_sha256,
        name="expected freeze manifest",
    )
    root = Path(os.path.abspath(os.fspath(project_root)))
    cases_path = f"corpus/cases.{split}.jsonl"
    gold_path = f"private/gold/scoring.{split}.jsonl"
    try:
        store = RawStore(root, authorized_root=root)
        manifest_payload = _read_fixed(
            store,
            "corpus/freeze-manifest.json",
            expected_sha256=expected_manifest_sha,
            maximum_bytes=5_000_000,
        )
        manifest = loads(manifest_payload)
        if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS:
            raise CorpusEvidenceError("freeze manifest fields are invalid")
        if manifest["schema_version"] != "1.0" or manifest["status"] != "frozen":
            raise CorpusEvidenceError("freeze manifest version or status is invalid")
        if manifest["gold_status"] not in {
            "provisional_pending_human_adjudication",
            "human_adjudicated",
        }:
            raise CorpusEvidenceError("freeze manifest gold status is invalid")
        entries = manifest["files"]
        if not isinstance(entries, list):
            raise CorpusEvidenceError("freeze manifest files must be a list")
        by_path: dict[str, dict[str, Any]] = {}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != _REF_FIELDS:
                raise CorpusEvidenceError("freeze manifest file reference fields are invalid")
            path = entry.get("path")
            if not isinstance(path, str) or not path or path in by_path:
                raise CorpusEvidenceError("freeze manifest file paths must be unique text")
            by_path[path] = entry
        cases_sha, cases_bytes = _reference(by_path.get(cases_path), expected_path=cases_path)
        gold_sha, gold_bytes = _reference(by_path.get(gold_path), expected_path=gold_path)
        cases_payload = _read_fixed(
            store,
            cases_path,
            expected_sha256=cases_sha,
            expected_bytes=cases_bytes,
            maximum_bytes=maximum_artifact_bytes,
        )
        gold_payload = _read_fixed(
            store,
            gold_path,
            expected_sha256=gold_sha,
            expected_bytes=gold_bytes,
            maximum_bytes=maximum_artifact_bytes,
        )
        cases = loads_jsonl(cases_payload, source_name=cases_path)
        gold = loads_jsonl(gold_payload, source_name=gold_path)
        case_by_id: dict[str, dict[str, Any]] = {}
        for source_case in cases:
            validate_case(source_case)
            case_id = source_case["case_id"]
            if case_id in case_by_id:
                raise CorpusEvidenceError(f"duplicate case in frozen split: {case_id}")
            if source_case.get("split", split) != split:
                raise CorpusEvidenceError(f"case has the wrong frozen split: {case_id}")
            case_by_id[case_id] = source_case
        if not case_by_id:
            raise CorpusEvidenceError("frozen scoring split has no cases")
        finding_ids: set[tuple[str, str]] = set()
        for finding in gold:
            case_id = finding.get("case_id")
            source_case = case_by_id.get(case_id)
            if source_case is None:
                raise CorpusEvidenceError(f"gold finding references unknown case: {case_id}")
            validate_finding(finding, source_case)
            identity = (case_id, finding["finding_id"])
            if identity in finding_ids:
                raise CorpusEvidenceError(f"duplicate gold finding identity: {case_id}:{finding['finding_id']}")
            finding_ids.add(identity)
        return VerifiedScoringCorpus(
            freeze_manifest_sha256=expected_manifest_sha,
            cases_sha256=cases_sha,
            gold_sha256=gold_sha,
            split=split,
            gold_status=manifest["gold_status"],
            cases_payload=cases_payload,
            gold_payload=gold_payload,
            _attestation=_ATTESTATION,
        )
    except CorpusEvidenceError:
        raise
    except (OSError, PathSafetyError, TamperError, StrictJsonError, ValidationError) as exc:
        raise CorpusEvidenceError(str(exc)) from exc
