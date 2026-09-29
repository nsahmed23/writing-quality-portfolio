"""Write-once ingestion for untrusted diagnostic model outputs."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .storage import PathSafetyError, RawStore, Receipt, _hold_directory_tree
from .strict_json import StrictJsonError, loads_jsonl
from .validation import (
    ValidationError,
    flatten_diagnostic_outputs,
    validate_diagnostic_output_set,
)


class PayloadLimitError(ValueError):
    """Raised before copying an artifact that exceeds a configured hard limit."""


class UnsafeInputPathError(ValueError):
    """Raised when an inbox artifact is reachable through an unsafe alias."""


@dataclass(frozen=True)
class IngestResult:
    status: str
    raw_receipt: Receipt
    normalized_receipt: Receipt | None
    record_count: int
    error_type: str | None = None
    error_message: str | None = None


def _parse_jsonl_bytes(payload: bytes) -> list[dict[str, Any]]:
    return loads_jsonl(payload, source_name="diagnostic output")


def _serialize_jsonl(records: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for item in records
    ).encode("utf-8")


def _lexical_absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_lexical_traversal(path: str | Path, *, name: str) -> None:
    if ".." in Path(path).parts:
        raise UnsafeInputPathError(f"{name} contains lexical traversal")


def _lstat_without_alias(path: Path) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise UnsafeInputPathError(f"registered inbox path is unavailable: {path.name}") from exc
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_flag:
        raise UnsafeInputPathError(
            f"registered inbox path contains a symlink, junction, or reparse point: {path.name}"
        )
    return metadata


def _validate_direct_inbox_path(path: Path, root: Path) -> os.stat_result:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise UnsafeInputPathError("registered inbox artifact escapes the run root") from exc
    if len(relative.parts) != 2 or relative.parts[0].casefold() != "inbox":
        raise UnsafeInputPathError("registered inbox artifact is not a direct inbox file")

    root_metadata = _lstat_without_alias(root)
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise UnsafeInputPathError("run root is not a directory")
    inbox_metadata = _lstat_without_alias(root / relative.parts[0])
    if not stat.S_ISDIR(inbox_metadata.st_mode):
        raise UnsafeInputPathError("registered inbox parent is not a directory")
    artifact_metadata = _lstat_without_alias(path)
    if not stat.S_ISREG(artifact_metadata.st_mode):
        raise UnsafeInputPathError("registered inbox artifact is not a regular file")
    if artifact_metadata.st_nlink != 1:
        raise UnsafeInputPathError("registered inbox artifact is a hardlink")
    return artifact_metadata


def _file_snapshot(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def read_registered_inbox_artifact(
    input_path: str | Path,
    *,
    run_root: str | Path,
    artifact_name: str,
    registered_output_path: str | Path,
    max_bytes: int = 50_000_000,
) -> bytes:
    """Read one direct inbox file while rejecting traversal and filesystem aliases.

    Metadata is checked before, during, and after the read. A same-size overwrite
    with restored timestamps can evade metadata-only mutation detection, so callers
    must publish completed inbox files atomically and never edit them in place.
    """

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    if not isinstance(artifact_name, str) or not artifact_name or Path(artifact_name).name != artifact_name:
        raise UnsafeInputPathError("artifact name must be one direct file name")

    _reject_lexical_traversal(input_path, name="input path")
    _reject_lexical_traversal(registered_output_path, name="registered output path")
    root = _lexical_absolute(run_root)
    supplied = _lexical_absolute(input_path)
    expected = root / "inbox" / artifact_name
    registered = _lexical_absolute(registered_output_path)
    if supplied != expected or registered != expected:
        raise UnsafeInputPathError(f"input path is an unsafe alias for {artifact_name}")

    try:
        with _hold_directory_tree(
            expected.parent,
            authorized_root=root,
            create=False,
        ) as boundary:
            before = _validate_direct_inbox_path(expected, root)
            if before.st_size > max_bytes:
                raise PayloadLimitError(f"raw payload exceeds {max_bytes} bytes")

            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(expected, flags)
            except OSError as exc:
                raise UnsafeInputPathError("registered inbox artifact could not be opened safely") from exc
            try:
                opened = os.fstat(descriptor)
                if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                    raise UnsafeInputPathError("opened inbox artifact is not a unique regular file")
                if _file_snapshot(opened) != _file_snapshot(before):
                    raise UnsafeInputPathError("registered inbox artifact changed before it was opened")
                with os.fdopen(descriptor, "rb", closefd=False) as handle:
                    payload = handle.read(max_bytes + 1)
                after_read = os.fstat(descriptor)
                if _file_snapshot(after_read) != _file_snapshot(opened) or len(payload) != opened.st_size:
                    raise UnsafeInputPathError("registered inbox artifact changed while it was read")
            finally:
                os.close(descriptor)
            if len(payload) > max_bytes:
                raise PayloadLimitError(f"raw payload exceeds {max_bytes} bytes")

            boundary.assert_current()
            after = _validate_direct_inbox_path(expected, root)
            if _file_snapshot(after) != _file_snapshot(after_read):
                raise UnsafeInputPathError("registered inbox artifact changed while it was read")
            return payload
    except PathSafetyError as exc:
        raise UnsafeInputPathError(str(exc)) from exc


def ingest_diagnostic_bytes(
    payload: bytes,
    *,
    cases: list[dict[str, Any]],
    system_id: str,
    run_number: int,
    artifact_name: str,
    raw_store: RawStore,
    normalized_store: RawStore,
    max_raw_bytes: int = 50_000_000,
    max_findings_per_case: int = 100,
    allowed_normalized_codes: set[str] | None = None,
    recover_existing: bool = False,
    failure_injector: Callable[[str], None] | None = None,
) -> IngestResult:
    """Preserve bytes first, then validate and normalize without repair.

    Recovery accepts an existing artifact only when its bytes exactly equal the
    deterministic bytes for this invocation. ``failure_injector`` is a test seam
    for simulating process loss between immutable publications.
    """

    if isinstance(max_raw_bytes, bool) or not isinstance(max_raw_bytes, int) or max_raw_bytes < 1:
        raise ValueError("max_raw_bytes must be a positive integer")
    if len(payload) > max_raw_bytes:
        raise PayloadLimitError(f"raw payload exceeds {max_raw_bytes} bytes")
    if isinstance(max_findings_per_case, bool) or not isinstance(max_findings_per_case, int) or max_findings_per_case < 1:
        raise ValueError("max_findings_per_case must be a positive integer")
    publisher = RawStore.publish_or_verify if recover_existing else RawStore.write_once
    raw_receipt = publisher(raw_store, artifact_name, payload)
    if failure_injector is not None:
        failure_injector("raw_published")
    try:
        records = _parse_jsonl_bytes(payload)
        for record in records:
            findings = record.get("findings") if isinstance(record, dict) else None
            if isinstance(findings, list) and len(findings) > max_findings_per_case:
                raise ValidationError(f"per-case finding limit is {max_findings_per_case}")
        validate_diagnostic_output_set(
            records,
            cases,
            allowed_normalized_codes=allowed_normalized_codes,
        )
        flattened = flatten_diagnostic_outputs(records, system_id=system_id, run_number=run_number)
        normalized_payload = _serialize_jsonl(flattened)
        normalized_receipt = publisher(normalized_store, artifact_name, normalized_payload)
        if failure_injector is not None:
            failure_injector("normalized_published")
    except (StrictJsonError, ValidationError) as exc:
        return IngestResult(
            status="invalid",
            raw_receipt=raw_receipt,
            normalized_receipt=None,
            record_count=0,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    return IngestResult(
        status="valid",
        raw_receipt=raw_receipt,
        normalized_receipt=normalized_receipt,
        record_count=len(records),
    )
