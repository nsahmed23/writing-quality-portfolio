# Automated writing comparison (development protocol)

This package implements `automated_proxy`, a separate workflow from the archived editing-pilot human-review protocol. No human grade is required: missing evidence, failed judge calibration, unstable judgments, and close comparisons end in an automatic **inconclusive** result. Software demos verify plumbing only; they cannot approve a candidate. The public controls and references are development material, not a blind holdout or a measure of expert writing quality.

The approach adapts [Meta's Unslopping AI](https://facebookresearch.github.io/RAM/blogs/unslop/) lesson about compact, task-aware rubrics and evaluator calibration. It does not reproduce RL-XAR or train model weights. The six rubric criteria cover purpose, meaning, useful detail, economy, cohesion and voice; no word blacklist defines quality.

Run from the repository root with Python 3.11 or later. The demo needs no API key and makes no model call:

```sh
python -m evaluation.benchmark_v2.automated validate --suite evaluation/benchmark_v2/automated/data/controls.json --rubric evaluation/benchmark_v2/automated/data/rubric.json
python -m evaluation.benchmark_v2.automated validate --suite evaluation/benchmark_v2/automated/data/references.json --rubric evaluation/benchmark_v2/automated/data/rubric.json
python -m evaluation.benchmark_v2.automated demo --out .eval-runs/demo-1
python -m unittest discover -s tests -p 'test_automated_*.py'
```

Use a **new** output directory for each invocation; runs refuse to overwrite old evidence. The demo creates `.eval-runs/` on first use. Its `complete: false` and `eligible: false` are expected: it saves `synthetic-response-valid.bin` and `synthetic-response-invalid.bin` to demonstrate a functioning synthetic path and a rejected judgment. This is a successful software demo, not a broken installation or a live quality verdict.

Suite validation rejects identical normalized prompt, context and candidate pairs assigned to different document IDs, even within one split; repetitions under the same document ID remain valid. This prevents copied cases from inflating independent calibration or comparison document counts.

## Live adapter configuration

Copy `adapters/example-config.json` to `adapters/local-config.json` in the same directory (Git ignores that path, so local executable paths stay out of commits) and edit the command arrays for your installed, trusted local adapters. The example contains **one** Codex judge family, which is insufficient for an eligible live comparison: add a genuinely distinct second judge family. Each judge has a distinct `id` and a `family`; a complete live comparison needs at least two independent judge families. The config declares `schema_version: 1`, `judges: [{id, family, command: [executable, argv...] }]`, optional `writer` and `optimizer` with the same shape, `timeout_seconds` (default 120, up to 600), and `max_calls` (default 200). A configured command receives one JSON request on stdin and normally writes one raw UTF-8 JSON response to stdout. Commands execute as argv with `shell=False`; treat them as trusted software, not an OS sandbox. Config-relative executable/script paths resolve from the config directory. The included Codex CLI adapter is one available command; for another model CLI that accepts a prompt on stdin and emits raw JSON on stdout, the generic bridge accepts `python generic_json_adapter.py -- MODEL_CLI ARG...` in the command array. Supply credentials through the normal environment, not in config files. The runner preserves request, first response, stderr, exit status, elapsed time and hashes. Judge requests exclude candidate identity, private expected labels and suite files, but provider retention policies still apply.

The runner sets `WQ_EVAL_FINAL_RESPONSE_FILE` to an absolute, unique per-call path for trusted adapters that obtain a provider's final message through a file. The Codex adapter passes this path to `--output-last-message`; the runner reads the file after the subprocess ends, including after a nonzero exit or process-tree timeout. When that file exists, its bytes become `response.bin` and determine `response_sha256`. The adapter's captured stdout remains in `adapter-stdout.bin` with `adapter_stdout_sha256`; provider progress and diagnostics remain in `stderr.bin`. Adapters that do not write the sidecar keep the normal stdout response contract. All failed calls remain invalid and are never retried.

Pin an available model explicitly in each adapter command (the Codex wrapper accepts `--model MODEL_ID`) and record your CLI versions with the run. The calibration signature hashes declared judge IDs, families and command arguments; it cannot detect a provider changing its default model behind unchanged arguments. Recalibrate after changing model or adapter settings. The generic bridge turns the JSON request into a role-specific prompt for a CLI that accepts a prompt on stdin and returns raw JSON on stdout; its command flags depend on the CLI you install.

The judge returns `{"winner":"A|B|tie|both_bad","reason":"...","evidence":[{"candidate":"A|B","quote":"literal excerpt"}]}`. Decisive and both-bad judgments must quote both candidates; a tie may cite one. The writer receives the selected `SKILL.md` text as `instructions` and returns `{"text":"nonblank response"}`. Comparing a skill with external reference files evaluates only the supplied instruction snapshot, not the entire routed portfolio. A skill directory resolves to its `SKILL.md`.

After configuring adapters, run calibration before comparison. These are command templates; no live run is claimed here:

```sh
python -m evaluation.benchmark_v2.automated calibrate --suite evaluation/benchmark_v2/automated/data/controls.json --rubric evaluation/benchmark_v2/automated/data/rubric.json --config evaluation/benchmark_v2/automated/adapters/local-config.json --out .eval-runs/calibration-1
python -m evaluation.benchmark_v2.automated compare --suite evaluation/benchmark_v2/automated/data/controls.json --rubric evaluation/benchmark_v2/automated/data/rubric.json --config evaluation/benchmark_v2/automated/adapters/local-config.json --calibration .eval-runs/calibration-1 --candidate-skill skills/concision --repetitions 1 --out .eval-runs/comparison-1
python -m evaluation.benchmark_v2.automated prepare-optimize --suite evaluation/benchmark_v2/automated/data/controls.json --out .eval-runs/optimize-suite-1.json
python -m evaluation.benchmark_v2.automated optimize --suite .eval-runs/optimize-suite-1.json --rubric evaluation/benchmark_v2/automated/data/rubric.json --config evaluation/benchmark_v2/automated/adapters/local-config.json --rounds 2 --out .eval-runs/optimization-1
```

Calibration requires at least eight labeled controls across four documents, two presentation orders per judge, complete valid coverage, and engineering-default thresholds of 0.90 for stable correctness and order stability. A comparison requires a matching eligible **live** calibration for the same rubric and judge signature. It samples independent documents, treats abstentions and disagreements as zero preference, and recommends a candidate only if every evaluated lane clears its lower confidence bound and deterministic checks. Otherwise it can recommend retaining the baseline or report inconclusive. The controls are public synthetic checks, so even a passing proxy does not establish an expert or held-out quality result. `prepare-optimize` writes a new, validated calibration/development-only subset from a mixed starter suite without human filtering or labels; it refuses to overwrite a file. Optimize uses only that subset and stops after at most three proposed rounds; it never edits a skill or admits test examples.

## Plugin Eval extension or direct JSON

The optional local-only metric pack reads an **existing** report; `analyze` never starts model work. Install Plugin Eval's CLI so `plugin-eval` is on `PATH` (the installed package declares that binary at `scripts/plugin-eval.js`). If your installation does not expose a command, replace `plugin-eval` below with `node PATH_TO_PLUGIN_EVAL/scripts/plugin-eval.js`, using your own installed package path. The manifest calls `python`; if your Python 3.11+ executable has another name, update only that command's executable. Choose the exact report file emitted in the comparison output directory and analyze the same skill snapshot. `WQ_EVAL_REPORT` must be absolute because Plugin Eval starts the adapter from the manifest directory. From the repository root, on POSIX:

```sh
WQ_EVAL_REPORT="$(pwd)/.eval-runs/comparison-1/report.json" plugin-eval analyze skills/concision --format json --metric-pack evaluation/benchmark_v2/automated/plugin_eval/manifest.json
WQ_EVAL_REPORT="$(pwd)/.eval-runs/comparison-1/report.json" python evaluation/benchmark_v2/automated/metric_pack.py skills/concision skill
```

In PowerShell:

```powershell
$env:WQ_EVAL_REPORT = (Resolve-Path '.eval-runs/comparison-1/report.json').Path
plugin-eval analyze skills/concision --format json --metric-pack evaluation/benchmark_v2/automated/plugin_eval/manifest.json
python evaluation/benchmark_v2/automated/metric_pack.py skills/concision skill
```

The direct Python command prints only the extension JSON and does not require Plugin Eval. The manifest supports `skill` and `plugin`; plugin roots with more than one skill are ambiguous and yield a warning, so analyze a specific skill in this portfolio. The extension verifies the report schema, suite/rubric/config/judge provenance digests, and the candidate skill hash against raw `SKILL.md` bytes. It trusts the selected local report as runner evidence; hashes detect mismatch, not malicious fabrication. Missing, stale, mismatched, calibration or demo evidence yields warnings, no quality pass. Valid numeric metrics, including per-lane document counts and confidence bounds, appear under `extensions[]` with `wq-automated-*` IDs; they never replace Plugin Eval's core score. Baseline check failures remain visible warnings even when an eligible live report recommends the candidate; candidate/coverage/calibration failures prevent the extension's quality pass.

## Public reference examples

`data/references.json` contains three small audience-guidance comparisons. Candidate A is excerpted from [GSA's archived plain-language guidance](https://github.com/GSA/plainlanguage.gov/blob/main/_pages/guidelines/audience/index.md); candidate B is a new adaptation, with distinct SHA256 hashes for both UTF-8 strings in each provenance note. The [repository license](https://github.com/GSA/plainlanguage.gov/blob/main/LICENSE.md) declares U.S. public domain and CC0 1.0 worldwide. All cases have `split=development`, `expected=null`, and `kind=published_reference`; authorship gives no winner label. The three examples cover only short government guidance sentences in the editing lane, so they cannot validate memos, literary prose, long-form cohesion, communication replies or other genres.

To add material without human grading, secure the original publisher's reuse license first. Save source URL, license identifier/URL, an exact short excerpt and its UTF-8 SHA256; write an alternate candidate with its own hash and note which text is adapted. Add a unique case/document ID, `split=development`, `expected=null`, lane/prompt/context and `checks={}`. Run the `validate --suite ... --rubric ...` command above with your expanded suite. Do not infer preference from published authorship and do not move an inspected public example into a sealed test set.
