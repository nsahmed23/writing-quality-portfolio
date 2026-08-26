"""Command-line interface for deterministic offline validation and scoring."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .corpus_evidence import verify_frozen_scoring_corpus
from .evaluation import build_verified_stage1_evaluation
from .storage import RawStore
from .strict_json import load_jsonl
from .validation import validate_case


def _write_json_once(path: Path, value: Any) -> None:
    path = Path(os.path.abspath(os.fspath(path)))
    if not path.parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    RawStore(path.parent, authorized_root=path.parent).write_once(path.name, payload)


def _require_output_outside_run_tree(output: Path, run_root: Path) -> Path:
    output = Path(os.path.abspath(os.fspath(output)))
    root = Path(os.path.abspath(os.fspath(run_root)))
    try:
        output.relative_to(root)
    except ValueError:
        return output
    raise ValueError("output must be outside the immutable Stage 1 run tree")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wqeval")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--kind", choices=("cases",), required=True)
    validate.add_argument("--input", type=Path, required=True)
    score = commands.add_parser("score-stage1")
    score.add_argument("--project-root", type=Path, required=True)
    score.add_argument("--corpus-freeze-sha256", required=True)
    score.add_argument("--split", choices=("dev", "test"), required=True)
    score.add_argument("--run-root", type=Path, required=True)
    score.add_argument("--output-evidence-sha256", required=True)
    score.add_argument("--system-id", required=True)
    score.add_argument("--expected-runs", type=int, required=True)
    score.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        arguments = parser.parse_args(argv)
        if arguments.command == "validate":
            records = load_jsonl(arguments.input)
            for record in records:
                validate_case(record)
            print(json.dumps({"kind": arguments.kind, "valid_records": len(records)}, sort_keys=True))
            return 0
        if arguments.command == "score-stage1":
            output_path = _require_output_outside_run_tree(arguments.output, arguments.run_root)
            corpus = verify_frozen_scoring_corpus(
                arguments.project_root,
                expected_freeze_manifest_sha256=arguments.corpus_freeze_sha256,
                split=arguments.split,
            )
            evaluation = build_verified_stage1_evaluation(
                corpus,
                run_root=arguments.run_root,
                expected_output_evidence_sha256=arguments.output_evidence_sha256,
                system_id=arguments.system_id,
                expected_runs=arguments.expected_runs,
            )
            _write_json_once(output_path, evaluation.report_metrics)
            return 0
        raise ValueError("unsupported command")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
