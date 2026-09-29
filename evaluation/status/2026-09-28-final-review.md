# Final whole-branch review

## Verdict: Ready

Reviewed local HEAD `db08200a558d9c4a9662d5c0b023e8e8b745a1aa` against the integration specification and implementation plan. **Ready for publication as the planned draft PR; no unresolved critical or important defect found.** This verdict covers the integration and offline development milestone. It is not a benchmark-readiness, diagnostic-quality, human-adjudication, Stage 2, remote-CI, or merge-approval verdict.

The remaining delivery actions are publishing the branch/draft PR, verifying the published tree and parent topology if commits are reconstructed, and reporting actual remote check outcomes. These are not represented as already completed by this review.

## Scope and method

- Read the specification, plan, SDD ledger, all four task reviews and their fix dispositions, and the substantive new source, tests, configuration and documentation represented by `a4cd638..db08200` (18 changed files).
- Reviewed historical integration using pinned source-tree comparisons instead of reinterpreting thousands of immutable evidence lines or re-reviewing the old evaluator implementation.
- Independently checked Git merge topology, byte preservation, exact manifest scopes, CRLF attributes and whitespace; ran two narrowly scoped writer-failure probes in disposable repositories.
- Did not rerun the already passed 28-test foundation/integrity suite, 198-test legacy suite, portfolio validation, README example or recount. Their results remain controller/task evidence, accurately identified in the committed verification record. This review independently verifies the preservation and integrity claims below.
- No source, historical evidence, manifest or tracked configuration was changed. This report is the sole review artifact written.

## Findings and explicit disposition of deferred minors

### Critical / Important

None.

### Low — recount input completeness is descriptive, not an acceptance gate

`evaluation/status/recount_pilot.py:95-109,149-162`

The recount discovers normalized and raw/inbox files and reports their counts; it does not require 33 normalized runs, 36 pairs or a complete expected per-run case set. This can produce incomplete totals on an altered checkout when invoked alone. **Accepted as nonblocking for this milestone:** the program is an arithmetic audit of the preserved dataset, all source bytes are independently unchanged, exact historical manifest coverage passes, and `evaluation/status/2026-09-28-integration-verification.md:87` explicitly describes the limit and instructs readers to verify manifests first. No model-readiness or data-acceptance decision depends on the script's exit status. If this utility becomes a general input validator, add explicit expected-set validation then.

### Low — writer failure safeguards lack committed direct regression tests

`tests/test_verify_manifests.py:133-142`; implementation at `scripts/verify_manifests.py:118-119,135-137`

The committed tests exercise successful explicit regeneration and read-only rejection, but do not directly preserve root output across a `--write-root` attempt with corrupt historical bytes or a symlinked root manifest. **Accepted as a nonblocking test-coverage opportunity, with present behavior independently confirmed:** two disposable-repository probes each returned exit code 1 and left the prior output bytes unchanged. Nested corruption reported `hash mismatch: evaluation/original.txt`; a symlinked output reported `symlink traversal: MANIFEST.sha256` and left its target unchanged. No implementation defect was found. These cases can be added when the writer next changes.

## Independently verified integration and manifest evidence

| Check | Observed result |
|---|---|
| Local integration merge | `a4cd638e368f44bb6e1d6bb3c72a3671f9174587` has parents `28454c197246e6147da952b72d044273f6bb192f` and `ac6d52e1c57c71d43070884bb56335ee3176888f` |
| Original main files | Recomputed Git blob hashes for all original paths except intentionally edited README/root manifest: 1,690 checked, zero missing or changed |
| Historical evaluation files | Recomputed Git blob hashes for all evaluation paths from reviewed tip: 476 checked, zero missing or changed |
| Tracked tree and root scope | 2,184 tracked paths; root manifest has 2,183 entries |
| Historical nested scope | 475 nested manifest entries; the historical manifest itself is the 476th preserved evaluation file |
| Integrity verifier | `python scripts/verify_manifests.py` passed exact tracked coverage and byte hashes for both manifests |
| CRLF policy | Exactly five files contain CRLF, all existing CSVs: counts 11, 253, 16, 322 and 9; `git check-attr text` reports `unset` for each and both manifests |
| Diff whitespace | `git diff --check a4cd638..db08200` passed |
| Two explicit writer-failure probes | Both rejected and preserved prior output bytes, as detailed above |

The preservation computation uses the source tree's blob object IDs and `sha1(b"blob " + byte_length + b"\0" + contents)` on current file bytes. It confirms equality to the pinned Git objects, not authorship. The root/nested manifest verifier separately confirms current exact tracked coverage and SHA-256 bytes. The nested manifest remains byte-identical to the reviewed historical input; only the two expressly named new development subtrees are excluded from its scope, and both are covered by the root manifest.

## Code and CI assessment

- Quote resolution follows the specified literal, overlapping, code-point contract. Occurrence validation rejects booleans and invalid indexes; occurrence selection precedes adjacent-context filtering. It does not guess among ambiguous matches or normalize Unicode/line endings.
- Ingestion preserves raw-byte and UTF-8 case-text hashes, retains native labels, keeps original finding indexes, rejects malformed findings locally, distinguishes labels/explanations in duplicate detection, and permits abstention. Duplicate JSON keys, nonfinite numbers and invalid envelopes are response-level failures as specified. The prior global depth/scalar check was removed; required-string/context surrogate checks now occur locally. Every result remains `development_only`.
- Public implementation is small and uses only the standard library. No new provider, model runner, scorer, taxonomy mapper, router, arbitration logic, persistence or unlock was introduced. The recount does not import the historical scorer.
- Manifest verification accepts GNU text/binary markers, rejects unsafe or duplicate paths and symlink traversal, hashes exact bytes and verifies coverage against Git's tracked set. Explicit regeneration verifies the historical scope first and changes only the root manifest.
- The workflow defines the requested Ubuntu/Windows by Python 3.11/3.14 matrix. Its commands and `PYTHONPATH` use are compatible with the respective runner shells; legacy discovery supplies its top-level path explicitly. Permissions are `contents: read`, checkout credentials are not persisted, actions are SHA-pinned and the existing PyYAML dependency is version-pinned. No secrets or write action is used. Task 2's review records official action revision checks; this review did not repeat external revision lookups.
- `* -text` prevents checkout/checkin newline conversion, including preservation of the five preexisting CRLF CSVs. Symlink tests may skip where Windows lacks symlink creation privileges; actual per-cell results and skips still need to be reported from remote execution.

## Documentation and human readiness boundaries

The root entry point and new status pages separate the historical editing pilot from the later communication experiments. They give the erratum priority over the provisional report, preserve the review sequence, identify the reoptimization proposal as historical, and explain the limited new implementation. The independent recount values and controller-observed tests are attributed separately from older reports. Local verification is not presented as remote CI evidence.

The readiness page leaves real reviewer identity/calibration, independent gold and adjudication, equivalent boundaries, numeric gates/opportunity floors, metadata leakage evaluation, fresh holdout, exact execution provenance and blinded human judgments pending. It explicitly distinguishes structural ingestion acceptance from diagnostic correctness. No new human identity, adjudication, label approval, inherited threshold, comparative ranking or Stage 2 permission is manufactured.

## Considered and declined changes or behaviors

- **Re-read/re-score historical evaluation outputs:** declined because this milestone preserves already-reviewed evidence; source-tree equality establishes the integration claim without changing the historical audit's scope.
- **Rerun every previously passed suite:** declined because there was no specific remaining failure hypothesis; targeted writer probes addressed the only untested behavior raised in the deferred review.
- **Make recount a new readiness gate:** declined because it is documented as a descriptive audit, the frozen inputs are protected by manifest verification, and benchmark eligibility requires separate human-owned contracts.
- **Add a new global JSON depth/scalar policy:** declined because it would again risk erasing valid siblings or inventing an undeclared input restriction. The standard decoder's own parsing limitations remain response-level failures; successfully parsed finding errors stay local.
- **Add resource quotas or optimize worst-case repeated-quote searching:** declined because no bounded service or hostile-input throughput contract is part of this small offline foundation. Current literal semantics are clear and testable; future operational limits should be explicit contracts.
- **Normalize line endings or regenerate the historical manifest:** declined because both would violate the immutable-byte boundary. Root regeneration alone is explicit and verified.
- **Claim remote CI success or publication equivalence in advance:** declined because neither has been observed. Reconstructed remote commit IDs may differ; compare actual tree IDs/contents and parent topology and retain the documented local commit labels.
- **Promote syntactic findings or software-test success into quality/readiness:** declined because human gold, calibration and preregistered acceptance inputs are absent and the design keeps Stage 2 locked.

## Final disposition

**Ready for the planned draft PR, with two accepted low-severity follow-up opportunities and no required source fix.** Complete the publication and observed remote-check reporting steps without broadening this milestone's evidence or readiness claims.
