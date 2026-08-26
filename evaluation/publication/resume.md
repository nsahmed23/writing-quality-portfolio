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

## In progress

- Freeze and security-scan the exact final tree.
- Obtain the final independent code-review verdict.
- Commit, push, open the draft pull request, and verify the remote publication.

## Hard boundaries

- Do not alter the preserved pilot evidence.
- Do not copy or execute third-party repositories.
- Do not claim that the pilot ranks the systems.
- Do not unlock or run Stage 2.
- Do not display authentication tokens.
