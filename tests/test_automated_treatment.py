"""Treatment snapshot: the instructions the writer is given are SKILL.md plus the files under its references/ folder.

No model is called. The writer and the judges are stand-in scripts that the real runner starts, and the calibration
certificate is written by hand, as in test_automated_runs.py. The writer requests the runner saved under calls/ show
exactly what the writer was given: for the first document, call 1 is the baseline and call 2 is the candidate."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation.benchmark_v2.automated import runner
from evaluation.benchmark_v2.automated.__main__ import main
from evaluation.benchmark_v2.automated.adapters import canonical_bytes, digest, load_config

AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"
RUBRIC = AUTOMATED / "data" / "rubric.json"
PY = sys.executable
LIMIT = 60000
SKILL_TEXT = "# Skill\nCANDIDATE-MARK\nWrite briefly.\n"

# Stand-in writer: instructions that hold CANDIDATE-MARK get the brief text, any others the wordy text.
WRITER = '''import json, sys
request = json.load(sys.stdin)
lead = "Brief take on " if "CANDIDATE-MARK" in request["instructions"] else "A rather wordy take on "
print(json.dumps({"text": lead + request["prompt"]}))
'''

# Stand-in judge: prefers the text that starts with "Brief" and quotes the first five characters of both texts.
JUDGE = '''import json, sys
request = json.load(sys.stdin)
a, b = request["A"], request["B"]
winner = "A" if a.startswith("Brief") else "B"
print(json.dumps({"winner": winner, "reason": "briefer",
                  "evidence": [{"candidate": "A", "quote": a[:5]}, {"candidate": "B", "quote": b[:5]}]}))
'''


def suite_dict():
    cases = []
    for n in range(1, 3):
        cases.append({"id": f"case-{n}", "document_id": f"doc-{n}", "split": "test", "lane": "editing",
                      "prompt": f"Revise item {n}.", "context": f"Context {n}",
                      "a": f"alpha {n}", "b": f"beta {n}", "expected": None, "checks": {},
                      "provenance": {"kind": "synthetic_control", "source": "test fixture", "license": "CC0"}})
    return {"schema_version": 1, "name": "treatment-fixture", "cases": cases}


class SkillFolder(unittest.TestCase):
    """A temporary folder, and a way to write skill folders into it byte for byte."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # Resolve once: a Windows TEMP can be an 8.3 short path (RUNNER~1) while the runner reports the long spelling.
        self.root = Path(tmp.name).resolve()

    def skill(self, name, text=SKILL_TEXT, references=None):
        """A skill folder with SKILL.md and the given references/ files (relative path to str or bytes), written unconverted."""
        folder = self.root / name
        folder.mkdir()
        (folder / "SKILL.md").write_bytes(text.encode("utf-8"))
        for relative, content in (references or {}).items():
            path = folder / "references" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return folder


class SnapshotTextTests(SkillFolder):
    def snapshot(self, path):
        return runner._skill_snapshot(path)[1]

    def test_the_snapshot_is_skill_md_then_each_reference_under_a_header(self):
        folder = self.skill("two", "# Skill\nBody.\n", {"b.md": "Second.\n", "a.md": "First.\n"})
        self.assertEqual(self.snapshot(folder),
                         "# Skill\nBody.\n\n=== references/a.md ===\nFirst.\n\n=== references/b.md ===\nSecond.\n")

    def test_references_sort_by_forward_slash_path_as_plain_text_on_every_platform(self):
        names = ["z.md", "sub/m.md", "a.md", "a-b.md", "B.md"]
        folder = self.skill("sorted", "S\n", {name: f"{name}\n" for name in names})
        # Plain text order: capitals before lower case, "-" before ".", and "sub/m.md" after "a.md".
        self.assertEqual(sorted(names), ["B.md", "a-b.md", "a.md", "sub/m.md", "z.md"])
        expected = "S\n" + "".join(f"\n=== references/{name} ===\n{name}\n" for name in sorted(names))
        self.assertEqual(self.snapshot(folder), expected)

    def test_line_endings_are_read_as_lf_in_skill_md_and_in_every_reference(self):
        folder = self.skill("crlf", "# Skill\r\nBody.\r\n", {"a.md": "One.\r\nTwo.\r\n"})
        self.assertEqual(self.snapshot(folder), "# Skill\nBody.\n\n=== references/a.md ===\nOne.\nTwo.\n")

    def test_a_skill_without_references_is_exactly_its_own_text(self):
        folder = self.skill("alone", "# Alone\r\nText.\r\n")
        raw, text = runner._skill_snapshot(folder)
        self.assertEqual(text, "# Alone\nText.\n")
        self.assertEqual(raw, b"# Alone\r\nText.\r\n")

    def test_a_header_always_starts_its_own_line_after_a_blank_line(self):
        folder = self.skill("bare", "Body", {"a.md": "A", "b.md": "B"})
        self.assertEqual(self.snapshot(folder), "Body\n\n=== references/a.md ===\nA\n\n=== references/b.md ===\nB")

    def test_a_folder_path_and_a_skill_md_path_give_the_same_snapshot(self):
        folder = self.skill("same", SKILL_TEXT, {"r.md": "R.\n"})
        self.assertEqual(runner._skill_snapshot(folder), runner._skill_snapshot(folder / "SKILL.md"))

    def test_raw_bytes_stay_those_of_skill_md_alone(self):
        folder = self.skill("raw", SKILL_TEXT, {"r.md": "R.\n"})
        self.assertEqual(runner._skill_snapshot(folder)[0], SKILL_TEXT.encode("utf-8"))

    def test_only_skill_md_and_references_are_included(self):
        folder = self.skill("others", "S\n", {"r.md": "R\n"})
        (folder / "scripts").mkdir()
        (folder / "scripts" / "x.md").write_text("never", encoding="utf-8")
        (folder / "NOTES.md").write_text("never", encoding="utf-8")
        self.assertEqual(self.snapshot(folder), "S\n\n=== references/r.md ===\nR\n")

    def test_a_file_that_is_not_utf8_is_refused_by_skill_and_file(self):
        folder = self.skill("broken", "S\n", {"ok.md": "fine\n", "bad.md": b"\xff\xfe\x00"})
        with self.assertRaises(ValueError) as caught:
            runner._skill_snapshot(folder)
        message = str(caught.exception)
        for part in ("references/bad.md", "broken", "not valid UTF-8"):
            self.assertIn(part, message)


class SnapshotLimitTests(SkillFolder):
    def test_the_limit_is_60000_characters_not_bytes(self):
        self.assertEqual(runner.MAX_SNAPSHOT_CHARACTERS, LIMIT)
        # 60000 two-byte characters are 120000 bytes; only a count of characters accepts them.
        at_limit = self.skill("at-limit", "é" * LIMIT)
        self.assertEqual(len(runner._skill_snapshot(at_limit)[1]), LIMIT)
        with self.assertRaises(ValueError) as caught:
            runner._skill_snapshot(self.skill("one-over", "é" * LIMIT + "x"))
        self.assertEqual(str(caught.exception),
                         f"skill snapshot too large: one-over is {LIMIT + 1} characters, over the limit of {LIMIT}")

    def test_the_size_is_that_of_the_whole_snapshot_headers_included(self):
        folder = self.skill("big-skill", "x" * 40000, {"more.md": "y" * 30000})
        size = len("x" * 40000 + "\n\n=== references/more.md ===\n" + "y" * 30000)
        with self.assertRaises(ValueError) as caught:
            runner._skill_snapshot(folder)
        self.assertEqual(str(caught.exception),
                         f"skill snapshot too large: big-skill is {size} characters, over the limit of {LIMIT}")

    def test_the_name_in_the_message_is_the_skill_folder_even_for_a_skill_md_path(self):
        folder = self.skill("named-skill", "x" * (LIMIT + 5))
        with self.assertRaises(ValueError) as caught:
            runner._skill_snapshot(folder / "SKILL.md")
        self.assertIn("named-skill", str(caught.exception))


class CompareFixture(SkillFolder):
    """A two-document test suite, stand-in adapters, a config and a hand-written certificate."""

    def setUp(self):
        super().setUp()
        self.suite_path = self.root / "suite.json"
        self.suite_path.write_bytes(canonical_bytes(suite_dict()))
        (self.root / "writer.py").write_text(WRITER, encoding="utf-8")
        (self.root / "judge.py").write_text(JUDGE, encoding="utf-8")
        config = {"schema_version": 1,
                  "judges": [{"id": "j1", "family": "f1", "command": [PY, str(self.root / "judge.py")]},
                             {"id": "j2", "family": "f2", "command": [PY, str(self.root / "judge.py")]}],
                  "writer": {"id": "w", "family": "fw", "command": [PY, str(self.root / "writer.py")]}}
        self.config_path = self.root / "config.json"
        self.config_path.write_bytes(canonical_bytes(config))
        report = {"schema_version": 1, "evaluation_type": "automated_proxy", "execution": "live",
                  "mode": "calibrate", "complete": True, "eligible": True,
                  "provenance": runner._provenance(self.suite_path, RUBRIC, self.config_path, load_config(self.config_path))}
        self.certificate = self.root / "certificate"
        self.certificate.mkdir()
        (self.certificate / "report.json").write_bytes(canonical_bytes(report))

    def compare(self, name, candidate, **options):
        return runner.compare(self.suite_path, RUBRIC, self.config_path, self.certificate, candidate,
                              self.root / name, **options)

    def read(self, name, filename):
        return json.loads((self.root / name / filename).read_bytes())

    def writer_instructions(self, name, call):
        """The instructions field of one writer request the runner saved under calls/."""
        request = json.loads((self.root / name / "calls" / f"{call:05d}" / "request.json").read_bytes())
        self.assertEqual(request["role"], "writer")
        return request["instructions"]


class CompareSnapshotTests(CompareFixture):
    def test_the_writer_is_given_the_candidate_snapshot_not_skill_md_alone(self):
        candidate = self.skill("candidate", SKILL_TEXT, {"b.md": "Second.\n", "a.md": "First.\n"})
        snapshot = SKILL_TEXT + "\n=== references/a.md ===\nFirst.\n\n=== references/b.md ===\nSecond.\n"
        self.compare("run", candidate, documents=["doc-1"])
        self.assertEqual(self.writer_instructions("run", 2), snapshot)
        self.assertEqual(self.read("run", "instructions.json")["candidate"],
                         {"sha256": digest(snapshot.encode("utf-8")), "text": snapshot})
        # candidate-SKILL.md keeps the raw SKILL.md bytes, which is what the metric pack checks.
        self.assertEqual((self.root / "run" / "candidate-SKILL.md").read_bytes(), SKILL_TEXT.encode("utf-8"))

    def test_the_baseline_skill_follows_the_same_snapshot_rule(self):
        candidate = self.skill("candidate")
        baseline = self.skill("baseline", "# Baseline\r\nKeep the draft.\r\n", {"r.md": "Rule.\r\n"})
        self.compare("run", candidate, documents=["doc-1"], baseline_skill=baseline)
        expected = "# Baseline\nKeep the draft.\n\n=== references/r.md ===\nRule.\n"
        self.assertEqual(self.writer_instructions("run", 1), expected)
        self.assertEqual(self.read("run", "instructions.json")["baseline"],
                         {"sha256": digest(expected.encode("utf-8")), "text": expected})
        self.assertEqual((self.root / "run" / "baseline-SKILL.md").read_bytes(), b"# Baseline\r\nKeep the draft.\r\n")

    def test_an_oversized_snapshot_is_refused_before_any_output_or_call(self):
        small = self.skill("small")
        big = self.skill("big-skill", "x" * 40000, {"more.md": "y" * 30000})
        for label, candidate, options in (("candidate", big, {}), ("baseline", small, {"baseline_skill": big})):
            with self.subTest(label):
                with self.assertRaises(ValueError) as caught:
                    self.compare(label, candidate, documents=["doc-1"], **options)
                self.assertIn("skill snapshot too large: big-skill is", str(caught.exception))
                self.assertFalse((self.root / label).exists())

    def test_the_command_line_refuses_an_oversized_snapshot_with_exit_2(self):
        big = self.skill("big-skill", "x" * (LIMIT + 1))
        out = self.root / "cli"
        argv = ["compare", "--suite", str(self.suite_path), "--rubric", str(RUBRIC), "--config", str(self.config_path),
                "--calibration", str(self.certificate), "--candidate-skill", str(big), "--out", str(out)]
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured), self.assertRaises(SystemExit) as caught:
            main(argv)
        self.assertEqual(caught.exception.code, 2)
        self.assertIn(f"skill snapshot too large: big-skill is {LIMIT + 1} characters", captured.getvalue())
        self.assertFalse(out.exists())


class ShippedSkillTests(unittest.TestCase):
    """The limit was chosen against the real skills, so a skill that grows past it fails here and not in a live run."""

    SKILLS = Path(__file__).resolve().parents[1] / "skills"

    def test_every_shipped_skill_fits_the_limit_and_carries_all_its_references_in_order(self):
        folders = sorted(path for path in self.SKILLS.iterdir() if (path / "SKILL.md").is_file())
        self.assertGreaterEqual(len(folders), 8)
        for folder in folders:
            with self.subTest(folder.name):
                text = runner._skill_snapshot(folder)[1]
                self.assertLessEqual(len(text), LIMIT)
                references = sorted(path.relative_to(folder).as_posix()
                                    for path in (folder / "references").rglob("*") if path.is_file())
                headers = [line[len("=== "):-len(" ===")] for line in text.split("\n")
                           if line.startswith("=== references/") and line.endswith(" ===")]
                self.assertEqual(headers, references)


if __name__ == "__main__":
    unittest.main()
