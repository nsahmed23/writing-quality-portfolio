# Review 2026-08-28 — Claude Code

- Release: `operations-blueprint/v1.0.0` at commit `476e75cc855fde943c6eaab4bbfa73abd0ee62a9` on branch `laptop-qualification-program-v2.0.1`, reviewed against the immutable `v2.0.1` release
- Reviewer: Claude Code (session-based source review; record filed on branch `claude/windows-endpoint-iac-qualification-2dtb2g` because the reviewer session may not push to the release branch)
- Review request: `RR-GOV-IAC-2026-08-27` (`review-forum/review-request-2026-08-27-governance-iac.md`)
- Review environment: Linux container, read-only source analysis. Python 3 with `jsonschema` 4.26.0 for Draft 2020-12 compilation, `sha256sum` for manifest verification, `git` for tree and history verification. No PowerShell, Pester, Node, Ajv, cloud, tenant, or hardware execution, per the review request's own rule that source review is read-only and executable validation belongs to the protected trusted-base runner.
- Independence statement: this review inspected the committed bytes directly and recomputed every digest and cross-reference it cites. No completion summary, test log, or PR description was accepted without independent recomputation. The reviewer did not author any file under `operations-blueprint/` or `v2.0.1/`.
- Scope: all six attack tracks of `RR-GOV-IAC-2026-08-27` at source level. Track conclusions below distinguish what was independently verified from what a Windows trusted-base run must still confirm.
- Outcome: `APPROVED_WITH_CONDITIONS`

## Executive conclusion

The blueprint's fail-closed core survives source-level attack. The public validator is structurally incapable of authorizing anything: `Test-LeadershipClaimChain` hard-sets `Allowed = $false` and caps its state at `VALIDATED_DERIVED_INPUT` (`Test-OperationsBlueprint.ps1:10354-10358`), `Get-ActivationDecision` unconditionally appends `PRIVATE_ACTIVATION_IMPLEMENTATION_REQUIRED` and returns a blocked state (`Test-OperationsBlueprint.ps1:15148-15150`), and `Test-OperationsBlueprintBundle` hard-codes `ActivationState = 'HOLD'` regardless of registry content (`Test-OperationsBlueprint.ps1:15496-15504`). The v2.0.1 release is byte-identical across the new commit, and the blueprint's pinned tree, baseline commit, and semantic-validator digest all recompute correctly.

The conditions are one integrity-hygiene defect and two smaller code-quality findings. The repository-root `MANIFEST.sha256` is stale at the reviewed commit: three modified files fail verification and fourteen new files are uncovered (F-20260828-001). That is exactly the "byte drift that the manifest fails to detect" class this request asked reviewers to hunt, at repository scope rather than blueprint scope. It does not weaken the blueprint's own manifest chain, which verifies completely, but it breaks the repository's previously established zero-mismatch convention and should be corrected before this branch is treated as a verified bundle. No finding affects a phase gate, privacy boundary, evidence-integrity mechanism, or verdict correctness, so `APPROVED_WITH_CONDITIONS` rather than `HOLD`; activation state is unaffected and remains `HOLD` by construction.

## Validation evidence

- PowerShell Core result: not run (Linux review host; execution prohibited during source review). The Windows-only guards in `Test-OperationsBlueprint.ps1` (`Test-IsWindowsRuntime`, `Test-TrustedWindowsPathBoundary`) would also fail closed here by design.
- Windows PowerShell 5.1 result: not run (same reason).
- Strict Ajv result: not run. Independent substitute: `jsonschema` 4.26.0 `Draft202012Validator.check_schema` compiles `operations-record-contracts.schema.json` without error; declared `$schema` is Draft 2020-12 and `$id` is `urn:laptop-qual:operations-record-contracts:1.0.0`.
- Additional reproductions, all independently recomputed on the reviewed commit:
  - `BLUEPRINT_MANIFEST.sha256`: 11/11 entries verify; the manifest is self-excluding as documented.
  - `deliverables/laptop-qualification-program/MANIFEST.sha256`: 33/33 entries verify, including the hash of `BLUEPRINT_MANIFEST.sha256`, closing the chain at the deliverable level.
  - Repository-root `MANIFEST.sha256`: 102/105 verify, 3 fail, 14 files uncovered (finding F-20260828-001).
  - v2.0.1 immutability: `git diff 53c2ae1 476e75c -- deliverables/laptop-qualification-program/v2.0.1` is empty; `git rev-parse <commit>:deliverables/laptop-qualification-program/v2.0.1` yields `ee333ff4ee0a02a1571bfc631d3537ba91028256` at both commits, matching `tool-registry.json` `immutableRelease.gitTreeId` and the validator's hard-coded anchors (`Test-OperationsBlueprint.ps1:3885-3894`); file count 15 matches.
  - Semantic-validator pin: `$expectedSemanticValidatorReleaseDigest` (`Test-OperationsBlueprint.ps1:10283`) equals the recomputed SHA-256 of `v2.0.1/ContractSchemas.Tests.ps1` (`b4fdd576...`), which defines `Test-ContractBundleSemantics` at its line 130.
  - JSON strictness: all four blueprint JSON files parse with a duplicate-key-rejecting loader; no duplicate keys.
- Checks not run and why: the 553-count Pester run, the Ajv PRODUCTION/TEST schema execution, the seven bench integrations, and every tenant/Graph/Intune/Terraform path — all require the protected Windows trusted-base runner or private bindings, and the request forbids executing repository script content during source review.

## Track conclusions

### Track 1 — Five-link leadership chain

**Conclusion: no exploitable source-level break found; one low-severity clock-trust asymmetry (F-20260828-002).**

Attacks attempted and the enforcing evidence:

- Turn a public validation into an approval: impossible by construction. `$result.Allowed = $false` is unconditional (`Test-OperationsBlueprint.ps1:10358`); the only states are `BLOCKED`, `TEST_FIXTURE_VALIDATED`, and `VALIDATED_DERIVED_INPUT` (`:10354-10356`). The strings `PILOT_DECISION_READY` and `PURCHASE_DECISION_READY` do not exist anywhere in the validator.
- Re-label ancient evidence as `CURRENT`: the canonical envelope requires `freshness: CURRENT` as a constant, but the label is not trusted — `Get-CanonicalRecordMap` independently rejects records outside their `validFrom`/`validUntil` window at evaluation time (`Test-OperationsBlueprint.ps1:2396-2403`) and recomputes `envelopeCoreDigest`, requiring `attestationSubjectDigest` to equal the recomputation (`:2372-2384`), so the window cannot be edited without breaking the attested core.
- Forge lineage on a simulated `ISSUED` chain: the semantic-validation record must match a recomputed canonical input digest, the pinned immutable v2.0.1 semantic validator digest, the complete source-record set digest, and a `PASS` result, with chronology ordered against every source record (`Test-OperationsBlueprint.ps1:10284-10337`); the decision claim must render after semantic validation (`:10338-10344`).
- Mistake the committed templates for a ready packet: `leadership-claim-chain.json` ships `status: NOT_ISSUED` with null links and `derivedDocumentsAreEvidence: false`; the validator rejects `derivedDocumentsAreEvidence != false` outright (`DERIVED_DOCUMENT_AS_EVIDENCE`). `LEADERSHIP_DECISION_PACKET_TEMPLATE.md` defaults to `NOT_READY` with `RETURN_FOR_EVIDENCE` as the only allowed action (template lines 5-9).
- Smuggle a measured effect into `NOT_MEASURED`: the three `businessImpactPayload` branches (`businessCostDeltaPayload`, `businessNonPriceEffectPayload`, `businessNotMeasuredPayload`) carry distinct `effectType` constants and each closes with `unevaluatedProperties: false`, so cross-branch fields fail schema validation; `Test-BusinessImpactRecordSemantics` additionally constrains `decisionImpact` to a blocking vocabulary (`Test-OperationsBlueprint.ps1:10685`).

### Track 2 — One-writer rule

**Conclusion: holds in the machine-readable model and validator.**

- Exactly one binding (`intune`) is classified `INTUNE_ENFORCEMENT`; the 53 `bindings` entries and 53 `toolClassifications` keys are bijective with no duplicates (recomputed from `tool-registry.json`).
- Transports are `TRANSPORT_ONLY`; Ansible is `BENCH_OR_NON_INTUNE_ONLY`; Group Policy, Configuration Manager, OEM management, and emergency automation are explicitly inventoried as bounded non-Intune writers rather than omitted.
- `Get-ActivationDecision` restricts `writerToolRef` to `msgraph-terraform-provider` or `microsoft-graph-write` (`Test-OperationsBlueprint.ps1:13176-13178`); the direct-Graph path demands a private, digest-bound, unexpired exception and forbids one on the provider path (`:13182-13195`); requester and write identity must differ (`:13199-13201`).
- `intuneTransportOwnership.objectTypeOwnership` is empty and the registry rules state an empty inventory is an activation blocker, not runtime freedom; `Test-ToolRegistry` requires its `activationState` to be `HOLD` (`Test-OperationsBlueprint.ps1:4059`).

### Track 3 — Intune promotion and independent readback

**Conclusion: holds at source level.**

- Readback cannot be faked by HTTP success: the validator requires exact status 200 plus a present response body, and separately compares observed revision, package digest, membership digest, scope, target population, assignment match, and device-state match against the authorized request (`Test-OperationsBlueprint.ps1:15122-15147`); the exception rule in `control-matrix.json` `INTUNE-004` states no HTTP status or Terraform state value substitutes for readback.
- Readback freshness is bounded and ordered after the write and after authorization consumption (`:15119-15124`).
- Stage/ring binding: `PILOT` must target `AUTHORIZED_PILOT` and `PRODUCTION` must target `PERSONA_QUALIFIED` or `BROAD` (`:13172-13175`).
- Production evaluation time is pinned to the host clock within five minutes (`:13105-13108`) — see F-20260828-002 for the asymmetry with the claim-chain path.

### Track 4 — Tool and control completeness

**Conclusion: no dangling references; one integrity defect outside the blueprint directory (F-20260828-001), one dead schema definition (F-20260828-003).**

- All 18 controls in `control-matrix.json` resolve `ownerRole`/`approverRole` against the 67-role catalog and every `toolRefs` entry against the 53 bindings; zero dangling references (recomputed).
- The three catalog roles not referenced by any binding or control (`ROLE_EVALUATION_OWNER`, `ROLE_INDEPENDENT_VERIFIER`, `ROLE_PROCUREMENT_APPROVER`) are used by the validator and checklist (e.g. `ROLE_PROCUREMENT_APPROVER` is a required production approval role at `Test-OperationsBlueprint.ps1:13229`), so they are not dead.
- The schema's 45 `oneOf` branches carry unique `recordType` constants and every branch closes with `unevaluatedProperties: false`; all payload definitions are closed. The ten monitoring signal classes agree exactly among prose (`GOVERNANCE_AND_IAC_OPERATING_MODEL.md:475`), schema, and validator (`$requiredSignalClasses`, `Test-OperationsBlueprint.ps1:12871-12875`), including separate `REVIEW_RESPONSE` and `MONITOR_HEALTH_DEADMAN` ownership checks (`:13006-13007`).
- `Test-BlueprintFileManifest` enforces the exact eleven-file set, rejects unexpected directory entries and reparse points, verifies every hash, and requires the manifest to exclude itself (`Test-OperationsBlueprint.ps1:15154-15285`).

### Track 5 — Privacy and custody

**Conclusion: holds at source level.**

- No email address, GUID, tenant identifier, `onmicrosoft` domain, device serial, or SSID appears in the public blueprint files (pattern scan over all `.md`/`.json`; every match was policy language about such identifiers, not an identifier).
- Diagnostics are code-led by construction: `Add-BlueprintError` never renders the caller-supplied message — output is always `Validation failed: <CODE>.` with the code shape-checked against `^[A-Z][A-Z0-9_]{2,127}$` (`Test-OperationsBlueprint.ps1:3779-3795`), and `ConvertTo-SafeDiagnosticMessage` strips control/format/surrogate/private-use/line-separator characters and caps length (`:3740-3778`). Caller-controlled text cannot reach public output through the error path. See F-20260828-004 for the documentation consequence.
- Fabric/Power BI are bound as projection/view custody only, with `prohibitedUses` including evidence-store substitution and verdict authority (`tool-registry.json`).

### Track 6 — Activation HOLD boundary

**Conclusion: holds; the public path is triple-locked.**

- The checked-in registry state is `HOLD` and `Test-ToolRegistry` fails any registry whose `activation.state` is not `HOLD` (`Test-OperationsBlueprint.ps1:4206`), whose `endpointWriteOwnership.activationState` is not `HOLD` (`:4010`), or whose `intuneTransportOwnership.activationState` is not `HOLD` (`:4059`).
- `Get-ActivationDecision` therefore cannot be satisfied by any input: a registry must pass `Test-ToolRegistry` (which requires `HOLD`) yet also be `ACTIVE` to avoid `CONTROL_PLANE_NOT_ACTIVE` (`:13130-13136`) — mutually exclusive — and even a hypothetical bypass ends at the unconditional `PRIVATE_ACTIVATION_IMPLEMENTATION_REQUIRED` error (`:15148`). The bundle result hard-codes `ActivationState = 'HOLD'` and `Allowed = $false` with an explicit comment that a caller-controlled registry declaration is never surfaced as effective state (`:15494-15504`).
- Fixture records: `fixture://` artifact or attestation references are rejected under the default `PRODUCTION` profile (`FIXTURE_RECORD_FORBIDDEN_IN_PRODUCTION`, `:2386-2388`); `TEST`-profile outcomes are distinct `TEST_*` states and `New-BlueprintResult` computes `Allowed = $false` for any `TEST_`-prefixed state (`:3803-3811`).

## Findings

### F-20260828-001 — Repository-root MANIFEST.sha256 is stale at commit 476e75c

- Severity: Medium (integrity-verification hygiene; no content tampering)
- Status: `OPEN`
- Artifact and line: `MANIFEST.sha256` (repository root) at `476e75cc855fde943c6eaab4bbfa73abd0ee62a9`; failing entries `./README.md`, `./deliverables/laptop-qualification-program/CLAUDE.md`, `./deliverables/laptop-qualification-program/review-forum/README.md`
- Claim tested: "byte drift that the manifest fails to detect" (review request, Files-in-scope paragraph) and the repository's own convention, established at `53c2ae1` ("extend the repository integrity manifest to cover every staged file"), that the root manifest verifies with zero mismatches.
- Evidence or reproduction: on a clean checkout of `476e75c`, `sha256sum -c MANIFEST.sha256` reports 102 OK, 3 FAILED (the three files above, all modified by `476e75c` without regenerating the root manifest), and the 14 files added by `476e75c` (all of `operations-blueprint/v1.0.0/` plus `review-forum/CLAUDE_REVIEW_HANDOFF.md` and `review-forum/review-request-2026-08-27-governance-iac.md`) are absent from it. On `53c2ae1` the same check is 105/105 OK with zero uncovered files.
- Acceptance impact: any reviewer or pipeline that verifies the repository-root manifest on this branch gets a hard failure and cannot distinguish this benign staleness from tampering. The PR #1-#3 review lineage in this repository treats "root manifest: zero mismatches" as a headline verification claim; this branch head silently breaks that invariant.
- Operational impact: none on the blueprint itself — `BLUEPRINT_MANIFEST.sha256` (11/11) and the deliverable-level `MANIFEST.sha256` (33/33, covering the blueprint manifest) both verify, and `Test-BlueprintFileManifest` never consults the root manifest. The Git commit remains the authenticity anchor as documented.
- Proposed correction: regenerate the repository-root `MANIFEST.sha256` on the release branch (a follow-up commit; `v2.0.1/` untouched) so it again covers every staged file, or, if the root manifest is now intentionally descoped to the evaluation bundle, say so explicitly next to it and in `README.md` so a failing verification is interpretable. Do not weaken the deliverable-level manifests.
- Owner: Codex (release-branch author)
- Resolution evidence: pending
- Independently verified by: pending

### F-20260828-002 — No production clock guard or evaluation-time binding on the claim-chain entry point

- Severity: Low (defense-in-depth inconsistency; bounded by the non-authorizing result)
- Status: `OPEN`
- Artifact and line: `Test-OperationsBlueprint.ps1:8635-8642` (`Test-LeadershipClaimChain` parameters) versus `:13105-13108` (`Get-ActivationDecision` clock guard); `New-BlueprintResult` at `:3796-3812`
- Claim tested: "Confirm that freshness is derived at evaluation time from the canonical policy, baseline, release, and source records rather than trusted from a label" (Track 1).
- Evidence or reproduction: freshness and every validity/expiry comparison key off the `$EvaluationTime` parameter. `Get-ActivationDecision` rejects a `PRODUCTION`-profile evaluation time more than five minutes from the host UTC clock (`PRODUCTION_EVALUATION_TIME_UNTRUSTED`). `Test-LeadershipClaimChain` accepts an arbitrary caller-supplied `$EvaluationTime` under the default `PRODUCTION` profile with no host-clock cross-check, so a caller can evaluate a chain "as of" any past instant and obtain `VALIDATED_DERIVED_INPUT` for evidence that is stale now. The result object (`Valid/Allowed/State/ReasonCodes/Errors`) does not record the evaluation time or profile, so the output cannot be distinguished downstream from a present-time validation. (`Test-OperationsBlueprintBundle` itself is unaffected: it calls the chain with the default `UtcNow`.)
- Acceptance impact: a "public checks passed" claim can be minted against a chosen historical clock. The blueprint's own defense holds — the result is never authorizing and the private semantic-validation record carries its own `evaluationTime`/`expiresAt` that the validator orders and expiry-checks — but the two public entry points present inconsistent clock-trust postures for the same `PRODUCTION` profile.
- Operational impact: low; exploitation yields only a mislabeled non-authorizing result. Risk concentrates if any private process ever trusts a `VALIDATED_DERIVED_INPUT` result object without re-deriving time.
- Proposed correction: apply the same ±5-minute host-clock guard in `Test-LeadershipClaimChain` under `PRODUCTION`, and include `evaluationTime` and `validationProfile` in `New-BlueprintResult` output so every result is self-describing. Both changes tighten fail-closed behavior and weaken nothing.
- Owner: Codex (release-branch author)
- Resolution evidence: pending
- Independently verified by: pending

### F-20260828-003 — Dead schema definition `recordVariant`

- Severity: Info
- Status: `OPEN`
- Artifact and line: `operations-record-contracts.schema.json`, `$defs.recordVariant`
- Claim tested: schema surface minimality (Track 4, "strict-compile ... attack every `oneOf` boundary ... unknown property").
- Evidence or reproduction: `recordVariant` is defined (an open object requiring `recordType` and `payload`) but `"#/$defs/recordVariant"` is referenced zero times anywhere in the schema. It is unreachable and cannot affect validation, but it is the only open, non-composed object definition in the pack and invites accidental future use as a weak branch.
- Acceptance impact: none today.
- Operational impact: none today.
- Proposed correction: delete the definition in the next blueprint version, or reference it deliberately with a closing context.
- Owner: Codex (release-branch author)
- Resolution evidence: pending
- Independently verified by: pending

### F-20260828-004 — Validator error messages are never emitted; message text is unverified documentation

- Severity: Info (deliberate privacy design with a documentation-drift consequence)
- Status: `OPEN`
- Artifact and line: `Test-OperationsBlueprint.ps1:3779-3795` (`Add-BlueprintError`)
- Claim tested: "logs, readback bodies, error messages, and resolution evidence cannot become a disclosure path" (Track 5).
- Evidence or reproduction: `Add-BlueprintError` intentionally discards the `-Message` argument and emits only `Validation failed: <CODE>.`. This is the correct privacy posture and is documented in-function. The consequence: the hundreds of descriptive `-Message` literals throughout the 15,510-line validator are never rendered and no test can cover their accuracy, so they can silently drift from the code they describe. Reviewers (including this one) must treat them as comments, not behavior.
- Acceptance impact: none; positive for privacy.
- Operational impact: minor maintenance risk only.
- Proposed correction: none required. Optionally note in the README that public diagnostics are reason-code-only and message literals are documentation.
- Owner: Codex (release-branch author)
- Resolution evidence: pending
- Independently verified by: pending

## Questions filed

None. Nothing found rose to a decision-blocking ambiguity; the findings above carry their own proposed corrections.

## Residual unknowns

Preserved as unknowns, not passes:

1. The `553 = TotalCount = PassedCount` Pester claim is not statically verifiable: `OperationsBlueprint.Tests.ps1` declares 289 `It` blocks with 96 `-TestCases` usages, so 553 executed cases is plausible but only the protected Windows Pester 3.4.0 run can confirm it. A green count from any other environment proves nothing, per the request's own standard.
2. The Windows-only trusted-base machinery (path-boundary, reparse, case-sensitivity, pinned Git/Node/Ajv guards, held runtime guards) was reviewed as source but cannot be exercised on this host; its behavior under a hostile filesystem remains for the trusted runner.
3. Deep semantic paths of the validator — capacity-waterfall recomputation, pilot completion/sentiment representation proofs, role-binding closure, authorization-consumption ledger semantics, Azure deployment semantics (functions between `Test-OperationsBlueprint.ps1:4411` and `:12336`) — were reviewed by sampling and cross-reference, not exhaustively line-by-line in this round. No inconsistency was found in the sampled paths; a second round can target them individually if wanted.
4. Whether the private implementation exists at all is out of scope by design; nothing here attests to tenant readiness, and activation remains `HOLD`.
