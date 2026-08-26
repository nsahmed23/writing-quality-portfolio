"""Prepare immutable, gold-free Stage 1 generation job packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from wqeval.jobs import assert_no_gold_leak, prepare_stage1_jobs, validate_stage1_job
from wqeval.provenance import resolve_pinned_source, verify_frozen_corpus_file
from wqeval.storage import _HeldDirectoryBoundary, _hold_directory_tree, _lexical_absolute
from wqeval.strict_json import load_jsonl, loads
from wqeval.validation import validate_case


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_keys(value: Any, required: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{name} fields do not match the frozen schema")
    return value


def encode_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _write_new_bytes(path: Path, payload: bytes) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace existing job artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        os.unlink(temporary)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_new(path: Path, value: Any) -> None:
    _write_new_bytes(path, encode_json(value))


def _safe_relative_artifact_path(value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("artifact path must be non-empty POSIX-relative text")
    parts = value.split("/")
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    reserved = {"con", "prn", "aux", "nul"}
    reserved.update(f"com{index}" for index in range(1, 10))
    reserved.update(f"lpt{index}" for index in range(1, 10))
    unsafe_segment = any(
        part in {"", ".", ".."}
        or ":" in part
        or part.endswith((" ", "."))
        or any(ord(character) < 32 for character in part)
        or part.split(".", 1)[0].rstrip(" .").casefold() in reserved
        for part in parts
    )
    if windows.is_absolute() or windows.drive or posix.is_absolute() or unsafe_segment:
        raise ValueError(f"artifact path escapes or aliases the run tree: {value}")
    return Path(*parts)


def _publish_held_tree(
    boundary: _HeldDirectoryBoundary,
    source: Path,
    destination: Path,
) -> None:
    boundary.rename_directory(source, destination)


def publish_new_tree(
    run_root: Path,
    artifacts: dict[str, Any],
    *,
    authorized_root: Path,
) -> None:
    """Publish a complete job tree inside one explicit lexical trust boundary."""

    root = _lexical_absolute(run_root)
    authorization = _lexical_absolute(authorized_root)
    try:
        root.relative_to(authorization)
    except ValueError as exc:
        raise ValueError("run tree escapes the explicit authorized root") from exc
    if root == authorization:
        raise ValueError("run tree must be a child of the explicit authorized root")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("job publication requires at least one artifact")

    encoded: dict[Path, bytes] = {}
    for relative, value in artifacts.items():
        path = _safe_relative_artifact_path(relative)
        if path in encoded:
            raise ValueError(f"duplicate artifact path: {relative}")
        encoded[path] = encode_json(value)

    with _hold_directory_tree(
        root.parent,
        authorized_root=authorization,
        create=True,
    ) as boundary:
        try:
            root.lstat()
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(f"refusing to replace existing run tree: {root}")
        staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.", suffix=".preparing", dir=root.parent))
        boundary.ensure_directory(staging, create=False)
        for relative, payload in sorted(encoded.items(), key=lambda item: item[0].as_posix()):
            target = staging / relative
            boundary.ensure_directory(target.parent, create=True)
            _write_new_bytes(target, payload)
        boundary.assert_current()
        _publish_held_tree(boundary, staging, root)


def manifest_job_entries(job_artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for relative_path in sorted(job_artifacts):
        _safe_relative_artifact_path(relative_path)
        payload = encode_json(job_artifacts[relative_path])
        entries.append(
            {
                "path": relative_path,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    return entries


def resolve_source(project: Path, workspace: Path, record: dict[str, Any]) -> dict[str, Any]:
    return resolve_pinned_source(project, workspace, record)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--mode", choices=("development", "confirmatory"), required=True)
    arguments = parser.parse_args()
    project = arguments.project.resolve()
    workspace = arguments.workspace.resolve()
    run_root = _lexical_absolute(arguments.run_root)
    systems_path = project / "systems" / "systems.json"
    prompt_path = project / "systems" / "prompt-manifest.json"
    run_config_path = project / "config" / "run.json"
    thresholds_path = project / "config" / "thresholds.json"
    corpus_freeze_path = project / "corpus" / "freeze-manifest.json"
    systems_manifest = exact_keys(
        loads(systems_path.read_bytes()),
        {"schema_version", "frozen", "common_envelope", "systems"},
        "systems manifest",
    )
    prompt_manifest = exact_keys(
        loads(prompt_path.read_bytes()),
        {
            "schema_version",
            "status",
            "candidate_count",
            "common_envelope_sha256",
            "problem_families",
            "native_map",
            "systems_sha256",
            "run_config_sha256",
            "thresholds_sha256",
            "corpus_freeze_manifest_sha256",
            "rules",
            "settings_source",
            "systems_source",
        },
        "prompt manifest",
    )
    run_config = exact_keys(
        loads(run_config_path.read_bytes()),
        {
            "schema_version",
            "run_id",
            "status_label",
            "random_seed",
            "stage1_runs_per_case",
            "stage2_runs_per_case",
            "job_order",
            "generator_isolation",
            "model",
            "network",
            "human_review",
        },
        "run config",
    )
    thresholds = exact_keys(loads(thresholds_path.read_bytes()), {"schema_version", "stage1", "stage2"}, "thresholds")
    corpus_freeze = exact_keys(
        loads(corpus_freeze_path.read_bytes()),
        {"schema_version", "status", "gold_status", "files"},
        "corpus freeze manifest",
    )
    if systems_manifest["schema_version"] != "1.0" or systems_manifest["frozen"] is not True:
        raise ValueError("systems manifest is not frozen")
    if prompt_manifest["schema_version"] != "1.0" or prompt_manifest["status"] != "frozen_before_stage1_generation":
        raise ValueError("prompt manifest is not frozen for Stage 1 generation")
    if run_config["schema_version"] != "1.0" or thresholds["schema_version"] != "1.0":
        raise ValueError("configuration schema version is invalid")
    observed_hashes = {
        "systems_sha256": sha256(systems_path),
        "run_config_sha256": sha256(run_config_path),
        "thresholds_sha256": sha256(thresholds_path),
        "corpus_freeze_manifest_sha256": sha256(corpus_freeze_path),
    }
    for field, observed in observed_hashes.items():
        if prompt_manifest[field] != observed:
            raise ValueError(f"prompt manifest hash mismatch for {field}")
    if prompt_manifest["candidate_count"] != len(systems_manifest["systems"]):
        raise ValueError("candidate count does not match systems manifest")
    if prompt_manifest["native_map"].get("generator_visible") is not False:
        raise ValueError("evaluator-private native map visibility is invalid")
    verify_frozen_corpus_file(
        arguments.cases,
        project=project,
        freeze_manifest_path=corpus_freeze_path,
        expected_freeze_sha256=observed_hashes["corpus_freeze_manifest_sha256"],
    )
    expected_case_name = "cases.dev.jsonl" if arguments.mode == "development" else "cases.test.jsonl"
    expected_runs = 1 if arguments.mode == "development" else run_config["stage1_runs_per_case"]
    if arguments.cases.resolve().name != expected_case_name or arguments.runs != expected_runs:
        raise ValueError(f"{arguments.mode} mode requires {expected_case_name} and {expected_runs} run(s)")
    cases = load_jsonl(arguments.cases)
    for item in cases:
        validate_case(item)
        assert_no_gold_leak(item)

    systems: list[dict[str, Any]] = []
    by_id = {item["system_id"]: item for item in systems_manifest["systems"]}
    for system_id in sorted(by_id):
        source = by_id[system_id]
        systems.append(
            {
                "system_id": system_id,
                "display_name": source["display_name"],
                "family": source["family"],
                "fidelity_class": source["fidelity_class"],
                "diagnostic_status": source["diagnostic_status"],
                "source_files": [resolve_source(project, workspace, item) for item in source["source_files"]],
            }
        )

    jobs = prepare_stage1_jobs(
        cases,
        systems,
        runs=arguments.runs,
        seed=run_config["random_seed"],
        model=run_config["model"],
    )
    common = resolve_source(project, workspace, {"path": "systems/common-envelope.md", "sha256": prompt_manifest["common_envelope_sha256"]})
    taxonomy = resolve_source(project, workspace, prompt_manifest["problem_families"])
    job_artifacts: dict[str, dict[str, Any]] = {}
    system_lookup = {item["system_id"]: item for item in systems}
    for job in jobs:
        system = system_lookup[job["system_id"]]
        job["common_envelope"] = common
        job["problem_families"] = taxonomy
        job["system_display_name"] = system["display_name"]
        job["family"] = system["family"]
        job["fidelity_class"] = system["fidelity_class"]
        job["diagnostic_status"] = system["diagnostic_status"]
        job["output_contract"] = {
            "format": "utf8_jsonl",
            "records": job["expected_case_count"],
            "one_record_per_case": True,
            "surrounding_prose": False,
            "output_path": str((run_root / "inbox" / f"{job['job_id']}.jsonl").resolve()),
        }
        assert_no_gold_leak(job)
        validate_stage1_job(job, run_root=run_root)
        relative_path = f"jobs/{job['job_id']}.json"
        job_artifacts[relative_path] = job
    manifest = {
        "schema_version": "1.0",
        "stage": 1,
        "mode": arguments.mode,
        "case_file": str(arguments.cases.resolve()),
        "case_file_sha256": sha256(arguments.cases.resolve()),
        "job_count": len(job_artifacts),
        "runs": arguments.runs,
        "random_seed": run_config["random_seed"],
        "model": run_config["model"],
        "systems_manifest_sha256": observed_hashes["systems_sha256"],
        "prompt_manifest_sha256": sha256(prompt_path),
        "run_config_sha256": observed_hashes["run_config_sha256"],
        "thresholds_sha256": observed_hashes["thresholds_sha256"],
        "corpus_freeze_manifest_sha256": observed_hashes["corpus_freeze_manifest_sha256"],
        "jobs": manifest_job_entries(job_artifacts),
    }
    execution_order = {
        "schema_version": "1.0",
        "stage": 1,
        "mode": arguments.mode,
        "order_policy": run_config["job_order"],
        "random_seed": run_config["random_seed"],
        "jobs_manifest_sha256": hashlib.sha256(encode_json(manifest)).hexdigest(),
        "job_count": len(jobs),
        "job_ids": [job["job_id"] for job in jobs],
    }
    publish_new_tree(
        run_root,
        {
            **job_artifacts,
            "manifests/jobs.json": manifest,
            "manifests/execution-order.json": execution_order,
        },
        authorized_root=project / "runs",
    )
    print(json.dumps({"jobs": len(job_artifacts), "cases_per_job": len(cases), "runs": arguments.runs}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
