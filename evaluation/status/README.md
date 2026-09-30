# Current evaluation status

The reviewed editing-pilot audit is integrated alongside the later communication work. The audit withdraws comparative ranking claims from the editing pilot. The benchmark-v2 diagnostic foundation resolves literal quote anchors and ingests diagnostic JSON offline; it does not evaluate diagnostic quality or establish readiness for a sealed benchmark. The new [automated writing comparison](../benchmark_v2/automated/README.md) is a separate `automated_proxy` protocol that can run without human grading; no live judge/model quality run is claimed here. Stage 2 under the archived pilot remains locked. The [2026-09-30 live evaluation record](2026-09-30-live-evaluation.md) documents three live judge calibrations that did not qualify a judge pair; no skill comparison, metric pack or rubric optimization ran, so it claims no skill quality result.

## Evidence streams

| Location | Question and limits |
|---|---|
| [`evaluation/pilot/`](../pilot/) and the audit documents | How the seven editing skills and comparison surfaces detected writing defects under the original wrapper. The corpus is now development-only; leaked identifiers, provisional gold and compound scoring prevent reliable ranking. |
| [`evals/communication/`](../../evals/communication/) | How a separate communication skill affected reply shape, preservation and model-judge preferences. Iteration 4 compared three arms; iteration 5 checked targeted v5 repairs. These small experiments do not supply human gold or validation for the editing pilot. |
| [`evaluation/benchmark_v2/`](../benchmark_v2/README.md) | New deterministic development code for anchors and response ingestion. Its accepted findings satisfy the input contract; acceptance is not a judgment that a diagnosis is correct. |
| [`evaluation/benchmark_v2/automated/`](../benchmark_v2/automated/README.md) | Separate unattended writer/judge comparison with synthetic calibration controls, public unlabeled references, and a Plugin Eval extension. Demo output is a software smoke check; quality recommendations require matching live calibrated evidence. It neither completes nor depends on the historical human-review protocol. |

## Read order and document authority

1. Read the [benchmark-validity erratum](../docs/benchmark-validity-erratum.md) before interpreting the [original provisional report](../docs/stage1-provisional-report.md). The erratum supersedes the report's interpretation; the original report remains historical evidence.
2. Read the [first Claude review](../CLAUDE_REVIEW.md), [Codex response](../CODEX_RESPONSE_TO_CLAUDE.md), and [second Claude review](../CLAUDE_REVIEW_2.md). These preserve the review sequence, including the corrected count of 84 unreachable-code predictions and the distinction between reported and observed test results.
3. Read the [reoptimization proposal](../docs/reoptimization-proposal.md) for the broader historical diagnostic design, then [v2 readiness and next steps](benchmark-v2-readiness.md) for that protocol's boundary. Read [automated comparison usage](../benchmark_v2/automated/README.md) separately; it does not inherit the earlier protocol's human prerequisites. The historical proposal's implementation status is not updated in place.
4. Read the [integration verification record](2026-09-28-integration-verification.md) for the branch consolidation and the [automated verification record](2026-09-28-automated-verification.md) for the new evaluator. These record commands, environment and preservation checks. Historical test counts describe their recorded environments; they are not new test results or remote CI results.
5. Run the [offline foundation example](../benchmark_v2/README.md#offline-example) and, if useful, the [no-key automated demo](../benchmark_v2/automated/README.md). For the separate communication evidence, begin with its [eval summary](../../skills/communication/references/eval-summary.md), [iteration-4 report](../../evals/communication/iteration-4/report.md), and [iteration-5 report](../../evals/communication/iteration-5/report.md).

The existing [evaluation README](../README.md) remains the historical audit-bundle entry point. Existing files under `evaluation/`, including the pilot, review records, source investigation and checkpoints, retain their reviewed bytes. Current navigation and development status live here.

## Local verification

Run these commands from the repository root with Python 3.11 or later. The existing portfolio validator also requires PyYAML. The new foundation and manifest verifier use the Python standard library.

```sh
python scripts/verify_manifests.py
python scripts/validate_portfolio.py
python -m unittest discover -s tests -p 'test_*.py'
```

The manifest verifier also accepts an explicit checkout root: `python scripts/verify_manifests.py /path/to/checkout` (usage: `python scripts/verify_manifests.py [ROOT]`). Verification reads files without rewriting them. The root manifest covers the current tracked tree; `evaluation/MANIFEST.sha256` remains the historical audit manifest and excludes the new development/status paths.

Run the legacy evaluator tests from `evaluation/pilot`. On POSIX shells:

```sh
cd evaluation/pilot
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

On PowerShell:

```powershell
Set-Location evaluation/pilot
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m unittest discover -s tests -v
```

Report the actual interpreter, platform, tests run, tests passed and skipped tests separately. Windows-specific skips on another platform do not count as passed tests. Local checks do not establish that remote CI executed; its outcomes require their own observed evidence.
