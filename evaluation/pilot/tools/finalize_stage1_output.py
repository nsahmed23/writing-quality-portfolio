"""Finalize a complete Stage 1 run directory into one detached-hash anchor."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from wqeval.output_evidence import finalize_stage1_output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finalize_stage1_output.py")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--expected-jobs-manifest-sha256", required=True)
    parser.add_argument("--maximum-artifact-bytes", type=int, default=50_000_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        receipt = finalize_stage1_output(
            arguments.run_root,
            expected_jobs_manifest_sha256=arguments.expected_jobs_manifest_sha256,
            maximum_artifact_bytes=arguments.maximum_artifact_bytes,
        )
        print(json.dumps(asdict(receipt), ensure_ascii=False, sort_keys=True))
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
