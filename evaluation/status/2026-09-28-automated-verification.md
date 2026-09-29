# Automated evaluation verification — 2026-09-28

This update builds on the existing GitHub repository's published consolidation commit `4f00130d2e93ba4b6f8b44d11b0fbb6f40673b9a`. Its branch is `codex/automated-writing-evals`. The new protocol is an unattended **automated proxy**; human grading is not required. It does not claim to reproduce RL-XAR, validate expert writing quality, or satisfy the historical pilot's human-review protocol.

## Observed local checks

Environment: Linux, Python 3.12.14, Node 24.19.0. Commands below ran from the repository root unless stated otherwise.

| Check | Observed result |
|---|---|
| `python -m unittest discover -s tests -p 'test_*.py' -q` | 83 tests passed in 43.976 seconds at code commit `2a4948c`, including the existing 28 tests and 55 automated-evaluator tests. |
| Legacy suite, from `evaluation/pilot`: `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests` | 198 tests ran: 187 passed and 11 Windows-specific tests skipped. Historical code was unchanged throughout this update. |
| `python scripts/validate_portfolio.py` | Passed: 252 principles, seven editing skills, 84 skill fixtures, 44 portfolio fixtures, and the separate communication skill with eight evals. |
| `python -m evaluation.benchmark_v2.automated validate --suite evaluation/benchmark_v2/automated/data/controls.json --rubric evaluation/benchmark_v2/automated/data/rubric.json` | 18 cases and six criteria validated. |
| Same validation command with `data/references.json` | Three development-only, unlabeled reference cases validated. |
| `python -m evaluation.benchmark_v2.automated prepare-optimize --suite evaluation/benchmark_v2/automated/data/controls.json --out .eval-runs/optimize-suite-1.json` | Eight calibration cases written; test cases excluded without manual filtering. |
| `python -m evaluation.benchmark_v2.automated demo --out .eval-runs/final-demo` | Exited successfully. Synthetic valid and invalid judgment bytes preserved. `execution=demo`, `complete=false`, `eligible=false`, `recommendation=not_applicable`; the deliberately invalid quote was rejected. |
| Installed Plugin Eval `scripts/plugin-eval.js analyze skills/concision --format json --metric-pack evaluation/benchmark_v2/automated/plugin_eval/manifest.json`, with absolute `WQ_EVAL_REPORT` pointing at the actual demo | Exited successfully. The extension emitted an informative-only warning, no metrics and no quality pass. Plugin Eval's core score stayed separate. |
| Baseline preservation against `4f00130` | All 2,176 pre-existing files outside the explicitly editable README, root manifest, ignore/CI files and current-status directory match their baseline Git blob bytes. No missing files or unexpected changes. This includes skill instructions, historical pilot evidence and communication experiments. |

The runner tests use real local subprocess fixtures to check exit failures, malformed JSON, partial output, process-tree timeout cleanup, raw-byte hashes, budget preflight and refusal to overwrite evidence. Fake Codex and generic-CLI executables verify wrapper arguments, prompts and response-file extraction. They do not test a live model service.

Each of the three implementation tasks received an independent code/spec review and scoped review of fixes. Review records are included in the delivery archive. The [final integration review record](2026-09-28-automated-final-review.md) records two evidence-integrity fixes and their approved scoped rereview.

## Limits and first live run

No authenticated `codex`, `claude`, `gemini` or `agy` executable was available here. No live judge calibration, cross-provider writing comparison or paid model call was performed. Actual Codex structured-output acceptance and Windows process behavior remain unverified in this environment. The CI matrix includes Ubuntu and Windows, but no remote CI result is claimed.

To run unattended evaluation, configure trusted, authenticated adapters as described in [the automated README](../benchmark_v2/automated/README.md). The example has one judge family; comparison eligibility requires at least two genuinely distinct families. Pin model identifiers and recalibrate when settings change. Model and CLI defaults are not immutable provenance.

Starter controls are public synthetic engineering checks. The three licensed reference examples are unlabeled development material covering a narrow genre. Rubric refinement is bounded and excludes test cases; it does not edit or deploy skill instructions. Close, unstable, incomplete or uncalibrated comparisons resolve automatically without creating a human-review queue.

## Final integration

The final whole-branch review identified exact copied cases under different document IDs and loss of Codex final-message files on failed/timed-out calls. Both were reproduced, fixed, and independently rereviewed. Exact normalized pair aliases now retain one document identity; the runner recovers provider response files after termination while preserving stdout separately. The final root suite above ran after these fixes. No Critical, Important or Minor finding remains open in the final review scope.

`python scripts/verify_manifests.py --write-root` refreshes only the root manifest after documentation changes. `python scripts/verify_manifests.py` verifies both manifests against the tracked file set; the historical evaluation manifest remains unchanged. The delivered bundle and ZIP are checked separately by restoring the branch into a fresh clone, verifying both manifests, running the no-key demo, and comparing every archived source file with the restored Git tree.

Archive checks passed: the complete Git bundle restored into a fresh checkout; both manifests and the offline demo passed; all 2,209 archived source files matched restored Git bytes. All four original branch tips remain ancestors of the updated branch. The delivery contains source, the Git bundle, startup/publishing instructions and independent review records.
