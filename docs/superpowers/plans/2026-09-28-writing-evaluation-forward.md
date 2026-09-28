# Writing Evaluation Forward Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the reviewed evaluation audit with current main and deliver verified integrity tooling and an offline quote-ingestion foundation.

**Architecture:** Preserve the audit and communication evidence as separate histories. Add new verification and development code in isolated paths; integrate the final review tip with a merge commit. Ship a draft PR with evidence and a specific next human gate.

**Tech Stack:** Git, Python 3.11+ standard library, existing PyYAML portfolio dependency, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-28-writing-evaluation-forward-design.md`

## Global Constraints

- Preserve all existing `evaluation/` files byte-for-byte from `ac6d52e1c57c71d43070884bb56335ee3176888f`.
- Preserve `skills/`, `evals/communication/`, existing `tests/` files, and `scripts/validate_portfolio.py` byte-for-byte from `28454c197246e6147da952b72d044273f6bb192f`.
- Stage 2 remains locked; no rankings, human adjudication, or sealed-run readiness claims.
- New benchmark code uses Python 3.11+ standard library only and makes no network requests.
- The root manifest covers every tracked file except itself; the nested evaluation manifest stays unchanged and excludes explicitly named new development subtrees.
- Each agent owns only its assigned paths. The controller regenerates the final root manifest after integration.

## Review Focus

1. CRLF bytes must be verified exactly across checkout platforms; test mismatch detection and preserve existing CSV bytes.
2. Malformed or duplicate manifest paths must fail clearly; test duplicate, traversal, absolute, missing, and uncovered tracked paths.
3. Repeated Unicode quotes must never select a guessed span; test ambiguous, overlapping, context-selected, and occurrence-selected anchors.
4. A malformed finding must not erase siblings or become a scored result; test partial ingestion and development-only output.
5. Existing audit conclusions and later communication experiments must retain their distinct scopes; inspect status/docs and historical preservation.

## Task 1: Integration and independent recount

**Files:** root `README.md`, root `MANIFEST.sha256`, new `evaluation/status/2026-09-28-integration-verification.md`.
**Consumes:** four source commit anchors above.
**Produces:** merged baseline, recount report, preservation verification.

- [ ] Merge the final review tip into current main on `codex/consolidate-writing-evaluation`; resolve only the generated manifest conflict.
- [ ] Independently recount leak, score decomposition, unreachable labels, and raw/inbox equality without importing the scorer.
- [ ] Verify unchanged trees with `git diff` against pinned sources.
- [ ] Record commands, observed Linux test environment/results, and limits in the new status report.

## Task 2: Integrity tooling and CI

**Files:** create `scripts/verify_manifests.py`, `tests/test_verify_manifests.py`, `.gitattributes`, `.github/workflows/validate.yml`, `requirements-validation.txt`.
**Consumes:** root/nested historical manifests and tracked file set.
**Produces:** CLI `python scripts/verify_manifests.py [ROOT]` and explicit `--write-root`; CI verification on Python 3.11 and 3.14, Linux and Windows.

- [ ] Write failing tests for exact coverage, GNU formats, CRLF bytes, duplicate/malformed/unsafe paths, missing files, hash mismatch, and explicit new-subtree exclusions.
- [ ] Run `python -m unittest discover -s tests -p 'test_verify_manifests.py'` and record the failing behavior.
- [ ] Implement the smallest verifier and root-regeneration command; document evaluation exclusions in code/CLI help.
- [ ] Add checkout byte policy and minimal-permission CI using verified action revisions and pinned PyYAML.
- [ ] Run focused tests and portfolio validation. Root manifest regeneration is deferred to the controller after cherry-picks.
- [ ] Commit assigned files and report commands/results/limits for task review.

## Task 3: Development quote anchors and local rejection

**Files:** create `evaluation/benchmark_v2/__init__.py`, `anchors.py`, `ingest.py`, and `tests/test_benchmark_v2.py`.
**Consumes:** exact interfaces and behavioral rules in the spec.
**Produces:** `resolve_anchor`, `AnchorError`, and `ingest_response`; no scorer, router, model adapter, or unlock.

- [ ] Write failing behavioral tests covering every quote and ingestion rule from the spec.
- [ ] Run `python -m unittest discover -s tests -p 'test_benchmark_v2.py'` to demonstrate the missing behavior.
- [ ] Implement the two focused modules with stable rejection codes and deterministic output.
- [ ] Run focused tests and inspect that the frozen pilot has no diff.
- [ ] Commit assigned files and report commands/results/limits for task review.

## Task 4: Current navigation and human-gate handoff

**Files:** update root `README.md`; create `evaluation/status/README.md`, `evaluation/status/benchmark-v2-readiness.md`, `evaluation/benchmark_v2/README.md`.
**Consumes:** the integration decision, independent recount, and implemented module interfaces.
**Produces:** a clear starting point, runnable offline example, and pending human-input checklist.

- [ ] Explain the two evaluation directories and the authority of each source document.
- [ ] Document the exact implemented foundation and remaining work, with all human inputs pending unless actual evidence exists.
- [ ] Include an offline example using the module's actual response contract and show how to run every local validation command.
- [ ] Check local links and the example after Task 3 is integrated.
- [ ] Commit assigned files and report review evidence.

## Task 5: Review, final verification, and delivery

**Files:** root manifest, final verification report, this plan's checklist.
**Consumes:** task reports and diff packages; final whole-branch review.
**Produces:** verified commit and draft PR to main.

- [ ] Review each implementation task for spec compliance and quality; fix important findings with scoped re-review.
- [ ] Stage final tracked files, regenerate only the root manifest, and verify both scopes.
- [ ] Run portfolio validation, all new tests, and the frozen evaluator suite; report exact pass/skip counts.
- [ ] Independently review the whole change including preservation and readiness language.
- [ ] Push the new branch and create a draft PR; record remote CI outcomes only when observed.

## Self-review

Tasks 2 and 3 are independent. Task 4 consumes Task 3's fixed interfaces and is checked against the implementation before integration. Task 5 owns final manifest regeneration and consolidated verification. Task 1 changes no historical evaluation content; new verification records are outside the frozen nested manifest. No task depends on human gold or permission to run model experiments.
