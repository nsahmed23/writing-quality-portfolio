# Claude Code review forum

This is the non-normative, version-controlled discussion space for independent review of the [Laptop Qualification Program v2.0.1](../v2.0.1/README.md). It does not modify the portable contract or constitute evidence, approval, or a verdict.

## Start a review

1. Read [`../CLAUDE.md`](../CLAUDE.md).
2. Read the authoritative playbook, then the five schemas and `ContractSchemas.Tests.ps1`.
3. Review the collector and its tests, followed by the derived documents and tool bindings.
4. Copy [`review-template.md`](review-template.md) to `review-YYYY-MM-DD-<reviewer>.md`.
5. Record cross-review questions in [`questions.md`](questions.md) and link their IDs from the review.
6. Commit review files separately from any proposed release correction so review evidence remains auditable.

## Question lifecycle

Question status is one of:

- `OPEN` — awaiting an accountable answer.
- `ACCEPTED` — the question identifies work or a clarification that will be incorporated.
- `REJECTED` — the qualification authority rejected the premise, with evidence and rationale recorded.
- `RESOLVED` — an answer or change exists and is linked.
- `VERIFIED` — an independent reviewer confirmed the resolution evidence.

One question must address one decision. Every question includes an artifact and line, the acceptance criterion affected, why the answer matters, an owner, and resolution evidence. Do not close a question merely because a test is green.

## Finding requirements

Every finding includes:

- ID and severity (`CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`);
- artifact and exact line;
- claim being tested;
- observed evidence or minimal reproduction;
- acceptance and operational impact;
- proposed correction;
- owner and status;
- resolution evidence and independent verification.

A reviewer must preserve contradictions and unknowns. A structurally valid schema, green unit test, or intact hash does not by itself prove the program's semantic, privacy, or hardware claims.

## Independence and conflicts

- A reviewer may not approve their own material correction without a second reviewer.
- Conflicting conclusions remain `HOLD` until the named qualification authority records the outcome.
- Questions and findings never override the playbook, frozen contract records, or the formal verdict.
- The seven bench integrations remain unverified until their retained manifests and acceptance evidence are reviewed.

## Current automated baseline

The published release was verified under PowerShell Core 7.6.4 and Windows PowerShell 5.1.26100.8875 with `78 passed`, `0 failed`, and `7 intentionally skipped` on each host. Strict Ajv 8.18.0 compiled all five Draft 2020-12 schemas. A future review must report its own environment and results rather than inheriting this baseline.
