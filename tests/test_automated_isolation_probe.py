"""Writer-isolation probe tests. Stand-in scripts print JSON; no model call is made."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:  # discover -s tests puts this folder on sys.path; python -m unittest tests.test_x does not
    from test_automated_certificate import ADAPTER, certificate_cases, comparison_cases, config_of, suite_of
except ModuleNotFoundError:
    from tests.test_automated_certificate import ADAPTER, certificate_cases, comparison_cases, config_of, suite_of

from evaluation.benchmark_v2.automated import isolation
from evaluation.benchmark_v2.automated.__main__ import main
from evaluation.benchmark_v2.automated.adapters import canonical_bytes, digest, load_config
from evaluation.benchmark_v2.automated.runner import calibrate, compare

AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"

# The ordinary stand-in adapter, plus one tick in a file for every call it receives (when the test names the file).
COUNTING_ADAPTER = ('import os\n'
                    'if os.environ.get("WQ_TEST_COUNTER"):\n'
                    '    open(os.environ["WQ_TEST_COUNTER"], "a").write("x")\n' + ADAPTER)


def usage_output(input_tokens, cache_creation=0, cache_read=0):
    """What `claude -p --output-format json` prints, cut to the fields the probe reads."""
    return {"type": "result", "is_error": False, "result": "ok",
            "usage": {"input_tokens": input_tokens, "cache_creation_input_tokens": cache_creation,
                      "cache_read_input_tokens": cache_read, "output_tokens": 4}}


def printing(value):
    """Stand-in probe body that prints one JSON value."""
    return f"print(json.dumps({value!r}))\n"


def probe_script(folder, name, body):
    """Write a stand-in probe that reads its stdin like a CLI would, then runs body; return its command."""
    path = Path(folder) / name
    path.write_text("import json, os, sys\nsent = sys.stdin.read()\n" + body, encoding="utf-8")
    return [sys.executable, str(path)]


class ProbeConfigTests(unittest.TestCase):
    BAD_PROBES = (
        None, [], "probe", 5,
        {}, {"command": [sys.executable]}, {"max_prompt_tokens": 5},
        {"command": [sys.executable], "max_prompt_tokens": 5, "extra": 1},
        {"command": [], "max_prompt_tokens": 5},
        {"command": "claude -p", "max_prompt_tokens": 5},
        {"command": [sys.executable, ""], "max_prompt_tokens": 5},
        {"command": [sys.executable, "  "], "max_prompt_tokens": 5},
        {"command": [sys.executable, 3], "max_prompt_tokens": 5},
        {"command": [sys.executable], "max_prompt_tokens": 0},
        {"command": [sys.executable], "max_prompt_tokens": -1},
        {"command": [sys.executable], "max_prompt_tokens": True},
        {"command": [sys.executable], "max_prompt_tokens": 1.5},
        {"command": [sys.executable], "max_prompt_tokens": "10"},
        {"command": [sys.executable], "max_prompt_tokens": None},
    )

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def load(self, **extra):
        path = self.root / "config.json"
        path.write_text(json.dumps(config_of([sys.executable, "adapter.py"], **extra)), encoding="utf-8")
        return load_config(path)

    def test_a_config_without_a_probe_has_no_probe_key(self):
        self.assertNotIn("isolation_probe", self.load())

    def test_a_valid_probe_is_kept(self):
        probe = {"command": [sys.executable, "-c", "pass"], "max_prompt_tokens": 10000}
        self.assertEqual(self.load(isolation_probe=probe)["isolation_probe"], probe)

    def test_a_probe_script_beside_the_config_resolves_like_an_adapter_script(self):
        (self.root / "probe.py").write_text("pass\n", encoding="utf-8")
        config = self.load(isolation_probe={"command": [sys.executable, "probe.py"], "max_prompt_tokens": 5})
        self.assertEqual(config["isolation_probe"]["command"], [sys.executable, str(self.root / "probe.py")])

    def test_a_malformed_probe_is_refused(self):
        for probe in self.BAD_PROBES:
            with self.subTest(probe=probe):
                with self.assertRaisesRegex(ValueError, "isolation_probe"):
                    self.load(isolation_probe=probe)


class ProbeTests(unittest.TestCase):
    UNPARSABLE_OUTPUTS = (
        "", "not json", "[]", "{}", '{"usage": 3}', '{"usage": {}}', '{"usage": {"input_tokens": "5"}}',
        '{"usage": {"input_tokens": true}}', '{"usage": {"input_tokens": -1}}', '{"usage": {"input_tokens": 1.5}}',
        '{"usage": {"input_tokens": 1, "cache_read_input_tokens": null}}',
        '{"usage": {"input_tokens": 1}, "usage": {"input_tokens": 2}}',
    )

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def run_body(self, body, limit=10000, **kwargs):
        command = probe_script(self.root, "probe.py", body)
        return isolation.run_probe({"command": command, "max_prompt_tokens": limit}, **kwargs)

    def test_no_settings_means_no_probe(self):
        self.assertIsNone(isolation.run_probe(None))

    def test_the_three_usage_counts_are_summed_and_the_limit_itself_passes(self):
        command = probe_script(self.root, "probe.py", printing(usage_output(100, 20, 3)))
        result = isolation.run_probe({"command": command, "max_prompt_tokens": 123})
        self.assertEqual(result, {"command_sha256": digest(canonical_bytes(command)),
                                  "max_prompt_tokens": 123, "prompt_tokens": 123})

    def test_a_count_over_the_limit_refuses_with_the_pinned_message(self):
        with self.assertRaises(ValueError) as caught:
            self.run_body(printing(usage_output(100, 20, 3)), limit=122)
        self.assertEqual(str(caught.exception), "isolation probe: writer prompt is 123 tokens, over the limit of 122")
        self.assertEqual(str(caught.exception), isolation.OVER_LIMIT.format(tokens=123, limit=122))

    def test_cache_counts_are_summed_too(self):
        # A project instruction file reaches the model as cached input, so input_tokens alone would miss it.
        for body in (printing(usage_output(10, 0, 8990)), printing(usage_output(10, 8990, 0))):
            with self.subTest(body=body):
                with self.assertRaisesRegex(ValueError, "writer prompt is 9000 tokens"):
                    self.run_body(body, limit=100)

    def test_a_missing_cache_count_counts_as_zero(self):
        self.assertEqual(self.run_body(printing({"usage": {"input_tokens": 5}}))["prompt_tokens"], 5)

    def test_the_result_event_of_an_event_list_is_read(self):
        events = [{"type": "system", "subtype": "init"}, usage_output(7, 1, 2)]
        self.assertEqual(self.run_body(printing(events))["prompt_tokens"], 10)

    def test_the_probe_sends_one_fixed_line_on_stdin_from_a_scratch_folder(self):
        body = (f"open({str(self.root / 'sent.txt')!r}, 'w', encoding='utf-8').write(sent)\n"
                f"open({str(self.root / 'cwd.txt')!r}, 'w', encoding='utf-8').write(os.getcwd())\n"
                + printing(usage_output(1)))
        self.run_body(body)
        self.assertEqual((self.root / "sent.txt").read_text(encoding="utf-8"), isolation.PROBE_PROMPT)
        self.assertNotIn("\n", isolation.PROBE_PROMPT)
        scratch = Path((self.root / "cwd.txt").read_text(encoding="utf-8"))
        self.assertTrue(scratch.name.startswith("wq-probe-"))
        self.assertNotEqual(scratch.resolve(), Path.cwd().resolve())
        self.assertFalse(scratch.exists())

    def test_a_probe_that_fails_refuses_with_the_reason(self):
        failing = ("sys.exit(3)\n", printing({**usage_output(1), "is_error": True}))
        reasons = ("exit code 3", "the probe reported an error")
        for body, reason in zip(failing, reasons):
            with self.subTest(reason=reason):
                with self.assertRaises(ValueError) as caught:
                    self.run_body(body)
                self.assertEqual(str(caught.exception), f"isolation probe failed: {reason}")

    def test_a_probe_that_cannot_start_refuses(self):
        missing = {"command": [str(self.root / "no-such-program"), "x"], "max_prompt_tokens": 100}
        with self.assertRaisesRegex(ValueError, "^isolation probe failed: could not start"):
            isolation.run_probe(missing)

    def test_a_probe_that_runs_too_long_refuses(self):
        with self.assertRaisesRegex(ValueError, "^isolation probe failed: timed out after 1 seconds$"):
            self.run_body("import time\ntime.sleep(60)\n", timeout_seconds=1)

    def test_unreadable_output_refuses_with_the_parse_message(self):
        for text in self.UNPARSABLE_OUTPUTS:
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "^isolation probe output cannot be parsed: "):
                    self.run_body(f"sys.stdout.write({text!r})\n")

    def test_message_templates_are_pinned(self):
        self.assertEqual(isolation.OVER_LIMIT, "isolation probe: writer prompt is {tokens} tokens, over the limit of {limit}")
        self.assertEqual(isolation.FAILED, "isolation probe failed: {reason}")
        self.assertEqual(isolation.UNPARSABLE, "isolation probe output cannot be parsed: {reason}")

    def test_the_contract_quotes_each_template_exactly(self):
        contract = (AUTOMATED / "CONTRACT.md").read_text(encoding="utf-8")
        for template in (isolation.OVER_LIMIT, isolation.FAILED, isolation.UNPARSABLE):
            self.assertIn(template, contract, template)


class CompareProbeTests(unittest.TestCase):
    """compare runs the probe once, before any model call and before its output folder exists."""

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name).resolve()
        script = cls.root / "adapter.py"
        script.write_text(COUNTING_ADAPTER, encoding="utf-8")
        cls.command = [sys.executable, str(script)]
        cls.rubric = cls.write_json("rubric.json", {
            "schema_version": 1, "id": "r", "criteria": [{"id": "meaning", "description": "Preserve meaning."}]})
        cls.cal_suite = cls.write_json("cal-suite.json", suite_of(certificate_cases()))
        cls.cmp_suite = cls.write_json("cmp-suite.json", suite_of(comparison_cases()))
        cls.config = cls.write_json("config.json", config_of(cls.command))
        cls.skill = cls.root / "skill"
        cls.skill.mkdir()
        (cls.skill / "SKILL.md").write_text("Keep it short.\n", encoding="utf-8")
        cls.certificate_dir = cls.root / "certificate"
        certificate = calibrate(cls.cal_suite, cls.rubric, cls.config, cls.certificate_dir)
        if not certificate["eligible"]:
            raise AssertionError(f"fixture certificate is not eligible: {certificate['checks']}")

    @classmethod
    def write_json(cls, name, value):
        path = cls.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def probe_config(self, name, body, limit=10000):
        """A config whose probe is a stand-in running body; returns the config path and the probe command."""
        command = probe_script(self.root, f"{name}-probe.py", body)
        config = self.write_json(f"{name}-config.json",
                                 config_of(self.command, isolation_probe={"command": command, "max_prompt_tokens": limit}))
        return config, command

    def run_compare(self, name, config):
        return compare(self.cmp_suite, self.rubric, config, self.certificate_dir, self.skill, self.root / name,
                       calibration_suite=self.cal_suite)

    def test_compare_runs_the_probe_once_and_records_it_in_provenance(self):
        ticks = self.root / "ticks-record.txt"
        body = f"open({str(ticks)!r}, 'a').write('x')\n" + printing(usage_output(100, 20, 3))
        config, command = self.probe_config("record", body)
        report = self.run_compare("out-record", config)
        expected = {"command_sha256": digest(canonical_bytes(command)), "max_prompt_tokens": 10000, "prompt_tokens": 123}
        self.assertEqual(report["provenance"]["isolation_probe"], expected)
        saved = json.loads((self.root / "out-record" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["provenance"]["isolation_probe"], expected)
        self.assertEqual(ticks.read_text(encoding="utf-8"), "x")  # once, although compare made many calls
        self.assertGreater(report["counts"]["received_records"], 0)

    def test_a_config_without_a_probe_runs_as_before(self):
        report = self.run_compare("out-plain", self.config)
        self.assertNotIn("isolation_probe", report["provenance"])
        self.assertGreater(report["counts"]["received_records"], 0)

    def test_a_refused_probe_stops_compare_before_any_call_and_before_the_output_folder(self):
        cases = {
            "over": (printing(usage_output(10001)), "isolation probe: writer prompt is 10001 tokens, over the limit of 10000"),
            "failed": ("sys.exit(1)\n", "isolation probe failed: exit code 1"),
            "garbled": ("print('not json')\n", "isolation probe output cannot be parsed: "),
        }
        for name, (body, message) in cases.items():
            with self.subTest(name):
                counter = self.root / f"calls-{name}.txt"
                config, _ = self.probe_config(name, body)
                with mock.patch.dict(os.environ, {"WQ_TEST_COUNTER": str(counter)}):
                    with self.assertRaises(ValueError) as caught:
                        self.run_compare(f"out-{name}", config)
                self.assertTrue(str(caught.exception).startswith(message), str(caught.exception))
                self.assertFalse((self.root / f"out-{name}").exists())
                self.assertFalse(counter.exists())

    def test_a_failing_version_command_stops_compare_before_the_probe_is_asked(self):
        # Version commands cost no model call, so they are read first; the probe is the first model call after them.
        ticks = self.root / "ticks-versions.txt"
        command = probe_script(self.root, "versions-probe.py",
                               f"open({str(ticks)!r}, 'a').write('x')\n" + printing(usage_output(100)))
        config = self.write_json("versions-config.json", config_of(
            self.command, isolation_probe={"command": command, "max_prompt_tokens": 10000},
            version_commands={"gone": [str(self.root / "no-such-tool")]}))
        with self.assertRaises(ValueError) as caught:
            self.run_compare("out-versions", config)
        self.assertEqual(str(caught.exception), "version command failed before the run: gone")
        self.assertFalse(ticks.exists())
        self.assertFalse((self.root / "out-versions").exists())

    def test_the_probe_is_not_charged_to_max_calls(self):
        # max_calls=30 fits the run exactly: 5 test cases x (2 writer calls + 2 judges x 2 calls). The probe still runs.
        ticks = self.root / "ticks-budget.txt"
        command = probe_script(self.root, "budget-probe.py",
                               f"open({str(ticks)!r}, 'a').write('x')\n" + printing(usage_output(100)))
        config = self.write_json("budget-config.json", config_of(
            self.command, isolation_probe={"command": command, "max_prompt_tokens": 10000}, max_calls=30))
        report = self.run_compare("out-budget", config)
        self.assertEqual(ticks.read_text(encoding="utf-8"), "x")
        self.assertGreater(report["counts"]["received_records"], 0)

    def test_calibrate_does_not_run_the_probe(self):
        # Calibration makes no writer call, so a probe that would refuse is never asked.
        ticks = self.root / "ticks-calibrate.txt"
        config, _ = self.probe_config("calibrate", f"open({str(ticks)!r}, 'a').write('x')\nsys.exit(1)\n")
        report = calibrate(self.cal_suite, self.rubric, config, self.root / "calibrate-with-probe")
        self.assertTrue(report["eligible"])
        self.assertNotIn("isolation_probe", report["provenance"])
        self.assertFalse(ticks.exists())

    def test_the_command_line_exits_2_with_the_message(self):
        config, _ = self.probe_config("cli", printing(usage_output(10001)))
        argv = ["compare", "--suite", str(self.cmp_suite), "--rubric", str(self.rubric), "--config", str(config),
                "--out", str(self.root / "out-cli"), "--calibration", str(self.certificate_dir),
                "--candidate-skill", str(self.skill), "--calibration-suite", str(self.cal_suite)]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
            main(argv)
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("error: isolation probe: writer prompt is 10001 tokens, over the limit of 10000", stderr.getvalue())
        self.assertFalse((self.root / "out-cli").exists())


if __name__ == "__main__":
    unittest.main()
