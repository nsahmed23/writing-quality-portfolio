# New Laptop Evaluation Playbook v2

**Status:** Authoritative method. Supersedes every v1 playbook and contract artifact.

**Contract schema release:** 2.0.1 (v2 hardening patch).

This playbook and the five schemas define the portable qualification contract. The corrected diagram below is normative. **TOOL_BINDINGS.md** is a replaceable, non-normative implementation binding; no named tool is part of the method.

The program answers one question repeatably and auditably: which exact laptop configuration should the company buy, for which employees, at what cost, under what conditions, based on which evidence.

## Core rules (normative)

1. **The corporate stack is part of the effective hardware specification.** Capacity, battery, and experience claims are stated net of its measured floor.
2. **The claim cannot be stronger than the measurement.** Use direct attribution when instrumentation supports it, controlled deltas when isolation is possible, and association otherwise.
3. **Enumerate; do not infer.** Component identity comes from enumeration, not behavior, marketing, or press reports.
4. **Missing evidence is not a pass.** Unknown critical identity produces HOLD; insufficient coverage or unusable evidence produces INCONCLUSIVE.
5. **Freeze before results.** Configuration, tests, numeric sampling floors, thresholds, reserves, pilot selection, bridge requirements, and versions are approved in Phase 0. They cannot be relaxed after candidate results are seen.
6. **Preserve evidence boundaries.** Evidence collected under different BIOS, driver, Windows, image, security-agent, or test-pack baselines is kept in separate strata and is never silently joined.
7. **Maintain two verdicts.** Fleet readiness and persona fit are separate decisions with an explicit conflict path.

## Corrected program diagram (normative)

~~~
Phase 0: Intake and configuration lock
                     │
                     ▼
Phase 1: Device ground truth
                     │
                     ▼
Phase 2: Research + application compatibility + security gate   [HARD GATE]
                     │
                     ▼
Phase 3: Controlled candidate/control testing
         Candidate + incumbent + sibling
         Same time, same image baseline, same protocol
                     │
             Provisional lab verdict                            [GATE]
                     │
                     ▼
Phase 4: Authorized production pilot
         Telemetry + employee evidence
                     │
                     ▼
Phase 5: Fleet verdict + persona verdict
         Arbitration + procurement lock
                     │
                     ▼
Phase 6: Sustain, monitor, and requalify
~~~

There are exactly seven phases, numbered 0 through 6. Compatibility and security are a hard gate inside Phase 2; there is no Phase 2.5. Candidate, incumbent control, and sibling or alternative control pass through the same Phase 3 protocol during the same test campaign. Controls are Phase 3 subjects, not a parallel or later phase.

A production pilot is prohibited unless all three preconditions are recorded:

1. Phase 2 compatibility and security approval.
2. Phase 3 provisional lab approval.
3. Approved pilot stop conditions and rollback plan.

## Portable contract artifacts

The five schemas in **schemas/** are normative:

- **candidate-manifest.schema.json** — bounded configuration, personas, candidate and controls, peripherals, deadline, owners, and contract references.
- **test-plan.schema.json** — versioned tests, dependencies, numeric sampling floors, conditions, evidence, decision rules, and staleness dependencies.
- **evidence-record.schema.json** — provenance, identity, baseline, tool and test-pack versions, results, distributions, quality, limitations, and artifact hashes.
- **threshold-policy.schema.json** — preapproved thresholds and structured reserve constants.
- **verdict-record.schema.json** — an immutable pre-Phase 4 `pilot-authorization` record or an immutable `phase5-final` record carrying dual verdicts, conditions, exceptions, arbitration, procurement envelope, risks, triggers, approvers, and evidence releases.

## Qualification tiers

- **Full:** a new platform, silicon generation, or device class. All phases and all applicable test classes run.
- **Delta:** a change to a qualified configuration. Every test whose staleness dependency intersects the change reruns; all applicable floors remain in force.
- **Paper:** a documented change with no dependency intersection, such as packaging or cosmetics. It requires a recorded dependency review and cannot be used when component identity is unknown.

The tier and its dependency rationale are frozen in the Phase 0 manifest. Phase 6 uses the same tiers for requalification. A lower tier never overrides a triggered test, a sampling floor, or a gate.

## Sampling and reporting

One laptop can support engineering investigation. One laptop cannot support a fleet-wide conclusion.

Every applicable test entry must contain numeric **minUnits** and **minRepetitionsPerUnit** values in the Phase 0 test plan. A phrase such as “representative sample” is not a numeric floor. The plan may raise the program floors below but may not lower them. A delta evaluation may omit a class only when its frozen dependency analysis shows that the class is unaffected; an applicable class that cannot meet its floor ends INCONCLUSIVE.

An individual one-device engineering or context record may be below a fleet floor, but it cannot satisfy a gate. For a gate, semantic validation aggregates only T0 records marked `gate-or-verdict`, keyed by frozen test, required role, `conditionRef`, and baseline fingerprint. Unit and run identities must be unique so no device or run is counted twice. Every role in the test's `appliesTo` list and every required condition must have a single, internally comparable baseline stratum that meets the frozen unit and repetition floor; records from different baseline strata are never added together to manufacture coverage.

Unless the row says otherwise, the floor applies separately to candidate, incumbent, and sibling or alternative control.

| Test class | Sampling concern | Program floor frozen in Phase 0 |
|---|---|---|
| Component identification | Supplier variation | 5 units per role, 1 complete enumeration per unit; include every known lot or supplier stratum |
| Controlled benchmarks | Run-to-run and unit variance | 3 units per role, 5 accepted runs per unit per condition |
| Sustained performance | Thermal stabilization and steady-state variance | 3 units per role, 3 accepted runs per unit per condition after stabilization |
| Battery and standby | Cycle and overnight variation | 3 units per role, 3 full cycles or overnight sessions per unit per condition |
| Dock reliability | Intermittent attach, detach, sleep, and resume faults | 3 units per role, 20 complete cycles per unit for each required dock/condition combination |
| Application compatibility | Application, agent, and peripheral combinations | Phase 2: 2 candidate units, 2 accepted runs of every critical matrix combination per unit |
| Production pilot | Users, personas, regions, and work patterns | 30 preselected participant-devices, 10 accepted daily evidence windows per participant; Phase 0 sets larger numeric strata where needed |
| Sentiment | Selection and nonresponse bias | 24 preselected participants, 1 completed exit survey per participant, and at least 80% of the pilot cohort; use the larger participant count |
| Corporate floor | Unit and measurement-window variance | 3 units per role, 3 settled measurement windows per unit per image baseline |
| Agent state | Scheduled and burst-state variance | 3 units per role, 3 observation windows per unit for every required agent state |

The production-pilot and sentiment rows apply to candidate participants. The application-compatibility row is the candidate hard-gate matrix in Phase 2. When Phase 3 measures comparative application timing, reliability, battery, or docking, that work uses the corresponding dynamic class and its fresh candidate/control floors. For the pilot and sentiment classes, Phase 0 also freezes numeric quotas for each applicable persona, region, and work-pattern stratum. Participants are selected from the target population; self-selected volunteers alone are not an acceptable sample.

Every result release reports distributions, not only a single score:

- unit count and run count;
- median and range or percentile spread;
- variation between runs and, where applicable, between units;
- coverage and missing results;
- outliers and exclusions with their preregistered rule and reason.

### Concurrent controls, cache, bridge, and bootstrap

“Concurrent” means one Phase 3 campaign window using the same frozen test plan, test pack, image baseline, platform conditions, agent states, and protocol. The systems do not need to start at the same clock second, but candidate-only testing followed by a later control campaign is not concurrent.

Fresh full-floor testing of all three roles is the default. Reuse has three distinct paths:

1. **Documentary and stable-identity reuse:** published T1 specifications, component-identity records, and stable hardware-inventory records may be reused as context only when the artifact applies to the exact configuration, its hash/reference is verified, it is inside the Phase 0 currency window, and no identity, support, or staleness dependency changed. These artifacts do not need run distributions, repetition counts, or a bridge because they do not count as a controlled test result. They never replace fresh Phase 1 collection, current-unit identity, or a Phase 3 dynamic-class floor.
2. **Prior compatibility-result reuse:** a prior application-compatibility test result is the only cached test result that may count toward a sampling floor. Every hardware, firmware, operating-system, agent, application, peripheral, condition, test/test-pack, support-currency, threshold-policy, and staleness dependency must match.
3. **Dynamic evidence:** fresh contemporaneous candidate and controls are mandatory for corporate-floor measurements, agent states, controlled benchmark or workload timing, sustained performance, battery or sleep, dock reliability, pilot production experience, and sentiment. Cached records never satisfy the unit, repetition, bridge, or coverage floors for these classes.

A prior compatibility-result cache may count only under all of these rules:

1. It identifies the exact subject configuration and evidence release, verifies artifact hashes, is within the Phase 0 maximum age, contains complete results, coverage, missingness, and limitations, and includes distributions where the frozen compatibility test requires them.
2. The cached record, fresh bridge, and current frozen test definition use the same test and test-pack versions; threshold-policy version, baseline stratum, support status, and every declared dependency also match. A mismatch remains a separate stratum and invalidates cache admission.
3. A contemporaneous bridge uses at least one candidate unit and all required repetitions of every critical matrix combination under the same Phase 2 protocol. Phase 0 freezes the numeric bridge counts.
4. The bridge meets the frozen functional, repeatability, and drift rules. A failed or missing bridge invalidates reuse.
5. Cache plus accepted bridge meets the full frozen compatibility unit and run floors. The bridge is not an exception to those floors.

The cached record preserves its original observation `timestamp`, which may predate the current Phase 0 freeze. Its `admission` object records the current `admittedAt` and `bridgeAcceptedAt` times, reuse-policy and cached-release references, dependency snapshot and exact-match declaration, verified hashes/completeness/age, frozen bridge/rule references, and the fresh candidate bridge-evidence references. `admittedAt` must be later than the current manifest, test-plan, and threshold-policy `frozenAt` values and later than `bridgeAcceptedAt`; `bridgeAcceptedAt` must follow every referenced fresh bridge observation and admission. Only T0, gate-bearing application-compatibility evidence may use `compatibility-cache`; all dynamic-class observations remain fresh and post-freeze.

If prior compatibility cache is absent, stale, ineligible, or fails its bridge, the **compatibility bootstrap rule** requires the complete fresh matrix at the full Phase 0 floor before Phase 2 can pass. If fresh eligible control evidence is absent for a Phase 3 dynamic class, the **control bootstrap rule** requires enough fresh control units and repetitions through the full concurrent protocol to meet that class's floor. Existing production telemetry may identify risks; it does not replace either bootstrap. A single anchor run never bootstraps a fleet baseline.

## Evidence provenance and release

- **T0:** direct observation or measurement on an identified device/configuration.
- **T1:** a primary vendor or authoritative platform document tied to the claim and configuration.
- **T2:** press, community, or other secondary material.

A T2 record must contain **corroborationRef** naming a specific T0 or T1 evidence-record ID that supports the same claim, regardless of whether the T2 record is being used as context, a hypothesis, or gate/verdict evidence. A generic “checked against vendor information” note is not enough. Uncorroborated T2 is not an admissible evidence record; a research lead may remain outside the evidence release until it is corroborated.

Each evidence record carries subject identity, role, `conditionRef`, baseline stratum, original observation `timestamp`, admission mode and `admittedAt`, tool and test-pack versions, unique unit/run identities for T0 distributions, coverage, data quality, known limitations, and SHA-256 artifact hashes. Evidence records are assembled into immutable, versioned evidence releases. Derived documents cite evidence-release and verdict-record IDs; they are not themselves evidence.

Standalone JSON Schema validation is necessary but not sufficient for an evidence release. Before any phase exit, the release process must also perform bundle-level semantic validation: resolve every cross-record ID and version; bind the test plan and every fresh T0 subject to the current manifest; reject dangling, self-corroborating, or wrong-provenance T2 references; prove that every `admission.admittedAt` is strictly later than `candidate-manifest.frozenAt`, `test-plan.frozenAt`, and `threshold-policy.frozenAt`; require fresh observation timestamps to be post-freeze while applying the bounded compatibility-cache exception above; enforce cache/bridge acceptance chronology and test-pack identity; enforce pilot authorization and observation chronology; resolve each evidence record to its frozen test and condition; reject release-wide duplicate run identities or a device identity that changes role/configuration/manifest; enforce the applicable sampling floor for every required gate-bearing test/role/condition/baseline aggregate; reconcile unit/run/missing counts, coverage percentages, and ordered ranges; recalculate the capacity equations from the referenced frozen threshold policy; and prove that manifest, tier, test-plan, baseline, condition, exception, and substitution references agree. Contract identifiers, references, and versions use ordinal case-sensitive equality; hexadecimal SHA-256 text may compare case-insensitively. Absence of a required gate aggregate is a failure, not a vacuous pass. A schema-valid record that fails any semantic check does not satisfy a gate.

## Reserve policy

Capacity is calculated using versioned constants:

~~~text
Usable memory  = physical memory    - corporate floor  - memory reserve
Usable storage = formatted capacity - corporate image  - storage reserve - persona working set
~~~

Each memory or storage reserve in the threshold policy is a structured constant containing:

- value and units;
- why the reserve exists;
- selection method and evidence references;
- personas to which it applies;
- approver;
- conditions under which it may be revised;
- historical comparisons that become non-comparable after revision.

The policy version and actual values are frozen in Phase 0 before candidate results are reviewed. A revision requires a new version and approval; no one may adjust a reserve after seeing that a candidate narrowly failed.

## Verdicts and arbitration

Allowed outcomes are **QUALIFY**, **QUALIFY_WITH_CONDITIONS**, **HOLD**, **FAIL**, and **INCONCLUSIVE**.

- Fleet HOLD or FAIL blocks deployment even when a persona verdict passes.
- Persona FAIL blocks assignment to that persona even when fleet readiness passes.
- Conflicting conditional verdicts go to the named qualification authority frozen in Phase 0.
- When the procurement deadline arrives while required evidence is INCONCLUSIVE, the evidence outcome remains INCONCLUSIVE. The authority may sign a narrowly scoped, expiring risk exception or decline the purchase; neither action converts the evidence to QUALIFY.
- Every exception records owner, reason, compensating control, scope, expiration, and evidence required for closure.

**Substitution path:** procurement may not silently substitute a component or configuration. Compare the proposed substitute with the approved Hardware Configuration Envelope, document observable equivalence, and map every difference to test-plan dependencies. Material differences trigger delta qualification. Unknown component identity produces HOLD, never inherited approval. Only a Phase 5 procurement envelope may authorize an explicitly named substitution.

## Phase 0: Intake and configuration lock

**Purpose:** define the evaluation object, controls, decision authority, sampling, and rules before testing.

**Required work:**

- Create the candidate manifest with orderable SKUs, Hardware Configuration Envelope, platform baseline, intended personas, candidate units, incumbent control, sibling or alternative control, standard docks and peripherals, deadline, evaluation owner, tier, and dependency rationale.
- Name the qualification authority. A role label without an accountable person or approved authority record is incomplete.
- Create the pilot population plan with numeric representation strata and a named privacy owner. The privacy owner is frozen with the manifest; a blank owner is not an open item.
- Freeze the test plan: tests, conditions, numeric unit and repetition floors for every applicable class, control-cache references and maximum ages, bridge counts, rules, evidence requirements, and staleness dependencies.
- Freeze the threshold-policy version, including actual threshold and reserve values, rationales, selection methods, approvers, revision rules, and non-comparable history.
- Define program cost for the selected tier in engineer-days, lab hardware, and elapsed time.

**Exit condition:** the manifest, test plan, and threshold policy are versioned and approved; the qualification authority and privacy owner are named; every applicable sampling field and every threshold/reserve value is numeric and nonblank. Other unknown critical fields have an owner and closure date and cannot be treated as satisfied. No result-bearing test begins before this exit.

## Phase 1: Device ground truth

**Purpose:** record what is actually installed and running on every candidate and control unit.

**Required work:** collect privacy-safe T0 evidence on platform identity, BIOS and firmware, CPU, per-DIMM identity, SSD model and firmware, WLAN module and driver, panel, battery identity and condition, GPU and NPU with drivers, TPM and Secure Boot, BitLocker and VBS, structured battery data, storage reliability where available, problem devices and recent hardware-event summaries, and raw vendor-management output.

Inventory the corporate security and management stack from a versioned classification file: running services, relevant scheduled tasks, kernel drivers, file-system minifilters, product/version, running state, signature/provider, and collection time. Record the classification version and SHA-256 in the bundle manifest. The methodology contains no vendor-name allowlist. **Safe** is the default shareable bundle mode: it pseudonymizes serials and other direct identifiers and excludes active Wi-Fi details and restricted raw artifacts. **Restricted** is an authorized-internal mode; it may include direct identifiers and sensitive artifacts only when a nonblank authorization reference is supplied and recorded in the manifest. Both modes check native exit codes, preserve partial-section failures, and manifest and hash the bundle.

**Exit condition:** every unit in scope has a complete evidence record or an explicit failed-section record; a second engineer can reconstruct the observed configuration and limitations from the hashed release. Unknown critical component identity remains HOLD and is not inferred.

## Phase 2: Research + application compatibility + security gate [HARD GATE]

**Purpose:** convert external evidence into testable risks and approve the corporate stack's compatibility and security posture before controlled qualification testing can proceed.

**Research:** review primary vendor specifications, service documentation, firmware and driver release notes, security advisories, processor-platform documents, dock advisories, predecessor/sibling history, and field reports. Research creates evidence records, risks, and tests, not a verdict. T2 follows the corroboration rule above.

**Compatibility:** evaluate EDR, DLP, ZTNA/VPN, VDI, management agents, authentication, critical applications, and standard peripherals. Before approval, execute the complete current app/agent/peripheral matrix at the application-compatibility unit and repetition floors frozen in Phase 0. Classify each combination as officially supported, supported with conditions, unsupported but functioning, failed, or unknown. “Unsupported but functioning” remains unsupported. A prior result may contribute only under the compatibility cache and bridge rules above.

**Security:** the named security approver records the posture for local AI and model storage, NPU access, platform AI features, TPM or hardware-root capabilities, Secure Boot, BitLocker, VBS, and attestation. Required compensating controls and exceptions are explicit.

**Exit condition — hard gate:** the full compatibility matrix meets its Phase 0 numeric floor and has a versioned evidence release; compatibility and security approvers sign an approval tied to that release and the manifest. No critical dependency or security decision is unknown or unowned. Failed or unsupported critical dependencies block passage unless an authorized, scoped, expiring exception exists. Phase 3 and Phase 4 are prohibited until this gate passes.

## Phase 3: Controlled candidate/control testing

**Purpose:** measure candidate, incumbent, and sibling or alternative control concurrently under the same frozen protocol and comparable baseline strata.

**Required work:**

- **Corporate floor:** restart, sign in, stabilize for the frozen duration, and measure over fixed windows. Record median and p95 CPU, memory in use, disk/network activity, process/service counts, sustained consumers, and agent versions/state.
- **Agent states:** test the frozen settled, scan, patch, inventory, sync, meeting, and persona-workload states. Mismatched states are different strata.
- **Attribution:** report direct per-agent measurements when supported, controlled before/after deltas when safe, and association otherwise. Apply the same discipline to battery and wake effects.
- **Reference versus corporate image:** execute identical workloads on safely restorable matched systems. Report the corporate software delta for boot, idle, launch, workload completion, battery, storage, and sleep.
- **Sustained workloads:** use frozen workloads of at least 20 minutes after defined thermal stabilization. Log work completed, clocks, temperatures, fan behavior, and power across required AC/battery, dock, power-mode, image, and system conditions.
- **Component variation and failure modes:** enumerate every unit and execute the standby, biometric, dock/resume, storage, firmware, and other tests derived from Phase 2.
- **Compatibility release:** reference the just-issued Phase 2 matrix rather than silently duplicating it. If any Phase 3 condition or dependency differs or the record becomes stale, rerun the affected matrix combinations at the full compatibility floor before the provisional verdict. Comparative application timing, reliability, battery, and dock claims always use fresh concurrent candidate/control evidence in their dynamic classes.
- **Controls:** apply the concurrent cache, bridge, and bootstrap rules above. No candidate comparison proceeds with a control role below its frozen floor.

**Exit condition — provisional lab gate:** the Phase 2 compatibility release remains current, and every applicable Phase 3 class meets its frozen candidate and control floors; evidence is comparable within explicit baseline strata; distributions, coverage, missing results, and exclusions are released; all rules still match the Phase 0 versions. Record a provisional lab verdict. Only QUALIFY or QUALIFY_WITH_CONDITIONS constitutes Phase 3 approval for a pilot; HOLD, FAIL, or INCONCLUSIVE prohibits Phase 4.

## Phase 4: Authorized production pilot

**Purpose:** determine whether approved lab results survive representative employee use.

**Three required preconditions (none may be waived):**

1. The Phase 2 compatibility/security approval reference is present and current.
2. The Phase 3 provisional verdict is QUALIFY or QUALIFY_WITH_CONDITIONS.
3. Pilot stop conditions and rollback plan are documented and approved, including severity levels, maximum incident rate, device-swap process, spare pool, service-desk briefing, duration, and minimum evidence coverage.

Before enrollment begins, issue an immutable verdict record with `recordStage` = `pilot-authorization`. It must carry `pilotPopulationPlanRef`, the named `privacyOwner`, the three approvals above, and their evidence and approver references. A later final record cannot retroactively authorize pilot entry.

**Required work:** after the pilot-authorization record is issued, enroll the preselected sample and frozen representation strata and record `pilotCompletion.startedAt`. Collect endpoint telemetry, management state, incidents, application failures, battery/sleep and dock events, support contacts, and a structured survey mapped to technical claims. Join machine and employee evidence only under the collection rules approved by the Phase 0 privacy owner. Stop and execute rollback when a stop condition is reached.

**Exit condition:** the planned observation window and numeric sampling floors are complete; telemetry and survey coverage meet the frozen thresholds; missingness and exclusions are reported; no unresolved stop condition remains. Otherwise the pilot result is HOLD, FAIL, or INCONCLUSIVE under the frozen rules.

## Phase 5: Fleet verdict + persona verdict, arbitration, procurement lock

**Purpose:** issue the two decisions and translate an approval into a purchasable configuration.

**Fleet verdict:** decide whether the organization can provision, secure, update, recover, manage, repair, support, monitor, and roll back the configuration at scale.

**Persona verdict:** for each intended persona, decide fit using usable memory/storage after corporate floor and reserves, sustained performance, battery, graphics or AI capability, docking, reliability, and portability.

Apply the arbitration, deadline, and substitution rules above. The `phase5-final` verdict record carries `pilotAuthorizationRecordRef`, conditions and exceptions with expirations, the arbitration trigger/outcome, residual risks and owners, approvers, and evidence releases. Semantic release validation must resolve the referenced authorization record and prove `approvedAt` precedes `pilotCompletion.startedAt`, which precedes completion.

**Procurement lock:** convert the qualified Hardware Configuration Envelope into approved SKUs, required memory/storage, approved WLAN and SSD classes, display and battery requirements, warranty/repair terms, asset registration, explicit acceptable substitutions, product-change-notification terms, quantity/scope, and return rights. No procurement lock exists before the verdict record.

**Exit condition:** the verdict record is approved and immutable, both verdicts are present, conflicts are resolved or remain blocking, the procurement envelope matches the evidence, and every condition/risk/exception has an owner. Derived artifacts receive the verdict-record and evidence-release IDs.

## Phase 6: Sustain, monitor, and requalify

**Purpose:** maintain qualification as a controlled state.

**Triggers:** BIOS, embedded-controller, driver, firmware, Windows, security-agent, dock, or hardware-component changes; product-change notices or substitutions; security advisories; incident/repair clusters; support expiration; new required applications or workloads; threshold-policy revision; or an expired condition/exception.

**Required work:** monitor each trigger with named model, firmware, security, support, procurement, evidence, exception, and requalification owners. Mark dependent evidence stale through the test plan, assign the full/delta/paper tier, and rerun every affected class at its full floor. Preserve old evidence and comparability boundaries.

**Exit condition:** monitoring and product-change-notification feeds are active, owners and rollback paths are current, triggered evidence is either requalified or the deployment state is HOLD, and reopening rules are recorded.

## Derived artifacts

The following are derived, non-normative views:

- **hp-zbook-8-g2a-spec-sheet.md** — sanitized summary of cited T0 evidence.
- **g2a-persona-fit.md** — deployment-desk view of the corporate floor, capacity waterfall, and issued persona verdicts.
- **g2a-leadership-brief.md** — six-question decision view of an issued gate or verdict.

They cite evidence-release and verdict-record IDs, restate rather than originate claims, and never authorize a gate, pilot, assignment, or purchase on their own.
