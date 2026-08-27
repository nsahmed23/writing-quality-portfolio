# Enterprise Laptop Qualification Program v2

This directory is one coherent v2 set. No v1 artifact is authoritative or should be restored beside it.

## Source-of-truth order

1. **NEW_LAPTOP_EVALUATION_PLAYBOOK_v2.md** — authoritative method, normative seven-phase diagram, gates, sampling, reserves, controls, arbitration, procurement lock, and requalification.
2. **schemas/** — the five portable contract schemas: candidate manifest, test plan, evidence record, threshold policy, and verdict record.
3. **TOOL_BINDINGS.md** — current implementation binding, explicitly non-normative and replaceable.
4. Derived views — the persona sheet, leadership brief, and observed configuration sheet. These cite releases and verdicts; they never originate a gate or decision.

If a derived view conflicts with the playbook or a cited contract record, the playbook and contract record control.

## Files

### Portable contract

Contract schema release: **2.0.1** (v2 hardening patch; stricter records are intentionally distinguishable from the earlier 2.0 draft).

- **NEW_LAPTOP_EVALUATION_PLAYBOOK_v2.md**
- **schemas/candidate-manifest.schema.json**
- **schemas/test-plan.schema.json**
- **schemas/evidence-record.schema.json**
- **schemas/threshold-policy.schema.json**
- **schemas/verdict-record.schema.json**

### Non-normative Phase 1 implementation support

These files implement and verify the current collection binding. They do not add to or replace the portable contract.

- **Get-EvalEvidence.ps1** — collector v2.0.1 with Safe (default; shareable after manifest review) and Restricted (authorized internal) bundle modes plus section-level failure isolation; non-elevated runs record unavailable sections, while elevation is required for the full protected evidence set.
- **Get-EvalEvidence.Tests.ps1** — unit assertions plus a clearly skipped bench integration matrix for token- and hardware-dependent cases.
- **ContractSchemas.Tests.ps1** — non-normative portable-contract verification using Pester, Node.js, Ajv 8, and `ajv-formats`.
- **agent-classification.json** — the single vendor-empty production template at the collector's default path; add the organization's versioned classification rules here. No competing example file is shipped.

Safe mode pseudonymizes direct identifiers, excludes active Wi-Fi details and restricted raw artifacts, and omits the raw classification-rule file. Review its manifest before sharing. Restricted mode requires a nonblank authorization reference, records it in the bundle manifest, and remains internal under the approved access controls.

Nonempty agent-classification rules are inert unless `-ApprovedAgentClassificationSha256` matches the preapproved SHA-256 of **agent-classification.json**. CMSL is never imported merely because it is discoverable on `PSModulePath`; a CMSL-present run requires both the exact absolute `.psd1` path in `-ApprovedCmslModulePath` and the preapproved complete module-tree digest in `-ApprovedCmslTreeSha256`. Obtain that digest with `Get-ModuleTreeSha256` after dot-sourcing **Get-EvalEvidence.ps1** using `-LoadFunctionsOnly`, then approve it outside the collection run. The manifest records both bindings.

Bundle SHA-256 values provide tamper detection, not publisher authenticity. Verify every file before use and release the bundle through an approved signed channel.

Skipped integration cases are not simulated passes. Elevated/non-elevated behavior, present/absent battery, present/absent vendor tooling, unsupported storage counters, and other hardware-dependent paths must run on representative bench units before the collector is released.

Schema verification requires Ajv major version 8 and `ajv-formats`; release 2.0.1 was verified with Ajv 8.18.0 and `ajv-formats` 3.0.1. Resolution uses `AJV_2020_PATH` and `AJV_FORMATS_PATH`, then project-local `node_modules`, then the known development-host installation. If none is available, install those verifier dependencies locally or set both overrides. They remain non-normative verification tooling, so this deliberately small contract set does not add a package manifest or lockfile.

Standalone JSON Schema validation proves record shape and the conditionals expressible inside one record. It does not prove cross-record reference resolution, freeze/admission/bridge chronology, gate-bearing aggregates against frozen sampling floors, global identity uniqueness, count equality, percentage arithmetic, or capacity equations. Before an evidence or verdict release, the mandatory bundle-semantic gate must run `Test-ContractBundleSemantics` from **ContractSchemas.Tests.ps1** (or an independently implemented equivalent) and return no errors. Every record's `admission.admittedAt` must be strictly later than the manifest, test-plan, and threshold-policy `frozenAt` values; fresh observations must also be post-freeze. A pre-freeze observation is admissible only through the exact-dependency, test-pack, age, hash, completeness, and already-accepted fresh-bridge controls for `compatibility-cache`. The test plan and fresh T0 subjects must resolve to the current manifest. Gate coverage is calculated by every required frozen test, role, condition, and baseline stratum using release-wide unique unit/run identities; subfloor context records remain valid but cannot satisfy a gate, and missing gate evidence cannot pass vacuously. IDs, references, and versions compare with ordinal case-sensitive equality; SHA-256 hexadecimal text may compare case-insensitively. Every T2 record requires a resolvable T0/T1 `corroborationRef`; uncorroborated research leads remain outside the evidence release.

Pilot entry is never authorized retrospectively by a Phase 5 record. Before Phase 4 starts, issue an immutable `pilot-authorization` instance of **verdict-record.schema.json** with the Phase 2 approval, Phase 3 provisional approval, population/privacy reference, stop conditions, rollback plan, and approval time. The later `phase5-final` instance must reference it through `pilotAuthorizationRecordRef`; the bundle gate verifies that authorization exists and that authorization time precedes pilot start and completion.

### Derived, non-normative views

- **hp-zbook-8-g2a-spec-sheet.md** — sanitized point-in-time configuration summary; requires T0 release references before decision use.
- **g2a-persona-fit.md** — corporate-baseline and capacity-waterfall view; requires an issued Phase 5 persona verdict before routing.
- **g2a-leadership-brief.md** — six-question decision brief; requires the applicable gate or verdict references before approval.

Blank evidence and verdict slots mean “not yet issued,” not pass.

### Replaceable implementation

- **TOOL_BINDINGS.md** — Atmos, Terraform/OpenTofu, Azure, Intune, Microsoft Graph, Ansible, SysTrack, ServiceNow, CI/CD, and other current bindings beneath the portable contract.

## Required human inputs before Phase 0 can exit

- numeric test-class sampling floors at or above the playbook floors;
- threshold and reserve values, including rationale, selection method, applicable personas, approver, and revision rule;
- named qualification authority;
- named pilot privacy owner and numeric representation strata;
- persona workload requirements;
- organization-owned **agent-classification.json** rules and the approved SHA-256 used to activate them.

Phase 0 rejects blanks in these required fields. Later evidence-release and verdict-record IDs are process outputs and remain blank in derived templates until the corresponding phase issues them.
