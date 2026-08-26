from __future__ import annotations

import tempfile
import unittest
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from wqeval.storage import ImmutableWriteError, PathSafetyError, RawStore, TamperError, _identity


class RawStoreTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows file identity behavior")
    def test_windows_identity_matches_the_32_bit_handle_volume_serial(self) -> None:
        metadata = type(
            "Metadata",
            (),
            {"st_dev": (0x91ABCDEF << 32) | 0x12345678, "st_ino": 0x1020304050607080},
        )()
        self.assertEqual(_identity(metadata), (0x12345678, 0x1020304050607080))

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_publication_blocks_a_root_or_parent_swap_to_a_real_junction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            original_rename = os.rename
            for swap_level in ("root", "parent"):
                with self.subTest(swap_level=swap_level):
                    run_root = base / f"run-{swap_level}"
                    run_root.mkdir()
                    store = RawStore(run_root / "raw", authorized_root=run_root)
                    relative = "nested/current.jsonl"
                    target_parent = store.root / "nested"
                    target_parent.mkdir()
                    swap_target = store.root if swap_level == "root" else target_parent
                    moved = base / f"moved-{swap_level}"

                    def swap_to_junction(source: str | Path, destination: str | Path) -> None:
                        original_rename(swap_target, moved)
                        created = subprocess.run(
                            ["cmd.exe", "/d", "/c", "mklink", "/j", str(swap_target), str(moved)],
                            check=False,
                            capture_output=True,
                            text=True,
                        )
                        if created.returncode != 0:
                            raise RuntimeError(f"junction creation unavailable: {created.stderr.strip()}")
                        original_rename(source, destination)

                    try:
                        with patch("wqeval.storage.os.rename", side_effect=swap_to_junction):
                            with self.assertRaises((OSError, PathSafetyError)):
                                store.write_once(relative, b"must stay inside\n")
                        self.assertFalse((moved / "nested" / "current.jsonl").exists())
                        self.assertFalse((moved / "current.jsonl").exists())
                    finally:
                        if swap_target.is_dir() and swap_target.is_symlink():
                            os.rmdir(swap_target)
                        elif os.path.lexists(swap_target) and getattr(swap_target.lstat(), "st_file_attributes", 0) & 0x400:
                            os.rmdir(swap_target)
                        if moved.exists() and not swap_target.exists():
                            original_rename(moved, swap_target)

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_rejects_junctions_for_every_stage1_store_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for relative_store in (Path("raw"), Path("normalized"), Path("manifests") / "receipts"):
                with self.subTest(store=relative_store.as_posix()):
                    run_root = base / ("run-" + "-".join(relative_store.parts))
                    run_root.mkdir()
                    outside = base / ("outside-" + "-".join(relative_store.parts))
                    outside.mkdir()
                    store_path = run_root / relative_store
                    store_path.parent.mkdir(parents=True, exist_ok=True)
                    created = subprocess.run(
                        ["cmd.exe", "/d", "/c", "mklink", "/j", str(store_path), str(outside)],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if created.returncode != 0:
                        self.skipTest(f"junction creation unavailable: {created.stderr.strip()}")
                    try:
                        with self.assertRaisesRegex(PathSafetyError, "junction|reparse"):
                            store = RawStore(store_path, authorized_root=run_root)
                            store.write_once("escaped.jsonl", b"must stay inside\n")
                        self.assertFalse((outside / "escaped.jsonl").exists())
                    finally:
                        os.rmdir(store_path)

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_rejects_a_junction_in_the_receipt_store_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run_root = base / "run"
            run_root.mkdir()
            outside = base / "outside-manifests"
            (outside / "receipts").mkdir(parents=True)
            manifests = run_root / "manifests"
            created = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/j", str(manifests), str(outside)],
                check=False,
                capture_output=True,
                text=True,
            )
            if created.returncode != 0:
                self.skipTest(f"junction creation unavailable: {created.stderr.strip()}")
            try:
                with self.assertRaisesRegex(PathSafetyError, "junction|reparse"):
                    RawStore(run_root / "manifests" / "receipts", authorized_root=run_root)
                self.assertFalse((outside / "receipts" / "escaped.json").exists())
            finally:
                os.rmdir(manifests)

    def test_write_once_creates_verifiable_receipt_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RawStore(Path(directory) / "raw", authorized_root=directory)
            receipt = store.write_once("stage1/run-01/current.jsonl", b'{"case_id":"C001"}\n')

            self.assertEqual(receipt.relative_path, "stage1/run-01/current.jsonl")
            self.assertEqual(len(receipt.sha256), 64)
            self.assertEqual(receipt.byte_count, 19)
            self.assertTrue(store.verify(receipt))

            with self.assertRaises(ImmutableWriteError):
                store.write_once("stage1/run-01/current.jsonl", b'{"case_id":"C001"}\n')
            self.assertTrue(store.verify(receipt))

    def test_bounded_regular_file_read_rejects_oversize_and_invalid_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RawStore(Path(directory) / "raw", authorized_root=directory)
            store.write_once("current.jsonl", b"12345")
            _normalized, target = store._target("current.jsonl")

            self.assertEqual(store._read_regular_file(target, maximum_bytes=5), b"12345")
            with self.assertRaisesRegex(TamperError, "exceeds 4 bytes"):
                store._read_regular_file(target, maximum_bytes=4)
            for invalid in (True, 0, -1, 1.5):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    store._read_regular_file(target, maximum_bytes=invalid)  # type: ignore[arg-type]

    @unittest.skipUnless(os.name == "nt", "Windows directory-handle behavior")
    def test_public_hold_directory_chain_blocks_ancestor_rename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run_root = base / "run"
            run_root.mkdir()
            store = RawStore(run_root / "raw", authorized_root=run_root)
            (store.root / "nested").mkdir()
            moved = base / "moved"

            with store.hold_directory_chain("nested"):
                with self.assertRaises(OSError):
                    os.rename(run_root, moved)
                # The containment handle does not lock the child set.
                (store.root / "nested" / "allowed-child.txt").write_text("allowed", encoding="utf-8")

            os.rename(run_root, moved)
            self.assertTrue((moved / "raw" / "nested" / "allowed-child.txt").exists())

    def test_recovery_accepts_only_identical_existing_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RawStore(Path(directory) / "raw", authorized_root=directory)
            first = store.publish_or_verify("current.jsonl", b"original\n")
            recovered = store.publish_or_verify("current.jsonl", b"original\n")

            self.assertEqual(recovered, first)
            with self.assertRaisesRegex(ImmutableWriteError, "different bytes"):
                store.publish_or_verify("current.jsonl", b"changed\n")
            self.assertTrue(store.verify(first))

    @unittest.skipUnless(os.name == "nt", "Windows atomic rename behavior")
    def test_recovery_handles_an_exception_after_atomic_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RawStore(Path(directory) / "raw", authorized_root=directory)
            original_rename = os.rename

            def publish_then_interrupt(source: str | Path, destination: str | Path) -> None:
                original_rename(source, destination)
                raise RuntimeError("injected post-publication interruption")

            with patch("wqeval.storage.os.rename", side_effect=publish_then_interrupt):
                with self.assertRaisesRegex(RuntimeError, "post-publication"):
                    store.write_once("current.jsonl", b"original\n")

            receipt = store.publish_or_verify("current.jsonl", b"original\n")
            self.assertTrue(store.verify(receipt))

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_rejects_a_junction_inserted_below_an_initialized_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run_root = base / "run"
            run_root.mkdir()
            store = RawStore(run_root / "raw", authorized_root=run_root)
            outside = base / "outside-nested"
            outside.mkdir()
            nested = run_root / "raw" / "nested"
            created = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/j", str(nested), str(outside)],
                check=False,
                capture_output=True,
                text=True,
            )
            if created.returncode != 0:
                self.skipTest(f"junction creation unavailable: {created.stderr.strip()}")
            try:
                with self.assertRaisesRegex(PathSafetyError, "junction|reparse"):
                    store.write_once("nested/escaped.jsonl", b"must stay inside\n")
                self.assertFalse((outside / "escaped.jsonl").exists())
            finally:
                os.rmdir(nested)

    def test_concurrent_writes_have_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RawStore(Path(directory) / "raw", authorized_root=directory)

            def attempt(payload: bytes) -> str:
                try:
                    store.write_once("stage1/run-01/union.jsonl", payload)
                    return "written"
                except ImmutableWriteError:
                    return "rejected"

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(attempt, (b"first", b"second")))
            self.assertCountEqual(outcomes, ["written", "rejected"])

    def test_manual_mutation_and_truncation_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "raw"
            store = RawStore(root, authorized_root=directory)
            receipt = store.write_once("stage1/run-01/current.jsonl", b"original\n")
            (root / receipt.relative_path).write_bytes(b"changed\n")
            with self.assertRaises(TamperError):
                store.verify(receipt)

            missing_receipt = store.write_once("stage1/run-01/other.jsonl", b"other\n")
            (root / missing_receipt.relative_path).unlink()
            with self.assertRaises(TamperError):
                store.verify(missing_receipt)

    def test_absolute_traversal_and_sibling_prefix_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "raw"
            store = RawStore(root, authorized_root=directory)
            invalid = (
                "../escape.jsonl",
                "..\\escape.jsonl",
                "stage1/../../escape.jsonl",
                str((Path(directory) / "absolute.jsonl").resolve()),
                "C:\\Windows\\Temp\\escape.jsonl",
                "//server/share/escape.jsonl",
                "stage1/result.jsonl:secret",
                "stage1/CON.jsonl",
                "stage1/trailing. ",
            )
            for path in invalid:
                with self.subTest(path=path), self.assertRaises(PathSafetyError):
                    store.write_once(path, b"no")

            self.assertFalse((Path(directory) / "escape.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
