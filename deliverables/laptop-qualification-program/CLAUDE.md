# Claude Code review instructions

These instructions apply to `deliverables/laptop-qualification-program/` and all of its descendants.

## Review boundary

- Treat `v2.0.1/` as an immutable release. Review it; do not edit it in place.
- The authoritative method is `v2.0.1/NEW_LAPTOP_EVALUATION_PLAYBOOK_v2.md`.
- The five files under `v2.0.1/schemas/` are the normative portable contract.
- `v2.0.1/TOOL_BINDINGS.md` is explicitly non-normative and replaceable.
- The persona sheet, leadership brief, and specification sheet are derived views. They cannot originate evidence or a verdict.
- Put review work only in `review-forum/`, using a dated copy of `review-template.md`. Put cross-review questions in `review-forum/questions.md`.

## Required review posture

1. Inspect the actual files and tests before accepting any completion summary.
2. Cite `file:line` evidence for every finding and question.
3. Separate normative-contract defects from implementation-binding defects and derived-document wording.
4. State severity, acceptance impact, reproduction, and proposed correction.
5. Preserve unknowns. Missing evidence is not a pass.
6. Do not claim that the seven skipped bench integrations passed. They require representative Windows hardware.
7. Do not run the full collector, Restricted mode, CMSL, or hardware/native collection as part of a source review. The Pester suites are the safe automated review boundary.
8. Do not add agent-vendor names to the collector or the vendor-empty `agent-classification.json` template.
9. Propose release-file corrections in a new version or follow-up branch; never rewrite `v2.0.1/` silently.

## High-value review targets

- Exactly seven phases numbered 0 through 6 in prose and diagram.
- The compatibility/security hard gate inside Phase 2 and all three pilot preconditions.
- Candidate, incumbent, and sibling/alternative controls under the same Phase 3 protocol.
- Sampling-floor aggregation by test, role, condition, and baseline without duplicate units or runs.
- Fresh-versus-cache chronology, bridge acceptance, exact dependency/test-pack binding, and bootstrap behavior.
- Universal T2 corroboration, dual verdict arbitration, deadline handling, procurement substitution, and requalification.
- Safe/Restricted privacy boundaries, partial-failure semantics, native provenance, external agent rules, CMSL isolation, and manifest accuracy.
- Corporate-floor capacity waterfall and evidence discipline in derived documents.

## Safe validation

From `v2.0.1/`, run:

```powershell
Import-Module Pester
$result = Invoke-Pester -Script @(
    '.\Get-EvalEvidence.Tests.ps1',
    '.\ContractSchemas.Tests.ps1'
) -PassThru

if ($result.FailedCount -ne 0 -or
    $result.PassedCount -ne 78 -or
    $result.SkippedCount -ne 7) {
    throw "Unexpected result: passed=$($result.PassedCount), failed=$($result.FailedCount), skipped=$($result.SkippedCount)"
}
```

Run that command under both PowerShell Core and Windows PowerShell 5.1 when revalidating cross-host behavior. Schema tests require Node.js, Ajv 8, and `ajv-formats` as described in the release README.

## Review outcome

Use one of: `APPROVED`, `APPROVED_WITH_CONDITIONS`, `HOLD`, or `FAIL`. An unresolved finding that affects a phase gate, privacy boundary, evidence integrity, or verdict correctness prevents `APPROVED`.
