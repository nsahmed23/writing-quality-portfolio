"""Behavior tests for exact, byte-level tracked-file manifest verification."""

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_manifests.py"


class ManifestCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.put("README.md", b"hello\n")
        self.put("evaluation/original.txt", b"historical\r\n")
        self.put("evaluation/MANIFEST.sha256", self.row("evaluation/original.txt", marker="*").encode())
        self.put("MANIFEST.sha256", self.root_rows().encode())
        self.track()

    def put(self, name, data):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def row(self, name, marker=" "):
        path = self.root / name
        relative = name.removeprefix("evaluation/")
        return f"{hashlib.sha256(path.read_bytes()).hexdigest()} {marker}./{relative}\n"

    def root_rows(self):
        names = ["README.md", "evaluation/MANIFEST.sha256", "evaluation/original.txt"]
        return "".join(self.row(name) if not name.startswith("evaluation/") else
                       f"{hashlib.sha256((self.root / name).read_bytes()).hexdigest()}  ./{name}\n"
                       for name in names)

    def track(self):
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.root), *args],
                              capture_output=True, text=True)

    def assert_rejects(self, expected):
        outcome = self.run_cli()
        self.assertNotEqual(outcome.returncode, 0, outcome.stdout)
        self.assertIn(expected.lower(), (outcome.stdout + outcome.stderr).lower())

    def test_valid_gnu_text_and_binary_rows_hash_crlf_bytes(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.put("evaluation/original.txt", b"historical\n")
        self.assert_rejects("hash mismatch")

    def test_root_exact_coverage_reports_missing_entry(self):
        self.put("extra.md", b"new")
        self.track()
        self.assert_rejects("unlisted tracked")

    def test_root_manifest_must_not_list_itself(self):
        with (self.root / "MANIFEST.sha256").open("ab") as file:
            file.write(b"0" * 64 + b"  ./MANIFEST.sha256\n")
        self.assert_rejects("unexpected")

    def test_nested_manifest_does_not_cover_only_two_new_subtrees(self):
        self.put("evaluation/benchmark_v2/new.py", b"new")
        self.put("evaluation/status/readme.md", b"new")
        self.track()
        # Regeneration is explicit, covers both excluded historical subtrees,
        # and never changes the original nested manifest.
        nested_before = (self.root / "evaluation/MANIFEST.sha256").read_bytes()
        result = self.run_cli("--write-root")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((self.root / "evaluation/MANIFEST.sha256").read_bytes(), nested_before)
        self.assertEqual(self.run_cli().returncode, 0)
        self.put("evaluation/other.md", b"unexpected historical addition")
        self.track()
        self.assert_rejects("unlisted tracked")

    def test_nested_manifest_must_not_list_excluded_subtree(self):
        self.put("evaluation/status/new.md", b"new")
        self.track()
        with (self.root / "evaluation/MANIFEST.sha256").open("ab") as file:
            file.write(self.row("evaluation/status/new.md").encode())
        self.assert_rejects("unexpected")

    def test_duplicate_even_with_different_dot_prefix(self):
        with (self.root / "MANIFEST.sha256").open("ab") as file:
            file.write(self.row("README.md").replace("./README.md", "README.md").encode())
        self.assert_rejects("duplicate")

    def test_malformed_row_rejected(self):
        with (self.root / "MANIFEST.sha256").open("ab") as file:
            file.write(b"invalid  ./README.md\n")
        self.assert_rejects("malformed")

    def test_unsafe_parent_absolute_and_backslash_paths_rejected(self):
        for unsafe in ("../escape", "/tmp/escape", "sub\\file"):
            with self.subTest(unsafe=unsafe):
                original = (self.root / "MANIFEST.sha256").read_bytes()
                self.put("MANIFEST.sha256", original + ("0" * 64 + "  " + unsafe + "\n").encode())
                self.assert_rejects("unsafe")
                self.put("MANIFEST.sha256", original)

    def test_missing_file_and_hash_mismatch_rejected(self):
        (self.root / "README.md").unlink()
        self.assert_rejects("missing file")
        self.put("README.md", b"wrong")
        self.assert_rejects("hash mismatch")

    def test_symlink_in_place_of_tracked_file_rejected(self):
        (self.root / "README.md").unlink()
        try:
            (self.root / "README.md").symlink_to(self.root / "evaluation/original.txt")
        except OSError as exc:
            self.skipTest(f"symlink unavailable: {exc}")
        self.assert_rejects("symlink")

    def test_symlink_directory_ancestor_rejected(self):
        real = self.root / "original-evaluation"
        (self.root / "evaluation").rename(real)
        try:
            (self.root / "evaluation").symlink_to(real, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink unavailable: {exc}")
        self.assert_rejects("symlink")

    def test_write_root_is_explicit_and_keeps_nested_bytes(self):
        old_root = (self.root / "MANIFEST.sha256").read_bytes()
        self.put("new.bin", b"\x00\r\n")
        self.track()
        self.assert_rejects("unlisted tracked")
        self.assertEqual((self.root / "MANIFEST.sha256").read_bytes(), old_root)
        result = self.run_cli("--write-root")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertIn(b"  ./new.bin\n", (self.root / "MANIFEST.sha256").read_bytes())


if __name__ == "__main__":
    unittest.main()
