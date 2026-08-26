from __future__ import annotations

import hashlib
import math
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.prepare_stage1_jobs import (
    _write_new_bytes,
    encode_json,
    manifest_job_entries,
    publish_new_tree,
)


class JobPublicationTests(unittest.TestCase):
    def test_publication_requires_and_enforces_an_explicit_authorized_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorized = Path(directory) / "authorized"
            authorized.mkdir()
            outside = Path(directory) / "outside" / "stage1-sealed-v1"

            with self.assertRaises(TypeError):
                publish_new_tree(  # type: ignore[call-arg]
                    authorized / "stage1-sealed-v1",
                    {"jobs/first.json": {"job_id": "first"}},
                )
            with self.assertRaisesRegex(ValueError, "escapes"):
                publish_new_tree(
                    outside,
                    {"jobs/first.json": {"job_id": "first"}},
                    authorized_root=authorized,
                )

            self.assertFalse(outside.exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_rejects_a_preexisting_junction_at_the_run_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            outside = base / "outside"
            outside.mkdir()
            aliased_parent = base / "runs"
            created = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/j", str(aliased_parent), str(outside)],
                check=False,
                capture_output=True,
                text=True,
            )
            if created.returncode != 0:
                self.skipTest(f"junction creation unavailable: {created.stderr.strip()}")
            try:
                with self.assertRaises((ValueError, OSError)):
                    publish_new_tree(
                        aliased_parent / "stage1-sealed-v1",
                        {"jobs/first.json": {"job_id": "first"}},
                        authorized_root=base,
                    )
                self.assertFalse((outside / "stage1-sealed-v1").exists())
            finally:
                os.rmdir(aliased_parent)

    @unittest.skipUnless(os.name == "nt", "Windows rename boundary")
    def test_rename_boundary_swap_cannot_publish_outside(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            run_root = parent / "stage1-sealed-v1"
            moved = parent / "attacker-controlled"
            original_rename = os.rename

            def swap_source(_boundary: object, source: Path, destination: Path) -> None:
                original_rename(source, moved)
                created = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/j", str(source), str(moved)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if created.returncode != 0:
                    raise RuntimeError(f"junction creation unavailable: {created.stderr.strip()}")
                original_rename(source, destination)

            with patch("tools.prepare_stage1_jobs._publish_held_tree", side_effect=swap_source):
                with self.assertRaises((OSError, ValueError)):
                    publish_new_tree(
                        run_root,
                        {"jobs/first.json": {"job_id": "first"}},
                        authorized_root=parent,
                    )

            self.assertFalse((moved / "jobs" / "first.json").exists())
            self.assertFalse(run_root.exists())

    def test_existing_run_root_is_rejected_before_any_artifact_is_published(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            run_root = parent / "stage1-sealed-v1"
            run_root.mkdir()
            late_target = run_root / "manifests" / "jobs.json"
            late_target.parent.mkdir()
            late_target.write_text("existing", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                publish_new_tree(
                    run_root,
                    {
                        "jobs/first.json": {"job_id": "first"},
                        "manifests/jobs.json": {"jobs": []},
                    },
                    authorized_root=parent,
                )

            self.assertFalse((run_root / "jobs" / "first.json").exists())
            self.assertEqual(late_target.read_text(encoding="utf-8"), "existing")

    def test_all_payloads_are_encoded_before_the_official_tree_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory) / "stage1-sealed-v1"

            with self.assertRaises(ValueError):
                publish_new_tree(
                    run_root,
                    {
                        "jobs/first.json": {"job_id": "first"},
                        "manifests/jobs.json": {"bad": math.nan},
                    },
                    authorized_root=Path(directory),
                )

            self.assertFalse(run_root.exists())

    def test_complete_tree_is_published_with_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory) / "stage1-sealed-v1"
            artifacts = {
                "jobs/first.json": {"job_id": "first"},
                "manifests/jobs.json": {"jobs": [{"path": "jobs/first.json"}]},
            }

            publish_new_tree(run_root, artifacts, authorized_root=Path(directory))

            self.assertEqual((run_root / "jobs" / "first.json").read_bytes(), encode_json(artifacts["jobs/first.json"]))
            self.assertEqual(
                (run_root / "manifests" / "jobs.json").read_bytes(),
                encode_json(artifacts["manifests/jobs.json"]),
            )
            with self.assertRaises(FileExistsError):
                publish_new_tree(run_root, artifacts, authorized_root=Path(directory))

    def test_production_manifest_entries_bind_each_job_byte_for_byte(self) -> None:
        jobs = {
            "jobs/stage1-a-run-01.json": {"job_id": "stage1-a-run-01", "cases": ["é"]},
            "jobs/stage1-b-run-01.json": {"job_id": "stage1-b-run-01", "cases": []},
        }

        entries = manifest_job_entries(jobs)

        self.assertEqual([entry["path"] for entry in entries], sorted(jobs))
        for entry in entries:
            payload = encode_json(jobs[entry["path"]])
            self.assertEqual(entry["bytes"], len(payload))
            self.assertEqual(len(entry["sha256"]), 64)
            self.assertEqual(entry["sha256"], hashlib.sha256(payload).hexdigest())

    def test_mid_staging_failure_leaves_no_official_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory) / "stage1-sealed-v1"
            calls = 0

            def fail_second(path: Path, payload: bytes) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected write failure")
                _write_new_bytes(path, payload)

            with patch("tools.prepare_stage1_jobs._write_new_bytes", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "injected"):
                    publish_new_tree(
                        run_root,
                        {
                            "jobs/first.json": {"job_id": "first"},
                            "manifests/jobs.json": {"jobs": []},
                        },
                        authorized_root=Path(directory),
                    )

            self.assertFalse(run_root.exists())

    def test_destination_created_before_rename_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory) / "stage1-sealed-v1"

            def collide(_boundary: object, source: Path, destination: Path) -> None:
                destination.mkdir()
                (destination / "sentinel.txt").write_text("preserve", encoding="utf-8")
                raise FileExistsError("injected destination race")

            with patch("tools.prepare_stage1_jobs._publish_held_tree", side_effect=collide):
                with self.assertRaisesRegex(FileExistsError, "destination race"):
                    publish_new_tree(
                        run_root,
                        {"jobs/first.json": {"job_id": "first"}},
                        authorized_root=Path(directory),
                    )

            self.assertEqual((run_root / "sentinel.txt").read_text(encoding="utf-8"), "preserve")

    def test_relative_paths_cannot_escape_the_new_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            unsafe = (
                "../outside.json",
                "C:outside.json",
                "D:outside.json",
                "jobs/result.json:stream",
                "jobs/CON.json",
                "jobs/name. ",
                "jobs/bad\x01name.json",
            )

            for index, relative in enumerate(unsafe):
                run_root = parent / f"stage1-sealed-v1-{index}"
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    publish_new_tree(
                        run_root,
                        {relative: {"bad": True}},
                        authorized_root=parent,
                    )
                self.assertFalse(run_root.exists())

            self.assertFalse((parent / "outside.json").exists())


if __name__ == "__main__":
    unittest.main()
