"""Freeze a private real-human roster against one canonical Stage 1 panel report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from wqeval.roster_anchor import (
    build_human_roster_anchor,
    encode_human_roster_anchor,
    panel_report_sha256,
)
from wqeval.storage import RawStore, _lexical_absolute
from wqeval.strict_json import loads


def _read_json_under_root(path: str | Path, *, authorized_root: str | Path) -> Any:
    root = _lexical_absolute(authorized_root)
    target = _lexical_absolute(path)
    try:
        relative = target.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("input must be inside authorized_root") from error
    store = RawStore(root, authorized_root=root)
    _, safe_target = store._target(relative)
    return loads(store._read_regular_file(safe_target, maximum_bytes=5_000_000))


def freeze_human_roster_anchor_file(
    *,
    roster_path: str | Path,
    source_panel_report_path: str | Path,
    run_id: str,
    destination_path: str | Path,
    authorized_root: str | Path,
) -> dict[str, Any]:
    """Create one write-once anchor; roster truth remains externally attested."""

    root = _lexical_absolute(authorized_root)
    roster = _read_json_under_root(roster_path, authorized_root=root)
    report = _read_json_under_root(source_panel_report_path, authorized_root=root)
    if not isinstance(roster, dict):
        raise ValueError("roster must be a JSON object")
    if not isinstance(report, dict):
        raise ValueError("source panel report must be a JSON object")
    anchor = build_human_roster_anchor(
        human_roster=roster,
        run_id=run_id,
        source_panel_report_sha256=panel_report_sha256(report),
    )
    destination = _lexical_absolute(destination_path)
    try:
        relative = destination.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("destination_path must be inside authorized_root") from error
    receipt = RawStore(root, authorized_root=root).write_once(
        relative,
        encode_human_roster_anchor(anchor),
    )
    return {
        "schema_version": "1.0",
        "status": "FROZEN_PRE_REVIEW",
        "run_id": anchor["run_id"],
        "source_panel_report_sha256": anchor["source_panel_report_sha256"],
        "human_roster_anchor_sha256": receipt.sha256,
        "path": receipt.relative_path,
        "bytes": receipt.byte_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--source-panel-report", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--authorized-root", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        receipt = freeze_human_roster_anchor_file(
            roster_path=arguments.roster,
            source_panel_report_path=arguments.source_panel_report,
            run_id=arguments.run_id,
            destination_path=arguments.destination,
            authorized_root=arguments.authorized_root,
        )
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
