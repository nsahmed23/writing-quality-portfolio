# Automated Writing Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement and independently review each task. User requested execution of the in-chat design.

**Goal:** Deliver a runnable, unattended calibration and comparison workflow with a Plugin Eval metric pack, based on the existing repository.

**Architecture:** New standard-library package under benchmark_v2, preserving the historical pilot. Separate deterministic scoring, subprocess orchestration, and report integration; explicit contracts in the spec coordinate parallel work.

**Tech Stack:** Python >=3.11 standard library; existing Node-based Plugin Eval for optional reports.

**Spec:** docs/superpowers/specs/2026-09-28-automated-writing-evals-design.md

## Global Constraints

- No new human grading, invented expert labels, paid/model calls during development without an available configured adapter, or claims of scientific validation from demos.
- Preserve all baseline tracked bytes except root README/MANIFEST, .gitignore, CI, and evaluation/status/; append only under benchmark_v2 and docs.
- Exact interfaces, schemas, thresholds and artifact semantics are defined in the spec and bind every task.
- Workers use separate branches/worktrees; each commits only owned files, reports tests and waits for controller review. No worker subagents.
- New core/runtime code uses Python >=3.11 and only standard library.

## Review Focus

- Reversed-order judgments, duplicates, missing outputs and evidence hallucination must never become a win (Task1).
- Document overlap, copied examples under new IDs and correlated repetitions must not inflate evidence (Task1).
- Timeouts, partial response bytes, exhausted call budgets and existing output directories must preserve evidence (Task2).
- Held-out labels and skill identities must not reach judges; optimized rubrics must not inspect test cases (Task2).
- Plugin Eval must reject stale/mismatched reports and display demo results without a quality pass (Task3).

### Task 1: Calibration and scoring engine

**Files:** Create evaluation/benchmark_v2/automated/{__init__.py,contracts.py,scoring.py}, data/{controls.json,rubric.json}, tests/test_automated_scoring.py.

**Interfaces:** Implement the exact contracts.py/scoring.py functions and report keys from the spec. Task2 consumes these; Task3 consumes reports. Publish a tiny valid report example in the task report, not the source tree.

- [x] Write failing tests for schema validation, hidden answer leakage through split aliases, literal evidence, order reversal, incomplete/duplicate results, min controls, demo ineligibility, per-document intervals and candidate correctness gates.
- [x] Run focused tests and record expected failures before implementation.
- [x] Implement contracts, scoring and honest synthetic controls with distinct document groups. Keep load/parse and aggregation responsibilities separate.
- [x] Run focused tests, then all root tests once; record counts and commit only owned files.

### Task 2: Unattended runner and bounded rubric refinement

**Files:** Create evaluation/benchmark_v2/automated/{__main__.py,runner.py,adapters.py,optimize.py}, adapters/{codex_adapter.py,generic_json_adapter.py,example-config.json}, tests/test_automated_runner.py.

**Interfaces:** Consume Task1's exact interfaces. Implement CLI/data contracts from spec. Provide a working codex CLI adapter that accepts JSON on stdin and extracts final JSON via a temporary output file; no shell or generated command execution. A small generic stdin/stdout CLI bridge lets other model CLIs use the documented JSON command contract; do not invent provider APIs. Demo works without external commands.

- [x] Write failing integration tests with a tiny local subprocess adapter for timeout/nonzero/malformed response handling, stdout/stderr/partial evidence retention, identity/label exclusion, budget-before-calls, existing-output refusal, skill snapshot hashes, calibration signatures and optimizer test-split exclusion.
- [x] Implement shell-free subprocess execution and artifact persistence; implement validate/demo/calibrate/compare/optimize with bounded calls and visible failures.
- [x] Ensure demo exercises incomplete judgments and always stays demo/ineligible. Build a usable CLI adapter and JSON example with clear executable configuration and explicit judge families.
- [x] Run focused tests and all root tests after Task1 is integrated into this worktree; commit only owned files with report.

### Task 3: Plugin Eval adapter, reference examples and user documentation

**Files:** Create evaluation/benchmark_v2/automated/{README.md,metric_pack.py}, plugin_eval/manifest.json, data/references.json, tests/test_automated_metric_pack.py. Modify root README.md and evaluation/status/{README.md,benchmark-v2-readiness.md}; add current automated protocol status document if useful.

**Interfaces:** Consume common report contract and runner provenance: runner report must include `provenance` with `candidate_skill_sha256` (null for calibration/demo), `suite_sha256`, `rubric_sha256`, `config_sha256`, and `judge_signature` (sha256 over canonical list of judge id/family/command). Task2 must expose these exact keys. Metric pack compares candidate hash with target SKILL.md raw bytes; reports must be compare/live for any quality pass. Calibration/demo are informative only.

- [x] Inspect installed Plugin Eval metric-pack contract; create failing tests for missing report, invalid schema, stale skill hash, correct extension output and demo warning behavior.
- [x] Implement local-only metric adapter and manifest. Never initiate model work from analyze.
- [x] Retrieve a few explicitly reusable primary-source writing examples; record exact provenance and no winner labels. Keep them development-only and document limited genre coverage. Use primary license evidence. If retrieval is blocked, deliver schema/import recipe and report concern; no invented corpus.
- [x] Document exact runnable commands and no-human outcomes. Current status explicitly distinguishes automated proxy results from preserved historical protocol. No claim of observed live runs.
- [x] Run tests with temporary reports and commit owned changes with citations/source provenance in report.

### Task 4: Integration, independent review and delivery (controller)

**Files:** Update .gitignore, CI, root MANIFEST.sha256; add actual verification note and delivery instructions.

- [x] Integrate each reviewed worker commit, resolve interfaces, and run installed Plugin Eval against a real demo report.
- [x] Independently review whole branch; fix important findings with regression tests.
- [x] Run root tests, legacy tests, portfolio validator, offline demo and both manifests. Compare historical/skill bytes against baseline.
- [x] Package source and full branch history; verify fresh clone and archive contents; save and return updated repo ZIP.
