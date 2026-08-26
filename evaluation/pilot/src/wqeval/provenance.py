"""Hash-chain verification for frozen generation jobs."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .jobs import validate_stage1_job
from .strict_json import loads


class ProvenanceError(ValueError):
    """Raised when a job is not bound to the expected frozen manifest."""


@dataclass(frozen=True)
class VerifiedJobArtifact:
    """A parsed job and the digest already verified against its manifest entry."""

    job: dict[str, Any]
    sha256: str
    byte_count: int


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _verified_artifact_bytes(reference: Any, *, max_bytes: int = 5_000_000) -> bytes:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ProvenanceError("artifact reference must contain only path and sha256")
    path_value = reference["path"]
    digest = reference["sha256"]
    if not isinstance(path_value, str) or not path_value or not isinstance(digest, str):
        raise ProvenanceError("artifact reference values are invalid")
    path = Path(path_value)
    if not path.is_absolute() or not path.is_file():
        raise ProvenanceError("pinned artifact path is missing or not absolute")
    size = path.stat().st_size
    if size > max_bytes:
        raise ProvenanceError(f"pinned artifact exceeds {max_bytes} bytes")
    payload = path.read_bytes()
    if len(payload) != size or _sha256(payload) != digest:
        raise ProvenanceError("pinned artifact bytes do not match the job reference")
    return payload


def load_public_problem_vocabulary(reference: Any) -> set[str]:
    value = loads(_verified_artifact_bytes(reference))
    required = {"schema_version", "mapping_status", "change_families", "keep_families"}
    if not isinstance(value, dict) or set(value) != required or value["schema_version"] != "1.0":
        raise ProvenanceError("public problem vocabulary schema is invalid")
    if value["mapping_status"] != "frozen_before_sealed_generation":
        raise ProvenanceError("public problem vocabulary is not frozen")
    codes: list[str] = []
    for section in ("change_families", "keep_families"):
        entries = value[section]
        if not isinstance(entries, list) or not entries:
            raise ProvenanceError(f"{section} must be a non-empty list")
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"code", "description"}:
                raise ProvenanceError("problem-family entry schema is invalid")
            code = entry["code"]
            description = entry["description"]
            if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", code):
                raise ProvenanceError("problem-family code is invalid")
            if not isinstance(description, str) or not description.strip():
                raise ProvenanceError("problem-family description is invalid")
            codes.append(code)
    if len(codes) != len(set(codes)):
        raise ProvenanceError("problem-family codes must be unique")
    return set(codes)


def verify_job_artifacts(job: dict[str, Any]) -> None:
    for reference in job["source_files"]:
        _verified_artifact_bytes(reference)
    _verified_artifact_bytes(job["common_envelope"])
    load_public_problem_vocabulary(job["problem_families"])


def verify_frozen_corpus_file(
    cases_path: str | Path,
    *,
    project: str | Path,
    freeze_manifest_path: str | Path,
    expected_freeze_sha256: str,
) -> None:
    project_root = Path(project).resolve()
    corpus_root = (project_root / "corpus").resolve()
    cases_file = _contained(Path(cases_path), corpus_root, "corpus case file")
    freeze_file = _contained(Path(freeze_manifest_path), corpus_root, "corpus freeze manifest")
    freeze_bytes = freeze_file.read_bytes()
    if _sha256(freeze_bytes) != expected_freeze_sha256:
        raise ProvenanceError("corpus freeze manifest hash does not match the expected hash")
    freeze = loads(freeze_bytes)
    if not isinstance(freeze, dict) or set(freeze) != {"schema_version", "status", "gold_status", "files"}:
        raise ProvenanceError("corpus freeze manifest schema is invalid")
    if freeze["schema_version"] != "1.0" or freeze["status"] != "frozen" or not isinstance(freeze["files"], list):
        raise ProvenanceError("corpus freeze manifest is not frozen")
    matches: list[dict[str, Any]] = []
    registered_paths: set[Path] = set()
    for entry in freeze["files"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "bytes"}:
            raise ProvenanceError("corpus freeze entry schema is invalid")
        relative = _safe_manifest_path(entry["path"])
        registered = _contained(project_root.joinpath(*relative.parts), project_root, "registered corpus artifact")
        if registered in registered_paths:
            raise ProvenanceError("corpus freeze manifest has duplicate paths")
        registered_paths.add(registered)
        if registered == cases_file:
            matches.append(entry)
    if len(matches) != 1:
        raise ProvenanceError("case file is not registered exactly once in the corpus freeze manifest")
    payload = cases_file.read_bytes()
    match = matches[0]
    if (
        isinstance(match["bytes"], bool)
        or not isinstance(match["bytes"], int)
        or match["bytes"] != len(payload)
        or match["sha256"] != _sha256(payload)
    ):
        raise ProvenanceError("case file bytes do not match the corpus freeze manifest")


def _contained(path: Path, root: Path, name: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ProvenanceError(f"{name} escapes its authorized root") from exc
    return resolved


def _safe_manifest_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ProvenanceError("manifest job path must be non-empty text")
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value.replace("\\", "/"))
    if windows.is_absolute() or windows.drive or posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise ProvenanceError("manifest job path is unsafe")
    return posix


def resolve_pinned_source(
    project: str | Path,
    workspace: str | Path,
    record: dict[str, Any],
) -> dict[str, str]:
    if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
        raise ProvenanceError("source reference must contain only path and sha256")
    relative = _safe_manifest_path(record["path"])
    project_root = Path(project).resolve()
    workspace_root = Path(workspace).resolve()
    if relative.parts[0].casefold() == "work":
        path = workspace_root.joinpath(*relative.parts).resolve()
        allowed_roots = (
            (workspace_root / "work" / "writing-quality-portfolio").resolve(),
            (workspace_root / "work" / "research-writing-repos" / "sources").resolve(),
        )
    else:
        path = project_root.joinpath(*relative.parts).resolve()
        allowed_roots = (
            (project_root / "systems").resolve(),
            (project_root / "taxonomy").resolve(),
            (project_root / "config").resolve(),
        )
    if not any(_is_relative_to(path, root) for root in allowed_roots):
        raise ProvenanceError("source path is outside the allowlisted roots")
    if any(part.casefold() in {"private", "gold", ".git", ".ssh"} for part in path.parts):
        raise ProvenanceError("private, gold, credential, or repository metadata paths are forbidden")
    if not path.is_file():
        raise ProvenanceError("source file is missing")
    payload = path.read_bytes()
    digest = record["sha256"]
    if not isinstance(digest, str) or _sha256(payload) != digest:
        raise ProvenanceError("source file hash does not match its frozen reference")
    return {"path": str(path), "sha256": digest}


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def verify_job_artifact_from_manifest(
    job_path: str | Path,
    manifest_path: str | Path,
    *,
    run_root: str | Path,
    expected_manifest_sha256: str,
) -> VerifiedJobArtifact:
    root = Path(run_root).resolve()
    manifest_file = _contained(Path(manifest_path), root / "manifests", "jobs manifest")
    job_file = _contained(Path(job_path), root / "jobs", "job")
    manifest_bytes = manifest_file.read_bytes()
    if _sha256(manifest_bytes) != expected_manifest_sha256:
        raise ProvenanceError("jobs manifest hash does not match the frozen expected hash")
    manifest = loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0" or not isinstance(manifest.get("jobs"), list):
        raise ProvenanceError("jobs manifest schema is invalid")

    matches: list[dict[str, Any]] = []
    for entry in manifest["jobs"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "bytes"}:
            raise ProvenanceError("jobs manifest entry schema is invalid")
        relative = _safe_manifest_path(entry["path"])
        registered = _contained(root.joinpath(*relative.parts), root / "jobs", "registered job")
        if registered == job_file:
            matches.append(entry)
    if len(matches) != 1:
        raise ProvenanceError("job is not registered exactly once in the frozen manifest")
    job_bytes = job_file.read_bytes()
    entry = matches[0]
    if isinstance(entry["bytes"], bool) or not isinstance(entry["bytes"], int):
        raise ProvenanceError("registered job byte count is invalid")
    if entry["bytes"] != len(job_bytes) or entry["sha256"] != _sha256(job_bytes):
        raise ProvenanceError("job bytes do not match the frozen manifest entry")
    job = loads(job_bytes)
    if not isinstance(job, dict):
        raise ProvenanceError("job must be a JSON object")
    try:
        validate_stage1_job(job, run_root=root)
    except ValueError as exc:
        raise ProvenanceError(f"registered job schema is invalid: {exc}") from exc
    return VerifiedJobArtifact(job=job, sha256=entry["sha256"], byte_count=entry["bytes"])


def verify_job_from_manifest(
    job_path: str | Path,
    manifest_path: str | Path,
    *,
    run_root: str | Path,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    """Compatibility wrapper returning only the verified parsed job."""

    return verify_job_artifact_from_manifest(
        job_path,
        manifest_path,
        run_root=run_root,
        expected_manifest_sha256=expected_manifest_sha256,
    ).job
