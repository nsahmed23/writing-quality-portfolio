# Private activation checklist

**Status: HOLD**

**Document type:** Public, non-normative checklist for a private production activation record

**Applies to:** Operations Blueprint v1.0.0 and the byte-immutable Laptop Qualification Program v2.0.1

This file says what must be completed in the organization's private control-plane repository before activation. It intentionally contains no person names, tenant details, group identifiers, endpoint addresses, credentials, secrets, evidence, or production configuration. Complete values and evidence references belong only in the access-controlled private activation record.

Nothing in this checklist changes the portable qualification contract or authorizes a pilot, deployment, verdict, exception, or purchase. Do not edit `../../v2.0.1/` to satisfy a checklist item. A contract correction requires a complete new release.

## Fail-closed rule

The public blueprint remains `HOLD`. Missing, stale, unknown, expired, mismatched, unverified, or inaccessible activation evidence cannot be treated as approval. A required item cannot be marked not applicable. The optional Fabric decision is the only choice that may be `NOT_SELECTED`, and that choice still requires an approved architecture decision record.

Each private checklist item must contain:

- the control and item identifier from this document;
- one accountable role and one responsible role bound to approved enterprise identities;
- an independent verifier identity that is not the responsible identity;
- immutable evidence references, including the tested revision and observed timestamp;
- an approval timestamp, expiration or review date, and revocation status;
- the exact checklist state and any blocking reason;
- a rollback or withdrawal runbook reference.

Use only these private checklist states:

| Checklist state | Meaning |
|---|---|
| `OPEN` | Required work or evidence is absent. Overall activation remains `HOLD`. |
| `EVIDENCE_READY` | The responsible role supplied immutable evidence. It has not been independently verified. |
| `VERIFIED` | A separate verifier reproduced or directly inspected the acceptance evidence. |
| `APPROVED` | The accountable role approved the verified evidence within its validity window. |
| `BLOCKED` | A failed control, conflict, risk, or unavailable dependency prevents progression. Overall activation remains `HOLD`. |

`APPROVED` is not permanent. Expiration, revocation, identity drift, configuration drift, failed monitoring, or a changed dependency returns the item to `OPEN` or `BLOCKED` and returns the private blueprint to `HOLD`.

## Exact activation states

Checklist states, qualification verdicts, and activation workflow states are different. Do not substitute one for another. The request-state labels below are deterministic private workflow projections over canonical records, not caller-supplied status strings and not additional portable-contract verdicts.

| Scope | Exact state | Canonical proof | Meaning |
|---|---|---|---|
| Tool registry | `HOLD` | `activation-record` with `state: HOLD`, or any blocking control | The control plane is not privately bound or has a blocking control. This is the current state. |
| Tool registry | `ACTIVE` | Current `activation-record` with `state: ACTIVE` | The private control plane is operational. This does not qualify a laptop or authorize a pilot. |
| Activation request | `BLOCKED` | One or more semantic validator reason codes; no valid current write authorization | A prerequisite, authorization, revision, scope, readback, or control failed. No write or enrollment may proceed. |
| Pilot request | `PILOT_WRITE_AUTHORIZED` | Current, unconsumed `write-authorization-record` for `PILOT`, backed by the typed Phase 2 approval, Phase 3 provisional verdict, pilot authorization, executable stop set, rollback, reviewed plan, verified package, exact object/target set, and approvals | The one bound pilot operation may proceed; readback is still pending. |
| Pilot request | `PILOT_ACTIVE` | Matching `write-operation-record` plus independently verified `readback-record` for the pilot authorization | The authorized pilot write completed and independent Graph readback matched the exact revision, scope, assignment, membership, and device state. |
| Production request | `PRODUCTION_WRITE_AUTHORIZED` | Current, unconsumed `write-authorization-record` for `PRODUCTION`, additionally bound to the issued semantic validation, decision claim, render manifest, rollout monitor, Phase 5 verdict, and procurement envelope | The one bound production operation may proceed; readback is still pending. |
| Production request | `PRODUCTION_ACTIVE` | Matching `write-operation-record` plus independently verified `readback-record` for the production authorization | The authorized production write completed and independent Graph readback matched the exact revision, scope, assignment, membership, and device state. |

Every write request binds a composite, identity-backed approval set to the exact reviewed plan digest and target scope. Pilot requires distinct principals for `ROLE_PROTECTED_ENVIRONMENT_APPROVER`, `ROLE_INTUNE_CHANGE_APPROVER`, `ROLE_QUALIFICATION_AUTHORITY`, and `ROLE_PRIVACY_APPROVER`; production also requires `ROLE_PROCUREMENT_APPROVER`. A role label, duplicate principal, approval on another plan or scope, expired approval, or self-approval is `BLOCKED`. The request also binds the managed object type to the private transport-ownership record. `msgraph-terraform-provider` is the default transport; `microsoft-graph-write` requires a separately approved, unexpired transport-exception record.

The allowed transition is:

```text
HOLD
  -> ACTIVE control plane
  -> PILOT_WRITE_AUTHORIZED
  -> PILOT_ACTIVE
  -> PRODUCTION_WRITE_AUTHORIZED
  -> PRODUCTION_ACTIVE
```

Any failed prerequisite or readback produces `BLOCKED`. Any control failure or stale private binding returns the control plane to `HOLD`. `PASS`, `QUALIFY`, and `QUALIFY_WITH_CONDITIONS` are upstream gate or verdict values; they are never substitutes for an activation state.

## Private identifier and endpoint register

Create a private, encrypted register and bind every reference below before any production credential is issued. Store only opaque `private://` references in public material.

- [ ] `ID-001` — Entra tenant ID, approved tenant boundary, and tenant-policy revision are recorded privately.
- [ ] `ID-002` — Azure management-group, subscription, resource-group, region, and environment identifiers are recorded privately.
- [ ] `ID-003` — Private repository, repository ID, default branch, ruleset IDs, CODEOWNERS team IDs, and protected-environment IDs are recorded privately.
- [ ] `ID-004` — Plan, apply, authorization-ledger write, authorization-ledger readback, Graph write, Intune Graph readback, Entra directory Graph readback, Azure Resource Manager readback, evidence-ingestion, evidence-release, monitoring, signing, and rendering workload identity IDs are recorded privately.
- [ ] `ID-005` — Every federated credential issuer, audience, subject, repository/environment restriction, credential ID, and expiration/review date is recorded privately.
- [ ] `ID-006` — Human approval group object IDs, membership owners, access-review policy IDs, PIM policy IDs, and break-glass group IDs are recorded privately.
- [ ] `ID-007` — Intune scope-tag IDs, role IDs, target-group IDs, Autopilot profile IDs, enrollment restriction IDs, update-ring IDs, and Multiple Administrative Approval policy IDs are recorded privately.
- [ ] `ID-008` — Every managed Microsoft Graph resource path, API version, provider resource type, permission, and readback path is recorded privately.
- [ ] `ID-009` — Terraform state account/container IDs, evidence landing/quarantine/release store IDs, Key Vault/key IDs, private endpoints, private DNS zones, and retention-policy IDs are recorded privately.
- [ ] `ID-010` — SysTrack, ServiceNow, survey, procurement, vendor-feed, alert, and decision-renderer endpoint or integration IDs are recorded privately.
- [ ] `ID-011` — If selected, Fabric workspace, capacity, OneLake/lakehouse, semantic model, gateway/private-link, and Power BI workspace IDs are recorded privately.
- [ ] `ID-012` — No secret value, token, certificate private key, tenant identifier, production endpoint, evidence object, employee identifier, or group membership is present in the public repository or CI logs.

Acceptance evidence: an independent verifier resolves every private reference, confirms it belongs to the approved boundary, and verifies that deleted, disabled, expired, or duplicate bindings produce `BLOCKED` rather than fallback behavior.

## RACI and identity separation

Bind each role to a private group or workload identity. The same human may be consulted or informed across lanes, but the private access model must prevent one principal from producing, changing, approving, and deploying the same outcome.

The canonical public `ROLE_*` identifiers in `control-matrix.json#/roleCatalog` are the only accepted control-bound role vocabulary. The private role-binding record maps each exact role ID to a principal and is independently read back. Free-text aliases do not satisfy a control, and changing the frozen role/control policy requires a reviewed blueprint version and digest. The Responsible and Accountable columns below use those exact IDs; Consulted and Informed are advisory functions and do not grant approval or write authority.

| Decision or operation | Responsible | Accountable | Consulted | Informed | Required separation |
|---|---|---|---|---|---|
| Contract release and immutable-tree verification | `ROLE_CONTRACT_RELEASE_OWNER` | `ROLE_QUALIFICATION_GOVERNANCE_APPROVER` | Software supply-chain owner; independent verifier | Program stakeholders | Release author cannot independently verify or approve the same material correction. |
| Device evidence collection | `ROLE_DEVICE_EVIDENCE_OWNER` | `ROLE_EVIDENCE_CUSTODY_OWNER` | Pilot privacy owner; endpoint security tooling owner | Qualification authority | Collector cannot approve, overwrite, or delete a released evidence object. |
| Evidence validation and release | `ROLE_CONTRACT_VALIDATION_OWNER` | `ROLE_EVIDENCE_CUSTODY_OWNER` | Qualification test owner; pilot privacy owner | Qualification authority | Evidence producer cannot be sole validator, custodian, or verdict approver. |
| Threshold, reserve, and test-plan freeze | `ROLE_QUALIFICATION_TEST_OWNER` | `ROLE_QUALIFICATION_AUTHORITY` | Security approver; privacy owner; persona owner | Procurement authority | Candidate-result viewers cannot change frozen constants in place. |
| IaC composition and plan | `ROLE_IAC_CONFIGURATION_OWNER` | `ROLE_IAC_PLATFORM_APPROVER` | IaC security owner; Graph automation owner | IaC operator | Plan identity is read-only and differs from apply identity. |
| IaC apply | `ROLE_IAC_APPLY_OPERATOR` | `ROLE_PROTECTED_ENVIRONMENT_APPROVER` | IaC security owner; service owner | Qualification governance owner | Plan author, apply identity, and environment approver are independently bound. |
| Intune/Graph desired-state write | `ROLE_GRAPH_AUTOMATION_OWNER` | `ROLE_INTUNE_CHANGE_APPROVER` | Security approver; Windows deployment owner | Service desk | Write identity differs from readback identity and is restricted to approved objects and target rings. |
| Graph and device readback | `ROLE_ENDPOINT_TELEMETRY_OWNER` | `ROLE_QUALIFICATION_OPERATIONS_APPROVER` | Windows endpoint engineering owner | Qualification authority | Readback does not use the Graph write identity and cannot change desired state. |
| Phase 2 security approval | `ROLE_ENDPOINT_SECURITY_APPLICATION_OWNER` | `ROLE_SECURITY_APPROVER` | Application and endpoint owners | Windows deployment owner | Collector, IaC applier, and candidate sponsor cannot self-approve. |
| Pilot privacy and evidence joining | `ROLE_PILOT_PRIVACY_OWNER` | `ROLE_PRIVACY_APPROVER` | Evidence-custody owner; pilot research owner | Qualification authority | Identified data access differs from leadership aggregate access. |
| Fleet/persona verdict and arbitration | `ROLE_DECISION_PRODUCT_OWNER` | `ROLE_QUALIFICATION_AUTHORITY` | Security, privacy, endpoint, support, persona, and procurement roles | Program stakeholders | The decision-product owner assembles the recommendation; only the qualification authority can issue or arbitrate it. Evidence producers and procurement cannot issue the verdict they depend on. Conflict remains blocking. |
| Procurement lock and substitution | `ROLE_PROCUREMENT_DATA_OWNER` | `ROLE_PROCUREMENT_APPROVER` | Qualification authority; hardware lifecycle owner | Windows deployment owner | Procurement cannot inherit approval for an unknown or changed component. |
| Alert handling and rollback | `ROLE_MONITORING_OWNER` | `ROLE_QUALIFICATION_OPERATIONS_APPROVER` | Service owner; security incident owner; requalification owner | Program stakeholders | The monitor may alert only; it cannot merge, apply, enroll, close, or execute comment content. |
| Independent verification | `ROLE_INDEPENDENT_VERIFIER` | `ROLE_QUALIFICATION_GOVERNANCE_APPROVER` | Relevant control owner | Program stakeholders | Verifier did not author, execute, or approve the tested change. |

Private identity checks:

- [ ] `RACI-001` — Every role has an enterprise group or workload identity, membership owner, purpose, review frequency, expiration rule, and private reference.
- [ ] `RACI-002` — Joiner, mover, leaver, access-review, PIM/JIT, and emergency revocation procedures are tested.
- [ ] `RACI-003` — Privileged human access requires phishing-resistant MFA and time-bounded elevation where supported.
- [ ] `RACI-004` — Workload identities use short-lived federation or managed identity; no long-lived client secret is accepted.
- [ ] `RACI-005` — Negative authorization tests prove every prohibited role combination and operation is denied.
- [ ] `RACI-006` — Break-glass identities are excluded from routine automation, monitored independently, tested without exposing credentials, and require post-use review.
- [ ] `RACI-007` — All approval, token, role-assignment, sign-in, and bypass events reach the independent audit destination.
- [ ] `RACI-008` — Pilot and production approval-set tests prove the required canonical roles are present, principals are distinct for the same operation, and the set is bound to the exact plan digest, scope, validity window, and revocation state.

## Repository, branch, and protected-environment controls

- [ ] `GOV-001` — The production desired-state repository is private. The public repository contains only sanitized blueprint and review material.
- [ ] `GOV-002` — The immutable v2.0.1 subtree is pinned to commit `53c2ae12891521e4c2491528a50657b74b979e8c`, Git tree `ee333ff4ee0a02a1571bfc631d3537ba91028256`, and 15 files. Any byte change fails; corrections use a new release directory.
- [ ] `GOV-003` — The default-branch ruleset requires pull requests, resolved conversations, required checks, CODEOWNERS review, signed commits, and at least two independent approvals from the required role groups.
- [ ] `GOV-004` — Stale approvals are dismissed; the author and most recent pusher cannot satisfy independent approval; force push and branch/tag deletion are denied.
- [ ] `GOV-005` — Workflow, CODEOWNERS, policy, identity, signing, evidence-store, and IaC paths require their specialist owner review.
- [ ] `GOV-006` — Ruleset bypass is restricted to named break-glass roles, creates an immediate high-severity alert, expires, and receives independent post-event review.
- [ ] `GOV-007` — Pull requests from forks or untrusted branches receive read-only tokens, no production secrets, no OIDC production subject, and no access to self-hosted or bench runners.
- [ ] `GOV-008` — Separate protected environments exist for plan, pilot apply, and production apply. Apply environments require independent reviewers and restrict branches/tags and workload-identity subjects.
- [ ] `GOV-009` — A signed release tag and provenance attestation bind repository, commit, tree, toolchain, test results, plan digest, and signer identity.
- [ ] `GOV-010` — Direct push, force push, unsigned release, self-approval, last-pusher approval, unauthorized environment deployment, and immutable-subtree mutation tests all fail as expected.
- [ ] `GOV-011` — Pull-request source review is non-executable. A human pins the reviewed commit before a trusted-base workflow may copy it into a disposable, credential-free, network-denied validation runner; the pull request cannot select the runner, image, toolchain, command, credentials, or network policy.

## CI, verifier, and artifact-signing controls

- [ ] `SUPPLY-001` — Select the enterprise CI service and record its private runner pool, image/build, network boundary, retention, log destination, and owner.
- [ ] `SUPPLY-002` — Pin every GitHub Action or equivalent task by immutable digest/full commit and allow only approved publishers or internal actions.
- [ ] `SUPPLY-003` — Pin PowerShell Core, Windows PowerShell host build, Pester 3.4.0 for blueprint v1.0.0, Node.js, Ajv, `ajv-formats`, Terraform, every provider and module, Atmos, the policy engine, IaC scanners, signing client, collector, test pack, classification rules, CMSL tree, and HPIA package where used. A Pester major change requires a reviewed runner/API migration and dual-host requalification; it is not an in-place dependency update.
- [ ] `SUPPLY-004` — Commit and verify dependency lockfiles and checksums. Ambient path, globally installed module, network-latest, mutable tag, or unrecorded fallback resolution fails the build.
- [ ] `SUPPLY-005` — CI runs repository validation, Operations Blueprint tests, strict schema compilation, bundle-semantic tests, manifest/tree verification, PowerShell tests under both supported hosts, script/static analysis, secret scanning, IaC format/validate/lint/security/policy checks, and documentation link checks.
- [ ] `SUPPLY-006` — The immutable v2.0.1 source suite must report exactly `78 passed`, `0 failed`, and `7 skipped` under each supported PowerShell host. The seven skips are bench requirements, not passes.
- [ ] `SUPPLY-007` — Every produced plan, package, evidence-release manifest, decision packet, and promotion record receives an approved enterprise signature or attestation. Verification checks signer trust, scope, artifact digest, revocation, timestamp, and provenance.
- [ ] `SUPPLY-008` — CI job permissions are explicitly minimal. Untrusted text is treated as data and cannot become a shell command, workflow expression, tool instruction, or credential selector.
- [ ] `SUPPLY-009` — A failed, unavailable, unpinned, unsigned, revoked, or mismatched verifier produces `FAIL`, `INCONCLUSIVE`, `BLOCKED`, or `HOLD` as defined by the owning control; it never produces success.
- [ ] `SUPPLY-010` — Dependency and action update automation opens reviewable changes and cannot merge or deploy them automatically.
- [ ] `SUPPLY-011` — Pester, Node, Ajv, and `ajv-formats` resolve only from an immutable trusted-toolchain root selected outside the repository. Validation starts in a fresh `-NoProfile -NonInteractive` PowerShell process. It imports exactly one attested Pester 3.4.0 module, verifies its module base/tree, resolves exactly one module-owned `Invoke-Pester` function, and invokes the captured `CommandInfo`; ambient aliases, functions, profiles, or command-name lookups cannot supply the result. Absolute paths and expected SHA-256 values are mandatory; `PATH`, user-profile, parent-directory, Firebase, globally installed, and repository-controlled fallbacks fail closed.
- [ ] `SUPPLY-012` — Every deployable application or script has a canonical package-verification record binding artifact digest, signature, signer, trust-policy revision, timestamp evidence, revocation status, verifier identity, and verification time. The plan, authorization, operation, readback, and monitor all resolve the same record and digest.
- [ ] `SUPPLY-013` — Blueprint v1.0.0 production validation runs only on a Windows runner whose toolchain boundary is a local fixed NTFS/ReFS volume. Native inspection proves per-directory case sensitivity is disabled and no reparse point exists on every ancestor/root/candidate path; unsupported, remote, case-sensitive, reparse, or unqueryable storage is rejected. The runner separately pins the Git executable and complete Git runtime tree; the Node executable and complete native-runtime tree with both portable full-content and native held-guard digests; Ajv and `ajv-formats` entry points; their complete package roots; the complete Node dependency tree; and a fixed external working directory. The external Git and Node/runtime/package roots, their namespaces, and the working directories are read/execute-only and cannot be created, renamed, deleted, or modified by the runner identity or any untrusted principal; a protected image or mount attestation, ACL verification, and approved WDAC/AppLocker policy establish those boundaries. Runtime-tree guards stay open across the child processes, prove final-handle paths and effective-token non-mutation, and validate retained contents and final state. Those guards and pre/post hashes are defense in depth, not substitutes for protected namespace immutability. Git and Node run from trusted external directories with closed `PATH` and loader environments; Git also uses a closed command grammar with no lazy fetch, signatures, filters, replace objects, grafts, shallow history, helpers, or network. Exact module resolution and Node `process.execPath`/working-directory identity are verified, every unapproved Git/config/helper/trace or Node/native-loader environment variable is rejected, and helper-created environment or working-directory state is restored after successful and failed invocations. Schema `PRODUCTION` is the default and has no fallback; explicit `TEST` output is non-authoritative, non-promotable, and cannot satisfy this control.
- [ ] `SUPPLY-014` — Before activation leaves `HOLD`, decompose the validator, operations schema, and test suite into review-source modules with one responsibility each. A separately protected and version-pinned deterministic packer consumes an exact ordered source manifest, rejects extras and reparse paths, records each source path and SHA-256 boundary, emits UTF-8/LF/no-BOM output with no timestamps, regenerates the committed single-file runtime bundle, and byte-compares it in protected CI. Production executes only that verified packed bundle; runtime dot-sourcing or discovery of modules is prohibited. The attested source manifest, packer identity/digest, packed-artifact digest, and byte-comparison result are required activation evidence.

## Identity-governance root, role binding, and freshness controls

- [ ] `IDENTITY-001` — A controlled root ceremony creates one canonical `identity-governance-root-authority-record` with an ordered authority-key set, immutable SPKI digests, canonical key-custodian principals, signed root subject, revocation evidence, chronology, and independently attested readback. The record and its artifacts are stored in the approved private authority boundary.
- [ ] `IDENTITY-002` — Root quorum is at least two and is distinct by both canonical custodian principal and SPKI. Every signature's canonical signer equals the matched key custodian. Multiple aliases or multiple keys controlled by one custodian count once, not multiple times.
- [ ] `IDENTITY-003` — The active root authority directly approves one versioned canonical role catalog and exact role-binding set for one tenant/environment. The role-binding approval, each binding, and independent role-binding readback resolve exact subjects and digests; delegated or self-approving bootstrap chains are forbidden.
- [ ] `IDENTITY-004` — Bootstrap freshness is acyclic: a root-approved `ROOT_BOOTSTRAP` policy governs only identity/role-binding readback freshness and depends on no role binding. Every operational `ROLE_BOUND` freshness policy resolves a distinct approved binding/readback chain governed by that bootstrap policy.
- [ ] `IDENTITY-005` — The private canonical principal map and separation matrix prove effective identity separation across root custodian, ceremony operator, independent root reader, role approver/reader, requester, plan reviewer, package signer/verifier, apply operator, Graph writer/reader, Azure deployer/reader, ledger writer/reader, exception authority, and verdict authority. Different display names alone are insufficient.
- [ ] `IDENTITY-006` — Authorization TTL, revocation age, readback age, exception age, and policy validity are taken from the exact signed policy bound into the authorization and operation digests. A caller-supplied wider limit, stale policy, revoked key, or inaccessible revocation/readback source produces `BLOCKED`.

## OIDC, Terraform, Atmos, and backend controls

- [ ] `IAC-001` — The private repository records exact Terraform, provider, module, and Atmos versions and digests; `.terraform.lock.hcl` is verified for every approved execution platform.
- [ ] `IAC-002` — Atmos organization, environment, ring, persona, and candidate layers render deterministically into a canonical `atmos-stack-render-record` with ordered source refs/digests, declared and used override keys, resolved non-secret output digest, affected components, secret-scan and policy results, renderer version, and render time. The reviewed plan and rollout monitor bind the exact record/digest; undeclared overrides, secret values, unresolved inheritance, or two renders with different digests produce `BLOCKED`.
- [ ] `IAC-003` — Plan and apply use separate Entra workload identities and separate federated credentials. Plan has read-only discovery/plan permissions; apply has only the approved resource and Graph write permissions.
- [ ] `IAC-004` — Each federated credential is restricted to the exact private repository, protected environment, audience, and approved branch/tag pattern. Pull-request subjects cannot obtain apply tokens.
- [ ] `IAC-005` — The reviewed binary plan is bound to commit, Terraform/Atmos/provider locks, tenant, subscription, variables digest, observed-state snapshot, target ring, desired-state digest, plan expiration, and plan SHA-256.
- [ ] `IAC-006` — Apply consumes the exact reviewed plan without rerendering or replanning. A changed commit, variable, target, identity, state snapshot, digest, or expired plan produces `BLOCKED`.
- [ ] `IAC-007` — Terraform state uses a private backend separate from Safe evidence, Restricted evidence, and public source. It uses Entra authorization, private networking, encryption, blob lease locking, version recovery, soft delete, diagnostic logs, and tested restore.
- [ ] `IAC-008` — Shared-key access and public network access are disabled for the state backend. No evidence payload, endpoint telemetry, secret value, or direct employee identifier is stored in state or plan output.
- [ ] `IAC-009` — State readers, state writers, backup/restore operators, plan identity, and apply identity are least-privilege and independently reviewed.
- [ ] `IAC-010` — Policy-as-code rejects public storage, shared-key access, missing diagnostics, missing retention, broad Owner/Contributor grants, wildcard Graph scope, unrestricted federation, absent private endpoints, and unapproved regions/resources.
- [ ] `IAC-011` — Scheduled drift plans use `-detailed-exitcode` or equivalent: no drift is recorded, detected drift opens a controlled record and produces `HOLD`, and execution/tool failure alerts separately from no drift.
- [ ] `IAC-012` — State-lock contention, restore, provider-upgrade, module-upgrade, Atmos-render determinism, plan-expiration, and rollback-to-prior-signed-plan tests are retained.
- [ ] `IAC-013` — Immediately before apply, an attested, expiring, single-use write-authorization record binds `authorizationNonce`, `maxUses: 1`, `authorizedOperationId`, stage, reviewed plan, verified package, desired-state revision, managed-object set, writer identity, exact approval set, target scope, separate membership-rule and assignment-filter refs/digests, and an authoritative `consumptionLedgerRef`, `consumptionLedgerPolicyRef`, and `consumptionLedgerPolicyDigest`. Authorization issuance follows plan and approval; the write follows issuance and atomically reserves and consumes the nonce in that ledger.
- [ ] `IAC-014` — A canonical, ledger-authority-attested `authorization-consumption-record` binds the exact authorization ID/digest/nonce and authorized operation; ledger/policy/authority; managed-object-set digest; `maxUses: 1`; `authorizationUseCount: 1`; monotonic `consumptionLedgerSequence`; previous-entry and resulting ledger digests; `replayCheckStatus: NOT_REUSED`; atomic-commit evidence; `consumedAt`; and independent-readback policy. A caller-supplied record index is not replay proof. Duplicate consumption, ledger rollback or broken chain, expiration, revocation, changed package, changed plan, changed writer, changed object set, target expansion, stale membership, or approval issued after the write produces `BLOCKED`; the operation and independent readback resolve that exact consumption record and digest.
- [ ] `IAC-015` — Each applied resource plane is read back through its independent observer: Intune Graph for Intune objects, directory Graph for Entra objects, and Azure Resource Manager for Azure, Key Vault, and backend resources. Missing any applicable plane is `BLOCKED`.
- [ ] `IAC-016` — Select an authoritative transactional authorization-consumption ledger and separately permissioned read-only observer. Pin ledger/API/schema and authority keys; atomic compare-and-set semantics; monotonic previous-entry chain; commit-attestation format; consistency/freshness; retention/audit; high availability; backup/restore; and fork, replay, deletion, rollback, and split-brain detection.
- [ ] `IAC-017` — Ledger writer, ledger reader, Graph writer, Graph reader, apply operator, requester, and approval authorities use distinct least-privilege short-lived identities. Loss of quorum, uncertain commit, failed independent observation, restore to an earlier sequence, broken chain, or identity overlap blocks endpoint mutation and invokes the approved recovery path.
- [ ] `IAC-018` — Every applicable Azure apply produces a canonical `azure-deployment-operation-record` bound to the same tenant/environment, reviewed plan, immutable artifact, deployer identity, target, write authorization, pre-mutation consumption record, operation result, and independent Azure Resource Manager readback. Expected and observed values have separate provenance; a caller cannot self-attest convergence.

## Microsoft Graph and Intune activation controls

Intune is the sole production enforcement plane. Ansible remains bench-only or limited to explicitly approved non-Intune-owned settings.

- [ ] `INTUNE-001` — Each app, script, setting, compliance policy, security policy, update policy, Autopilot object, and assignment has exactly one writer and one owning tool.
- [ ] `INTUNE-001A` — The private `objectTypeOwnership` record is non-empty and assigns every managed Intune object type to exactly one transport. The Microsoft Graph Terraform provider is the default; direct Graph requires a named owner, bounded scope, reason, compensating control, expiry, closure evidence, and no overlap. Runtime transport guessing or fallback is forbidden.
- [ ] `INTUNE-001B` — Group Policy, Configuration Manager/co-management, Defender security-settings management, Windows servicing, OEM management, Ansible, portal/manual paths, and emergency endpoint automation each have an explicit private disposition: disabled, migrated, or assigned a named non-overlapping field and scope. Conditional Access is separately owned and may consume compliance signals but may not become endpoint configuration or qualification authority. An absent inventory, ambient writer, or overlapping field is `BLOCKED`.
- [ ] `INTUNE-002` — Intune custom roles, built-in roles, scope groups, scope tags, assignment filters, target groups, and administrative-unit boundaries are privately enumerated and independently read back.
- [ ] `INTUNE-003` — Multiple Administrative Approval is configured for every supported protected resource type, with an approver group separate from requesters and automation identities.
- [ ] `INTUNE-004` — For any required resource type not covered by Multiple Administrative Approval, an approved compensating design uses protected-environment approval, least-privilege app permissions, bounded target scope, independent readback, expiration, and audit. Unsupported or unapproved coverage remains `HOLD`.
- [ ] `INTUNE-005` — Graph write and readback applications have separate identities and permissions. The readback identity has no mutation permission.
- [ ] `INTUNE-006` — Every used Graph endpoint has a private qualification row recording resource type, `v1.0` or `beta`, method set, permission, provider resource type, schema revision, create/read/update/delete behavior, import identifier, refresh behavior, ETag/concurrency behavior, pagination, readback projection, rollback, and owner.
- [ ] `INTUNE-007` — Every provider/endpoint pair passes create, import, no-change plan, controlled update, drift detection, readback, and delete/rollback tests in a non-production tenant or isolated scope.
- [ ] `INTUNE-008` — A `beta` endpoint requires a named exception owner, reason, risk, compensating control, API/schema pin, expiry, and requalification trigger. Silent fallback between API versions is forbidden.
- [ ] `INTUNE-009` — Graph clients honor `Retry-After`, use bounded exponential backoff with jitter, record request/correlation IDs, distinguish partial success, and stop at an approved retry-count and wall-clock budget. Exhaustion produces `BLOCKED` and an alert.
- [ ] `INTUNE-010` — Successful write status remains pending until independent read-after-write returns a body and matches desired-state revision, exact target scope, object fields, assignments, and device state.
- [ ] `INTUNE-011` — Portal/manual drift, assignment expansion, target-group change, provider drift, unknown device identity, or duplicate writer triggers `HOLD` and the applicable rollback.
- [ ] `INTUNE-012` — The exact signed package digest is promoted unchanged through compatibility, lab, authorized pilot, persona-qualified rollout, and production. Rerendering between rings is forbidden.
- [ ] `INTUNE-013` — Pilot and production target ceilings are numeric, privately approved, and tested. An over-broad group, empty exclusion, dynamic-membership surprise, or unknown scope produces `BLOCKED` before write.
- [ ] `INTUNE-014` — Rollback unassigns the affected revision, restores the prior signed revision and scope, reads back the result, and opens the required incident/change record.
- [ ] `INTUNE-015` — Activation requests bind `managedObjectType`, selected writer tool, transport-ownership record and digest, and selection status. A direct-Graph selection additionally binds a current exception record; changed ownership or expiration invalidates authorization.
- [ ] `INTUNE-016` — The write authorization's target-population binding and its typed directory-readback record bind observed count, approved numeric maximum, exclusions, static/dynamic mode, group rule and assignment-filter refs/digests, an independently acquired membership snapshot, and the canonical record validity window. Caller-supplied counts, unresolved exclusions, unbounded dynamic rules, stale readback, or any ceiling breach block the write.
- [ ] `INTUNE-017` — Rollback binds the last independently verified prior revision, signed package, exact membership, prior readback, immutable rollback artifact and attestation, and post-rollback readback policy. The new revision cannot serve as its own rollback target.
- [ ] `INTUNE-018` — Pilot authorization resolves a typed, current operations-layer Phase 2 approval record and the Phase 3 `provisionalLabVerdict` inside the applicable portable `verdict-record`, plus their digests, manifest/test-plan/threshold-policy/evidence-release bindings, executable stop-condition set, and rollback record. Caller-supplied status labels cannot satisfy a gate.

## Evidence stores and Restricted-output blocker

- [ ] `DATA-001` — Select and approve the private evidence-store implementation. Public GitHub, ordinary CI artifacts, Terraform state, and user-profile folders are not evidence stores.
- [ ] `DATA-002` — Safe and Restricted custody use separate storage accounts or equivalently isolated boundaries, identities, keys, networks, access policies, retention, logs, and release workflows.
- [ ] `DATA-003` — Each boundary has separate landing, quarantine, validation, and immutable release zones. Promotion verifies file hashes, manifest completeness, collector/test-pack/classification bindings, semantic validity, malware policy, signature, and authorization.
- [ ] `DATA-004` — Storage uses default-deny networking, private endpoints, Entra-only access, disabled shared keys/public access, approved encryption and key rotation, versioning, immutable retention, delete protection, audit export, and tested restore.
- [ ] `DATA-005` — The collector identity can write only to landing; it cannot approve, promote, overwrite, or delete a released object. Release and read identities are separately scoped.
- [ ] `DATA-006` — Restricted evidence cannot enter the Safe boundary, public source, public review, ordinary analytics workspace, email/chat attachment flow, or unapproved CI log/artifact.
- [ ] `DATA-007` — Every release signature binds manifest digest, every object version/digest, bundle mode, collector digest, classification digest, test pack, validation result, custodian, and release timestamp.
- [ ] `DATA-008` — Retention, legal hold where required, deletion authority, recovery-point objective, recovery-time objective, and restore frequency are numerically approved in the private record.
- [ ] `DATA-009` — Read, write, promote, sign, copy, export, denied access, overwrite, delete, retention, key, and policy events reach an independently protected audit destination.

### Blocking risk: Restricted collector final-output ACL and path

`Get-EvalEvidence.ps1` accepts an arbitrary `OutputRoot` and defaults it to the current user's Desktop. Its final bundle directory is created directly beneath that root. The release secures certain temporary directories, but it does not establish and verify a private ACL on the final Restricted bundle directory before all final writes. An authorization reference labels Restricted collection; it does not make the destination private.

- [ ] `DATA-010` — Record `RESTRICTED-FINAL-OUTPUT-ACL` as an open blocking risk. Current state is `BLOCKED`; overall activation remains `HOLD`.
- [ ] `DATA-011` — Resolve the risk in a new collector release or an independently reviewed, signed private launcher. Do not patch v2.0.1 in place.
- [ ] `DATA-012` — The accepted implementation must resolve and validate the final absolute path, require an approved local fixed-volume private staging root, reject remote/device/provider-qualified/alternate-data-stream/reparse traversal, establish least-privilege ACLs before sensitive writes, verify owner and ACL after every transition, and atomically promote only to an approved Restricted ingestion location.
- [ ] `DATA-013` — Negative tests cover Desktop and ordinary profile paths, inherited broad ACLs, unauthorized principal access, symlink/junction/reparse traversal, remote paths, alternate data streams, destination replacement, ACL mutation, partial failure, cleanup failure, and cross-boundary copy.
- [ ] `DATA-014` — Until `DATA-010` through `DATA-013` are independently `APPROVED`, Restricted collection and B7 Restricted activation remain `BLOCKED`. No procedural warning, ticket reference, or downstream upload compensates for plaintext sensitive files first written to an unverified final path.

## Seven real-hardware bench checks

Run on representative managed Windows bench units using the exact signed collector, approved classification digest, CMSL binding where applicable, OS image, security stack, and retained manifest. Each check must be executed, not skipped, and independently verified.

- [ ] `B1` — Non-elevated Safe run completes; protected sections are explicitly unavailable/unknown while remaining sections and the manifest survive.
- [ ] `B2` — Elevated Safe run captures the expected TPM, Secure Boot, BitLocker, VBS, driver/minifilter, and native status evidence without weakening the Safe privacy boundary.
- [ ] `B3` — CMSL-absent unit records `NOT_AVAILABLE`; the rest of the bundle and manifest remain complete.
- [ ] `B4` — CMSL-present unit uses the exact approved module path and complete-tree digest and retains full structured/raw command results or explicit per-command unknown/failure states.
- [ ] `B5` — Battery-present and battery-absent units produce correct structured states; Safe mode emits no raw battery XML.
- [ ] `B6` — Unsupported storage reliability counters remain explicitly unsupported/unknown and do not abort collection or fabricate zero values.
- [ ] `B7` — Safe and authorized Restricted runs enforce their privacy and manifest contracts end to end. Restricted execution additionally requires approved closure of `RESTRICTED-FINAL-OUTPUT-ACL`.

Bench acceptance:

- [ ] `BENCH-001` — Each result includes unit/configuration identity appropriate to its privacy boundary, baseline fingerprint, collector/test-pack/tool digests, timestamps, native statuses, errors, artifacts, hashes, and signer attestation.
- [ ] `BENCH-002` — The bench runner is isolated from untrusted pull requests, has no standing production apply permission, and is reset to the approved image between relevant cases.
- [ ] `BENCH-003` — An independent verifier reviews all seven retained manifests and artifacts. Seven skipped tests in ordinary CI cannot satisfy this gate.
- [ ] `BENCH-004` — A failed or unavailable case remains `INCONCLUSIVE`, `BLOCKED`, or `HOLD`; no synthetic mock or manual assertion converts it to pass.

## Fleet cohorts, query pack, privacy, and aggregation

- [ ] `PRIV-001` — Bind SysTrack, Microsoft Graph readback, Intune reporting, ServiceNow, survey, procurement, and vendor feeds to read-only or narrowly scoped identities and record their private endpoints, schemas, clocks/time zones, freshness limits, and owners.
- [ ] `PRIV-002` — Freeze a versioned and hashed query pack for corporate floor, agent state, performance, battery/sleep, dock, application, incident/support, repair, rollout, and requalification measurements.
- [ ] `PRIV-003` — Each query declares its canonical source, cohort reference, persona/region/work-pattern strata, observation window, baseline fingerprint, inclusion/exclusion rules, join key, aggregation, missingness, expected coverage, freshness, and evidence output.
- [ ] `PRIV-004` — Candidate, incumbent, sibling/alternative, pilot, and production cohorts are mutually understood, reproducible, and protected against duplicate devices, changing role identity, silent membership drift, volunteer-only selection, and unapproved dynamic-group expansion.
- [ ] `PRIV-005` — The privacy owner approves numeric minimum cohort/aggregation floors, low-count suppression, permitted joins, pseudonymization, retention, access, geography, and secondary-use rules in the private plan.
- [ ] `PRIV-006` — Device-to-employee joins occur only inside the approved Restricted boundary. Safe outputs and leadership views contain no direct identifier, reversible join key, profile path, or low-count disclosure.
- [ ] `PRIV-007` — Aggregates report unit count, run/window count, median, range or percentile spread, run variation, coverage, missing results, exclusions, and outliers without silently joining different baselines.
- [ ] `PRIV-008` — Query-pack tests use synthetic and known-answer fixtures for joins, deduplication, window boundaries, time zones, missingness, low-count suppression, baseline separation, and source disagreement.
- [ ] `PRIV-009` — Every produced dataset and leadership value binds query-pack digest, source snapshot/cursor, cohort revision, privacy-policy revision, render revision, evidence release, and freshness timestamp.
- [ ] `PRIV-010` — Stale, under-covered, low-count, conflicting, unmapped, or partially unavailable source data remains `INCONCLUSIVE` or `HOLD`; it never becomes zero or a clean-fleet claim.
- [ ] `PRIV-011` — Every leadership link carries structured freshness evidence bound to the canonical threshold policy and current platform-baseline record. The oldest source observation, latest admission, chain generation time, maximum age, Windows/BIOS/driver/image/agent/condition/test-pack snapshot and digest, source records, and release must reconcile at render time. A caller-supplied `CURRENT` value, changed dependency, chronology error, or age breach is `NOT_READY`.
- [ ] `PRIV-012` — The semantic-input digest closes over every direct five-link record plus release members, distributions, T2 corroboration, decision-source verdicts, and quote inputs. A persona/fleet conflict binds completed `verdict-conflict` arbitration and current conditional dispositions, and a date-only condition or exception expiring on the evaluation day is treated as expired.
- [ ] `PRIV-013` — Issue a privacy-approved `fleet-portfolio-record` from the versioned query pack and join policy. Source-record, unique-device, duplicate, planned, observed, missing, excluded, stale, retired, offline, unhealthy, join-eligible, joined, unjoinable, matched, unmatched, configuration, persona-allocation, and unknown-component counts reconcile with typed method/result/evidence; low-count rows remain suppressed; every displayed lifecycle, platform, or issue fact resolves through a declared evidence release; and the selected incumbent row matches the claim-chain configuration, cohort, persona, issue evidence, window, and freshness binding.
- [ ] `PRIV-019` — Bind every portfolio, configuration cohort, and persona allocation to release-scoped planned, eligible, observed, missing, and excluded set commitments plus digest-bound private partition/subset proofs. The protected resolver independently reconstructs the planned universe from the exact cohort, join, query, privacy release, observation window, baseline snapshot, and source bindings; verifies cardinality, disjointness, completeness, parent-child subsets, configuration and persona partitions, and the unassigned set; and rejects same-count/different-membership substitution.
- [ ] `PRIV-020` — Approve the commitment and proof profile: release-scoped derived HMAC key, explicit domain separation, opaque key reference and version, canonical source-ID case/format, NFC normalization, duplicate rejection after normalization, UTF-8 length encoding and byte ordering, proof-subject schema, trusted issuer, validity, revocation, and key rotation. Raw identities and proof bytes remain Restricted and never enter public records, diagnostics, leadership packets, or review threads.
- [ ] `PRIV-021` — Production validation uses an authenticated, authorized private resolver that recomputes or verifies the protected proof subject and exact source universe. An unresolved, stale, revoked, untrusted, mismatched, or unavailable proof returns `HOLD`; a public ref/digest or synthetic test proof cannot establish production verification or authorization.
- [ ] `PRIV-014` — Ordinary validator, monitor, CI, and renderer diagnostics contain only stable reason codes, bounded non-sensitive context, and one-way aliases. Full private canonical references, principals, tenants, devices, raw payloads, and restricted values reach only an access-controlled diagnostic sink with approved retention and audit.
- [ ] `PRIV-015` — The decision renderer applies context-aware Markdown, HTML, URL, and CSV encoding; rejects active HTML/script, control characters, unsafe schemes/domains, overlong fields, and spreadsheet formulas; and retains adversarial test vectors for links, markup, bidirectional/control text, delimiters, and formula prefixes.
- [ ] `PRIV-016` — Test fixtures run only under an explicit test profile and use a private fixture namespace. Production/default validation rejects `fixture://`, local synthetic attestations, and test-only states; no test result is promotable or labeled as a production validation, authorization, or buying action.
- [ ] `PRIV-017` — Every published packet has a canonical `render-manifest-record` binding the exact semantic validation/input digest, claim chain, decision claim, source-record set, renderer release/version, template digest/version, render mode, output artifact/digest/format, context-encoding and safe-link policies, privacy release, adversarial security-test PASS, generating identity, and generation time. Manual outcome overrides are forbidden, and the leadership render manifest is not interchangeable with the Atmos stack-render manifest.
- [ ] `PRIV-018` — Every `business-impact-record` selects exactly one branch. `COST_DELTA` retains current commercial inputs and currency math; `NON_PRICE_EFFECT` retains metric/unit/direction, denominator, window, distribution, coverage, limitations, sources, and freshness; `NOT_MEASURED` retains the controlled no-claim code, bounded reason, decision impact, time, assumptions, and current commercial quote basis, but contains no calculated or evidenced effect. Cross-branch measured-effect fields or invented positive benefit are invalid; the separately required quote basis does not become a measured outcome.

## Fabric and leadership-view decision

- [ ] `FABRIC-001` — Approve an architecture decision record with exact decision `SELECTED` or `NOT_SELECTED`, owner roles, rationale, cost, data classification, failure behavior, exit conditions, and replacement rule. While undecided, `fabric-onelake` and `power-bi` remain `CANDIDATE` and activation remains `HOLD`.

If `SELECTED`:

- [ ] `FABRIC-002` — Record private capacity, workspace, OneLake/lakehouse, semantic-model, gateway/private-network, service identity, sensitivity-label, row/object-level security, refresh, retention, audit, and regional bindings.
- [ ] `FABRIC-003` — Fabric receives only validated copies or views from the canonical evidence store. It cannot originate T0/T1/T2 evidence, alter an evidence release, issue a verdict, authorize a gate, or become the only copy.
- [ ] `FABRIC-004` — Power BI and decision packets expose only privacy-approved aggregates and display evidence release, verdict, query-pack, cohort, freshness, and render references. Failed or stale refresh is visibly `NOT CURRENT`.
- [ ] `FABRIC-005` — Workspace access, export, build permission, sharing, low-count disclosure, lineage, refresh failure, source mismatch, and withdrawal tests pass.

If `NOT_SELECTED`:

- [ ] `FABRIC-006` — Disable Fabric/Power BI production identities and paths, retain the approved ADR, and prove the deterministic decision-packet renderer reads canonical releases without Fabric.
- [ ] `FABRIC-007` — No control, evidence, verdict, monitor, rollback, or leadership publication depends on Fabric availability.

## Durable ten-minute response monitor

- [ ] `MON-001` — Create an actual review response surface: a protected pull request or Issue with stable repository, branch, review, question, and comment identifiers. A branch file alone is not a response channel.
- [ ] `MON-002` — Select the scheduler/runtime and bind its exact version, private workload identity, source revision, network path, and owner. A branch-only scheduled workflow that is not active on the scheduler's default/protected source does not satisfy this item.
- [ ] `MON-003` — Use event-driven delivery when available plus a reconciliation poll every ten minutes. Record the scheduler's best-effort behavior and an approved detection SLO; test that a synthetic response is detected and delivered within that SLO.
- [ ] `MON-004` — Persist a durable cursor outside ephemeral runner storage. It records source, last successful poll, branch SHA, event/comment/question ID, event timestamp, observed status, delivery ID, retry count, and monitor version.
- [ ] `MON-005` — Deduplicate by immutable source event ID plus state transition. A retry must not create duplicate Issues, ServiceNow records, or notifications.
- [ ] `MON-006` — Monitor pull-request reviews/comments, Issue comments, question-ledger changes, open findings, approval changes, required-check changes, identity/ruleset drift, evidence staleness, exception expiry, vendor changes, Graph/Intune drift, and monitor health.
- [ ] `MON-007` — The monitor token is read-only for source and review data and may write only to the selected alert/workflow record. It cannot merge, approve, close, modify evidence, apply IaC, write Intune, enroll devices, or execute comment content.
- [ ] `MON-008` — Untrusted review text is treated only as data. Claude review, if selected, requires an authorized actor and explicit dispatch label/change record, runs sandboxed without production cloud credentials, and writes only a review branch or PR. Claude output never counts as approval or independent verification.
- [ ] `MON-009` — Select a primary alert channel and an independent dead-man channel. Record delivery endpoint references, severity mapping, acknowledgment owner, escalation chain, retry budget, quiet-hours rule, and delivery receipts privately.
- [ ] `MON-010` — Two consecutive missed ten-minute polls, a stale cursor, failed delivery, authorization failure, rate-limit exhaustion, malformed response, or source disagreement triggers the dead-man alert and changes the affected state to `HOLD`.
- [ ] `MON-011` — Synthetic tests prove new response, updated response, deletion/withdrawal, duplicate delivery, out-of-order event, rate limit, network failure, expired token, cursor loss/rebuild, primary-channel failure, dead-man escalation, and recovery.
- [ ] `MON-012` — Recovery reconciles from the authoritative event log before advancing the cursor. It never acknowledges unseen events merely to restore a green heartbeat.

## Alert, rollback, exception, and requalification operations

- [ ] `OPS-001` — Every control in `control-matrix.json` has a private alert rule, severity, owner, acknowledgment target, escalation, readback, rollback/withdrawal runbook, evidence output, and test record.
- [ ] `OPS-002` — Rollback references the last verified prior revision, prior signed artifact, prior membership and readback, immutable rollback artifact/attestation, and exact prior scope; execution requires authorization appropriate to urgency and independent readback afterward.
- [ ] `OPS-003` — Intune rollback covers assignment removal, prior-package restoration, device state verification, spare/device-swap path, service-desk communications, and incident/change records.
- [ ] `OPS-004` — Evidence rollback withdraws invalid releases and derived packets without deleting history; access revocation, quarantine, key response, and dependent-claim invalidation are tested.
- [ ] `OPS-005` — IaC rollback covers identity revocation, state lock/integrity incident, state restore, prior signed plan, partial apply, and reconciliation before any new apply.
- [ ] `OPS-006` — Every exception records owner, reason, compensating control, scope, expiration, evidence required for closure, approver, and monitor rule. Expiration automatically produces `HOLD`.
- [ ] `OPS-007` — Firmware, driver, Windows, security-agent, component, dock, application, procurement, tool-binding, support, incident/repair, threshold, and exception changes enter a durable trigger ledger.
- [ ] `OPS-008` — Requalification maps each trigger to dependency intersection, affected evidence, staleness, full/delta/paper tier, target ring, owner, and deadline. Unknown identity or impact cannot use the paper path.
- [ ] `OPS-009` — Product-change, vendor-advisory, telemetry, ServiceNow, procurement, Graph, and evidence feeds have heartbeat, freshness, cursor, replay, deduplication, and missed-feed tests.
- [ ] `OPS-010` — Rollback and restore exercises use synthetic or isolated targets, record recovery time and data loss against approved objectives, and do not claim production recovery from a paper walkthrough alone.
- [ ] `OPS-011` — Before production activation, approve a canonical `rollout-monitoring-record` binding the issued semantic input and decision claim; leadership render manifest; verdict/persona/procurement pointers; Git, canonical Atmos stack render, Terraform, package, ring, scope, and membership; versioned SysTrack and Graph query pack; telemetry cohort/baseline; frozen coverage and signal thresholds; owners and private alert routes; and the exact stop, rollback, and requalification records. It contains exactly one governed entry for review response, monitor/dead-man health, Intune drift, target membership, SysTrack fleet health, ServiceNow incident/repair, evidence freshness, exception expiration, vendor/product change, and IaC drift. Any omission, mismatch, expiry, missing source, under-coverage, unresolved threshold, or unapproved/unbounded `NOT_APPLICABLE` state is `HOLD`.
- [ ] `OPS-012` — Every stop condition is a resolvable executable record with signal, typed telemetry/coverage and threshold-policy pointers, operator and threshold, scope, owner, disposition, expiry, rollback/requalification action, and membership in a recomputed set digest. Prose-only, dangling, empty, changed, or expired conditions block authorization.
- [ ] `OPS-013` — Monitoring resolves typed query-pack, telemetry-baseline, coverage-policy, semantic-validation, and requalification-plan records with exact digests, release/freshness bindings, and valid chronology. A production monitor action is deterministically `BUY` or `BUY_WITH_CONDITIONS`; `DO_NOT_BUY` cannot enter rollout activation.
- [ ] `OPS-014` — Qualification evidence resolves every applicable frozen Phase 0 test definition and role/condition/baseline stratum. Every governed distribution binds the exact test-plan reference/digest and sampling-floor pointer/digest and meets the frozen unit/run floors when they exceed public defaults. Omitted planned tests, lower declared floors, partial distributions, or arbitrary arbitration text inconsistent with fleet/persona dispositions are rejected.
- [ ] `OPS-015` — The issued current-fleet portfolio contains exactly the twelve machine-policy dimension IDs and each dimension contains exactly its closed claim-metric set. Every claim resolves its released source record/digest/pointer, quantitative distribution or structured summary, denominator, coverage/missingness/exclusions, baseline/window, provenance/corroboration, tool/query-pack/artifact bindings, freshness, limitations, and requalification triggers. A generic PASS bucket, unrelated metric, duplicate, omission, or mismatched binding keeps the decision packet `NOT_READY`.
- [ ] `OPS-016` — Fleet coverage is recomputed from counts and the frozen Phase 0 minimum-telemetry threshold; every rendered cohort meets the governed privacy aggregation floor. Count equality is insufficient: the authenticated private population-proof resolver must verify exact planned/eligible/observed/missing/excluded commitments and every partition/subset proof before a production leadership chain can become ready.

## Final activation gate

The private activation authority may change the private tool-registry state from `HOLD` to `ACTIVE` only when all conditions below are true:

- [ ] Every required checklist item is `APPROVED`; no item is `OPEN`, `EVIDENCE_READY`, `VERIFIED`, or `BLOCKED`.
- [ ] Every public `REQUIRED_SELECTION` and `CANDIDATE` binding has an approved private selection or an approved removal/`NOT_SELECTED` decision, and the private registry has no unresolved blocking decision.
- [ ] Every accountable role, responsible role, independent verifier, human group, workload identity, tenant/resource boundary, endpoint, and alert channel is privately bound and current.
- [ ] Branch/ruleset, protected-environment, OIDC, plan/apply, state, policy, signing, evidence custody, Intune/Graph, privacy, monitor, alert, rollback, and requalification negative tests pass.
- [ ] Trusted-runner isolation, external toolchain hashes, package verification, single-use authorization replay denial, target-ceiling/readback, renderer injection, diagnostic redaction, and test/production namespace separation negative tests pass.
- [ ] `RESTRICTED-FINAL-OUTPUT-ACL` is closed in a new signed implementation and independently verified.
- [ ] B1 through B7 were executed on representative real hardware and their signed evidence was independently approved.
- [ ] The Fabric decision is exactly `SELECTED` or `NOT_SELECTED`, with its applicable checks approved.
- [ ] The ten-minute monitor has a durable cursor, primary delivery, independent dead-man path, synthetic response test, and two-missed-poll test.
- [ ] The complete private activation record is signed, immutable, time-bounded, and approved by the qualification governance owner and independent security/privacy authorities.

After the control plane becomes `ACTIVE`, each candidate still begins with no deployment authority. Pilot and production transitions must be evaluated separately through the exact activation states above. A control-plane `ACTIVE` state, successful Graph HTTP status, green CI run, intact hash, leadership view, or Claude review cannot by itself qualify a candidate or authorize deployment.

## Current disposition

```text
Public blueprint activation: HOLD
Private identity bindings: OPEN
Private tenant and endpoint register: OPEN
Enterprise CI/apply path: OPEN
Private evidence store: OPEN
Restricted final-output ACL/path risk: BLOCKED
Graph endpoint lifecycle qualification: OPEN
Intune RBAC/scope tags/MAA: OPEN
Seven real-hardware bench checks: OPEN
Fleet query/cohort/privacy pack: OPEN
Fabric decision: OPEN
Ten-minute response monitor: OPEN
Alert, rollback, and dead-man evidence: OPEN
Result: HOLD
```

These are honest public states, not blanks to be inferred as success.
