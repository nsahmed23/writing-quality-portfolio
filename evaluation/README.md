# Writing-quality evaluation audit bundle

This directory publishes the complete first-party investigation and Stage 1 pilot so another coding session can run the unit tests, independently recompute reported arithmetic from preserved gold and normalized outputs, challenge the evidence, and improve the design. A fresh clone cannot replay the evaluator's fully verified evidence path because frozen jobs retain original absolute artifact references, including intentionally omitted source clones. The original model calls also cannot be reproduced because exact rendered prompts, model identity, and most generation settings were not preserved.

The most important conclusion is narrower than the original provisional report: none of the twelve surfaces met every frozen exact-match gate under the shared wrapper and provisional gold. The pilot does not support a reliable ranking of the writing approaches. The case identifiers leaked the hidden decision, the exact scorer combined several distinct error types, the gold was not independently adjudicated, and most external surfaces were adapted rather than tested as native diagnostic systems.

Stage 2 remains locked. Nothing in this branch changes the seven published skills or authorizes rewriting evaluation.

## Start here

1. Read the independent [Claude review](CLAUDE_REVIEW.md), the [Codex validation response](CODEX_RESPONSE_TO_CLAUDE.md), and the [second-round Claude review](CLAUDE_REVIEW_2.md) of that integration.
2. Read [benchmark-validity-erratum.md](docs/benchmark-validity-erratum.md) before relying on the original report.
3. Review [reoptimization-proposal.md](docs/reoptimization-proposal.md).
4. Use [CLAUDE_REVIEW_HANDOFF.md](CLAUDE_REVIEW_HANDOFF.md) to reproduce the adversarial review protocol.
5. Inspect the immutable pilot evidence under [pilot/](pilot/).
6. Inspect the separate nine-source research record under [source-review/](source-review/).

## Directory map

| Path | Purpose |
|---|---|
| `CLAUDE_REVIEW.md` | Independent adversarial recount and design review supplied by Claude. |
| `CODEX_RESPONSE_TO_CLAUDE.md` | Codex reproduction record, including the correction from 80 to 84 structurally unmatchable-code predictions. |
| `CLAUDE_REVIEW_2.md` | Second-round Claude review verifying the integration, conceding the F4 correction, and flagging the platform-dependent test-count wording. |
| `docs/source-investigation.md` | Evidence-backed review of the nine requested GitHub sources. |
| `docs/evaluation-plan.md` | Original two-stage evaluation plan. |
| `docs/stage1-provisional-report.md` | Original readable Stage 1 report, preserved without retrospective edits. |
| `docs/benchmark-validity-erratum.md` | Superseding diagnosis of benchmark and interpretation defects. |
| `docs/portfolio-root-cause-analysis.md` | Focused analysis of how the seven-skill portfolio behaved under the wrapper. |
| `docs/reoptimization-proposal.md` | Benchmark-first and routed-portfolio redesign proposal. |
| `docs/human-review-gate-hardening-record.md` | Implemented pre-review hardening record, with residual limits stated explicitly. |
| `pilot/src`, `pilot/tools`, `pilot/tests` | Offline evaluator implementation and test suite. |
| `pilot/corpus`, `pilot/private/gold` | Public cases and provisional scoring labels. This pilot is now development-only evidence, not a future holdout. |
| `pilot/runs` | Jobs, raw outputs, normalized outputs, receipts, and execution manifests. |
| `pilot/artifacts` | Frozen provisional JSON report and its tree manifest. |
| `pilot/.checkpoints`, `pilot/research_run` | Durable execution state, decisions, evidence, contradictions, and unknowns. |
| `source-review` | Durable research bundle for the nine external sources, excluding repository clones. |
| `THIRD_PARTY_BOUNDARY.md` | Source, license, and redistribution boundary. |
| `MANIFEST.sha256` | Hashes for the published evaluation bundle. |

## Reproduce the evaluator tests

From `evaluation/pilot`, run:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
py -3.11 -X utf8 -m unittest discover -s tests -v
py -3.14 -X utf8 -m unittest discover -s tests -v
```

The evaluator has no third-party runtime dependency. Do not execute any of the external repositories. Their code is not included here.

## Integrity and privacy notes

The original pilot files were copied byte for byte except that cache, coverage, bytecode, and duplicate build directories were omitted. The public package contains provisional gold because the pilot can no longer function as a sealed holdout and independent review requires the labels. No authentication token, private key, or credential should be present. See `MANIFEST.sha256` and the draft pull request checks for the final verification record.

The synthetic corpus contains invented organizations, incidents, figures, dates, and personal voices, including deliberate privacy-trap language. It is not client data. Preserved jobs, manifests, plans, and research records contain absolute local paths with the Windows account name `nsahm`. These path disclosures are repeated across the historical evidence, but they are not credentials. Publishing `pilot/private/gold` permanently declassifies this pilot and it must never be reused as a blind holdout.

Some preserved resume and delivery records point to the original local task `outputs/` directory. The five delivered files are relocated to `evaluation/docs/` in this repository. The original path references remain unchanged so the historical evidence stays byte-identical.

## Status

- Original pilot: frozen and preserved.
- Comparative ranking claim: withdrawn.
- Benchmark-validity audit: complete enough to block rankings.
- Independent Claude review: completed and preserved; its central verdict is confirmed, with one quantitative correction recorded in the Codex response.
- Second-round Claude review of the integration: completed; every substantive benchmark recount reproduced independently and the F4 correction is conceded. A test-metadata correction (run environment and passed-versus-ran accounting) is recorded separately in the review's revision note and checkpoint 05.
- Reoptimization: revised after adversarial review, not implemented.
- Human adjudication: not performed.
- Stage 2: not eligible and not run.
