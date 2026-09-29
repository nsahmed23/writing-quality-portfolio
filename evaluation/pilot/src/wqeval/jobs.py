"""Gold-free deterministic job preparation for isolated generator runs."""

from __future__ import annotations

import copy
import hashlib
import random
import re
from pathlib import Path
from typing import Any

from .validation import validate_case


class GoldLeakError(ValueError):
    """Raised when hidden corpus fields enter a generation job."""


FORBIDDEN_GOLD_KEYS = {
    "gold_findings",
    "case_decision",
    "propositions",
    "voice_signals",
    "provisional_gold",
    "features",
    "source_refs",
    "primary_source_id",
}
SYSTEM_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def validate_system_id(value: Any) -> str:
    if not isinstance(value, str) or not SYSTEM_ID_PATTERN.fullmatch(value) or value.casefold() in WINDOWS_RESERVED:
        raise ValueError("system_id must be a safe lowercase hyphenated identifier")
    return value


def _artifact_reference(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ValueError(f"{name} must contain only path and sha256")
    if not isinstance(value["path"], str) or not value["path"]:
        raise ValueError(f"{name} path must be non-empty text")
    digest = value["sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"{name} sha256 is invalid")
    return value


def validate_stage1_job(value: Any, *, run_root: str | Path) -> None:
    required = {
        "schema_version",
        "job_id",
        "stage",
        "system_id",
        "run_number",
        "model",
        "source_files",
        "expected_case_count",
        "cases",
        "common_envelope",
        "problem_families",
        "system_display_name",
        "family",
        "fidelity_class",
        "diagnostic_status",
        "output_contract",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Stage 1 job fields do not match the frozen schema")
    if value["schema_version"] != "1.0" or value["stage"] != 1:
        raise ValueError("Stage 1 job version or stage is invalid")
    system_id = validate_system_id(value["system_id"])
    run_number = value["run_number"]
    if isinstance(run_number, bool) or not isinstance(run_number, int) or run_number < 1:
        raise ValueError("run_number must be a positive integer")
    expected_job_id = f"stage1-{system_id}-run-{run_number:02d}"
    if value["job_id"] != expected_job_id:
        raise ValueError("job_id does not match system_id and run_number")
    if not isinstance(value["model"], dict):
        raise ValueError("model must be an object")
    if not isinstance(value["source_files"], list) or not value["source_files"]:
        raise ValueError("source_files must be a non-empty list")
    for index, reference in enumerate(value["source_files"]):
        _artifact_reference(reference, f"source_files[{index}]")
        if "private" in Path(reference["path"]).parts or "gold" in Path(reference["path"]).parts:
            raise ValueError("private or gold paths are forbidden in generator jobs")
    for name in ("common_envelope", "problem_families"):
        _artifact_reference(value[name], name)
    for name in ("system_display_name", "family", "fidelity_class", "diagnostic_status"):
        if not isinstance(value[name], str) or not value[name].strip():
            raise ValueError(f"{name} must be non-empty text")

    cases = value["cases"]
    expected_count = value["expected_case_count"]
    if not isinstance(cases, list) or isinstance(expected_count, bool) or not isinstance(expected_count, int):
        raise ValueError("cases or expected_case_count is invalid")
    if expected_count != len(cases) or expected_count < 1:
        raise ValueError("expected_case_count does not match cases")
    case_ids: list[str] = []
    for item in cases:
        validate_case(item)
        case_ids.append(item["case_id"])
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("job case IDs must be unique")
    assert_no_gold_leak(cases)

    contract = value["output_contract"]
    contract_fields = {"format", "records", "one_record_per_case", "surrounding_prose", "output_path"}
    if not isinstance(contract, dict) or set(contract) != contract_fields:
        raise ValueError("output_contract fields are invalid")
    if (
        contract["format"] != "utf8_jsonl"
        or contract["records"] != expected_count
        or contract["one_record_per_case"] is not True
        or contract["surrounding_prose"] is not False
    ):
        raise ValueError("output_contract values are invalid")
    inbox = (Path(run_root).resolve() / "inbox").resolve()
    output = Path(contract["output_path"])
    if not output.is_absolute() or output.resolve().parent != inbox or output.name != f"{expected_job_id}.jsonl":
        raise ValueError("output_contract path is outside the run inbox")


def assert_no_gold_leak(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_GOLD_KEYS:
                raise GoldLeakError(f"forbidden gold key at {path}.{key}")
            assert_no_gold_leak(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_no_gold_leak(item, f"{path}[{index}]")


def _job_seed(seed: int, system_id: str, run_number: int) -> int:
    digest = hashlib.sha256(f"{seed}:{system_id}:{run_number}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def prepare_stage1_jobs(
    cases: list[dict[str, Any]],
    systems: list[dict[str, Any]],
    *,
    runs: int,
    seed: int,
    model: dict[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(runs, bool) or not isinstance(runs, int) or runs < 1:
        raise ValueError("runs must be a positive integer")
    sorted_cases = sorted(copy.deepcopy(cases), key=lambda item: item["case_id"])
    sorted_systems = sorted(copy.deepcopy(systems), key=lambda item: item["system_id"])
    case_ids = [item["case_id"] for item in sorted_cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case IDs must be unique")
    system_ids = [item["system_id"] for item in sorted_systems]
    for system_id in system_ids:
        validate_system_id(system_id)
    if len(system_ids) != len(set(system_ids)):
        raise ValueError("system IDs must be unique")
    for item in sorted_cases:
        assert_no_gold_leak(item)

    jobs: list[dict[str, Any]] = []
    for system in sorted_systems:
        system_id = system["system_id"]
        for run_number in range(1, runs + 1):
            ordered_cases = copy.deepcopy(sorted_cases)
            random.Random(_job_seed(seed, system_id, run_number)).shuffle(ordered_cases)
            job = {
                "schema_version": "1.0",
                "job_id": f"stage1-{system_id}-run-{run_number:02d}",
                "stage": 1,
                "system_id": system_id,
                "run_number": run_number,
                "model": copy.deepcopy(model),
                "source_files": copy.deepcopy(system.get("source_files", [])),
                "expected_case_count": len(ordered_cases),
                "cases": ordered_cases,
            }
            assert_no_gold_leak(job)
            jobs.append(job)
    random.Random(seed).shuffle(jobs)
    return jobs
