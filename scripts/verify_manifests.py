#!/usr/bin/env python3
"""Verify byte-exact GNU SHA-256 manifests against Git's tracked file set.

The evaluation manifest is historical: it excludes itself and ONLY the new
evaluation/benchmark_v2/ and evaluation/status/ development subtrees. The
root manifest covers those subtrees and every other tracked file except itself.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import stat
import subprocess
import sys


ROOT_MANIFEST = "MANIFEST.sha256"
EVALUATION_MANIFEST = "evaluation/MANIFEST.sha256"
NEW_EVALUATION_SUBTREES = ("evaluation/benchmark_v2/", "evaluation/status/")
ROW = re.compile(rb"([0-9a-fA-F]{64}) ([ *])(.+)")


class IntegrityError(Exception):
    """A manifest, checkout, or tracked-file mismatch."""


def safe_relative(raw: str) -> str:
    """Accept a single optional GNU ./ prefix and reject ambiguous paths."""
    if raw.startswith("./"):
        raw = raw[2:]
    if (not raw or raw.startswith("/") or "\\" in raw or ":" in raw
            or any(part in ("", ".", "..") for part in raw.split("/"))
            or any(ord(c) < 32 or ord(c) == 127 for c in raw)):
        raise IntegrityError(f"unsafe path: {raw!r}")
    return raw


def file_bytes(root: Path, relative: str) -> bytes:
    """Reject symlinks at every path component before opening a regular file."""
    path = root
    for component in relative.split("/"):
        path = path / component
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError as exc:
            raise IntegrityError(f"missing file: {relative}") from exc
        if stat.S_ISLNK(mode):
            raise IntegrityError(f"symlink traversal: {relative}")
    if not stat.S_ISREG(mode):
        raise IntegrityError(f"not a regular file: {relative}")
    return path.read_bytes()


def tracked_files(root: Path) -> set[str]:
    result = subprocess.run(["git", "ls-files", "--cached", "-z"], cwd=root,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise IntegrityError(f"cannot list Git-tracked files: {result.stderr.decode(errors='replace').strip()}")
    try:
        paths = [safe_relative(p.decode("utf-8")) for p in result.stdout.split(b"\0") if p]
    except UnicodeDecodeError as exc:
        raise IntegrityError("unsafe Git path: invalid UTF-8") from exc
    if len(paths) != len(set(paths)):
        raise IntegrityError("duplicate Git-tracked path")
    return set(paths)


def read_manifest(root: Path, name: str, prefix: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for number, line in enumerate(file_bytes(root, name).splitlines(), 1):
        match = ROW.fullmatch(line)
        if match is None:
            raise IntegrityError(f"malformed row: {name}:{number}")
        try:
            relative = safe_relative(match.group(3).decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise IntegrityError(f"malformed UTF-8 path: {name}:{number}") from exc
        path = prefix + relative
        if path in entries:
            raise IntegrityError(f"duplicate path: {name}:{number}: {path}")
        entries[path] = match.group(1).decode("ascii").lower()
    return entries


def verify(root: Path, manifest: str, expected: set[str], prefix: str = "") -> None:
    entries = read_manifest(root, manifest, prefix)
    extra = sorted(entries.keys() - expected)
    if extra:
        raise IntegrityError(f"unexpected manifest path in {manifest}: {extra[0]}")
    absent = sorted(expected - entries.keys())
    if absent:
        raise IntegrityError(f"unlisted tracked path in {manifest}: {absent[0]}")
    for name, digest in entries.items():
        if hashlib.sha256(file_bytes(root, name)).hexdigest() != digest:
            raise IntegrityError(f"hash mismatch: {name}")


def evaluation_set(tracked: set[str]) -> set[str]:
    return {name for name in tracked
            if name.startswith("evaluation/") and name != EVALUATION_MANIFEST
            and not any(name.startswith(prefix) for prefix in NEW_EVALUATION_SUBTREES)}


def write_root(root: Path, tracked: set[str]) -> None:
    if ROOT_MANIFEST not in tracked:
        raise IntegrityError("root manifest must be Git-tracked")
    rows = []
    for name in sorted(tracked - {ROOT_MANIFEST}):
        safe_relative(name)
        if "\n" in name or "\r" in name:
            raise IntegrityError(f"unsafe filename for GNU manifest: {name!r}")
        digest = hashlib.sha256(file_bytes(root, name)).hexdigest()
        rows.append(f"{digest}  ./{name}\n")
    target = root / ROOT_MANIFEST
    file_bytes(root, ROOT_MANIFEST)  # Reject a symlink at the write target.
    target.write_bytes("".join(rows).encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1],
                        help="repository checkout (default: script parent)")
    parser.add_argument("--write-root", action="store_true",
                        help="regenerate ONLY root MANIFEST.sha256; verify historical evaluation first")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        tracked = tracked_files(root)
        if ROOT_MANIFEST not in tracked or EVALUATION_MANIFEST not in tracked:
            raise IntegrityError("both manifests must be Git-tracked")
        verify(root, EVALUATION_MANIFEST, evaluation_set(tracked), "evaluation/")
        if args.write_root:
            write_root(root, tracked)
            print(f"wrote {ROOT_MANIFEST}; historical evaluation manifest unchanged")
        else:
            verify(root, ROOT_MANIFEST, tracked - {ROOT_MANIFEST})
            print("both manifests verify against exact Git-tracked coverage")
        return 0
    except (IntegrityError, OSError) as exc:
        print(f"integrity error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
