# Automated writing comparison (development protocol)

This package implements `automated_proxy`, a separate workflow from the archived editing-pilot human-review protocol. No human grade is required: missing evidence, failed judge calibration, unstable judgments, and close comparisons end in an automatic **inconclusive** result. Software demos verify plumbing only; they cannot approve a candidate. The public controls and references are development material, not a blind holdout or a measure of expert writing quality.

Run from the repository root with Python 3.11 or later. The demo needs no API key and makes no model call:

```sh
python -m evaluation.benchmark_v2.automated validate --suite evaluation/benchmark_v2/automated/data/controls.json --rubric evaluation/benchmark_v2/automated/data/rubric.json
python -m evaluation.benchmark_v2.automated validate --suite evaluation/benchmark_v2/automated/data/references.json --rubric evaluation/benchmark_v2/automated/data/rubric.json
python -m evaluation.benchmark_v2.automated demo --out /tmp/wq-demo-1
python -m unittest discover -s tests -p 'test_automated_*.py'
```

Use a **new** output directory for each invocation; runs refuse to overwrite old evidence. The demo includes a functioning synthetic path and a rejected/inconsistent judgment path. Neither result qualifies as a live quality verdict.

## Live adapter configuration

Copy `adapters/example-config.json` to a local configuration and edit the command arrays for your installed, trusted local adapters. The example contains **one** Codex judge family, which is insufficient for an eligible live comparison: add a genuinely distinct second judge family. Each judge has a distinct `id` and a `family`; a complete live comparison needs at least two independent judge families. The config declares `schema_version: 1`, `judges: [{id, family, command: [executable, argv...] }]`, optional `writer` and `optimizer` with the same shape, `timeout_seconds` (default 120, up to 600), and `max_calls` (default 200). A configured command receives one JSON request on stdin and must write exactly one raw UTF-8 JSON response to stdout. Commands execute as argv with `shell=False`; treat them as trusted software, not an OS sandbox. Config-relative executable/script paths resolve from the config directory. The included Codex CLI adapter is one available command; for another model CLI that accepts JSON on stdin and emits raw JSON on stdout, the generic bridge accepts `python generic_json_adapter.py -- MODEL_CLI ARG...` in the command array. Supply credentials through the normal environment, not in config files. The runner preserves request, first response, stderr, exit status, elapsed time and hashes. Judge requests exclude candidate identity, private expected labels and suite files, but provider retention policies still apply.

The judge returns `{"winner":"A|B|tie|both_bad","reason":"...","evidence":[{"candidate":"A|B","quote":"literal excerpt"}]}`. Decisive and both-bad judgments must quote both candidates; a tie may cite one. The writer receives the selected `SKILL.md` text as `instructions` and returns `{"text":"nonblank response"}`. Comparing a skill with external reference files evaluates only the supplied instruction snapshot, not the entire routed portfolio. A skill directory resolves to its `SKILL.md`.

After configuring adapters, run calibration before comparison. These are command templates; no live run is claimed here:

```sh
python -m evaluation.benchmark_v2.automated calibrate --suite evaluation/benchmark_v2/automated/data/controls.json --rubric evaluation/benchmark_v2/automated/data/rubric.json --config /path/to/local-config.json --out /tmp/wq-calibration-1
python -m evaluation.benchmark_v2.automated compare --suite evaluation/benchmark_v2/automated/data/controls.json --rubric evaluation/benchmark_v2/automated/data/rubric.json --config /path/to/local-config.json --calibration /tmp/wq-calibration-1 --candidate-skill skills/concision --repetitions 1 --out /tmp/wq-comparison-1
python -m evaluation.benchmark_v2.automated prepare-optimize --suite evaluation/benchmark_v2/automated/data/controls.json --out /tmp/wq-optimize-suite-1.json
python -m evaluation.benchmark_v2.automated optimize --suite /tmp/wq-optimize-suite-1.json --rubric evaluation/benchmark_v2/automated/data/rubric.json --config /path/to/local-config.json --rounds 2 --out /tmp/wq-optimization-1
```

Calibration requires at least eight labeled controls across four documents, two presentation orders per judge, complete valid coverage, and engineering-default thresholds of 0.90 for stable correctness and order stability. A comparison requires a matching eligible **live** calibration for the same rubric and judge signature. It samples independent documents, treats abstentions and disagreements as zero preference, and recommends a candidate only if every evaluated lane clears its lower confidence bound and deterministic checks. Otherwise it can recommend retaining the baseline or report inconclusive. The controls are public synthetic checks, so even a passing proxy does not establish an expert or held-out quality result. `prepare-optimize` writes a new, validated calibration/development-only subset from a mixed starter suite without human filtering or labels; it refuses to overwrite a file. Optimize uses only that subset and stops after at most three proposed rounds; it never edits a skill or admits test examples.

## Plugin Eval extension or direct JSON

The optional local-only metric pack reads an **existing** report; `analyze` never starts model work. Choose the exact report file emitted in the comparison output directory and analyze the same skill snapshot:

```sh
WQ_EVAL_REPORT=/tmp/wq-comparison-1/report.json node /root/.codex/plugins/cache/openai-curated-remote/plugin-eval/0.1.2/src/cli.js analyze skills/concision --format json --metric-pack evaluation/benchmark_v2/automated/plugin_eval/manifest.json
WQ_EVAL_REPORT=/tmp/wq-comparison-1/report.json python evaluation/benchmark_v2/automated/metric_pack.py skills/concision skill
```

The second command prints only the extension JSON and does not require Plugin Eval. The manifest supports `skill` and `plugin`; plugin roots with more than one skill are ambiguous and yield a warning, so analyze a specific skill in this portfolio. The extension verifies the report schema, suite/rubric/config/judge provenance digests, and the candidate skill hash against raw `SKILL.md` bytes. It trusts the selected local report as runner evidence; hashes detect mismatch, not malicious fabrication. Missing, stale, mismatched, calibration or demo evidence yields warnings, no quality pass. Valid numeric metrics, including per-lane document counts and confidence bounds, appear under `extensions[]` with `wq-automated-*` IDs; they never replace Plugin Eval's core score. A report whose candidate is not eligible and recommended receives a warning even when its numeric diagnostic metrics remain visible.

## Public reference examples

`data/references.json` contains three small audience-guidance comparisons. Candidate A is excerpted from [GSA's archived plain-language guidance](https://github.com/GSA/plainlanguage.gov/blob/main/_pages/guidelines/audience/index.md); candidate B is a new adaptation, with distinct SHA256 hashes for both UTF-8 strings in each provenance note. The [repository license](https://github.com/GSA/plainlanguage.gov/blob/main/LICENSE.md) declares U.S. public domain and CC0 1.0 worldwide. All cases have `split=development`, `expected=null`, and `kind=published_reference`; authorship gives no winner label. The three examples cover only short government guidance sentences in the editing lane, so they cannot validate memos, literary prose, long-form cohesion, communication replies or other genres.

To add material without human grading, secure the original publisher's reuse license first. Save source URL, license identifier/URL, an exact short excerpt and its UTF-8 SHA256; write an alternate candidate with its own hash and note which text is adapted. Add a unique case/document ID, `split=development`, `expected=null`, lane/prompt/context and `checks={}`. Run the `validate --suite ... --rubric ...` command above with your expanded suite. Do not infer preference from published authorship and do not move an inspected public example into a sealed test set.
