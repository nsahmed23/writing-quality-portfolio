"""Suite contract tests: splits, clusters and report split selection. No model calls."""

import ast
import unittest
from pathlib import Path

from evaluation.benchmark_v2.automated import contracts
from evaluation.benchmark_v2.automated.contracts import validate_suite
from evaluation.benchmark_v2.automated.scoring import build_report

JUDGES = [{"id": "j1", "family": "f1"}, {"id": "j2", "family": "f2"}]
NO_CLUSTER = object()


def make_case(case_id, doc, split="test", cluster=NO_CLUSTER, text_key=None):
    key = text_key or doc
    value = {
        "id": case_id,
        "document_id": doc,
        "split": split,
        "lane": "editing",
        "prompt": f"Revise the notice for {key}.",
        "context": f"Context for {key}.",
        "a": f"First draft for {key}.",
        "b": f"Second draft for {key}.",
        "expected": None,
        "checks": {},
        "provenance": {"kind": "synthetic_control", "source": "unit test", "license": "CC0-1.0"},
    }
    if cluster is not NO_CLUSTER:
        value["cluster_id"] = cluster
    return value


def make_suite(*cases):
    return {"schema_version": 1, "name": "unit", "cases": list(cases)}


class ClusterFieldTests(unittest.TestCase):
    def test_cluster_id_is_optional(self):
        validate_suite(make_suite(make_case("c1", "d1")))

    def test_cluster_id_accepts_a_nonblank_string(self):
        validate_suite(make_suite(make_case("c1", "d1", cluster="thread-a")))

    def test_cluster_id_rejects_null_blank_and_non_string(self):
        for bad in (None, "", "   ", 7):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "cluster_id"):
                    validate_suite(make_suite(make_case("c1", "d1", cluster=bad)))

    def test_one_document_cannot_sit_in_two_clusters(self):
        suite = make_suite(make_case("c1", "d1", cluster="a"), make_case("c2", "d1", cluster="b"))
        with self.assertRaisesRegex(ValueError, "document assigned to more than one cluster"):
            validate_suite(suite)

    def test_a_document_is_clustered_in_every_case_or_in_none(self):
        clustered_first = make_suite(make_case("c1", "d1", cluster="a"), make_case("c2", "d1"))
        unclustered_first = make_suite(make_case("c1", "d1"), make_case("c2", "d1", cluster="a"))
        for label, suite in (("clustered first", clustered_first), ("unclustered first", unclustered_first)):
            with self.subTest(label):
                with self.assertRaisesRegex(ValueError, "more than one cluster"):
                    validate_suite(suite)

    def test_a_cluster_cannot_span_splits(self):
        suite = make_suite(make_case("c1", "d1", split="calibration", cluster="a"),
                           make_case("c2", "d2", split="test", cluster="a"))
        with self.assertRaisesRegex(ValueError, "cluster spans splits"):
            validate_suite(suite)

    def test_repetitions_and_sibling_documents_in_one_cluster_are_valid(self):
        validate_suite(make_suite(make_case("c1", "d1", cluster="a"),
                                  make_case("c2", "d1", cluster="a"),
                                  make_case("c3", "d2", cluster="a")))

    def test_earlier_leak_checks_still_fire(self):
        reused = make_suite(make_case("c1", "d1", split="calibration"), make_case("c2", "d1", split="test"))
        with self.assertRaisesRegex(ValueError, "document reused across splits"):
            validate_suite(reused)
        copied = make_suite(make_case("c1", "d1"), make_case("c2", "d2", text_key="d1"))
        with self.assertRaisesRegex(ValueError, "copied pair assigned to another document id"):
            validate_suite(copied)

    def test_unknown_case_fields_are_still_rejected(self):
        case = make_case("c1", "d1")
        case["cluster"] = "a"
        with self.assertRaisesRegex(ValueError, "invalid case fields"):
            validate_suite(make_suite(case))


class RequiredCaseFieldTests(unittest.TestCase):
    """Every case field but cluster_id is required; CONTRACT.md promises exactly that."""

    # Named here, not read off make_case, so a field the validator stops requiring is caught by name.
    REQUIRED = ("id", "document_id", "split", "lane", "prompt", "context", "a", "b", "expected", "checks", "provenance")

    def test_the_fixture_case_carries_exactly_the_required_fields(self):
        self.assertEqual(set(make_case("c1", "d1")), set(self.REQUIRED))

    def test_a_case_missing_any_required_field_is_rejected(self):
        for key in self.REQUIRED:
            with self.subTest(key=key):
                case = make_case("c1", "d1")
                del case[key]
                with self.assertRaisesRegex(ValueError, "invalid case fields"):
                    validate_suite(make_suite(case))


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_ignores_presentation_order_whitespace_and_unicode_form(self):
        first = make_case("c1", "d1")
        first["a"], first["b"] = "caf\u00e9 note", "plain"
        second = make_case("c2", "d2")
        second["prompt"] = "  " + first["prompt"].replace(" ", "  ") + " "
        second["context"] = first["context"]
        second["a"], second["b"] = "plain", "cafe\u0301 note"
        self.assertEqual(contracts.case_fingerprint(first), contracts.case_fingerprint(second))


class SplitConstantTests(unittest.TestCase):
    def test_splits_are_the_three_documented_names(self):
        self.assertEqual(contracts.SPLITS, ("calibration", "development", "test"))


def split_suite():
    calibration = make_case("cal1", "dc1", split="calibration")
    calibration["expected"] = "b"
    return make_suite(
        calibration,
        make_case("dev1", "dd1", split="development"),
        make_case("dev2", "dd2", split="development"),
        make_case("tst1", "dt1", split="test"),
        make_case("tst2", "dt2", split="test"),
        make_case("tst3", "dt3", split="test"),
    )


class SplitSelectionTests(unittest.TestCase):
    def expected_records(self, **kwargs):
        report = build_report(split_suite(), [], JUDGES, mode="compare", **kwargs)
        return report["counts"]["expected_records"]

    def test_compare_defaults_to_the_test_split(self):
        self.assertEqual(self.expected_records(), 12)

    def test_compare_can_score_the_development_split(self):
        self.assertEqual(self.expected_records(split="development"), 8)

    def test_compare_can_score_the_calibration_split(self):
        self.assertEqual(self.expected_records(split="calibration"), 4)

    def test_unknown_split_is_refused(self):
        with self.assertRaisesRegex(ValueError, "invalid split"):
            self.expected_records(split="holdout")

    def test_calibrate_scores_only_the_calibration_split(self):
        report = build_report(split_suite(), [], JUDGES, mode="calibrate")
        self.assertEqual(report["counts"]["expected_records"], 4)
        with self.assertRaisesRegex(ValueError, "calibrate scores the calibration split"):
            build_report(split_suite(), [], JUDGES, mode="calibrate", split="test")

    def test_compare_refuses_a_split_with_no_cases_and_names_the_split(self):
        suite = make_suite(make_case("tst1", "dt1", split="test"))
        with self.assertRaisesRegex(ValueError, "compare requires development cases"):
            build_report(suite, [], JUDGES, mode="compare", split="development")
        with self.assertRaisesRegex(ValueError, "compare requires calibration cases"):
            build_report(suite, [], JUDGES, mode="compare", split="calibration")

    def test_calibrate_refuses_a_calibration_split_with_no_labeled_cases(self):
        unlabeled = make_suite(make_case("cal1", "dc1", split="calibration"))
        with self.assertRaisesRegex(ValueError, "calibrate requires labeled calibration cases"):
            build_report(unlabeled, [], JUDGES, mode="calibrate")
        with self.assertRaisesRegex(ValueError, "calibrate requires labeled calibration cases"):
            build_report(make_suite(make_case("tst1", "dt1", split="test")), [], JUDGES, mode="calibrate")

    def test_score_mode_still_falls_back_to_every_case(self):
        suite = make_suite(make_case("dev1", "dd1", split="development"))
        report = build_report(suite, [], JUDGES, mode="score")
        self.assertEqual(report["counts"]["expected_records"], 4)


def is_main_guard(node):
    """True for a top-level `if __name__ == ...:` statement."""
    return (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__")


class TestFileLayoutTests(unittest.TestCase):
    def test_a_main_guard_is_the_last_statement_of_its_test_file(self):
        # A guard above a test class runs unittest.main() before that class exists, so its tests are never run.
        checked = 0
        for path in sorted(Path(__file__).resolve().parent.glob("test_*.py")):
            body = ast.parse(path.read_text(encoding="utf-8")).body
            guards = [index for index, node in enumerate(body) if is_main_guard(node)]
            if guards:
                checked += 1
                self.assertEqual(guards, [len(body) - 1], f"{path.name}: the __main__ guard must be the last statement")
        self.assertGreater(checked, 0)


class ContractDocumentTests(unittest.TestCase):
    """CONTRACT.md is part of the deliverable. These tests keep it in step with the code and the README."""

    AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"
    REQUIRED_HEADINGS = (
        "## Suites, splits and clusters",
        "## Split selection",
        "## Certificates and the judge signature",
        "## Calibration-suite leakage guard",
        "## Run provenance",
        "## Treatment snapshot",
        "## Judge output",
        "## Literal checks",
        "## Plumbing and failure kinds",
        "## Statistics",
        "## Private outputs and the export allowlist",
        "## Claims",
    )
    REQUIRED_NAMES = (
        "suite_sha256", "rubric_sha256", "config_sha256", "judge_signature", "adapter_sha256",
        "candidate_skill_sha256", "provenance.split", "provenance.certificate_suite_sha256",
        "provenance.calibration_overlap", "provenance.tool_versions", "tool_versions_stable",
        "version_commands", "cluster_id", "minItems",
        # The last name carries backticks because the bare word is a substring of the two counts.
        "owner_session", "candidate_check_diagnostics", "baseline_check_diagnostics", "`diagnostics`",
        "failure_kind", "`plumbing`", "`judgment`", "`skipped`", "`attempt`", "MAX_COMMAND_LINE_UNITS",
        "instructions.json", "provenance.documents", "provenance.merged_from", "provenance.rerun",
        "baseline_skill_sha256", "repetitions", "--documents", "`merge`", "rerun-failed",
        "max_calls", "timeout_seconds",
        "candidate_snapshot_sha256", "baseline_snapshot_sha256", "=== references/", "No additional instructions.",
        "--candidate-skill", "--baseline-skill", "60,000 characters",
        "WQ_EVAL_PRIVATE_ROOT", "private.require_private_output", "export.build_export", "export_version",
        "os.path.realpath", "os.path.commonpath", "export --report",
        # The statistics names. Bare "decisive" is a substring of an older sentence, so it carries backticks.
        "`decisive`", "`wins`", "`losses`", "`proportion`", "`wilson_lower`", "`wilson_upper`",
        "`sign_test_p_candidate`", "`sign_test_p_baseline`",
        "`holm(p_values, alpha)`", "lane_stats.py", "Z_90", "NULL_PROPORTION", "MIN_EFFECT", "ALPHA_ONE_SIDED",
        # The writer-isolation probe and the agy measurement script. The config key carries backticks because
        # the bare word is a substring of the provenance name.
        "`isolation_probe`", "max_prompt_tokens", "command_sha256", "prompt_tokens", "provenance.isolation_probe",
        "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "measure_agy.py",
    )
    REFUSAL_MESSAGES = (
        "document reused across splits",
        "document assigned to more than one cluster",
        "cluster spans splits",
        "copied pair assigned to another document id",
        "invalid split",
        "calibrate scores the calibration split",
        "calibrate requires labeled calibration cases",
        "matching eligible live calibration required",
        "certificate was issued on another suite",
        "calibration suite does not match the certificate",
        "overlaps a calibration control",
        "evidence must be nonempty",
        "decisive or both_bad judgment requires both candidate quotes",
        "invalid provenance kind",
        "owner session case cannot have expected winner",
        "documents must be a nonempty list of distinct document ids",
        "unknown document in documents",
        "merge needs at least two runs",
        "is a merged run; merge the original runs",
        "has writer failures",
        "chunk runs differ in",
        "chunk runs differ in instructions",
        "chunk runs differ in tool versions",
        "chunk runs were made with a different",
        "chunk runs overlap",
        "a chunk run changed tool versions while it ran",
        "the run has no plumbing failures to re-run",
        "a merged run or a re-run cannot be re-run",
        "tool versions changed since the run",
        "the run changed tool versions while it ran",
        "skill snapshot too large",
        "is not valid UTF-8",
        "suite has owner_session cases; set WQ_EVAL_PRIVATE_ROOT to a private folder and write the run inside it",
        "suite has owner_session cases; the output path must be inside WQ_EVAL_PRIVATE_ROOT",
        "WQ_EVAL_PRIVATE_ROOT must name an existing folder",
        "report is not a JSON object",
        "report is not an automated proxy report",
        "report is not valid JSON",
        "report field counts.ties has an unexpected value",
        # The writer-isolation probe. The templates are quoted from the code, so a reworded message fails here.
        "isolation probe: writer prompt is {tokens} tokens, over the limit of {limit}",
        "isolation probe failed: {reason}",
        "isolation probe output cannot be parsed: {reason}",
    )

    def contract(self):
        return (self.AUTOMATED / "CONTRACT.md").read_text(encoding="utf-8")

    def readme(self):
        return (self.AUTOMATED / "README.md").read_text(encoding="utf-8")

    def test_contract_has_every_required_section(self):
        headings = [line for line in self.contract().splitlines() if line.startswith("## ")]
        for required in self.REQUIRED_HEADINGS:
            self.assertTrue(any(line.startswith(required) for line in headings), required)

    def test_contract_names_every_split_and_provenance_key(self):
        text = self.contract()
        for name in contracts.SPLITS:
            self.assertIn(f"`{name}`", text)
        for name in self.REQUIRED_NAMES:
            self.assertIn(name, text, name)

    def test_contract_quotes_the_refusal_messages(self):
        text = self.contract()
        for message in self.REFUSAL_MESSAGES:
            self.assertIn(message, text, message)

    def test_contract_has_no_em_dash(self):
        self.assertNotIn(chr(0x2014), self.contract())

    def test_readme_points_to_the_contract(self):
        readme = self.readme()
        self.assertIn("CONTRACT.md", readme)
        self.assertIn("--calibration-suite", readme)

    def test_readme_describes_the_isolation_probe_and_the_agy_measurement(self):
        readme = self.readme()
        for name in ("isolation_probe", "max_prompt_tokens", "measure_agy.py", "AGENTS.md"):
            self.assertIn(name, readme, name)
        # One dated line records the live measurement in the residual-exposure text.
        self.assertRegex(readme, r"Measured 20\d\d-\d\d-\d\d with agy \d+\.\d+\.\d+")

    def test_contract_says_which_commands_run_the_probe(self):
        text = self.contract()
        self.assertIn("only `compare` runs the probe", text)
        self.assertIn("before the output folder exists", text)

    def test_readme_says_where_a_private_run_must_go_and_how_to_publish_its_aggregate(self):
        readme = self.readme()
        self.assertIn("WQ_EVAL_PRIVATE_ROOT", readme)
        self.assertIn("export --report", readme)
        self.assertIn("owner_session", readme)

    def test_contract_names_every_field_the_export_copies(self):
        from evaluation.benchmark_v2.automated import export
        text = self.contract()
        for name in (*export.COUNT_KEYS, *export.LANE_COUNT_KEYS, *export.LANE_NUMBER_KEYS, *export.HASH_KEYS,
                     *export.CHUNK_HASH_KEYS, *export.RERUN_HASH_KEYS, *export.ADAPTER_SCRIPTS, *export.LANES):
            self.assertIn(f"`{name}`", text, name)
        for kind in ("`owner_session`", "`prepare-optimize`", "`optimize`", "`calibrate`", "`compare`", "`merge`",
                     "`rerun-failed`", "`export`"):
            self.assertIn(kind, text, kind)

    def test_docs_say_every_case_field_but_cluster_id_is_required(self):
        self.assertIn("Every field except `cluster_id` is required", self.contract())
        # checks and expected are required keys: a case with nothing to say writes {} and null, never omits them.
        for name, text in (("CONTRACT.md", self.contract()), ("README.md", self.readme())):
            for phrase in ("may carry `checks`", "may carry `expected`", "optional `checks`", "optional `expected`"):
                self.assertNotIn(phrase, text, f"{name}: {phrase}")

    def test_docs_say_line_endings_are_read_as_lf_before_hashing(self):
        for name, text in (("CONTRACT.md", self.contract()), ("README.md", self.readme())):
            self.assertIn("CRLF", text, name)
            self.assertNotIn("same line endings", text, name)

    def test_contract_says_a_certificate_must_record_a_suite_hash(self):
        self.assertIn("records a `suite_sha256`", self.contract())

    def test_docs_say_a_version_command_is_looked_up_on_path(self):
        for name, text in (("CONTRACT.md", self.contract()), ("README.md", self.readme())):
            self.assertIn("looked up on `PATH`", text, name)
        self.assertNotIn("argv is used as written", self.readme())

    def test_contract_lists_only_documents_with_a_miss_under_diagnostics(self):
        self.assertIn("only the documents and lanes that have at least one miss", self.contract())

    def test_contract_pins_the_statistics_formulas_and_constants(self):
        section = self.contract().split("## Statistics", 1)[1].split("\n## ", 1)[0]
        for phrase in ("two-sided 90% Wilson score interval", "1.6448536269514722", "0.15", "0.5",
                       "(p + z^2 / (2n)) / (1 + z^2 / n)", "z * sqrt(p (1 - p) / n + z^2 / (4 n^2)) / (1 + z^2 / n)",
                       "0.6489", "[0, 1]", "inconclusive", "one-sided exact binomial", "Holm-Bonferroni",
                       "net preference", "`decisive`", "`wilson_lower`", "no bootstrap",
                       "lane_stats.py", "`sign_test_p_candidate`", "`sign_test_p_baseline`", "ALPHA_ONE_SIDED", "0.05",
                       "P(X >= wins)", "P(X <= wins)", "Binomial(decisive, 0.5)", "0.125", "0.0625", "0.03515625",
                       "the p-value of the direction being claimed"):
            self.assertIn(phrase, section, phrase)
        self.assertNotIn("`sign_test_p`", section)

    def test_readme_describes_the_wilson_rule_and_not_the_bootstrap(self):
        readme = self.readme()
        self.assertIn("Wilson", readme)
        self.assertNotIn("confidence bound", readme)
        self.assertNotIn("resampl", readme)

    def test_readme_describes_the_two_directional_sign_tests_and_the_alpha_rule(self):
        readme = self.readme()
        for phrase in ("two one-sided sign-test p-values", "at most 0.05", "wq-automated-wilson-lower"):
            self.assertIn(phrase, readme, phrase)
        self.assertNotIn("an exact one-sided sign-test p-value", readme)
        self.assertNotIn("sign_test_p`", readme)

    def test_contract_pins_the_treatment_snapshot_rules(self):
        section = self.contract().split("## Treatment snapshot", 1)[1].split("\n## ", 1)[0]
        for phrase in ("`references/`", "=== references/<path> ===", "CRLF", "UTF-8", "60,000 characters",
                       "`candidate_skill_sha256`", "raw `SKILL.md` bytes", "`null`", "No additional instructions.",
                       "skill snapshot too large: NAME is N characters, over the limit of 60000"):
            self.assertIn(phrase, section, phrase)

    def test_readme_says_the_writer_gets_the_snapshot_and_names_its_limit(self):
        readme = self.readme()
        for phrase in ("`references/`", "60,000 characters", "No additional instructions.", "candidate_snapshot_sha256"):
            self.assertIn(phrase, readme, phrase)
        # The old wording said the writer got SKILL.md alone and that a folder resolved to SKILL.md only.
        self.assertNotIn("receives the selected `SKILL.md` text", readme)
        self.assertNotIn("A skill directory resolves to its `SKILL.md`.", readme)


if __name__ == "__main__":
    unittest.main()
