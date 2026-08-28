# Governance and IaC Operating Model

**Status:** VALIDATED BLUEPRINT / PRODUCTION ACTIVATION HOLD

**Blueprint release:** 1.0.0

**Portable contract:** [Laptop Qualification Program v2.0.1](../../v2.0.1/README.md)

**Audience:** Windows endpoint engineering, qualification governance, security and privacy, platform automation, procurement, support, analytics, and leadership decision owners

## 1. Operating objective

The operating model exists to produce a decision that leadership can understand quickly and audit later:

> For this measured persona and its current incumbent-fleet problems, the named candidate configuration produced these results under this protocol, so the issued verdict supports this exact buying and rollout decision under these conditions.

The leadership decision packet is the primary output. Intune, Git, Terraform, Atmos, Microsoft Graph, SysTrack, ServiceNow, the collector, and optional Fabric/Power BI services are controls and evidence paths beneath it. They do not replace the qualification authority, the five portable schemas, or the verdict record.

The public blueprint has passed its local structural and adversarial checks. Production activation is on HOLD because public source cannot establish tenant identities, private state, custody, permissions, protected approvals, tool locks, or real-hardware results.

## 2. Architecture

```text
 CURRENT FLEET                         CANDIDATE QUALIFICATION
 SysTrack telemetry                   Collector and ground truth
 ServiceNow incidents/lifecycle       Phase 2 compatibility/security evidence
 Intune/Graph observed state          Candidate + incumbent + sibling tests
 Support and procurement facts        Authorized pilot evidence
          │                                      │
          └──────────────────┬───────────────────┘
                             ▼
              Immutable, versioned evidence releases
              Provenance + baseline + coverage + hashes
                             │
                             ▼
 Persona need → incumbent issue → candidate comparison → business effect
              (first four links remain NOT_ISSUED before verdict)
                             │
         issued fleet/persona verdict + procurement envelope
                             │
                             ▼
       Complete five-link verdict-backed buying recommendation
                             │
                             ▼
                 Leadership decision packet
            Snapshot for approval + optional drill-down
                             │
                             ▼
    Git desired state → Atmos → Terraform plan → approval
                             │
                             ▼
       package verification → single-use write authorization
                             │
                             ▼
             Graph write → Intune bounded ring
                             │
                             ▼
          Graph/Intune readback + SysTrack monitoring
                             │
                   mismatch or trigger
                             ▼
                HOLD, rollback, requalify
```

## 3. Non-negotiable principles

1. **The portable contract stays portable.** Tool bindings and enterprise controls may be replaced without silently changing qualification semantics.
2. **The decision packet is derived.** It may quote an issued verdict and procurement envelope; it cannot create or strengthen either.
3. **One field has one authority.** Git desired state, Terraform state, Intune observed state, telemetry, evidence, verdicts, and procurement records are not interchangeable.
4. **Each managed field has one production writer.** Intune and its Graph write path are the sole writer for the explicitly mapped Intune-owned scope. Group Policy, Configuration Manager/co-management, Defender security-settings management, update services, OEM tooling, Ansible, portal changes, scripts, and break-glass paths must be disabled, migrated, or assigned a non-overlapping owned scope.
5. **A write is pending until readback.** A successful Terraform or Graph response is transport evidence, not proof that the intended assignment reached the intended devices.
6. **The same artifact advances.** Re-rendering, repackaging, or changing an assignment payload between rings starts a new promotion.
7. **Unknowns fail closed.** Missing, stale, mismatched, unsupported, or unowned critical state produces HOLD, FAIL, or INCONCLUSIVE as defined by the portable contract.
8. **Public source remains sanitized.** People, devices, tenants, groups, tickets, quotes, and restricted evidence are private activation data.
9. **Automation cannot self-approve.** Authors, evidence producers, protected-environment approvers, and final authorities remain separated.
10. **Every operational dependency is pinned or explicitly unresolved.** A production binding cannot contain an active “or,” ambient executable, floating provider, or unreviewed API version.
11. **Test and production namespaces never mix.** Fixture records may run only under an explicit test profile and can never produce a production-shaped authorization, buying action, or promotable validation state.
12. **Diagnostic output is privacy-bounded.** Ordinary logs carry stable reason codes and one-way aliases, never private canonical references, tenant or principal identifiers, or raw restricted values.

## 4. Source-authority map

| Information | Authoritative source | What it may prove | What it must not be used to prove |
|---|---|---|---|
| Portable method and record shape | v2.0.1 playbook and five schemas | Qualification rules and contract structure | Tenant implementation or a device result |
| Enterprise desired state | Reviewed commit in the private Git repository plus canonical Atmos stack-render record | Intended infrastructure, Intune object, assignment, and ring configuration | Actual device receipt or compliance |
| Infrastructure transition | Reviewed Terraform plan, apply attestation, and protected state | Resources Terraform manages and the state transition it performed | Endpoint performance, compliance, or user experience |
| Intune intended state | Versioned Intune/Graph object and assignment payload | What the endpoint team intended to assign | Device-side application or business outcome |
| Intune observed state | Independent Graph readback and Intune reporting | Object, assignment, and reported device state at the recorded time | Workload performance or a qualification verdict |
| Residual endpoint authority | Private ownership inventories for Group Policy, Configuration Manager/co-management, Defender security-settings management, Windows servicing, OEM management, Ansible, and emergency automation | Which explicitly bounded field and scope, if any, each channel may still change | Permission to overlap an Intune-owned field or inherit rollout approval |
| Access enforcement | Separately governed Conditional Access policy plus independent directory readback | Access-policy intent, covered identity/workload scope, and recorded access outcome | Endpoint configuration, device-side compliance truth, or qualification verdict |
| Device ground truth | Collector and signed native/vendor artifacts admitted as T0 evidence | What was present or observed on an identified configuration | Fleet prevalence without adequate sampling |
| Current-fleet performance | Versioned SysTrack query/export and cohort definition | Measured resource, experience, and stability distributions for the covered cohort and window | Causation beyond the instrumentation and comparison design |
| Incidents, repairs, and support effort | ServiceNow records and a versioned extraction definition | Recorded operational burden for the covered population and time | Unrecorded events or device performance by itself |
| Vendor support and specification | Applicable first-party vendor record admitted as T1 | Published support, limits, lifecycle, and ordered configuration facts | Installed component identity without enumeration |
| Evidence release | Immutable evidence store and release index | Admitted provenance, hashes, quality, limitations, and comparability boundary | Approval unless an applicable gate or verdict cites it |
| Qualification decision | Immutable pilot-authorization or Phase 5 verdict record | Authorized stage, fleet/persona outcome, conditions, risks, and procurement envelope | A claim outside its scope or after expiration |
| Commercial fact | Approved procurement/quote/contract system | Price, availability, terms, expiration, and orderable configuration at the recorded time | Technical qualification |
| Write-authorization consumption | Authoritative transactional authorization ledger plus distinct read-only observer | Exact nonce/operation/object-set consumption, monotonic chain, one-use state, and commit attestation | Intune success, endpoint outcome, evidence, verdict, or approval |
| Leadership view | Deterministically generated packet | A fast, traceable restatement of current records | Evidence, verdict, procurement authorization, or live device state |
| Fabric/Power BI projection | Governed private semantic model, if activated | A convenient current view and drill-down over approved projections | Replacement for immutable source records or the approved packet snapshot |

If two systems disagree, the owning authority is not selected by convenience. The mismatch is recorded, the applicable gate moves to HOLD, and the owner resolves or explicitly bounds the discrepancy.

## 5. Leadership claim chain

Each recommended persona requires five complete links.

### 5.1 Persona need

Record the persona definition, target population, workload requirement, corporate floor, approved reserve, capacity waterfall, and persona-verdict pointer. Job title and preference are not substitutes for a measured requirement.

### 5.2 Current incumbent-fleet issue

Record the incumbent configuration envelope, cohort rule, observation window, unit count, denominator, coverage, missingness, relevant baseline, and distributions. Suitable sources include SysTrack for resource/experience behavior, ServiceNow for incidents and support burden, Intune/Graph for management state, and approved procurement or lifecycle sources for age, warranty, and support.

The claim chain copies the exact released `issueStatement` through its canonical pointer and displays `DIRECT`, `CONTROLLED_DELTA`, `ASSOCIATION`, or `UNKNOWN` attribution. The statement must be no stronger than the data. A cohort association is not device-root-cause attribution. Voluntary survey responses are not a representative population by themselves.

The issue also points into an issued operations-layer `fleet-portfolio-record`. That privacy-approved projection answers the broader estate question with a versioned join policy and reconciled source-record, unique-device, duplicate, planned, observed, missing, excluded, stale, retired, offline, unhealthy, join-eligible, joined, unjoinable, matched, unmatched, and unknown-component counts plus configuration/cohort and persona allocations. Its reconciliation method, result, and evidence are explicit; arithmetic inconsistencies are invalid rather than explained away in prose. It binds the versioned fleet query pack and source releases, then resolves the exact incumbent configuration/cohort row used by this persona decision. The portfolio is a derived index, never T0/T1/T2 evidence or a substitute for the released issue record.

The frozen `MUTUALLY_EXCLUSIVE_PRECEDENCE_V1` reconciliation requires: source records = unique devices + duplicates; unique devices = stale + retired + offline + unhealthy + join-eligible; join-eligible = joined + unjoinable; joined = matched + unmatched; and configuration-cohort counts = matched devices. A device may occupy only the first applicable state bucket under the versioned join policy.

### 5.3 Candidate comparison

Record candidate, incumbent, and sibling or alternative projections from one frozen candidate manifest. Every role must cover the exact same applicable frozen condition set, protocol, baseline stratum, and test pack. Preserve unit and run counts, distributions, coverage, missing results, exclusions, uncertainty, and known limitations.

### 5.4 Business effect

The canonical `business-impact-record` has three mutually exclusive branches:

- `COST_DELTA` binds current candidate and control quote/contract sources, currency, quantity, validity, formula, calculation result, assumptions, uncertainty, and source freshness.
- `NON_PRICE_EFFECT` binds one measured metric and unit, direction, denominator, observation window, distribution, coverage, limitations, source-record set, and freshness. A preference or anecdote cannot fill this branch.
- `NOT_MEASURED` carries no measured-only fields. It records the stable `NO_MEASURED_EFFECT_CLAIM` code, bounded reason, decision impact, and recording time. The renderer maps that code to the controlled display language below.

Never translate one branch into another or invent savings, productivity, experience, support, deployment, or other benefit evidence.

- Statement: `NOT_MEASURED: No non-price business effect is claimed for this decision.`
- Assumption: `No non-price business-effect estimate is available.`
- Decision impact: `No non-price benefit may support this recommendation; only current commercial quotes and the issued verdict remain decision inputs.`

### 5.5 Recommendation

Copy the scope and conditions from the issued verdict and approved procurement envelope. Include exact configuration, eligible persona, quantity or scope, price/quote validity, rollout ring, residual risks, expiration, and requalification triggers. A procurement deadline does not upgrade incomplete evidence.

A selected persona verdict that still records `conflictsWithFleetConditions: true` cannot produce an unconditional buying recommendation. It requires complete qualification-authority arbitration with the `verdict-conflict` trigger and retained evidence. If it proceeds, the persona assignment and procurement disposition remain conditional and bind current condition records; otherwise the decision remains blocking. Date-only condition and exception expirations are exclusive: a record dated on the evaluation day is expired for decision use and must be renewed before rendering.

### 5.6 Freshness and confidence

Every link reports:

- observation window and admission time;
- evaluated-at time and applicable maximum age;
- BIOS, driver, Windows, image, agent, condition, and test-pack dependencies;
- `CURRENT`, `STALE`, or `UNKNOWN` freshness;
- provenance, directness, comparability, coverage, repeatability, missingness, and limitations;
- a confidence label derived from those visible dimensions.

“Current” is derived at the packet evaluation time; it is never accepted as a caller-supplied label. Each link binds a canonical threshold-policy pointer, an integer maximum age, the oldest supporting-source observation, the latest supporting-source admission, the chain generation time, and a canonical platform-baseline snapshot. The snapshot carries Windows build, BIOS, driver pack, corporate image, security-agent-set digest, condition-set digest, and test-pack version. The link, every supporting evidence or decision record, its immutable release, and the current baseline record must agree on the policy reference, snapshot reference, digest, and dependency status. The snapshot digest is recomputed, observation must precede admission and generation, and every source must remain inside the frozen age window at render time. Any changed dependency, ancient observation, future time, chronology error, missing source binding, or policy mismatch makes the link stale or invalid and the packet `NOT_READY`.

The semantic-input digest covers the portable-contract set, the five link values, issuance context, and their decision-source records: evidence-release members, distribution records, T2 corroboration records, decision-source verdicts, and commercial-quote inputs. The derived decision-claim payload is generated only after semantic validation and binds that validation record/digest, so it is deliberately excluded from its own input digest to avoid a hash cycle. Rollout monitoring then binds both the semantic-validation and decision-claim records/digests. Replacing and re-attesting any decision source requires a new semantic validation; refreshing only a first-hop record or `CURRENT` label cannot preserve readiness.

A recent timestamp alone is insufficient. A confidence label never overrides a verdict, floor, exception expiry, or unknown identity.

### 5.7 Packet states

| State | Meaning | Permitted use |
|---|---|---|
| `NOT_ISSUED` | Public template or no issued records | Design and review only |
| `NOT_READY` | One or more required links are missing, stale, contradictory, or blocked | Evidence-gap discussion; no approval request |
| `PILOT_DECISION_READY` | Phase 2, Phase 3, and pilot-authorization prerequisites resolve and are current | Request the bounded authorized pilot only |
| `PURCHASE_DECISION_READY` | Pilot evidence, Phase 5 dual verdicts, risks, and procurement envelope resolve and are current | Request the exact scoped buying decision |
| `WITHDRAWN` | A trigger invalidated a published packet | Historical record only; replacement required |

The renderer produces a canonical `render-manifest-record`, source index, and digest. That record binds the semantic validation and input digest, exact claim chain and decision claim, every source-record ID and digest, renderer release/version, template digest/version, render mode, immutable output artifact/digest/format, context-encoding policy, safe-link policy, privacy release, adversarial security-test result, generating identity, and generation time. `manualOverrideAllowed` is false. It must reject manual outcome prose that lacks a canonical pointer. Every value is encoded for its output context: Markdown and HTML are escaped, links are restricted to approved schemes and domains, CSV cells that could be formulas are neutralized, control characters and active content are rejected, and field lengths are bounded. The approved snapshot is immutable; a live dashboard may show newer telemetry only with an explicit “newer than decision snapshot” boundary.

### 5.8 Public validation is not authorization

The checked-in `Test-LeadershipClaimChain` function may validate the shape, lineage, freshness, and canonical references of a proposed derived input. Its strongest successful result is `VALIDATED_DERIVED_INPUT`: the input is eligible to enter the separately governed private rendering and approval process. That result is not an issued verdict, pilot authorization, procurement approval, `PILOT_DECISION_READY`, or `PURCHASE_DECISION_READY` packet.

An `ISSUED` claim chain must carry non-null `lineage.semanticValidationRef` and `lineage.semanticValidationDigest` values that resolve inside the private evidence boundary to the retained semantic-validation result for the exact chain bytes. The public `NOT_ISSUED` template deliberately leaves both values null.

The checked-in `Get-ActivationDecision` function is a fail-closed precondition and lint simulation for public review. It may expose why a proposed request would be blocked, but it is not an authorizer and cannot permit a pilot, Intune write, production rollout, or purchase. Only the private control plane, after binding real identities, protected approvals, immutable records, current evidence, and independent readback, may issue the documented packet states. The checked-in public registry remains `HOLD`, so a public validation run must remain non-authorizing even when all synthetic inputs are internally consistent.

## 6. Enterprise Windows and Intune model

Intune is the primary enforcement plane for the explicitly mapped Intune-owned scope, not the whole system of record and not an assumption that every legacy or specialist management path has disappeared. An activated design must model each layer separately, inventory Group Policy, Configuration Manager/co-management, Defender security-settings management, Windows update services, OEM firmware tooling, Ansible, portal, script, and break-glass paths, and assign every setting or artifact exactly one writer.

| Layer | Content | Primary authority | Required readback |
|---|---|---|---|
| 0. Identity and enrollment | Entra device identity, enrollment restrictions, Autopilot registration/profile, ownership | Entra/Intune desired state | Enrollment and profile assignment state |
| 1. Hardware and firmware baseline | Model envelope, BIOS/firmware policy, driver/update binding, Secure Boot/TPM requirements | Qualified manifest plus approved update/vendor binding | Collector/vendor enumeration and Intune reporting |
| 2. Platform security | Security baselines, disk encryption, VBS, endpoint protection, firewall, attack-surface controls | Versioned Intune security policy | Graph object/assignment plus reported device state |
| 3. Device configuration | Settings catalog, CSP-backed settings, certificates, VPN/Wi-Fi configuration without public identifiers | Versioned Intune configuration | Per-setting/profile status and device-side evidence where required |
| 4. Applications and agents | Signed Win32 apps, dependencies, detection, supersedence, EDR/DLP/ZTNA/VPN/management stack | Versioned package and Intune app assignment | Install/detection state, version inventory, agent-state evidence |
| 5. Compliance and access signal | Compliance rules, grace periods, actions for noncompliance, Conditional Access dependency | Intune compliance desired state; access policy remains its own authority | Compliance report and access-policy audit |
| 6. Servicing | Windows quality/feature updates, drivers, firmware, restart and deadline behavior | Approved Windows update service binding | Update reports, build/driver enumeration, failure state |
| 7. Remediation | Detection/remediation scripts and health actions | Signed, versioned Intune-managed package | Detection/remediation output and postcondition evidence |
| 8. Experience and support | SysTrack measures, incidents, repair, support effort, structured sentiment | Evidence sources, not policy assignment | Versioned exports, cohort/coverage, hashes |
| 9. Qualification and decision | Evidence releases, pilot authorization, dual verdicts, procurement envelope | Portable contract records | Semantic validation and approval references |

### Known enterprise Windows truths

- The same marketed model or SKU can contain different memory, storage, WLAN, panel, battery, or other supplier components. Enumerate the actual units and preserve component strata; model name is not component identity.
- The corporate image and security/management stack consume measurable CPU, memory, storage, and battery capacity. Persona headroom must be calculated after the measured corporate floor and approved operating reserves.
- Vendor specifications establish published configuration and support facts, not behavior under the managed enterprise image. Managed performance, battery, compatibility, and experience require direct evidence under the corporate stack.
- Persona suitability follows a measured workload and representative cohort, not job title, seniority, preference, or a generic “power user” label.
- One laptop can support engineering investigation. It cannot support a fleet-wide conclusion. Every gate-bearing class must meet its frozen unit, repetition, coverage, and representation floor.
- Dynamic metrics such as corporate floor, agent state, workload timing, sustained performance, battery, sleep, docking, and production experience require fresh contemporaneous candidate and control evidence. A prior-quarter control does not become concurrent because its nominal version still looks similar.
- Missing source output, failed collection, an empty export, unsupported counters, and permission denial are not observed zero and are never a pass. Preserve the failure state and determine whether it forces HOLD or INCONCLUSIVE.
- Enrollment, policy assignment, device check-in, reporting, and Graph consistency are asynchronous. A successful request does not mean the device is compliant or the payload is effective.
- Multiple profiles and management authorities can target the same device. Assignment order is not a governance strategy; ownership and conflict detection must be explicit.
- Group Policy, Configuration Manager/co-management, Defender security-settings management, Windows Autopatch or other update services, OEM firmware tools, and emergency scripts may remain legitimate authorities for bounded fields. Private activation must inventory each path and its workload or setting ownership, then disable, migrate, or formally isolate overlaps before Intune promotion.
- User-targeted and device-targeted settings have different evaluation and sign-in behavior. A ring definition must state which identity and context it depends on.
- Filters and dynamic membership improve targeting but can change the effective population. A qualification or pilot ring needs a retained membership snapshot and a maximum scope.
- Offline, unhealthy, retired, stale, or duplicate device records distort denominators unless the cohort rule handles them explicitly.
- Win32 applications, PowerShell scripts, remediations, and other Intune Management Extension workloads have their own execution, detection, retry, and reporting semantics. Package success is not workload success.
- Security policy, configuration policy, applications, compliance, and update policy can converge on different schedules. Readback must identify the layer and time observed.
- Windows, firmware, drivers, agent versions, and update policy are evidence dependencies. Servicing drift can invalidate an otherwise recent benchmark or pilot result.
- A new candidate and an aged incumbent differ in battery wear, thermal condition, storage wear, software tenure, and accumulated state. Comparisons must measure and stratify those confounders; “new beat old” is not proof of a platform advantage.
- Windows edition, licensing/entitlement, processor architecture, management channel, and CSP or policy applicability determine whether an intended Intune control can exist and take effect. Hardware qualification cannot inherit management compatibility from a similar SKU.
- Autopilot success depends on correct OEM/device registration, TPM attestation and firmware state, enrollment restrictions, identity and licensing, network/proxy/TLS reachability, required Microsoft service endpoints, time synchronization, and Enrollment Status Page dependencies. A profile assignment alone does not prove provisioning readiness.
- Device-side T0 capture is still required for facts that service-side reporting cannot prove, such as installed component identity or a measured workload distribution.
- Graph throttling and partial failure are expected operational cases. Respect `Retry-After`, bound retries, preserve operation IDs and errors, and never translate timeout into clean state.

## 7. Promotion rings

Ring names are implementation bindings, not additional playbook phases.

| Ring | Purpose | Entry gate | Membership rule | Exit or rollback condition |
|---|---|---|---|---|
| Compatibility | Exercise the corporate app, agent, security, and peripheral matrix | Phase 0 frozen records and bounded test units | Explicit candidate units or retained evaluated membership snapshot | Phase 2 approval, or HOLD/FAIL with removal and evidence preservation |
| Controlled lab | Run candidate, incumbent, and sibling/alternative under the same Phase 3 protocol | Current Phase 2 hard-gate approval | Frozen test-unit identities and comparable strata | Provisional QUALIFY/QUALIFY_WITH_CONDITIONS, or rollback/HOLD |
| Authorized pilot | Determine whether lab results survive representative production use | Current Phase 2 approval, qualifying Phase 3 provisional verdict, approved stop/rollback plan, immutable pilot authorization | Preselected users/devices with frozen persona, region, and work-pattern strata | Completed coverage and no unresolved stop condition, or immediate stop/rollback |
| Persona-qualified rollout | Deploy only to approved personas and exact procurement envelope | Phase 5 fleet and persona verdicts plus procurement lock | Verdict-backed eligibility and configuration identity | Sustained monitoring remains current; mismatch or expired condition returns HOLD |
| Broad production, if separately approved | Scale only where the verdict scope permits | Explicit scope in final verdict and successful prior ring | Bounded production rule with exclusions and maximum scope | Phase 6 trigger, control breach, or health threshold invokes rollback/requalification |

Every promotion carries the same signed package digest, desired-state digest, source/target ring, membership snapshot hash, evidence/verdict references, approval record, rollback artifact, and expiration. Any payload or package change starts a new promotion; a new label on different bytes is not the same artifact.

The Phase 2 gate is represented by a typed operations-layer `phase2-approval-record` binding the manifest, frozen Phase 0 plan and thresholds, compatibility/security evidence release, baseline/test pack, and distinct compatibility and security approvals. Phase 3 remains a portable-contract decision: the pilot authorization resolves the applicable `verdict-record` and its `provisionalLabVerdict` rather than creating a competing operations verdict type.

## 8. Intune desired/observed separation

```text
Private Git commit
    └─ versioned Intune objects, assignments, packages, ownership map
          │
          ▼
Atmos render: organization → environment → ring → persona → candidate
          │
          ▼
Terraform plan for qualified infrastructure/Graph resources
          │
          ▼
Policy checks + independent approval + exact plan digest
          │
          ▼
Package signature/trust verification + single-use write authorization
          │
          ▼
Selected object-type transport applies exact approved scope
  (Microsoft Graph Terraform provider by default;
   bounded direct-Graph adapter only by expiring exception)
          │
          ▼
Graph operation record ── status is PENDING
          │
          ▼
Separate Intune Graph read identity obtains object, assignment, and device reports
          │
          ├─ desired digest and bounded scope match → ring active
          └─ mismatch, timeout, or expansion → HOLD and rollback
```

Desired state must distinguish object definition, assignment, filter, group membership rule, package content, detection logic, dependencies, supersedence, restart behavior, and rollback. Observed state must retain the raw response or export, normalized comparison, API version, request/operation identifiers, collection time, coverage, missingness, and errors.

A portal change is drift. An emergency portal action requires a private break-glass record, bounded authorization, readback, and an immediate source reconciliation; the portal never becomes the silent second authority.

The private `objectTypeOwnership` map is mandatory and non-overlapping. Terraform remains the desired-state engine, but each managed Intune object type names exactly one transport: the Microsoft Graph Terraform provider is the default, while the direct Graph adapter requires a recorded owner, reason, scope, compensating control, expiration, and closure evidence. Transport is not authority: Intune remains the enforcement plane. Intune objects are verified by the separate Intune Graph reader, Entra objects by the separate directory Graph reader, and Azure or Key Vault resources by Azure Resource Manager readback. The checked-in public ownership map is intentionally empty and therefore cannot activate writes.

## 9. Git, Atmos, and Terraform chain

### 9.1 Repository and review

The private deployment repository should enforce protected rules, code ownership, independent approvals, signed provenance, required checks, resolved conversations, no force push, and protected release tags. Pull requests from forks or untrusted branches receive no production secret, OIDC token, private runner, Graph permission, or bench access.

The author cannot be the sole reviewer, protected-environment approver, and final authority. Automation may validate and summarize; it cannot approve its own output.

### 9.2 Atmos composition

Atmos composes reviewed layers and reports the final rendered stack and affected components. Recommended precedence is explicit and narrow:

```text
organization defaults
  → platform and security baseline
    → environment
      → ring
        → persona
          → candidate/configuration override
```

Each higher-specificity layer may override only declared keys. The canonical `atmos-stack-render-record` binds source commit, stack/environment and private tenant-boundary reference; every contributing source in precedence order with its digest; declared and actually used override keys; resolved non-secret-values and rendered-output digests; affected components; secret-scan and policy bundles/results; renderer release/version; and render time. `VERIFIED` requires both scan and policy status `PASS`. It is distinct from the leadership `render-manifest-record`. Secret values are references resolved inside the private execution boundary, not public or committed stack values. The reviewed plan and rollout monitor resolve the exact record/digest, and their `atmosRenderDigest` must equal its `renderedOutputDigest`.

### 9.3 Terraform scope

Terraform manages Azure/Entra support infrastructure and only those Graph resources whose lifecycle, import, diff, retry, and readback behavior has been independently qualified. Terraform state is sensitive infrastructure metadata; it is not device evidence or endpoint compliance proof.

Use a separately bootstrapped, private remote backend with locking, isolation, encryption, version recovery, audit, and tested restore. Active Terraform state must remain mutable and must not share the immutable evidence container.

The plan must bind:

- source commit and rendered Atmos digest;
- Terraform/provider/module locks;
- private tenant/environment and variable-set digest;
- desired Intune state and target-ring digest;
- observed-state snapshot used for the plan;
- policy results, approvers, expiry, and rollback reference.

Apply accepts only that reviewed plan. A changed commit, variable, target, observed snapshot, provider lock, or expired approval invalidates it. Post-apply readback is mandatory even when Terraform reports success: Intune Graph for Intune objects, directory Graph for Entra objects, and Azure Resource Manager for Azure, Key Vault, and backend resources.

### 9.4 Package verification and pre-write authorization

The deployment package is accepted only through a canonical verification record that binds its immutable artifact digest, signature, signer identity, approved trust policy, timestamp evidence, revocation status, verification time, and verifier. The plan, write authorization, Graph operation, and rollout monitor all reference the same verified package record and digest. A filename, catalog label, successful upload, or signature-present flag is insufficient.

Immediately before a write, the private authority issues an attested, expiring, single-use authorization record. It binds a unique `authorizationNonce`, `maxUses: 1`, `authorizedOperationId`, stage, reviewed plan, verified package, desired-state revision, target scope, retained membership snapshot and separate rule/filter digests, managed-object set, writer identity, complete approval set, and an authoritative `consumptionLedgerRef`, `consumptionLedgerPolicyRef`, and `consumptionLedgerPolicyDigest`. All approvals and the reviewed plan must predate issuance, and issuance must predate the write.

The writer must atomically reserve and consume that nonce in the authoritative private ledger before it mutates Intune. A canonical `authorization-consumption-record` is attested by the ledger authority and binds the exact authorization ID, digest, nonce, and authorized operation; ledger/policy/authority; managed-object-set digest; `maxUses: 1`; `authorizationUseCount: 1`; monotonic `consumptionLedgerSequence`; previous-entry and resulting ledger digests; `replayCheckStatus: NOT_REUSED`; atomic-commit evidence; `consumedAt`; and the independent-readback policy. The Graph operation and independent readback resolve that exact consumption record and digest. A caller-supplied record index is only an input catalogue and cannot prove that no omitted prior consumption exists. Replay, duplicate use, target expansion, changed package, changed writer, expiration, revocation, ledger rollback, a broken previous-entry chain, a non-monotonic sequence, or an already-consumed nonce is blocked.

The target binding includes the observed population, an approved numeric ceiling, exclusions, static/dynamic membership mode, group rule and filter digests, and an independently acquired directory membership snapshot. A write cannot rely on a caller-supplied count or an unbounded dynamic group.

### 9.5 Identity and trust bootstrap

Use short-lived federated workload identities. Separate plan/read from apply/write. Scope Azure roles, Graph application permissions, Intune RBAC, scope tags, and protected groups to the minimum activated object types and rings. Long-lived client secrets, shared plan/apply identities, broad tenant roles, and pull-request access to production credentials are activation blockers.

The private identity-control plane begins with a canonical `identity-governance-root-authority-record`, not a role label or caller-supplied approver list. Its controlled ceremony binds an ordered key set, each immutable SPKI digest, and the canonical custodian principal for that key. Every verified signature binds its canonical signer principal to the matched custodian. Quorum must be satisfied by at least two distinct canonical custodians **and** at least two distinct SPKIs; two keys controlled by one person or service do not constitute two-party approval. The root subject, signatures, chronology, revocation state, and independent readback are attested and verified before the root authority may approve the canonical role catalog and exact role-binding set.

Trust bootstrap is acyclic. A root-approved `security-freshness-policy-record` in `ROOT_BOOTSTRAP` mode may govern only identity/role-binding readback freshness and may not depend on a role binding. Operational policies use `ROLE_BOUND` mode and resolve an approved role binding plus independently attested binding readback governed by that separate bootstrap policy. Authorization TTL, revocation age, package/readback age, and exception freshness are fixed by the exact signed policy and included in the authorization subject; a caller cannot widen them after issuance.

Canonical principal aliases are resolved once and cannot be counted as separate people or services. Root custodians, ceremony operator, root independent reader, role-binding approver/reader, requester, plan reviewer, package signer/verifier, apply operator, Graph writer, Graph reader, Azure deployer/reader, ledger writer/reader, exception authority, and verdict authority obey the explicit separation matrix. Private activation must prove the effective identities and permissions, not merely assign different role names.

An applicable Azure change also resolves a canonical `azure-deployment-operation-record` that binds the same tenant/environment, reviewed plan, immutable artifact, deployment identity, target, authorization and consumption records, result, and independently observed Azure Resource Manager readback. A caller-provided expected value cannot double as observed state.

## 10. Ansible boundary

Ansible may:

- configure isolated bench systems before enrollment;
- accelerate disposable experiments that do not support a gate until reproduced through the production delivery path;
- run bounded post-provisioning checks;
- collect or stage approved outputs without changing Intune-owned settings.

Ansible may not continuously configure a production setting, application, agent, compliance rule, update rule, or assignment owned by Intune. A bench change that becomes part of the approved configuration must be expressed in the Intune desired-state path and revalidated there. A break-glass production action needs explicit authorization, retained output, and immediate reconciliation; it does not create a permanent second writer.

## 11. Evidence, telemetry, and optional analytics custody

### 11.1 Evidence zones

Keep these boundaries separate:

1. Public blueprint and sanitized examples.
2. Safe evidence suitable for approved internal sharing after manifest review.
3. Restricted evidence containing authorized identifiers or sensitive artifacts.
4. Mutable Terraform state.
5. Immutable evidence releases and verdict records.
6. Derived leadership packets and dashboard projections.

Writers, readers, retention owners, auditors, and release approvers should be distinct where the platform permits. Hashes detect file changes; authenticity also requires approved signing or attestation and an authorized release channel.

### 11.2 Current-fleet evidence

SysTrack is the primary current-fleet performance and experience source in this binding. ServiceNow supplies incident, repair, lifecycle, change, and support-effort context. Intune/Graph supplies management and reported compliance state. The collector supplies device-side T0 ground truth. Joins occur only inside the private boundary using the approved privacy mapping and aggregation floor.

Every extraction definition is versioned and retains query/export version, source time, cohort definition, coverage, missingness, exclusions, and artifact hash. An empty export is not observed zero. Source failure remains unavailable or incomplete.

An issued fleet portfolio must satisfy the exact machine policy in `leadership-claim-chain.json`, not a generic “coverage passed” flag. It contains one typed dimension for each of configuration/persona/population; platform/support baseline; capacity/headroom; workload/resource pressure; application state; battery/standby; dock reliability; provisioning/update/compliance/management; incident/repair/support; region/work-pattern representation; provenance/integrity; and limitations/outliers/freshness/requalification. Each dimension contains the policy's complete, closed claim-metric set and exact source-record/digest/pointer, release, distribution or structured summary, denominator, coverage/missingness/exclusion, baseline/window, tool/query-pack, artifact, provenance/corroboration, freshness, limitation, and requalification bindings. A duplicate, unrelated metric, incomplete claim set, unreleased record, mismatched digest, or generic PASS bucket keeps the leadership chain `NOT_READY`.

Matching counts do not prove that measurements came from the declared cohort. Every portfolio, configuration cohort, and persona allocation therefore carries privacy-safe, release-scoped commitments for its planned, eligible, observed, missing, and excluded identity sets plus digest-bound private partition or subset proofs. The private proof resolver independently reconstructs the planned universe from the exact cohort, join, query, privacy release, observation window, and source-record bindings; verifies cardinalities, pairwise disjointness, completeness, parent-child subset relationships, configuration partitions, persona partitions, and the unassigned set; and rejects a same-count/different-membership substitution. The proof subject binds the portfolio, cohort, window and baseline snapshot, privacy policy and release digests, all counts and commitments, proof algorithm and canonicalization version, domain, key reference and version, issuer, validity, and revocation state.

Commitments use a release-scoped derived key and explicit domain separation so they cannot become stable cross-release tracking identifiers. Canonical identity handling fixes source-specific case and format, normalizes to NFC, rejects invalid or duplicate identities after normalization, and defines UTF-8 length encoding and byte ordering. Raw identities and proof bytes remain Restricted and never appear in the public record or diagnostics. A public ref and digest are commitments, not verification: production remains `HOLD` unless an authenticated, authorized, current, non-revoked private resolver verifies the exact proof and protected source universe. Synthetic proof validation is permitted only in test mode and never grants operational authority.

### 11.3 Microsoft Fabric and Power BI

Fabric/OneLake and Power BI are optional. If selected, use them for governed custody, semantic modeling, refresh, and leadership drill-down. The semantic model preserves source record IDs, baseline and cohort dimensions, observation window, freshness, and coverage. Row/object security and privacy aggregation must be tested before release.

The immutable generated packet remains the approval snapshot. A dashboard is a view, not a verdict, evidence release, or procurement lock. If Fabric is not selected, the packet can be built directly from validated evidence-release bundles without changing the portable method.

## 12. Roles and separation of duties

Only roles appear in this public repository. Private activation binds them to approved enterprise identities.

| Role | Accountable responsibility | Prohibited combination or action |
|---|---|---|
| `ROLE_QUALIFICATION_AUTHORITY` | Resolve conflicts and approve applicable gate/verdict records | Cannot treat missing evidence as approval |
| `ROLE_EVALUATION_OWNER` | Coordinate candidate, controls, test plan, schedule, and evidence closure | Cannot self-approve material evidence corrections |
| `ROLE_DEVICE_EVIDENCE_OWNER` | Collect and release attributable evidence | Cannot issue the verdict supported by their evidence alone |
| `ROLE_SECURITY_APPROVER` | Approve platform/security posture and exceptions | Cannot approve an unscoped or nonexpiring exception |
| `ROLE_PRIVACY_APPROVER` | Approve joins, cohorts, aggregation, retention, and output | Cannot permit direct identities in public/leadership output |
| `ROLE_ENDPOINT_ENGINEERING_OWNER` | Own Intune object model, assignment ownership, and readback | Cannot bypass ring gates through portal or alternate writer |
| `ROLE_GRAPH_AUTOMATION_OWNER` | Maintain bounded write/read clients and API lifecycle matrix | Write identity cannot serve as independent readback authority |
| `ROLE_IAC_CONFIGURATION_OWNER` | Own Atmos composition and change impact | Cannot inject unreviewed environment overrides |
| `ROLE_IAC_APPLY_OPERATOR` | Apply the exact approved plan | Cannot approve their own protected production apply |
| `ROLE_EVIDENCE_CUSTODY_OWNER` | Protect Safe/Restricted stores, retention, restore, and audit | Cannot silently alter released evidence |
| `ROLE_DECISION_PRODUCT_OWNER` | Generate the leadership packet from canonical records | Cannot author unsupported outcome language |
| `ROLE_PROCUREMENT_APPROVER` | Execute only the approved envelope and substitutions | Cannot inherit approval for unknown or changed components |
| `ROLE_REQUALIFICATION_OWNER` | Map change events to stale evidence and reruns | Cannot choose paper tier when impact or identity is unknown |
| `ROLE_INDEPENDENT_VERIFIER` | Verify material corrections and closure evidence | Cannot verify their own correction |

## 13. Compliance-as-code roadmap

The roadmap adds enforcement without changing the portable contract.

### Stage 0 — Public blueprint validation

- Validate tool and control references, authority classes, write/readback boundaries, and required failure states.
- Reject Ansible as a production Intune writer.
- Reject a claim chain missing persona need, current-fleet issue, same-manifest and same-condition candidate comparison, measured-or-explicitly-unmeasured business effect, verdict-backed recommendation, or retained semantic-validation lineage.
- Execute the versioned five-link machine policy itself: conditional business-effect fields and every typed current-fleet dimension/claim set must resolve; policy prose or a frozen digest is not a substitute for the corresponding checks.
- Bind every distribution to the exact Phase 0 test-plan reference, digest, sampling-floor pointer, and floor digest. A plan may freeze a floor above the public minimum; later evidence must meet that higher frozen floor.
- Report a complete chain as `VALIDATED_DERIVED_INPUT`, never as procurement approval or a decision-ready packet.
- Use `Get-ActivationDecision` only to reject a pilot/production request that lacks required gates, exact scope, rollback, or matching readback; this public simulation never authorizes a write or rollout.

### Stage 1 — Repository and supply-chain enforcement

- Protect default and release branches/tags; require CODEOWNERS and independent review.
- Pin actions, Terraform providers/modules, Atmos, PowerShell modules, Node/Ajv dependencies, scripts, packages, and test packs.
- Verify the immutable v2.0.1 tree and complete repository manifest.
- Run secret, dependency, PowerShell, workflow, IaC, and policy checks.
- Sign or attest promoted artifacts and reject revoked, unsigned, or changed bytes.

### Stage 2 — IaC plan and identity enforcement

- Validate deterministic Atmos render and provider/module locks.
- Reject public storage, shared-key access, public network paths where prohibited, broad roles, unrestricted OIDC subjects, local production state, and missing diagnostics.
- Separate plan/read and apply/write identities.
- Require exact-plan digest, protected-environment approval, expiration, and rollback.

### Stage 3 — Intune policy and ring enforcement

- Validate one-writer ownership for every setting and assignment.
- Reject unconstrained pilot membership, package digest changes, target expansion, policy conflicts, unsupported Graph endpoint lifecycles, and unapproved beta dependencies.
- Treat writes as pending until independent readback matches.
- Enforce Phase 2/3/pilot-authorization prerequisites for pilot and Phase 5 verdict/procurement prerequisites for production.

### Stage 4 — Evidence and decision-product enforcement

- Validate schema and bundle semantics, provenance, baseline, sampling, coverage, and staleness.
- Enforce privacy floors and Safe/Restricted separation.
- Require all five leadership links and deterministic rendering.
- Verify every displayed number and recommendation against its canonical pointer.

### Stage 5 — Continuous assurance

- Reconcile Intune desired/observed state and ring population.
- Monitor Windows, firmware, driver, agent, app, component, procurement, exception, support, and tool-binding changes.
- Mark dependent evidence stale and assign full/delta/paper requalification under the playbook.
- Exercise rollback, state restore, evidence restore, access denial, and monitor dead-man tests on the approved cadence.

## 14. Monitoring and response

Monitoring uses event-driven signals plus reconciliation; it does not run one undifferentiated ten-minute poll for every control.

Production activation binds one approved operations-layer `rollout-monitoring-record` to the already-issued leadership semantic-input digest and decision claim; the exact semantic-validation record, digest, source release, evaluation time, and `render-manifest-record`; final verdict, persona and procurement pointers; Git commit, Atmos stack render, reviewed Terraform plan, verified package, consumed write authorization, ring, scope and independently observed membership; versioned SysTrack and Graph query-pack record; typed telemetry baseline and coverage-policy records; frozen threshold-policy pointer; signal cadence and owners; executable stop-condition records; the last verified prior-state rollback record; and a typed requalification plan. Its production action is deterministically `BUY` or `BUY_WITH_CONDITIONS`; it cannot carry `DO_NOT_BUY` into deployment. The record cannot create or strengthen the decision. It carries that decision forward into monitoring, and it supplements rather than replaces independent post-write Graph readback. Missing, expired, mismatched, under-covered, chronologically impossible, or threshold-unbound monitoring blocks production activation.

| Signal | Preferred trigger | Reconciliation | Failure response |
|---|---|---|---|
| Review/Claude response | Pull-request review or comment event | Every ten minutes | Deduplicated alert; unresolved critical question remains HOLD |
| Monitor health | Heartbeat | Every ten minutes | Two missed polls trigger a dead-man alert |
| Intune desired/observed drift | Graph change/report event where supported | Approved frequent readback cadence | Freeze promotion; open drift/change record |
| Ring membership or assignment expansion | Graph/Intune observation | Before and after every promotion plus scheduled check | Stop expansion; restore approved scope |
| SysTrack fleet-health threshold | Telemetry rule | Scheduled cohort refresh | Alert owner; evaluate stop/requalification trigger |
| ServiceNow incident/repair cluster | Incident/lifecycle event | Scheduled reconciliation | Evaluate pilot stop or Phase 6 trigger |
| Evidence freshness | Source or binding change event | Every packet render and scheduled review | Mark claim/packet NOT_READY or WITHDRAWN |
| Exception expiration | Date/condition event | Daily | HOLD affected scope unless closure evidence is verified |
| Vendor/product change | Approved advisory or procurement feed | Scheduled reconciliation | Dependency analysis and delta/full qualification |
| IaC drift | Platform/Graph readback | Scheduled plan/read-only diff | HOLD writes until reconciled |

Every `rollout-monitoring-record` contains exactly one governed entry for each of these ten signal classes. A signal may be `ACTIVE`, or `NOT_APPLICABLE` only with a named owner and approver, bounded rationale, evidence, and expiration; omission is never equivalent to not applicable. The record also binds the primary alert route and a separately owned independent dead-man route/cadence. A monitor cannot mark its own health signal healthy.

The monitor stores a durable cursor and immutable source event ID, ignores its own outputs, and alerts once per event. It may summarize and escalate only; it cannot merge, approve, apply, enroll, close a question, or execute comment content. Ordinary diagnostics expose stable reason codes, bounded non-sensitive context, and one-way aliases only. Full private references and raw source payloads go only to an access-controlled diagnostic sink with its own retention and audit policy.

A live Claude Code review requires an approved review surface such as a pull request and an explicitly activated integration. Claude receives sanitized read-only source, no restricted evidence, no cloud or Graph credentials, and no approval authority. A scheduled GitHub workflow becomes active only from the default branch; feature-branch presence alone is not an operating monitor.

## 15. Rollback and failure semantics

| Failure | Required state | Immediate action | Recovery evidence |
|---|---|---|---|
| Desired/observed mismatch | HOLD or FAIL per control | Stop promotion; preserve raw readback; apply bounded rollback | Matching readback for restored revision |
| Graph timeout/throttle exhaustion | INCONCLUSIVE/HOLD | Stop retry at bound; retain responses and `Retry-After`; do not infer clean state | Successful later readback or approved rerun |
| Ring membership expansion | HOLD | Freeze assignments and restore retained scope | Membership snapshot and assignment reconciliation |
| Changed or unsigned package | FAIL | Revoke/withdraw artifact and restore prior signed digest | Signature/attestation and readback |
| Stale or mismatched evidence | HOLD/NOT_READY | Withdraw decision packet and mark dependent claims | New admissible release and regenerated packet |
| Stop condition reached | HOLD/FAIL | Resolve the executable condition record, preserve the threshold comparison, and execute the bound pilot/device rollback | Incident closure, device recovery, and new authorization if resumed |
| Terraform plan/state uncertainty | HOLD | Block apply; acquire/verify lock; restore tested state if required | State integrity and exact new plan review |
| Evidence custody breach | HOLD/FAIL | Quarantine, revoke access, preserve logs, notify owners | Incident resolution and independent custody verification |
| Alternate writer detected | HOLD | Stop alternate path; reconcile desired state; resolve conflict | Ownership map and clean readback |

Rollback returns to the last independently verified prior state; it does not point back to the newly deployed revision and it does not erase failed evidence, incidents, or history. The rollback record binds the prior revision, signed package, exact prior membership, prior independent readback, immutable rollback artifact and attestation, and required post-rollback readback. The executable stop-condition records provide the trigger-to-disposition and rollback/requalification mapping. If no verified prior state exists, no write is authorized; a future withdrawal, isolation, device-swap, or recovery design must first be represented in a new reviewed contract version and tested.

Every stop condition is a canonical executable record, not prose or a dangling reference. It binds a signal, typed telemetry/coverage and threshold-policy pointers, comparison operator and threshold, scope, owner, disposition, expiry, and rollback/requalification action. The authorization recomputes the exact stop-condition set digest; a missing, changed, unresolvable, expired, or non-executable condition blocks the write.

## 16. Private activation inputs

Production activation cannot infer these values:

- role-to-identity and independent-approval mappings;
- repository, CI, protected environment, branch/tag rule, and signing choices;
- tenant, subscription, state backend, region, network, encryption, retention, RTO/RPO, and budget decisions;
- Terraform, provider, module, Atmos, action/task, PowerShell, Pester, Node, Ajv, `ajv-formats`, policy, renderer, package, authorization-ledger, and independent-ledger-reader locks;
- trusted validation-runner image digest, externally pinned Pester/Node/Ajv toolchain paths and hashes, network policy, and source-commit allowlist;
- exact Microsoft Graph endpoint/API-version/lifecycle matrix and permission scopes;
- Intune RBAC, scope tags, non-overlapping per-object provider/direct-Graph transport ownership, ring groups/filters, population maxima, and rollback assignments;
- independent Intune Graph, Entra directory Graph, and Azure Resource Manager readback identities, scopes, projections, and freshness rules;
- authorization-consumption ledger and independent-reader implementations, identities, authority keys, atomicity/consistency rules, retention, recovery, rollback detection, and readback policy;
- persona definitions, current-fleet cohorts, observation windows, coverage and privacy floors;
- SysTrack, ServiceNow, procurement, survey, vendor-feed, Fabric/Power BI, and alert bindings;
- threshold/reserve values, agent-classification rules, and approved collector/vendor-tool hashes;
- hardware runner controls and retained results for all seven bench scenarios.

No private activation value belongs in this public repository.

## 17. Production acceptance gates

Activation is permitted only when independently retained evidence proves:

- protected source and release history reject direct/force push and unauthorized tag deletion;
- every production dependency is pinned and verified;
- authors cannot self-approve or use production credentials from pull-request jobs;
- Terraform uses the exact reviewed plan with isolated recoverable state and short-lived identities;
- policy tests reject public storage, broad permissions, shared keys/secrets, unbounded OIDC subjects, missing diagnostics, and cross-boundary access;
- Intune ownership has no duplicate production writer or unresolved assignment conflict;
- selected object-type transport and Graph write scope equal the approved map and ring, and the applicable independent Intune, directory, or Azure readback equals desired state;
- pilot and production requests satisfy the correct portable-contract gates and chronology;
- current-fleet and candidate evidence meet coverage, comparison, freshness, privacy, and sampling requirements;
- every decision-packet statement resolves to an admissible source and the rendered digest is reproducible;
- all seven real-hardware integration cases have signed retained results;
- package trust/revocation verification, single-use write-authorization replay denial, target-ceiling enforcement, and independent membership readback have passed negative tests;
- rollback to the last verified prior revision, state recovery, evidence recovery, alert delivery, and dead-man monitoring have passed realistic tests;
- renderer injection/encoding and diagnostic-redaction tests prove that untrusted text and private identifiers cannot escape their approved boundary.

Until then, the only honest production state is HOLD.

## 18. Key decisions and trade-offs

### Public blueprint and private activation

- **Benefit:** protects tenant, person, device, evidence, and operational identifiers while keeping the method reviewable.
- **Cost:** two repositories and an explicit digest/reference handoff.
- **Decision:** keep public templates here; activate exact identities, values, and live evidence privately.

### Intune enforcement with Graph write/readback

- **Benefit:** uses the real enterprise Windows path and makes desired/observed mismatch visible.
- **Cost:** Graph endpoint coverage, throttling, asynchronous convergence, and provider lifecycle require explicit qualification.
- **Decision:** Intune and its Graph write path are the sole production writer for the explicitly mapped Intune-owned scope; every write remains pending until independent readback.

### Terraform for infrastructure, not endpoint truth

- **Benefit:** deterministic plan/review/apply for Azure, identity, and qualified Graph resources.
- **Cost:** Terraform state can be mistaken for operational truth and may expose sensitive metadata.
- **Decision:** state proves managed-resource transition only; endpoint evidence comes from Graph/Intune and device-side sources.

### Immutable packet with optional live dashboard

- **Benefit:** leadership gets a fast snapshot that can be reproduced and audited, while analysts retain drill-down.
- **Cost:** the snapshot and dashboard can show different as-of times.
- **Decision:** the packet is the decision snapshot; Fabric/Power BI is an optional, clearly time-bounded view.

### Event-driven review plus ten-minute reconciliation

- **Benefit:** immediate response with a recovery path for missed events.
- **Cost:** scheduled execution is best-effort and needs an external dead-man control for a strict service level.
- **Decision:** use both; monitoring never performs approval or deployment.

## 19. Official source map

These sources describe product behavior and implementation mechanisms. They do not supersede the portable qualification contract or constitute proof that this blueprint is activated.

### Microsoft Intune and Windows

- [Create device profiles in Microsoft Intune](https://learn.microsoft.com/en-us/intune/device-configuration/create-device-profile)
- [Use assignment filters in Microsoft Intune](https://learn.microsoft.com/en-us/intune/fundamentals/filters/overview)
- [Device compliance overview](https://learn.microsoft.com/en-us/intune/device-security/compliance/overview)
- [Security baselines in Intune](https://learn.microsoft.com/en-us/intune/device-security/security-baselines/overview)
- [Add, assign, and monitor Win32 apps](https://learn.microsoft.com/en-us/intune/app-management/deployment/win32)
- [Intune Management Extension for Windows](https://learn.microsoft.com/en-us/intune/device-management/tools/management-extension-windows)
- [Monitor device configuration profiles](https://learn.microsoft.com/en-us/intune/device-configuration/monitor-device-profile)
- [Troubleshoot policies and profiles](https://learn.microsoft.com/en-us/intune/device-configuration/troubleshoot-device-profiles)
- [Intune reports overview](https://learn.microsoft.com/en-us/intune/device-management/reports/overview)
- [Role-based access-control scope tags](https://learn.microsoft.com/en-us/intune/fundamentals/role-based-access-control/scope-tags)
- [Multi Admin Approval](https://learn.microsoft.com/en-us/intune/fundamentals/role-based-access-control/multi-admin-approval)
- [Windows Autopilot overview](https://learn.microsoft.com/en-us/autopilot/overview)
- [Windows Update for Business reports overview](https://learn.microsoft.com/en-us/windows/deployment/update/wufb-reports-overview)
- [Configuration Manager and Intune co-management overview](https://learn.microsoft.com/en-us/intune/configmgr/comanage/overview)
- [Windows Policy CSP conflict-control policy](https://learn.microsoft.com/en-us/windows/client-management/mdm/policy-csp-controlpolicyconflict)
- [Windows Autopatch overview](https://learn.microsoft.com/en-us/windows/deployment/windows-autopatch/overview/windows-autopatch-overview)

### Microsoft Graph, identity, and provider

- [Microsoft Graph Intune overview](https://learn.microsoft.com/en-us/graph/api/resources/intune-graph-overview?view=graph-rest-1.0)
- [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling)
- [Microsoft Graph best practices](https://learn.microsoft.com/en-us/graph/best-practices-concept)
- [Microsoft Entra workload identity federation](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation)
- [Microsoft Terraform Provider for Microsoft Graph](https://registry.terraform.io/providers/microsoft/msgraph/latest/docs)

### Terraform and Atmos

- [Terraform AzureRM backend](https://developer.hashicorp.com/terraform/language/backend/azurerm)
- [Terraform dependency lock file](https://developer.hashicorp.com/terraform/language/files/dependency-lock)
- [Terraform plan command](https://developer.hashicorp.com/terraform/cli/commands/plan)
- [Terraform apply command and saved plans](https://developer.hashicorp.com/terraform/cli/commands/apply)
- [Atmos stacks](https://atmos.tools/core-concepts/stacks/)
- [Atmos stack inheritance](https://atmos.tools/core-concepts/stacks/inheritance/)
- [Atmos components](https://atmos.tools/core-concepts/components/)

### Review, automation, and analytics

- [GitHub Actions workflow events, including schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [GitHub repository rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [Secure use of GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use)
- [Configure OpenID Connect in Azure for GitHub Actions](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure)
- [Microsoft Fabric OneLake overview](https://learn.microsoft.com/en-us/fabric/onelake/onelake-overview)
- [Power BI semantic models](https://learn.microsoft.com/en-us/power-bi/connect-data/service-datasets-understand)

Product documentation changes over time. Private activation records the exact reviewed documentation date, API version, provider/runtime locks, and any enterprise support constraints used for the deployed binding.
