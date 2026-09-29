# Publication resume

## Objective

Publish the complete first-party writing-quality audit bundle on `codex/evaluation-audit-bundle` and open a draft pull request for independent Claude Code review.

## Completed

- Verified public repository ownership, push permission, default branch, clean baseline, and remote `main` SHA.
- Created the review branch from `74a282108da2a620542556fa001ebcdde0c9be85`.
- Copied the evaluator, corpus, provisional gold, raw and normalized outputs, tests, checkpoints, research registers, and delivered reports.
- Excluded third-party repository clones, build output, coverage databases, caches, bytecode, and empty working directories.
- Added the benchmark-validity erratum, portfolio root-cause analysis, reoptimization proposal, implemented human-gate hardening record, source boundary, and Claude handoff.
- Verified the 419-file pilot copy byte for byte, with no missing, unexpected, or mismatched files.
- Ran 198 tests on Python 3.11 and Python 3.14, with zero failures and two expected skips on each runtime.
- Passed the portfolio validator, secret and private-data scans, and third-party boundary review.
- Completed a broad security scan with zero findings. Its snapshot warning is preserved in `checkpoints/02-local-verification.json`; the exact final tree still requires a fresh scan.
- Generated and independently verified both integrity manifests, with portable paths, exact file-set equality, and zero hash mismatches.
- Received and preserved the independent Claude adversarial review of commit `5d1f2b4cf83c54b5b70e5d10f16a85cbc07b9ba4`.
- Independently confirmed the F1, F2, and F3 recounts, including the exact malformed finding IDs and both portfolio-localization definitions.
- Corrected F4 from 80 to 84 predictions using structurally unmatchable public codes. Of those 84, 64 overlap any gold CHANGE region and 19 use exact gold boundaries, so a universal paired-FN claim is not supported.
- Confirmed all 36 sealed `raw/` and `inbox/` file pairs are byte-identical.
- Revised the reoptimization proposal to add reviewer reliability, scored routing, minimum-opportunity, KEEP-lane, and lean Stage 1 core requirements.
- Reran the portfolio validator successfully and ran all 198 evaluator tests on Python 3.11 and Python 3.14, with zero failures and two expected skips on each runtime.
- Reverified 419 pilot files and 35 source-review files byte for byte, with zero differences from the reviewed commit.
- Passed final JSON, JSONL, local-link, repository-hygiene, secret, whitespace, and new-writing punctuation checks with zero actionable findings.
- Regenerated both integrity manifests using ordinal path ordering and independently verified exact file-set equality and every listed SHA-256 digest.

## In progress

- Obtain the final independent code-review verdict on the frozen feedback tree.
- Commit and push `codex/claude-review-feedback`, open a draft pull request into `codex/evaluation-audit-bundle`, and verify the remote publication.

## Hard boundaries

- Do not alter the preserved pilot evidence.
- Do not copy or execute third-party repositories.
- Do not claim that the pilot ranks the systems.
- Do not unlock or run Stage 2.
- Do not display authentication tokens.
