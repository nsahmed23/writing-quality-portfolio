# Research plan

- **Run ID:** RUN-20260825-writing-quality-eval
- **Plan status:** approved
- **Profile:** Audit
- **Planning policy:** User-approved execution plan
- **Plan adopted at:** 2026-08-26T02:19:51Z

## Research questions

1. Which systems identify exact, contextual writing problems with acceptable precision and recall?
2. Which systems preserve functional passives, em dashes, triads, terminology, repetition, fragments, author quirks, second-language voice, and protected Markdown?
3. Which suggested operations risk changing actors, quantities, dates, attribution, modality, negation, conditions, or causal status?
4. Which diagnostically eligible mechanisms improve the named problem while preserving facts, voice, and protected regions?

## Workstreams

Use `workstreams.csv` for the canonical rows.

## Required source classes

Pinned first-party repository instructions, code, fixtures, and the current portfolio contracts. Independently authored evaluation cases are the test material.

## Multimodal or quantitative analysis

Strict JSONL records; exact and overlap span matching; micro, macro, slice, stability, agreement, and preservation calculations. No multimodal evidence is required.

## Proposed workers

Planner, TDD guide, architect, test worker, corpus workers with disjoint source ownership, generator workers blind to gold, code reviewer, security reviewer, adversarial reviewer, and citation auditor.

## Verification layers

TDD known-answer tests, line coverage, immutable hashes, schema validation, corpus quota validation, independent code review, security review, adversarial review, citation audit, and human review packets.

## Checkpoints

See project `.checkpoints/00_scope.json` through `11_delivery.json` and the root `resume.md`.

## Evidence-convergence stopping conditions

Stop objective execution when all frozen jobs are ingested or honestly marked unavailable, metrics reproduce from hashes, and independent audits find no unresolved high-severity issue. Stop human-dependent conclusions at `PILOT_UNADJUDICATED` until real ratings arrive.

## Plan deviations

None at initialization. The 90-case confirmatory corpus was selected over a 36-case pilot to satisfy balanced source and slice coverage.
