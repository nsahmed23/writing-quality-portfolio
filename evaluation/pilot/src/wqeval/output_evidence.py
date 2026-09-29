"""Detached, immutable evidence anchoring for complete Stage 1 output sets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import random
import re
import stat
from typing import Any

from .jobs import validate_stage1_job
from .provenance import load_public_problem_vocabulary, verify_job_artifacts
from .storage import ImmutableWriteError, PathSafetyError, RawStore, Receipt, TamperError
from .strict_json import StrictJsonError, loads, loads_jsonl
from .validation import (
    ValidationError,
    flatten_diagnostic_outputs,
    validate_diagnostic_output_set,
    validate_finding,
)


ANCHOR_RELATIVE_PATH = "manifests/stage1-output-evidence.json"
JOBS_MANIFEST_RELATIVE_PATH = "manifests/jobs.json"
EXECUTION_ORDER_RELATIVE_PATH = "manifests/execution-order.json"
_HEX_256 = re.compile(r"[0-9a-f]{64}")
_ANCHOR_FIELDS = {"schema_version", "stage", "jobs_manifest", "execution_order", "jobs"}
_EXECUTION_ORDER_FIELDS = {
    "schema_version",
    "stage",
    "mode",
    "order_policy",
    "random_seed",
    "jobs_manifest_sha256",
    "job_count",
    "job_ids",
}
_ANCHOR_JOB_FIELDS = {
    "job_id",
    "status",
    "record_count",
    "job",
    "receipt",
    "raw",
    "normalized",
}
_REF_FIELDS = {"path", "sha256", "byte_count"}
_RECEIPT_FIELDS = {
    "status",
    "raw_receipt",
    "normalized_receipt",
    "record_count",
    "error_type",
    "error_message",
    "job_sha256",
    "jobs_manifest_sha256",
}


class OutputEvidenceError(RuntimeError):
    """Raised when a Stage 1 evidence set is unsafe, incomplete, or inconsistent."""


@dataclass(frozen=True)
class VerifiedStage1Run:
    """One run reconstructed exclusively from detached-hash-bound evidence."""

    job_id: str
    system_id: str
    run_number: int
    status: str
    record_count: int
    raw_sha256: str
    normalized_sha256: str | None
    normalized_byte_count: int | None
    normalized_payload: bytes | None
    cases_payload: bytes
    model_payload: bytes
    error_type: str | None = None
    error_message: str | None = None

    @property
    def predictions(self) -> tuple[dict[str, Any], ...]:
        """Parse a fresh projection so caller mutation cannot alter verified state."""

        if not self.normalized_payload:
            return ()
        return tuple(
            loads_jsonl(
                self.normalized_payload,
                source_name=f"verified/{self.job_id}.jsonl",
            )
        )

    @property
    def cases(self) -> tuple[dict[str, Any], ...]:
        """Return a fresh copy of the exact case panel embedded in the verified job."""

        value = loads(self.cases_payload)
        if not isinstance(value, list):
            raise OutputEvidenceError("verified case payload is not a list")
        return tuple(value)

    @property
    def model(self) -> dict[str, Any]:
        value = loads(self.model_payload)
        if not isinstance(value, dict):
            raise OutputEvidenceError("verified model settings payload is not an object")
        return value


@dataclass(frozen=True)
class VerifiedOutputEvidence:
    jobs_manifest_sha256: str
    output_evidence_sha256: str | None
    execution_order_sha256: str | None
    runs: tuple[VerifiedStage1Run, ...]
    anchor_payload: bytes | None


@dataclass(frozen=True)
class _JobContext:
    job: dict[str, Any]
    job_ref: dict[str, Any]
    receipt: dict[str, Any]
    receipt_ref: dict[str, Any]
    raw_receipt: Receipt
    raw_ref: dict[str, Any]
    normalized_receipt: Receipt | None
    normalized_ref: dict[str, Any] | None


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _serialize_jsonl(records: list[dict[str, Any]]) -> bytes:
    return b"".join(_canonical_json(item) for item in records)


def _digest(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or _HEX_256.fullmatch(value) is None:
        raise OutputEvidenceError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _positive_limit(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise OutputEvidenceError(f"{name} must be a positive integer")
    return value


def _safe_relative_path(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise OutputEvidenceError(f"{name} path is unsafe")
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    if windows.is_absolute() or windows.drive or posix.is_absolute():
        raise OutputEvidenceError(f"{name} path is unsafe")
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise OutputEvidenceError(f"{name} path is unsafe")
    if str(posix) != value:
        raise OutputEvidenceError(f"{name} path is not canonical")
    return value


def _ref(value: Any, *, name: str, expected_path: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _REF_FIELDS:
        raise OutputEvidenceError(f"{name} reference fields are invalid")
    path = _safe_relative_path(value["path"], name=name)
    digest = _digest(value["sha256"], name=f"{name} reference")
    byte_count = value["byte_count"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
        raise OutputEvidenceError(f"{name} reference byte_count is invalid")
    if expected_path is not None and path != expected_path:
        raise OutputEvidenceError(f"{name} reference path is inconsistent")
    return {"path": path, "sha256": digest, "byte_count": byte_count}


def _manifest_entry_ref(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"path", "sha256", "bytes"}:
        raise OutputEvidenceError("jobs manifest entry fields are invalid")
    path = _safe_relative_path(value["path"], name="job")
    if len(PurePosixPath(path).parts) != 2 or PurePosixPath(path).parts[0] != "jobs":
        raise OutputEvidenceError("jobs manifest entry is not a direct jobs artifact")
    digest = _digest(value["sha256"], name="job manifest entry")
    byte_count = value["bytes"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
        raise OutputEvidenceError("job manifest entry byte count is invalid")
    return {"path": path, "sha256": digest, "byte_count": byte_count}


def _receipt(value: Any, *, artifact_name: str, name: str) -> Receipt:
    if not isinstance(value, dict) or set(value) != {"relative_path", "sha256", "byte_count"}:
        raise OutputEvidenceError(f"{name} receipt fields are invalid")
    relative_path = value["relative_path"]
    if relative_path != artifact_name:
        raise OutputEvidenceError(f"{name} receipt path does not match the registered artifact")
    digest = _digest(value["sha256"], name=f"{name} receipt")
    byte_count = value["byte_count"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
        raise OutputEvidenceError(f"{name} receipt byte count is invalid")
    return Receipt(relative_path, digest, byte_count)


def _safe_read(
    store: RawStore,
    relative_path: str,
    *,
    maximum_bytes: int,
    expected_sha256: str | None = None,
    expected_byte_count: int | None = None,
) -> bytes:
    """Read through RawStore's ancestor, alias, hardlink, and mutation checks."""

    normalized, target = store._target(relative_path)
    try:
        metadata = target.lstat()
    except OSError as exc:
        raise OutputEvidenceError(f"required artifact is missing: {normalized}") from exc
    if metadata.st_size > maximum_bytes:
        raise OutputEvidenceError(f"artifact exceeds {maximum_bytes} bytes: {normalized}")
    payload = store._read_regular_file(target, maximum_bytes=maximum_bytes)
    if expected_byte_count is not None and len(payload) != expected_byte_count:
        raise OutputEvidenceError(f"artifact byte count does not match evidence: {normalized}")
    if expected_sha256 is not None and _sha256(payload) != expected_sha256:
        raise OutputEvidenceError(f"artifact SHA-256 does not match evidence: {normalized}")
    return payload


def _entry_kind(metadata: os.stat_result) -> str:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_flag:
        return "alias"
    if stat.S_ISREG(metadata.st_mode):
        return "file"
    if stat.S_ISDIR(metadata.st_mode):
        return "directory"
    return "other"


def _directory_entries(store: RawStore, relative_path: str) -> dict[str, str]:
    normalized, target = store._target(relative_path)
    try:
        before = target.lstat()
    except OSError as exc:
        raise OutputEvidenceError(f"required artifact directory is missing: {normalized}") from exc
    if _entry_kind(before) != "directory":
        raise OutputEvidenceError(f"artifact directory is unsafe: {normalized}")
    entries: dict[str, str] = {}
    try:
        with os.scandir(target) as iterator:
            for entry in iterator:
                metadata = entry.stat(follow_symlinks=False)
                kind = _entry_kind(metadata)
                if kind in {"alias", "other"}:
                    raise OutputEvidenceError(
                        f"artifact directory contains an unsafe entry: {normalized}/{entry.name}"
                    )
                entries[entry.name] = kind
        after = target.lstat()
    except OutputEvidenceError:
        raise
    except OSError as exc:
        raise OutputEvidenceError(f"artifact directory changed while reading: {normalized}") from exc
    before_identity = (before.st_dev, before.st_ino, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_mtime_ns)
    if before_identity != after_identity or _entry_kind(after) != "directory":
        raise OutputEvidenceError(f"artifact directory changed while reading: {normalized}")
    return entries


def _assert_exact_directory(
    store: RawStore,
    relative_path: str,
    *,
    files: set[str],
    directories: set[str] | None = None,
) -> None:
    directories = directories or set()
    entries = _directory_entries(store, relative_path)
    expected = {name: "file" for name in files} | {name: "directory" for name in directories}
    missing = sorted(set(expected) - set(entries))
    unexpected = sorted(set(entries) - set(expected))
    wrong_kind = sorted(name for name in set(entries) & set(expected) if entries[name] != expected[name])
    if missing or unexpected or wrong_kind:
        details: list[str] = []
        if missing:
            details.append(f"missing {relative_path} entries: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected {relative_path} entries: {', '.join(unexpected)}")
        if wrong_kind:
            details.append(f"wrong-kind {relative_path} entries: {', '.join(wrong_kind)}")
        raise OutputEvidenceError("; ".join(details))


def _assert_manifest_directory(
    store: RawStore,
    *,
    anchor_required: bool | None,
    execution_order_required: bool | None = None,
) -> tuple[bool, bool]:
    entries = _directory_entries(store, "manifests")
    base = {"jobs.json": "file", "receipts": "directory"}
    anchor_options = (anchor_required,) if anchor_required is not None else (False, True)
    order_options = (
        (execution_order_required,)
        if execution_order_required is not None
        else (False, True)
    )
    allowed = []
    for has_anchor in anchor_options:
        for has_order in order_options:
            shape = dict(base)
            if has_anchor:
                shape["stage1-output-evidence.json"] = "file"
            if has_order:
                shape["execution-order.json"] = "file"
            allowed.append(shape)
    if entries not in allowed:
        raise OutputEvidenceError("manifests entries do not match an allowed exact set")
    return (
        "stage1-output-evidence.json" in entries,
        "execution-order.json" in entries,
    )


def _load_jobs_manifest(payload: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = loads(payload)
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "1.0"
        or manifest.get("stage") != 1
        or manifest.get("mode") not in {"development", "confirmatory"}
        or isinstance(manifest.get("random_seed"), bool)
        or not isinstance(manifest.get("random_seed"), int)
    ):
        raise OutputEvidenceError("jobs manifest schema is invalid")
    entries = manifest.get("jobs")
    if not isinstance(entries, list) or not entries:
        raise OutputEvidenceError("jobs manifest has no registered jobs")
    if "job_count" in manifest and manifest["job_count"] != len(entries):
        raise OutputEvidenceError("jobs manifest job_count is inconsistent")
    refs = [_manifest_entry_ref(entry) for entry in entries]
    paths = [item["path"] for item in refs]
    if len(paths) != len(set(paths)):
        raise OutputEvidenceError("jobs manifest contains duplicate job paths")
    return manifest, refs


def _load_execution_order(
    payload: bytes,
    *,
    jobs_manifest_sha256: str,
    jobs_manifest: dict[str, Any],
    manifest_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    value = loads(payload)
    if not isinstance(value, dict) or set(value) != _EXECUTION_ORDER_FIELDS:
        raise OutputEvidenceError("execution order fields are invalid")
    if value["schema_version"] != "1.0" or value["stage"] != 1:
        raise OutputEvidenceError("execution order version or stage is invalid")
    if value["jobs_manifest_sha256"] != jobs_manifest_sha256:
        raise OutputEvidenceError("execution order jobs-manifest SHA-256 is inconsistent")
    if value["mode"] != jobs_manifest["mode"]:
        raise OutputEvidenceError("execution order mode is inconsistent with the jobs manifest")
    if value["order_policy"] != "deterministic_shuffle":
        raise OutputEvidenceError("execution order policy is invalid")
    if isinstance(value["random_seed"], bool) or not isinstance(value["random_seed"], int):
        raise OutputEvidenceError("execution order random seed is invalid")
    if value["random_seed"] != jobs_manifest["random_seed"]:
        raise OutputEvidenceError("execution order random seed is inconsistent with the jobs manifest")
    job_ids = value["job_ids"]
    if not isinstance(job_ids, list) or not all(isinstance(item, str) and item for item in job_ids):
        raise OutputEvidenceError("execution order job_ids are invalid")
    expected_job_ids = sorted(PurePosixPath(ref["path"]).stem for ref in manifest_refs)
    if (
        isinstance(value["job_count"], bool)
        or not isinstance(value["job_count"], int)
        or value["job_count"] != len(job_ids)
        or len(job_ids) != len(set(job_ids))
        or set(job_ids) != set(expected_job_ids)
    ):
        raise OutputEvidenceError("execution order does not bind the exact registered job set")
    expected_order = list(expected_job_ids)
    random.Random(value["random_seed"]).shuffle(expected_order)
    if job_ids != expected_order:
        raise OutputEvidenceError(
            "execution order does not match the declared deterministic shuffle"
        )
    return value


def _execution_order_reference(
    store: RawStore,
    manifest_payload: bytes,
    *,
    jobs_manifest_sha256: str,
    present: bool,
) -> dict[str, Any] | None:
    manifest, refs = _load_jobs_manifest(manifest_payload)
    if not present:
        if manifest["mode"] == "confirmatory":
            raise OutputEvidenceError("confirmatory jobs require an execution order manifest")
        return None
    payload = _safe_read(
        store,
        EXECUTION_ORDER_RELATIVE_PATH,
        maximum_bytes=5_000_000,
    )
    _load_execution_order(
        payload,
        jobs_manifest_sha256=jobs_manifest_sha256,
        jobs_manifest=manifest,
        manifest_refs=refs,
    )
    return {
        "path": EXECUTION_ORDER_RELATIVE_PATH,
        "sha256": _sha256(payload),
        "byte_count": len(payload),
    }


def _load_anchor(payload: bytes) -> dict[str, Any]:
    anchor = loads(payload)
    if not isinstance(anchor, dict) or set(anchor) != _ANCHOR_FIELDS:
        raise OutputEvidenceError("output evidence fields are invalid")
    if anchor["schema_version"] != "1.0" or anchor["stage"] != 1:
        raise OutputEvidenceError("output evidence version or stage is invalid")
    if _canonical_json(anchor) != payload:
        raise OutputEvidenceError("output evidence is not canonical compact JSON with one LF")
    _ref(
        anchor["jobs_manifest"],
        name="jobs manifest",
        expected_path=JOBS_MANIFEST_RELATIVE_PATH,
    )
    if anchor["execution_order"] is not None:
        _ref(
            anchor["execution_order"],
            name="execution order",
            expected_path=EXECUTION_ORDER_RELATIVE_PATH,
        )
    jobs = anchor["jobs"]
    if not isinstance(jobs, list) or not jobs:
        raise OutputEvidenceError("output evidence has no jobs")
    job_ids: list[str] = []
    for item in jobs:
        if not isinstance(item, dict) or set(item) != _ANCHOR_JOB_FIELDS:
            raise OutputEvidenceError("output evidence job fields are invalid")
        job_id = item["job_id"]
        if not isinstance(job_id, str) or not job_id:
            raise OutputEvidenceError("output evidence job_id is invalid")
        job_ids.append(job_id)
        if item["status"] not in {"valid", "invalid"}:
            raise OutputEvidenceError(f"output evidence status is invalid: {job_id}")
        if isinstance(item["record_count"], bool) or not isinstance(item["record_count"], int) or item["record_count"] < 0:
            raise OutputEvidenceError(f"output evidence record_count is invalid: {job_id}")
        _ref(item["job"], name=f"{job_id} job")
        _ref(item["receipt"], name=f"{job_id} receipt")
        _ref(item["raw"], name=f"{job_id} raw")
        if item["normalized"] is None:
            if item["status"] != "invalid":
                raise OutputEvidenceError(f"valid output evidence lacks normalized artifact: {job_id}")
        else:
            _ref(item["normalized"], name=f"{job_id} normalized")
            if item["status"] != "valid":
                raise OutputEvidenceError(f"invalid output evidence has normalized artifact: {job_id}")
    if job_ids != sorted(job_ids) or len(job_ids) != len(set(job_ids)):
        raise OutputEvidenceError("output evidence jobs must be sorted uniquely by job_id")
    return anchor


def _replay_raw(
    job: dict[str, Any],
    payload: bytes,
    vocabulary: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = loads_jsonl(payload, source_name="diagnostic output")
    for record in records:
        findings = record.get("findings") if isinstance(record, dict) else None
        if isinstance(findings, list) and len(findings) > 100:
            raise ValidationError("per-case finding limit is 100")
    validate_diagnostic_output_set(
        records,
        job["cases"],
        allowed_normalized_codes=vocabulary,
    )
    flattened = flatten_diagnostic_outputs(
        records,
        system_id=job["system_id"],
        run_number=job["run_number"],
    )
    return records, flattened


def _collect_contexts(
    store: RawStore,
    manifest_refs: list[dict[str, Any]],
    *,
    jobs_manifest_sha256: str,
    maximum_artifact_bytes: int,
) -> list[_JobContext]:
    contexts: list[_JobContext] = []
    seen_jobs: set[str] = set()
    seen_runs: set[tuple[str, int]] = set()
    for job_ref in manifest_refs:
        job_payload = _safe_read(
            store,
            job_ref["path"],
            maximum_bytes=5_000_000,
            expected_sha256=job_ref["sha256"],
            expected_byte_count=job_ref["byte_count"],
        )
        job = loads(job_payload)
        if not isinstance(job, dict):
            raise OutputEvidenceError("registered job must be a JSON object")
        try:
            validate_stage1_job(job, run_root=store.root)
            verify_job_artifacts(job)
        except Exception as exc:
            raise OutputEvidenceError(f"registered job is invalid: {exc}") from exc
        job_id = job["job_id"]
        expected_job_path = f"jobs/{job_id}.json"
        if job_ref["path"] != expected_job_path:
            raise OutputEvidenceError(f"job reference path does not match job identity: {job_id}")
        run_key = (job["system_id"], job["run_number"])
        if job_id in seen_jobs or run_key in seen_runs:
            raise OutputEvidenceError("jobs manifest contains duplicate job or system-run identity")
        seen_jobs.add(job_id)
        seen_runs.add(run_key)

        receipt_path = f"manifests/receipts/{job_id}.json"
        receipt_payload = _safe_read(
            store,
            receipt_path,
            maximum_bytes=1_000_000,
        )
        receipt = loads(receipt_payload)
        if not isinstance(receipt, dict) or set(receipt) != _RECEIPT_FIELDS:
            raise OutputEvidenceError(f"ingestion receipt fields are invalid: {job_id}")
        if receipt["job_sha256"] != job_ref["sha256"]:
            raise OutputEvidenceError(f"receipt job SHA-256 mismatch: {job_id}")
        if receipt["jobs_manifest_sha256"] != jobs_manifest_sha256:
            raise OutputEvidenceError(f"receipt manifest SHA-256 mismatch: {job_id}")
        artifact_name = f"{job_id}.jsonl"
        raw_receipt = _receipt(receipt["raw_receipt"], artifact_name=artifact_name, name="raw")
        raw_ref = {
            "path": f"raw/{artifact_name}",
            "sha256": raw_receipt.sha256,
            "byte_count": raw_receipt.byte_count,
        }
        normalized_receipt: Receipt | None
        normalized_ref: dict[str, Any] | None
        if receipt["status"] == "invalid":
            if (
                receipt["normalized_receipt"] is not None
                or receipt["record_count"] != 0
                or not isinstance(receipt["error_type"], str)
                or not isinstance(receipt["error_message"], str)
            ):
                raise OutputEvidenceError(f"invalid receipt fields are inconsistent: {job_id}")
            normalized_receipt = None
            normalized_ref = None
        elif receipt["status"] == "valid":
            if receipt["error_type"] is not None or receipt["error_message"] is not None:
                raise OutputEvidenceError(f"valid receipt contains an error: {job_id}")
            if receipt["record_count"] != job["expected_case_count"]:
                raise OutputEvidenceError(f"valid receipt record count mismatch: {job_id}")
            normalized_receipt = _receipt(
                receipt["normalized_receipt"],
                artifact_name=artifact_name,
                name="normalized",
            )
            normalized_ref = {
                "path": f"normalized/{artifact_name}",
                "sha256": normalized_receipt.sha256,
                "byte_count": normalized_receipt.byte_count,
            }
        else:
            raise OutputEvidenceError(f"receipt status is invalid: {job_id}")
        contexts.append(
            _JobContext(
                job=job,
                job_ref=job_ref,
                receipt=receipt,
                receipt_ref={
                    "path": receipt_path,
                    "sha256": _sha256(receipt_payload),
                    "byte_count": len(receipt_payload),
                },
                raw_receipt=raw_receipt,
                raw_ref=raw_ref,
                normalized_receipt=normalized_receipt,
                normalized_ref=normalized_ref,
            )
        )
    return contexts


def _assert_output_sets(
    store: RawStore,
    contexts: list[_JobContext],
    *,
    anchor_present: bool,
    execution_order_present: bool,
) -> None:
    job_ids = {item.job["job_id"] for item in contexts}
    valid_job_ids = {item.job["job_id"] for item in contexts if item.receipt["status"] == "valid"}
    _assert_exact_directory(
        store,
        "jobs",
        files={f"{job_id}.json" for job_id in job_ids},
    )
    _assert_exact_directory(
        store,
        "raw",
        files={f"{job_id}.jsonl" for job_id in job_ids},
    )
    _assert_exact_directory(
        store,
        "normalized",
        files={f"{job_id}.jsonl" for job_id in valid_job_ids},
    )
    _assert_exact_directory(
        store,
        "manifests/receipts",
        files={f"{job_id}.json" for job_id in job_ids},
    )
    _assert_manifest_directory(
        store,
        anchor_required=anchor_present,
        execution_order_required=execution_order_present,
    )


def _verify_contexts(
    store: RawStore,
    contexts: list[_JobContext],
    *,
    maximum_artifact_bytes: int,
) -> tuple[list[VerifiedStage1Run], list[dict[str, Any]]]:
    runs: list[VerifiedStage1Run] = []
    anchor_jobs: list[dict[str, Any]] = []
    for context in contexts:
        job = context.job
        job_id = job["job_id"]
        raw_payload = _safe_read(
            store,
            context.raw_ref["path"],
            maximum_bytes=maximum_artifact_bytes,
            expected_sha256=context.raw_ref["sha256"],
            expected_byte_count=context.raw_ref["byte_count"],
        )
        vocabulary = load_public_problem_vocabulary(job["problem_families"])
        normalized_payload: bytes | None = None
        if context.receipt["status"] == "invalid":
            try:
                _replay_raw(job, raw_payload, vocabulary)
            except (StrictJsonError, ValidationError) as exc:
                if (
                    type(exc).__name__ != context.receipt["error_type"]
                    or str(exc) != context.receipt["error_message"]
                ):
                    raise OutputEvidenceError(
                        f"invalid receipt error does not reproduce: {job_id}"
                    ) from exc
            else:
                raise OutputEvidenceError(f"invalid receipt raw bytes now validate: {job_id}")
        else:
            assert context.normalized_ref is not None
            normalized_payload = _safe_read(
                store,
                context.normalized_ref["path"],
                maximum_bytes=maximum_artifact_bytes,
                expected_sha256=context.normalized_ref["sha256"],
                expected_byte_count=context.normalized_ref["byte_count"],
            )
            _, flattened = _replay_raw(job, raw_payload, vocabulary)
            if _serialize_jsonl(flattened) != normalized_payload:
                raise OutputEvidenceError(
                    f"normalized artifact is not the deterministic raw projection: {job_id}"
                )
            normalized_records = (
                loads_jsonl(normalized_payload, source_name=f"normalized/{job_id}.jsonl")
                if flattened
                else []
            )
            case_by_id = {item["case_id"]: item for item in job["cases"]}
            for finding in normalized_records:
                source_case = case_by_id.get(finding.get("case_id"))
                if source_case is None:
                    raise OutputEvidenceError(
                        f"normalized finding references an unknown case: {job_id}"
                    )
                validate_finding(finding, source_case)

        runs.append(
            VerifiedStage1Run(
                job_id=job_id,
                system_id=job["system_id"],
                run_number=job["run_number"],
                status=context.receipt["status"],
                record_count=context.receipt["record_count"],
                raw_sha256=context.raw_receipt.sha256,
                normalized_sha256=(
                    context.normalized_receipt.sha256
                    if context.normalized_receipt is not None
                    else None
                ),
                normalized_byte_count=(
                    context.normalized_receipt.byte_count
                    if context.normalized_receipt is not None
                    else None
                ),
                normalized_payload=normalized_payload,
                cases_payload=_canonical_json(job["cases"]),
                model_payload=_canonical_json(job["model"]),
                error_type=context.receipt["error_type"],
                error_message=context.receipt["error_message"],
            )
        )
        anchor_jobs.append(
            {
                "job_id": job_id,
                "status": context.receipt["status"],
                "record_count": context.receipt["record_count"],
                "job": context.job_ref,
                "receipt": context.receipt_ref,
                "raw": context.raw_ref,
                "normalized": context.normalized_ref,
            }
        )
    runs.sort(key=lambda item: (item.system_id, item.run_number))
    anchor_jobs.sort(key=lambda item: item["job_id"])
    return runs, anchor_jobs


def _verify_chain(
    root: Path,
    store: RawStore,
    manifest_payload: bytes,
    *,
    jobs_manifest_sha256: str,
    maximum_artifact_bytes: int,
    anchor_present: bool,
    execution_order_present: bool,
) -> tuple[list[VerifiedStage1Run], list[dict[str, Any]]]:
    _, manifest_refs = _load_jobs_manifest(manifest_payload)
    contexts = _collect_contexts(
        store,
        manifest_refs,
        jobs_manifest_sha256=jobs_manifest_sha256,
        maximum_artifact_bytes=maximum_artifact_bytes,
    )
    _assert_output_sets(
        store,
        contexts,
        anchor_present=anchor_present,
        execution_order_present=execution_order_present,
    )
    runs, anchor_jobs = _verify_contexts(
        store,
        contexts,
        maximum_artifact_bytes=maximum_artifact_bytes,
    )
    _assert_output_sets(
        store,
        contexts,
        anchor_present=anchor_present,
        execution_order_present=execution_order_present,
    )
    return runs, anchor_jobs


def finalize_stage1_output(
    run_root: str | Path,
    *,
    expected_jobs_manifest_sha256: str,
    maximum_artifact_bytes: int = 50_000_000,
) -> Receipt:
    """Replay a complete run set and publish its fixed output anchor once.

    The caller-supplied jobs-manifest digest is the detached authority used only
    during finalization. The returned anchor receipt supplies the new detached
    authority required by reconciliation and scoring.
    """

    try:
        jobs_manifest_sha256 = _digest(
            expected_jobs_manifest_sha256,
            name="expected jobs manifest",
        )
        limit = _positive_limit(maximum_artifact_bytes, name="maximum_artifact_bytes")
        root = Path(os.path.abspath(os.fspath(run_root)))
        store = RawStore(root, authorized_root=root)
        manifest_payload = _safe_read(
            store,
            JOBS_MANIFEST_RELATIVE_PATH,
            maximum_bytes=5_000_000,
            expected_sha256=jobs_manifest_sha256,
        )
        anchor_preexists, execution_order_present = _assert_manifest_directory(
            store,
            anchor_required=None,
        )
        execution_order_ref = _execution_order_reference(
            store,
            manifest_payload,
            jobs_manifest_sha256=jobs_manifest_sha256,
            present=execution_order_present,
        )
        _, anchor_jobs = _verify_chain(
            root,
            store,
            manifest_payload,
            jobs_manifest_sha256=jobs_manifest_sha256,
            maximum_artifact_bytes=limit,
            anchor_present=anchor_preexists,
            execution_order_present=execution_order_present,
        )
        anchor = {
            "schema_version": "1.0",
            "stage": 1,
            "jobs_manifest": {
                "path": JOBS_MANIFEST_RELATIVE_PATH,
                "sha256": jobs_manifest_sha256,
                "byte_count": len(manifest_payload),
            },
            "execution_order": execution_order_ref,
            "jobs": anchor_jobs,
        }
        payload = _canonical_json(anchor)
        manifest_store = RawStore(root / "manifests", authorized_root=root)
        published = manifest_store.publish_or_verify("stage1-output-evidence.json", payload)
        _assert_manifest_directory(
            store,
            anchor_required=True,
            execution_order_required=execution_order_present,
        )
        _, verified_jobs = _verify_chain(
            root,
            store,
            manifest_payload,
            jobs_manifest_sha256=jobs_manifest_sha256,
            maximum_artifact_bytes=limit,
            anchor_present=True,
            execution_order_present=execution_order_present,
        )
        if verified_jobs != anchor_jobs:
            raise OutputEvidenceError("artifact evidence changed during finalization")
        return Receipt(
            relative_path=ANCHOR_RELATIVE_PATH,
            sha256=published.sha256,
            byte_count=published.byte_count,
        )
    except OutputEvidenceError:
        raise
    except (ImmutableWriteError, PathSafetyError, TamperError) as exc:
        raise OutputEvidenceError(str(exc)) from exc
    except Exception as exc:
        raise OutputEvidenceError(str(exc)) from exc


def verify_stage1_output_evidence(
    run_root: str | Path,
    *,
    expected_output_evidence_sha256: str,
    maximum_artifact_bytes: int = 50_000_000,
) -> VerifiedOutputEvidence:
    """Verify and replay the complete chain rooted at one detached anchor hash."""

    try:
        anchor_sha256 = _digest(
            expected_output_evidence_sha256,
            name="expected output evidence",
        )
        limit = _positive_limit(maximum_artifact_bytes, name="maximum_artifact_bytes")
        root = Path(os.path.abspath(os.fspath(run_root)))
        store = RawStore(root, authorized_root=root)
        anchor_payload = _safe_read(
            store,
            ANCHOR_RELATIVE_PATH,
            maximum_bytes=5_000_000,
        )
        if _sha256(anchor_payload) != anchor_sha256:
            raise OutputEvidenceError("output evidence does not match the expected SHA-256")
        anchor = _load_anchor(anchor_payload)
        manifest_ref = _ref(
            anchor["jobs_manifest"],
            name="jobs manifest",
            expected_path=JOBS_MANIFEST_RELATIVE_PATH,
        )
        manifest_payload = _safe_read(
            store,
            manifest_ref["path"],
            maximum_bytes=5_000_000,
            expected_sha256=manifest_ref["sha256"],
            expected_byte_count=manifest_ref["byte_count"],
        )
        manifest, manifest_refs = _load_jobs_manifest(manifest_payload)
        order_ref = anchor["execution_order"]
        if order_ref is None:
            if manifest["mode"] == "confirmatory":
                raise OutputEvidenceError(
                    "confirmatory jobs require a hash-bound execution order manifest"
                )
            execution_order_present = False
            execution_order_sha256 = None
        else:
            normalized_order_ref = _ref(
                order_ref,
                name="execution order",
                expected_path=EXECUTION_ORDER_RELATIVE_PATH,
            )
            order_payload = _safe_read(
                store,
                normalized_order_ref["path"],
                maximum_bytes=5_000_000,
                expected_sha256=normalized_order_ref["sha256"],
                expected_byte_count=normalized_order_ref["byte_count"],
            )
            _load_execution_order(
                order_payload,
                jobs_manifest_sha256=manifest_ref["sha256"],
                jobs_manifest=manifest,
                manifest_refs=manifest_refs,
            )
            execution_order_present = True
            execution_order_sha256 = normalized_order_ref["sha256"]
        runs, projected_jobs = _verify_chain(
            root,
            store,
            manifest_payload,
            jobs_manifest_sha256=manifest_ref["sha256"],
            maximum_artifact_bytes=limit,
            anchor_present=True,
            execution_order_present=execution_order_present,
        )
        if anchor["jobs"] != projected_jobs:
            raise OutputEvidenceError("output evidence contradicts verified job artifacts")
        return VerifiedOutputEvidence(
            jobs_manifest_sha256=manifest_ref["sha256"],
            output_evidence_sha256=anchor_sha256,
            execution_order_sha256=execution_order_sha256,
            runs=tuple(runs),
            anchor_payload=anchor_payload,
        )
    except OutputEvidenceError:
        raise
    except (PathSafetyError, TamperError) as exc:
        raise OutputEvidenceError(str(exc)) from exc
    except Exception as exc:
        raise OutputEvidenceError(str(exc)) from exc
