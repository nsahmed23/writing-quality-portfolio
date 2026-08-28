# Laptop Qualification Operations Blueprint v1.0.0

**Status:** PRODUCTION-GRADE IMPLEMENTATION CONTRACT / LIVE ACTIVATION HOLD

This directory defines the public, non-normative production implementation contract for turning the portable laptop-qualification contract into an enterprise Windows decision and rollout process. The leadership decision packet is the product. Governance, infrastructure as code, Intune, telemetry, and reporting are supporting controls that make the recommendation reproducible and safe to execute.

The contract and its reference validator are validated against structural and negative tests. It is not connected to a tenant, private production repository, evidence store, deployment identity, protected environment, or named approval chain. It therefore cannot authorize a pilot, production deployment, or purchase. “Production-grade” describes the enforced design and acceptance contract; “production-active” requires the private evidence and live independent readback listed below.

The committed validator, schema, and test suite are intentionally single-file review bundles in this public release. Their size is an audit and maintenance limitation, not a production-runtime pattern. Before activation can leave `HOLD`, `SUPPLY-014` requires deterministic, source-manifested decomposition and an externally pinned trusted packer that regenerates and byte-compares the one reviewed runtime bundle. Runtime dot-sourcing is prohibited: production executes only the verified packed artifact.

## What the blueprint must answer

Leadership should be able to see one evidence-backed chain without reconstructing it from separate technical reports:

1. Which target persona has a measured need beyond the corporate floor and approved reserve?
2. What current, persona-specific problems exist in that persona's incumbent fleet?
3. What did the candidate, incumbent control, and sibling or alternative show under the frozen qualification protocol?
4. What measured cost or business effect follows, or what is honestly still `NOT_MEASURED`?
5. What exact buying and rollout recommendation follows from the issued verdict and procurement envelope?

The unissued [`leadership-claim-chain.json`](leadership-claim-chain.json) is deliberately empty until all five links resolve: persona need, current-fleet issue, concurrent candidate/control comparison, measured or explicitly unmeasured business effect, and verdict-backed recommendation. A missing, stale, or contradictory link keeps the decision packet `NOT_READY`.

The public `Test-LeadershipClaimChain` function can return only a validation result for derived input. `VALIDATED_DERIVED_INPUT` means that the proposed input passed the public checks; it is not an issued verdict, pilot authorization, procurement approval, `PILOT_DECISION_READY`, or `PURCHASE_DECISION_READY` packet. An `ISSUED` chain must be created inside the private governed process and must bind the semantic-validation record, its digest, and a canonical input digest covering the exact portable-contract set, five links, issuance context, and decision-source record digests. The derived decision-claim payload is generated after semantic validation, binds back to that result, and is therefore deliberately outside its own input digest; rollout monitoring binds both records and digests.

## Authority boundary

The authoritative method remains the immutable [Laptop Qualification Program v2.0.1](../../v2.0.1/README.md), its playbook, and its five portable schemas. This blueprint does not add an eighth phase, a sixth portable schema, a new verdict, or a tool dependency to that method. The `v2.0.1/TOOL_BINDINGS.md` file is the release-scoped historical binding snapshot preserved for reproducibility. This directory's `tool-registry.json` is the later public operating-blueprint binding; it remains non-normative and non-activated while production status is HOLD. Private activation must point explicitly to one approved binding version and digest.

Within an activated enterprise implementation:

- Git records reviewed desired state and history.
- Atmos composes organization, environment, ring, persona, and candidate layers.
- Terraform is the reviewed desired-state engine for approved Azure, Entra, and qualified Graph resources. The Microsoft Graph Terraform provider is the default per-object Intune transport; direct Graph is allowed only through a recorded, expiring exception for an explicitly owned object type.
- Microsoft Intune and its Graph write path are the sole production writer for the settings and artifacts explicitly assigned to the Intune-owned scope. Private activation must inventory and assign every other Windows management authority rather than pretending it does not exist.
- Microsoft Graph has separate bounded write and independent Intune and Entra-directory readback paths; Azure Resource Manager supplies independent Azure-plane readback.
- SysTrack, ServiceNow, the evidence collector, approved test harnesses, and authoritative vendor material supply evidence; none can issue a verdict alone.
- Microsoft Fabric and Power BI may hold and present governed projections when selected. They never become evidence or verdict authorities.
- Ansible may accelerate isolated bench and post-provisioning work. It is never a second production writer for an Intune-owned setting.

See [`GOVERNANCE_AND_IAC_OPERATING_MODEL.md`](GOVERNANCE_AND_IAC_OPERATING_MODEL.md) for the full architecture, source-authority map, Intune layers, promotion gates, monitoring model, activation requirements, and official source map.

### Binding at a glance

| Capability | Current role | Authority boundary |
|---|---|---|
| Git and protected review | Desired-state history, review, and provenance | Cannot prove device state or approve its own change |
| Atmos | Compose organization, environment, ring, persona, and candidate layers | Orchestration only; cannot write an endpoint |
| Terraform and qualified providers | Plan and apply reviewed infrastructure and supported Graph resources | State records a transition, not endpoint truth |
| Microsoft Intune | Sole enforcement plane for explicitly mapped Intune-owned Windows domains | Cannot originate evidence, persona need, or verdict |
| Microsoft Graph write/readback | Bounded transport plus separately identified observation paths | Writer cannot serve as independent reader or broaden scope |
| Collector and test harnesses | Device ground truth and controlled candidate/control evidence | Evidence only; no verdict or fleet-prevalence claim by itself |
| SysTrack | Current-fleet performance and experience distributions | Telemetry source; no causal or verdict authority |
| ServiceNow | Incident, repair, lifecycle, change, and exception records | Workflow/evidence authority only for its recorded domain |
| Evidence store and signing | Custody, immutable releases, provenance, and authenticity | Cannot strengthen evidence semantics or approve deployment |
| Authorization ledger + independent reader | Atomically consume one approved nonce and prove its monotonic one-use state | No Intune, endpoint, evidence, verdict, or self-approval authority |
| Microsoft Fabric and Power BI | Optional governed data projection and leadership drill-down | View only; never the only evidence copy or decision authority |
| Ansible | Bounded bench setup and post-provisioning verification | Never a second production writer for Intune-owned state |
| CI, policy, schema, and semantic validators | Fail-closed verification and promotion controls | Execute only in the trusted runner; cannot self-authorize |
| Alerting and review integrations | Notify, reconcile, and preserve questions/findings | Cannot execute comment text, merge, deploy, or close a finding |

The exhaustive machine-readable inventory is `tool-registry.json`: every binding is classified, replaceable, and held until its private version, identity, scope, readback, failure mode, and owner are approved.

## Files

Read the set in this order:

1. This README for boundaries, activation state, and package navigation.
2. [`GOVERNANCE_AND_IAC_OPERATING_MODEL.md`](GOVERNANCE_AND_IAC_OPERATING_MODEL.md) for architecture, authorities, Intune layers, ring promotion, and governance.
3. [`tool-registry.json`](tool-registry.json) and [`control-matrix.json`](control-matrix.json) for the machine-checked binding and controls.
4. [`leadership-claim-chain.json`](leadership-claim-chain.json) and [`LEADERSHIP_DECISION_PACKET_TEMPLATE.md`](LEADERSHIP_DECISION_PACKET_TEMPLATE.md) for the decision product and its fail-closed public template.
5. [`private-activation-checklist.md`](private-activation-checklist.md) for the evidence that must be completed and independently approved in the private control plane.
6. The validator and Pester suite for executable acceptance and negative tests.
7. [`BLUEPRINT_MANIFEST.sha256`](BLUEPRINT_MANIFEST.sha256) for the byte hashes of all eleven functional files.

| File | Purpose | Authority |
|---|---|---|
| [`README.md`](README.md) | Package boundary, read order, activation state, and validation entry point | Non-normative blueprint index |
| [`GOVERNANCE_AND_IAC_OPERATING_MODEL.md`](GOVERNANCE_AND_IAC_OPERATING_MODEL.md) | Human-readable operating architecture and governance | Non-normative blueprint |
| [`tool-registry.json`](tool-registry.json) | Complete role, boundary, failure, replacement, and activation inventory for current and required tools | Non-normative machine-readable binding |
| [`control-matrix.json`](control-matrix.json) | Preventive, detective, and corrective controls with fail-closed states, readback, and rollback references | Non-normative operational policy |
| [`leadership-claim-chain.json`](leadership-claim-chain.json) | Empty public template tying persona need, incumbent issue, candidate/control evidence, business effect, and recommendation together | Derived-output input; not evidence |
| [`operations-record-contracts.schema.json`](operations-record-contracts.schema.json) | Strict Draft 2020-12 implementation contracts for operations-layer canonical records; it deliberately excludes the five portable records | Non-normative operations contract pack; not a sixth portable schema |
| [`LEADERSHIP_DECISION_PACKET_TEMPLATE.md`](LEADERSHIP_DECISION_PACKET_TEMPLATE.md) | Page-one joined leadership view plus gate, evidence, cost, risk, rollout, and approval sections | Derived, fail-closed template; not evidence or authority |
| [`private-activation-checklist.md`](private-activation-checklist.md) | Public-safe inventory of private identity, tenant, IaC, Intune, evidence, monitoring, and approval activation evidence | Non-normative checklist; incomplete until privately bound and verified |
| [`Test-OperationsBlueprint.ps1`](Test-OperationsBlueprint.ps1) | Validator for tool, control, claim-chain, and Intune activation invariants | Verification implementation |
| [`OperationsBlueprint.Tests.ps1`](OperationsBlueprint.Tests.ps1) | Positive and adversarial tests for the blueprint | Verification implementation |
| [`.gitattributes`](.gitattributes) | Pins LF line endings so the byte manifest is reproducible across supported Git clients | Integrity implementation |
| [`BLUEPRINT_MANIFEST.sha256`](BLUEPRINT_MANIFEST.sha256) | Self-excluding SHA-256 index for the eleven functional blueprint files | Drift detection only; authenticity comes from the reviewed Git commit |

The manifest excludes itself to avoid a circular digest. It detects local byte drift and unexpected file-set changes; it does not establish authorship or approval. Authenticity and review provenance must come from the protected, reviewed Git commit and the private release process.

## Decision flow

```text
Fleet portfolio + SysTrack + Graph + ServiceNow + collector + lab/pilot tests
                                │
                                ▼
        validated immutable evidence and phase-gate releases
                                │
                                ▼
          issued pilot/final verdict + procurement envelope
                                │
                                ▼
 five-link joined claim chain (evidence + verdict), current and complete
                                │
                                ▼
              deterministic leadership decision packet
                                │
                                ▼
 approved Intune ring promotion + bound monitoring + Graph readback
```

The first four links may be assembled before the verdict only as an explicitly `NOT_ISSUED` draft. The fifth link and complete issued chain require the applicable issued verdict and procurement envelope. The decision packet may summarize that issued decision; it cannot originate one. A dashboard may drill into a released packet. It cannot silently change the decision snapshot after approval.

## Public and private split

This public directory intentionally contains no personal name, employee or device identity, tenant identifier, subscription identifier, group identifier, service URL, secret, live evidence, quote, incident, or production state.

Production activation belongs in an approved private repository and evidence boundary. It must bind:

- public roles to approved enterprise identities and independent approvers through a root ceremony whose quorum is distinct by canonical custodian and signing key;
- exact tool, provider, module, script, action, policy, and test-pack versions or digests;
- tenant-scoped Graph permissions, Intune RBAC, scope tags, protected groups, and ring limits;
- a non-overlapping per-object Intune transport-ownership map, with the Terraform provider as the default and any direct-Graph exception separately approved and time-bounded;
- Atmos stack values, Terraform backend, workload-identity subjects, state isolation, and recovery;
- the root authority, canonical role catalog, signed role bindings, independent role-binding readback, and an acyclic bootstrap/operational freshness-policy chain;
- the authorization-consumption ledger, its independent read-only observer, distinct short-lived identities, authority keys, atomicity/consistency policy, retention, recovery, and rollback detection;
- Safe and Restricted evidence custody, retention, signing, privacy floors, and restore testing;
- authenticated private population-proof resolution, release-scoped commitment-key custody, proof issuer/revocation policy, and same-count/different-membership rejection;
- alert channels, response owners, escalation timing, and dead-man monitoring;
- all seven real-hardware integration results.

Until those bindings exist and pass their gates, the activation state remains `HOLD`.

The public `Get-ActivationDecision` function is only a fail-closed precondition and lint simulation. It can explain why a proposed request is blocked; it cannot authorize a pilot, Intune or Graph write, production rollout, or purchase. A real authorization decision belongs to the private control plane with bound identities, protected approvals, immutable records, current evidence, and independent readback.

## Validation

Source review is read-only. Do not dot-source, import, or execute PowerShell, Node, workflow, renderer, or test content from a pull-request checkout during review.

Execution belongs only in a trusted-base workflow after a human pins the reviewed commit. For blueprint v1.0.0, production validation is Windows-only in a fresh `-NoProfile -NonInteractive` PowerShell process on a disposable, credential-free, network-denied runner selected independently of the pull request. The toolchain is on a local fixed NTFS/ReFS boundary; native inspection must prove per-directory case sensitivity is disabled and no reparse point exists on every ancestor, root, executable, entry-point, and dependency path. Unsupported, remote, case-sensitive, reparse, or unqueryable storage fails closed. The image, PowerShell hosts, exact Pester 3.4.0 module tree, Git and Node executables, the complete Git and Node native-runtime trees, Ajv and `ajv-formats` entry points, module roots, and dependency trees are pinned outside the repository. Pester 3.4.0 is an explicit v1.0.0 compatibility binding because the verified suite uses its `-Script` and `PendingCount` result contract; a later major is a reviewed test-runner migration, not a silent upgrade. The runner imports exactly one attested Pester module, resolves exactly one module-owned `Invoke-Pester` function, and invokes the captured `CommandInfo`; an ambient alias, function, profile, or name lookup cannot forge the gate. The complete Git and Node/runtime/package namespaces and the trusted external working directory are read/execute-only and immutable to the runner identity and every untrusted principal, established by protected image or mount attestation, ACL verification, and approved WDAC/AppLocker policy. Runtime-tree guards remain open across each child process and verify final-handle paths, effective-token non-mutation, retained contents, and post-execution state; those guards and pre/post hashing supplement rather than replace the protected namespace. Git and Node run from trusted external directories with closed `PATH` and loader environments. Git also uses a closed command grammar with no lazy fetch, signatures, filters, replace objects, grafts, shallow history, helpers, or network. Ambient `PATH`, Git configuration/helper/trace overrides, Node or native-loader variables, user-profile, parent-directory, globally installed, Firebase, repository-controlled dependency discovery, and tree drift are rejected.

The workflow supplies `OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT`; Git pins `OPERATIONS_BLUEPRINT_GIT_PATH`, `OPERATIONS_BLUEPRINT_GIT_SHA256`, `OPERATIONS_BLUEPRINT_GIT_ROOT`, and `OPERATIONS_BLUEPRINT_GIT_TREE_SHA256`. Schema execution pins `OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT`, its portable full-content digest in `OPERATIONS_BLUEPRINT_NODE_RUNTIME_CONTENT_SHA256`, its native held-guard digest in `OPERATIONS_BLUEPRINT_NODE_RUNTIME_TREE_SHA256`, the fixed `OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY`, the Node executable path and digest, both Ajv entry points and digests, and the complete Ajv, `ajv-formats`, and Node dependency roots and tree digests. All paths are absolute, remain outside the reviewed checkout, resolve within the declared trusted boundary, and match their lowercase SHA-256 pins. The suite verifies exact executable, working-directory, and module resolution and rejects unapproved loader or Git environment state before use.

`Invoke-OperationsRecordSchemaValidation` defaults to `PRODUCTION` and never falls back. That profile requires the externally protected runtime namespace and a native runtime-tree guard held across the Node child. The explicit `TEST` profile still performs exact entry, package-tree, and full-runtime-content checks before and after the child, uses the fixed external working directory and closed child environment, and returns `TEST_SCHEMA_VALIDATED_NON_PROMOTABLE` with `authoritative: false` and `promotionEffect: NONE`. TEST results exercise source behavior only and cannot satisfy release, activation, deployment, or procurement evidence. The local verification reported with this public branch uses TEST because the available Ajv installation is user-owned; protected PRODUCTION execution remains required private activation evidence.

From that trusted runner, invoke the suite with the externally verified Pester module and the required trusted-toolchain environment variables documented by `OperationsBlueprint.Tests.ps1`:

```powershell
$pesterModules = @(Import-Module -Name $TrustedPesterModulePath -Force -PassThru)
$expectedPesterRoot = [IO.Path]::GetFullPath((Split-Path -Parent $TrustedPesterModulePath)).TrimEnd('\')
if ($pesterModules.Count -ne 1 -or
    $pesterModules[0].Version.ToString() -cne '3.4.0' -or
    -not [StringComparer]::OrdinalIgnoreCase.Equals([IO.Path]::GetFullPath($pesterModules[0].ModuleBase).TrimEnd('\'), $expectedPesterRoot)) {
    throw 'Blueprint v1.0.0 requires exactly one digest-pinned Pester 3.4.0 module from the attested root.'
}
$pesterCommands = @(Get-Command -Name 'Pester\Invoke-Pester' -CommandType Function -All -ErrorAction Stop)
if ($pesterCommands.Count -ne 1 -or $pesterCommands[0].Module.Path -cne $pesterModules[0].Path) {
    throw 'Invoke-Pester did not resolve uniquely to the imported attested module.'
}
$result = & $pesterCommands[0] -Script '.\OperationsBlueprint.Tests.ps1' -PassThru
$expectedTestCount = 553
if ($result.TotalCount -ne $expectedTestCount -or
    $result.PassedCount -ne $expectedTestCount -or
    $result.FailedCount -ne 0 -or
    $result.SkippedCount -ne 0) {
    throw "Operations blueprint validation failed: total=$($result.TotalCount), passed=$($result.PassedCount), failed=$($result.FailedCount), skipped=$($result.SkippedCount), expected=$expectedTestCount"
}
```

The exact committed count is updated only after the test set freezes and is part of the release gate: zero discovery, a missing test, any failure, any skip, an absent external tool pin, or a hash mismatch is not green. The suite tests the public blueprint only. Fixture-backed runs use an explicit test profile and cannot emit a production validation, authorization, or buying state. The suite does not prove tenant permissions, Graph lifecycle support, Intune convergence, evidence-store custody, a production Terraform plan, a hardware result, an alert delivery, or authorization to act.

## Activation gates

Production remains blocked until all of these statements are true:

- The private tool registry has no unresolved required selection and no unpinned production dependency.
- Repository rules, independent review, signed provenance, protected environments, and plan/apply separation are enforced.
- Source review remains non-executable; validation runs only from a human-pinned commit on a disposable, credential-free, network-denied runner with externally pinned and verified Pester/Node/Ajv toolchains.
- Terraform state and immutable evidence use separate custody boundaries.
- The Intune ownership map assigns one production writer to every setting, app, script, compliance rule, update policy, and assignment.
- Every Intune object type has one selected transport owner; Graph writes are bounded to the approved ring and independently read back, while Entra and Azure resources use their distinct readback planes. HTTP success alone is not acceptance.
- Pilot and production promotion records resolve to the required playbook gates, evidence releases, verdicts, and rollback packages.
- Every write resolves to a trusted package-verification record, an expiring single-use authorization, an authoritative ledger-attested authorization-consumption record, bounded and independently read target membership, an exact independent-readback policy, and the last verified prior rollback state.
- Leadership claims resolve to current, comparable evidence with coverage, missingness, uncertainty, and limitations preserved.
- Direct identifiers and low-count cohorts cannot enter the public repository or leadership output.
- All seven bench-only integration scenarios have retained, independently reviewed results.
- Monitoring detects review responses, drift, stale evidence, expired exceptions, fleet-health changes, and monitor failure.

## Change and release rule

Do not modify `v2.0.1/` to activate this blueprint. Implementation-only changes advance the blueprint or private binding version. A change to the portable method or schemas requires a complete new qualification-contract release. A binding change that affects measurement may stale existing evidence even when the portable contract version does not change.
