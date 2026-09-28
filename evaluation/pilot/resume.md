# Resume

Run: `RUN-20260825-writing-quality-eval`

## Current state

Stage 1 automated execution and objective scoring are complete. The result is `PILOT_UNADJUDICATED`: zero of 12 evaluated surfaces passed every frozen worst-run objective gate. Stage 2 is not eligible and has not been run.

The immutable provisional artifact contains exactly two files:

- `artifacts/stage1-sealed-v1/reports/stage1-provisional-report.json`
- `artifacts/stage1-sealed-v1/tree-manifest.json`

No reviewer roster, private crosswalk, human form, or review packet has been created.

The readable report, preregistered plan, full JSON report, and tree manifest have been copied to the task's `outputs` directory. Their hashes are recorded in `.checkpoints/11_delivery.json`.

## Completed

- Froze a 90-case corpus with 18 development and 72 sealed cases.
- Covered genuine defects, adversarial KEEP controls, factual traps, six genres, author types, and structured Markdown regions.
- Evaluated the seven-skill portfolio, ten authored external surfaces derived from nine sources, and one normalized union. Slopkit and Kami each contribute two distinct authored surfaces, for 12 surfaces total.
- Preserved three first responses for every surface under identical registered model settings, for 36 sealed jobs.
- Preserved all raw first outputs without repair or retry: 33 schema-valid and three invalid.
- Bound cases, provisional gold, execution order, jobs, settings, raw outputs, normalized predictions, thresholds, and the scoring amendment through detached hashes.
- Computed exact-match worst-run objective metrics for all 12 surfaces.
- Hardened the human-review architecture against incomplete panels, self-review, roster substitution, cross-packet replay, case or prediction mutation, and contradictory factual-meaning labels.
- Materialized only the provisional objective report because no verified real-human roster exists.
- Passed 198 tests on Python 3.11 and 198 tests on Python 3.14, with two Windows privilege-dependent skips on each runtime.
- Reached 84.01 percent traced production-line coverage: 5,784 of 6,885 executable lines.
- Passed independent final code and security reviews with zero findings for the Stage 1 path.

## Objective outcome

- Systems passed: 0
- Systems failed: 12
- Human review status: `PENDING_HUMAN_REVIEW`
- Stage 2 eligible: false
- Stage 2 executed: false

The highest provisional worst-run exact precision was 0.2941, below the frozen 0.80 minimum. The normalized union did not outperform the current portfolio on the registered exact-match measures. These are provisional objective diagnostics, not final human judgments or claims about authorship or overall writing quality.

## Remaining optional work

1. If the benchmark itself should be audited, identify two real reviewers and one separate real-human adjudicator.
2. Freeze their exact roster in the run-bound roster anchor.
3. Materialize blinded diagnostic and gold-review packets.
4. Collect and verify complete ratings without revealing the system crosswalk.
5. Publish human agreement, explanation validity, and factual-meaning risk only after adjudication.

Human review cannot make the current surfaces Stage 2 eligible because all 12 already failed at least one objective gate. A new diagnostic design or revised mechanisms would require a new preregistered run rather than retroactive threshold changes.

## Do not do

- Do not modify or push `work/writing-quality-portfolio`.
- Do not execute third-party repository code.
- Do not expose provisional gold or private crosswalks to generators or reviewers.
- Do not call these results human agreement, reader preference, factual preservation, or validated voice retention.
- Do not run Stage 2 against this failed Stage 1 panel.
