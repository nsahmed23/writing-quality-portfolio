# Claude Code review handoff

## Review objective

Independently audit the writing-quality source investigation, Stage 1 evaluator, preserved pilot evidence, corrected diagnosis, and proposed redesign. Try to falsify the corrected diagnosis. Do not assume that either the original provisional report or the later erratum is right.

## Baseline

- Repository: `nsahmed23/writing-quality-portfolio`
- Portfolio baseline: `74a282108da2a620542556fa001ebcdde0c9be85`
- Publication branch: `codex/evaluation-audit-bundle`
- Pilot run: `RUN-20260825-writing-quality-eval`
- Original result: 0 of 12 surfaces passed every frozen worst-run exact gate.
- Corrected interpretation: the reported arithmetic can be independently recomputed from preserved gold and normalized outputs, but benchmark defects prevent comparative ranking or broad claims about diagnostic quality.
- Stage 2: not run.

## Portability boundary

A fresh clone can run the unit tests and independent recount scripts or calculations. It cannot replay the evaluator's fully verified frozen-evidence path because the preserved jobs require original absolute artifact references, including references to source clones intentionally excluded from this branch. It also cannot reproduce the original model calls because exact rendered prompts, model identity, and most generation settings were not preserved. Treat those limits as evidence gaps, not setup problems to repair by editing the frozen pilot.

## Required review sequence

1. Read `evaluation/docs/benchmark-validity-erratum.md` and check every material claim against `evaluation/pilot`.
2. Reproduce the case-ID leakage calculation without using model outputs.
3. Recompute exact, same-code overlap, and any-code overlap counts from the 33 valid normalized runs.
4. Check whether protected regions were hidden from generators while retained in provisional gold.
5. Audit the public taxonomy, private native map, and one-label exact scorer for semantic collisions.
6. Check the three invalid runs and determine how many valid records were discarded.
7. Verify the F1, F2, and native-evaluation classifications in `evaluation/pilot/systems/systems.json`.
8. Audit the portfolio-specific causal analysis and the proposed routed architecture.
9. Run both supported Python test suites.
10. Inspect the Git diff for secrets, copied third-party expressive content, unsafe external-input handling, and misleading claims.

## Questions that need an explicit answer

- Does the public case identifier predict CHANGE or KEEP for all 90 cases and all 72 sealed cases?
- Is the phrase “none of the twelve surfaces met every frozen exact-match gate under the shared wrapper and provisional gold” fully supported?
- Which original claims remain valid, which need qualification, and which must be withdrawn?
- Are the overlap recounts correct, and what do they establish without overclaiming?
- Are any provisional gold labels or span boundaries clearly wrong, ambiguous, or incomplete?
- Did the shared taxonomy materially change what “as authored” means?
- Does the reoptimization proposal fix leakage, batching, boundary, taxonomy, provenance, and partial-ingestion failures?
- What smaller design would achieve the same validity with less complexity?
- Is any first-party evidence missing from this branch?
- Is any third-party material included beyond a defensible research or citation boundary?

## Evidence discipline

Separate each conclusion into one of these categories:

- **Observed:** directly supported by repository files or a reproduced calculation.
- **Inferred:** the best explanation, but not directly established.
- **Unknown:** evidence is missing or contradictory.

Do not let the evaluator grade itself. Do not treat model agreement as human agreement. Do not execute third-party repositories. Do not modify the original pilot evidence when reporting a defect.

## How to return feedback

The preferred return path is a pull-request review with line comments plus a concise summary. If review comments are unavailable, create a separate feedback branch, add `evaluation/CLAUDE_REVIEW.md` there, and open a pull request back to `codex/evaluation-audit-bundle`. Do not commit feedback directly to the publication branch. Any later integration of that file must regenerate and reverify both `evaluation/MANIFEST.sha256` and the repository-root `MANIFEST.sha256`.

The review document should contain:

1. verdict and scope;
2. blocking findings ordered by severity;
3. reproduced calculations and commands;
4. counterevidence;
5. recommended changes;
6. tests run and exact results;
7. unresolved questions.

This is an asynchronous handoff, not a direct live conversation between agents. After the review is posted, ask the user to tell the original Codex task to read the pull-request comments or `evaluation/CLAUDE_REVIEW.md`. Codex can then respond in the pull request or prepare a follow-up commit.

## Suggested Claude Code prompt

```text
Review the branch codex/evaluation-audit-bundle in nsahmed23/writing-quality-portfolio as an adversarial benchmark and code audit. Start at evaluation/CLAUDE_REVIEW_HANDOFF.md. Reproduce material calculations from repository evidence, distinguish observation from inference, and try to disprove both the original report and the erratum. Do not execute third-party repositories and do not modify frozen pilot evidence. Run the local evaluator tests. Return findings as a GitHub pull-request review. If review comments are unavailable, create a separate feedback branch containing evaluation/CLAUDE_REVIEW.md and open a pull request back to codex/evaluation-audit-bundle. Do not commit directly to the publication branch.
```
