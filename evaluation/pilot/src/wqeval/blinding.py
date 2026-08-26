"""Deterministic system-identity masking for reviewer packets."""

from __future__ import annotations

import copy
import json
import random
import string
from typing import Any


class IdentityLeakError(ValueError):
    """Raised when a blinded packet still contains a forbidden identity term."""


def _aliases(count: int) -> list[str]:
    values: list[str] = []
    for first in string.ascii_uppercase:
        for second in string.ascii_uppercase:
            for third in string.ascii_uppercase:
                values.append(f"System-{first}{second}{third}")
                if len(values) == count:
                    return values
    raise ValueError("too many systems to blind")


def build_blind_map(system_ids: list[str], *, seed: int) -> dict[str, str]:
    unique = sorted(set(system_ids))
    if len(unique) != len(system_ids):
        raise ValueError("system IDs must be unique")
    aliases = _aliases(len(unique))
    random.Random(seed).shuffle(aliases)
    return dict(zip(unique, aliases))


IDENTITY_KEYS = {
    "system_id",
    "system_name",
    "generator_id",
    "adapter",
    "prompt_path",
    "raw_path",
    "model_name",
    "finding_id",
    "system_issue_code",
    "field_origin",
}


def _strip_identity(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_identity(item) for key, item in value.items() if key not in IDENTITY_KEYS}
    if isinstance(value, list):
        return [_strip_identity(item) for item in value]
    return value


def blind_records(records: list[dict[str, Any]], mapping: dict[str, str], *, seed: int) -> list[dict[str, Any]]:
    public, _ = blind_review_records(records, mapping, seed=seed)
    return public


def blind_review_records(
    records: list[dict[str, Any]],
    mapping: dict[str, str],
    *,
    seed: int,
    forbidden_terms: list[str] | None = None,
    include_system_alias: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordering = sorted(
        range(len(records)),
        key=lambda index: (
            str(records[index].get("system_id", "")),
            str(records[index].get("case_id", "")),
            int(records[index].get("run_number", 0)),
            str(records[index].get("finding_id", "")),
            index,
        ),
    )
    item_ids = [f"Item-{index:06d}" for index in range(1, len(records) + 1)]
    random.Random(seed).shuffle(item_ids)
    item_id_by_index = dict(zip(ordering, item_ids, strict=True))
    blinded: list[dict[str, Any]] = []
    private: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        system_id = record.get("system_id")
        if system_id not in mapping:
            raise ValueError(f"missing blind mapping for system: {system_id}")
        item = _strip_identity(copy.deepcopy(record))
        if include_system_alias:
            item["system_alias"] = mapping[system_id]
        item["review_item_id"] = item_id_by_index[index]
        blinded.append(item)
        private.append(
            {
                "review_item_id": item_id_by_index[index],
                "system_id": system_id,
                "case_id": record.get("case_id"),
                "run_number": record.get("run_number"),
                "finding_id": record.get("finding_id"),
            }
        )
    random.Random(seed + 1).shuffle(blinded)
    private.sort(key=lambda item: item["review_item_id"])
    derived_forbidden = list(mapping)
    derived_forbidden.extend(
        str(record[key])
        for record in records
        for key in ("system_name", "model_name", "adapter")
        if isinstance(record.get(key), str) and record[key]
    )
    derived_forbidden.extend(forbidden_terms or [])
    assert_no_identity_leak(blinded, sorted(set(derived_forbidden), key=str.casefold))
    return blinded, private


def assert_no_identity_leak(value: Any, forbidden_terms: list[str]) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).casefold()
    for term in forbidden_terms:
        if isinstance(term, str) and term and term.casefold() in serialized:
            raise IdentityLeakError(f"blinded packet contains forbidden identity term: {term}")
