from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wqeval.ingest import UnsafeInputPathError, read_registered_inbox_artifact


class RegisteredInboxArtifactTests(unittest.TestCase):
    def _paths(self, directory: str) -> tuple[Path, Path, str]:
        run_root = Path(directory) / "run"
        inbox = run_root / "inbox"
        inbox.mkdir(parents=True)
        artifact_name = "stage1-union-run-01.jsonl"
        return run_root, inbox / artifact_name, artifact_name

    def _read(self, supplied: Path, run_root: Path, artifact_name: str) -> bytes:
        return read_registered_inbox_artifact(
            supplied,
            run_root=run_root,
            artifact_name=artifact_name,
            registered_output_path=run_root / "inbox" / artifact_name,
        )

    def test_reads_only_the_direct_registered_inbox_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root, artifact, artifact_name = self._paths(directory)
            artifact.write_bytes(b'{"case_id":"C001"}\n')

            self.assertEqual(self._read(artifact, run_root, artifact_name), b'{"case_id":"C001"}\n')

    def test_rejects_lexical_parent_traversal_even_when_it_normalizes_to_registered_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root, artifact, artifact_name = self._paths(directory)
            artifact.write_bytes(b"registered\n")
            alias = run_root / "inbox" / ".." / "inbox" / artifact_name

            with self.assertRaisesRegex(UnsafeInputPathError, "traversal"):
                self._read(alias, run_root, artifact_name)

    def test_rejects_file_symlink_to_an_outside_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root, artifact, artifact_name = self._paths(directory)
            outside = Path(directory) / "outside.jsonl"
            outside.write_bytes(b"outside\n")
            try:
                artifact.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"file symlinks unavailable: {exc}")

            with self.assertRaisesRegex(UnsafeInputPathError, "reparse|symlink"):
                self._read(artifact, run_root, artifact_name)

    def test_rejects_inbox_directory_symlink_to_an_outside_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory) / "run"
            run_root.mkdir()
            outside = Path(directory) / "outside"
            outside.mkdir()
            artifact_name = "stage1-union-run-01.jsonl"
            (outside / artifact_name).write_bytes(b"outside\n")
            inbox = run_root / "inbox"
            try:
                inbox.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")

            with self.assertRaisesRegex(UnsafeInputPathError, "reparse|symlink"):
                self._read(inbox / artifact_name, run_root, artifact_name)

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_rejects_a_real_junction_at_a_lexical_ancestor_above_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            physical = base / "physical"
            run_root = physical / "run"
            inbox = run_root / "inbox"
            inbox.mkdir(parents=True)
            artifact_name = "stage1-union-run-01.jsonl"
            (inbox / artifact_name).write_bytes(b"outside alias\n")
            alias = base / "aliased-parent"
            created = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/j", str(alias), str(physical)],
                check=False,
                capture_output=True,
                text=True,
            )
            if created.returncode != 0:
                self.skipTest(f"junction creation unavailable: {created.stderr.strip()}")
            aliased_run_root = alias / "run"
            try:
                with self.assertRaisesRegex(UnsafeInputPathError, "reparse|junction|symlink"):
                    self._read(
                        aliased_run_root / "inbox" / artifact_name,
                        aliased_run_root,
                        artifact_name,
                    )
            finally:
                os.rmdir(alias)

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_rejects_inbox_junction_to_an_outside_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory) / "run"
            run_root.mkdir()
            outside = Path(directory) / "outside"
            outside.mkdir()
            artifact_name = "stage1-union-run-01.jsonl"
            (outside / artifact_name).write_bytes(b"outside\n")
            inbox = run_root / "inbox"
            created = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/j", str(inbox), str(outside)],
                check=False,
                capture_output=True,
                text=True,
            )
            if created.returncode != 0:
                self.skipTest(f"junction creation unavailable: {created.stderr.strip()}")
            try:
                with self.assertRaisesRegex(UnsafeInputPathError, "reparse|junction"):
                    self._read(inbox / artifact_name, run_root, artifact_name)
            finally:
                os.rmdir(inbox)

    def test_rejects_hardlink_to_an_outside_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root, artifact, artifact_name = self._paths(directory)
            outside = Path(directory) / "outside.jsonl"
            outside.write_bytes(b"outside\n")
            os.link(outside, artifact)

            with self.assertRaisesRegex(UnsafeInputPathError, "hardlink"):
                self._read(artifact, run_root, artifact_name)

    def test_rejects_an_unregistered_lookalike_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root, artifact, artifact_name = self._paths(directory)
            artifact.write_bytes(b"registered\n")
            lookalike_parent = run_root / "alternate-inbox"
            lookalike_parent.mkdir()
            lookalike = lookalike_parent / artifact_name
            lookalike.write_bytes(b"registered\n")

            with self.assertRaisesRegex(UnsafeInputPathError, "alias"):
                self._read(lookalike, run_root, artifact_name)

    def test_rejects_a_generic_windows_reparse_point_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root, artifact, artifact_name = self._paths(directory)
            artifact.write_bytes(b"registered\n")
            original_lstat = Path.lstat

            def flagged_lstat(path: Path):
                metadata = original_lstat(path)
                if path == artifact:
                    return SimpleNamespace(
                        st_mode=metadata.st_mode,
                        st_file_attributes=0x400,
                    )
                return metadata

            with patch.object(Path, "lstat", new=flagged_lstat):
                with self.assertRaisesRegex(UnsafeInputPathError, "reparse"):
                    self._read(artifact, run_root, artifact_name)

    def test_rejects_a_symlink_mode_even_when_live_symlink_creation_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root, artifact, artifact_name = self._paths(directory)
            artifact.write_bytes(b"registered\n")
            original_lstat = Path.lstat

            def symlink_lstat(path: Path):
                metadata = original_lstat(path)
                if path == artifact:
                    return SimpleNamespace(
                        st_mode=stat.S_IFLNK,
                        st_file_attributes=0,
                    )
                return metadata

            with patch.object(Path, "lstat", new=symlink_lstat):
                with self.assertRaisesRegex(UnsafeInputPathError, "symlink"):
                    self._read(artifact, run_root, artifact_name)

    def test_rejects_in_place_mutation_during_read_even_when_inode_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root, artifact, artifact_name = self._paths(directory)
            artifact.write_bytes(b"registered\n")

            class MutatingHandle:
                def __init__(self, descriptor: int) -> None:
                    self.descriptor = descriptor

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback) -> bool:
                    return False

                def read(self, limit: int) -> bytes:
                    payload = os.read(self.descriptor, limit)
                    with artifact.open("ab") as writer:
                        writer.write(b"changed\n")
                    return payload

            with patch("wqeval.ingest.os.fdopen", side_effect=lambda descriptor, *_args, **_kwargs: MutatingHandle(descriptor)):
                with self.assertRaisesRegex(UnsafeInputPathError, "changed"):
                    self._read(artifact, run_root, artifact_name)


if __name__ == "__main__":
    unittest.main()
