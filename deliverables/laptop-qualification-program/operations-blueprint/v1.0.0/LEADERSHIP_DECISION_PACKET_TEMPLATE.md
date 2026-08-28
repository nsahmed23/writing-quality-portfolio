# Leadership Decision Packet Template

> **Decision ask — exact governed text:** `MISSING — copy verbatim from the applicable pilot-authorization or phase5-final verdict record and cite its record ID and JSON pointer.`
>
> **Packet status:** `NOT_READY`
>
> **Allowed action while NOT_READY:** `RETURN_FOR_EVIDENCE`

This packet is a derived decision view. It may restate approved records; it may not originate a claim, number, threshold, causal attribution, exception, approval, recommendation, or procurement scope. `NOT_READY` remains the default until the governed claim chain, gate ledger, evidence releases, and verdict references pass semantic validation.

## Joined decision chain — [leadership-claim-chain record ID required]

Use one row per candidate-persona decision. This is the page-one leadership view: it keeps persona need, incumbent evidence, candidate/control results, cost, and recommendation in one chain. Every numeric cell must retain its unit, observation window, denominator, distribution, coverage, missingness, exclusions, and source pointer.

| Persona need | Current fleet issue | Candidate/control result | Delta / uncertainty | Cost / business effect | Recommendation | Evidence / freshness |
|---|---|---|---|---|---|---|
| **Persona:** `MISSING — public persona ID`<br>**Measured requirement:** `MISSING — metric, unit, window, and requirement-record pointer`<br>**Capacity waterfall:** `MISSING — exact child of this persona-verdict pointer; physical/formatted capacity, corporate floor/image, approved reserve, remaining headroom, persona requirement, and pass/shortfall`<br>**Distribution:** `MISSING — unit count, run/window count, median, spread`<br>**Coverage:** `MISSING — planned, observed, missing, exclusions` | **Incumbent/cohort:** `MISSING — incumbent projection from the same candidate manifest plus cohort ref`<br>**Issue tested:** `MISSING — exact record-backed statement; no generic pain claim`<br>**Baseline/window:** `MISSING — configuration fingerprint and start/end`<br>**Distribution:** `MISSING — denominator, median/rate, spread, outliers`<br>**Coverage/missingness:** `MISSING`<br>**Attribution:** `MISSING — direct, controlled delta, association, or unknown` | **Frozen manifest/test/conditions:** `MISSING — one manifest; candidate, incumbent, sibling projections; test-plan and exact condition-set refs`<br>**Candidate:** `MISSING — units, accepted runs, median, spread for every condition`<br>**Incumbent:** `MISSING — units, accepted runs, median, spread for every condition`<br>**Sibling/alternative:** `MISSING — units, accepted runs, median, spread for every condition`<br>**Comparability:** `MISSING — baseline fingerprint, test-pack version, agent state, exclusions`<br>**Coverage/missingness:** `MISSING for every role and condition` | **Defined comparison:** `MISSING — exact formula and direction`<br>**Observed delta:** `MISSING — value, unit, and spread/confidence interval if preregistered`<br>**Run/unit variation:** `MISSING`<br>**Uncertainty:** `MISSING — missing results, outliers, exclusions, unsupported states, and limitations`<br>**Claim strength:** `MISSING — direct measurement, controlled delta, association, or no admissible claim` | **Effect type:** `MISSING — COST_DELTA / NON_PRICE_EFFECT / NOT_MEASURED`<br>**Cost branch:** `MISSING — exact configuration; dated candidate/control quote refs; currency, quantity, validity, formula, uncertainty`<br>**Non-price branch:** `MISSING — metric/unit/direction, denominator, window, distribution, coverage, limitations, sources`<br>**Not-measured branch:** `MISSING — NO_MEASURED_EFFECT_CLAIM, reason, decision impact`<br>**No-evidence rule:** `NOT_MEASURED cannot be rewritten as a benefit` | **Verbatim verdict statement:** `MISSING — do not draft a recommendation here`<br>**Fleet verdict:** `NOT_ISSUED`<br>**Persona verdict:** `NOT_ISSUED`<br>**Scope/conditions/expiration:** `MISSING`<br>**Procurement envelope/substitution status:** `MISSING`<br>**Permitted action now:** `RETURN_FOR_EVIDENCE` | **Portable contract, manifest/test/threshold refs:** `MISSING`<br>**Evidence and verdict refs:** `MISSING`<br>**Provenance:** `MISSING — T0/T1/T2 with T2 corroboration`<br>**Tool/test-pack versions:** `MISSING`<br>**Observed/admitted/approved times:** `MISSING`<br>**Freshness:** `UNKNOWN`<br>**Staleness dependencies:** `MISSING` |

If non-price business effect is not measured, the renderer must use the controlled statement, assumption, and decision-impact text defined in section 5.4 of the operating model. It may still display current candidate and incumbent commercial quotes, but it may not add an inferred productivity, experience, deployment, support, or savings benefit.

Add rows only from validated claim-chain records. A row with a missing leadership link remains visible and `NOT_READY`; do not remove it to make the packet appear complete.

## Decision identity — [pilot-authorization or phase5-final verdict record ID required]

| Field | Required governed value |
|---|---|
| Decision stage | `MISSING — PILOT or FINAL_PROCUREMENT from the applicable verdict record` |
| Exact decision-record pointer | `MISSING — <verdict-record-id>#/<field>` |
| Requested scope | `MISSING — configuration, public persona/cohort labels, quantity, region class, duration, and expiration copied from the governed record` |
| Packet ID and version | `MISSING — immutable derived-packet ID/version` |
| Leadership claim-chain reference | `leadership-claim-chain.json — status is NOT_ISSUED until populated and validated` |
| Candidate manifest | `MISSING — candidate-manifest ID/version` |
| Test plan | `MISSING — frozen test-plan ID/version` |
| Threshold policy | `MISSING — frozen threshold-policy ID/version` |
| Evidence release | `MISSING — immutable evidence-release ID/version` |
| Pilot authorization | `MISSING — exact pilot-authorization verdict-record ID and pointer. Required for both PILOT and FINAL_PROCUREMENT packets; if the portable record says NOT_REQUIRED, render that exact status with its governed authority approval and reason, never an unreferenced NOT_APPLICABLE.` |
| Final verdict | `MISSING — phase5-final verdict-record ID or NOT_ISSUED` |
| Procurement envelope | `MISSING — verdict-record pointer or NOT_ISSUED` |
| Decision owner role | `ROLE_QUALIFICATION_AUTHORITY` |
| Packet producer role | `decision product owner` |
| Independent verifier role | `qualification governance owner` |
| Leadership render-manifest record | `MISSING — semantic-validation/input, claim-chain, decision-claim, exact source-record set, renderer release/version, template digest/version, privacy release, security-test PASS, generated-at time, and packet SHA-256` |
| Semantic input binding | `MISSING — exact portable-contract refs, canonical input SHA-256, semantic-validation record ID/digest, and validation time` |

Release rule: every reference above must resolve with ordinal case-sensitive equality. A missing, stale, expired, mismatched, or non-resolving required reference keeps this packet `NOT_READY`.

## Gate ledger — [manifest, evidence-release, pilot-authorization, and verdict IDs required]

Enter only the outcome present in the cited governed record. Do not infer `PASS` from a green test, an HTTP success, an intact hash, an approval discussion, or the absence of an incident.

| Gate or controlled state | Governed record ID and pointer | Recorded outcome | Approval/observation time | Distribution, coverage, and missingness required for this gate | Freshness and staleness result | Blocking reason or exception record |
|---|---|---|---|---|---|---|
| Phase 0 configuration, sampling, threshold, reserve, and authority freeze | `MISSING` | `NOT_ISSUED` | `MISSING` | `MISSING — applicable test-class floors and frozen population strata` | `UNKNOWN` | `MISSING_PHASE0_FREEZE` |
| Phase 1 device ground truth for candidate and controls | `MISSING` | `NOT_ISSUED` | `MISSING` | `MISSING — in-scope units, completed captures, failed sections, and identity unknowns` | `UNKNOWN` | `MISSING_PHASE1_EVIDENCE` |
| Phase 2 compatibility and security hard gate | `MISSING` | `NOT_ISSUED` | `MISSING` | `MISSING — critical matrix combinations, units, runs, coverage, missing results, and unsupported dependencies` | `UNKNOWN` | `MISSING_PHASE2_APPROVAL` |
| Phase 3 provisional lab gate | `MISSING` | `NOT_ISSUED` | `MISSING` | `MISSING — candidate, incumbent, and sibling/alternative distributions under matching conditions and baseline strata` | `UNKNOWN` | `MISSING_PHASE3_VERDICT` |
| Pilot stop conditions and rollback approval | `MISSING` | `NOT_ISSUED` | `MISSING` | `MISSING — stop thresholds, severity mapping, spare/device-swap capacity, duration, and minimum coverage` | `UNKNOWN` | `MISSING_PILOT_SAFETY_PLAN` |
| Immutable pre-enrollment pilot authorization | `MISSING` | `NOT_ISSUED` | `MISSING` | `MISSING — authorized population strata and privacy approval` | `UNKNOWN` | `MISSING_PILOT_AUTHORIZATION` |
| Phase 4 representative production pilot | `MISSING` | `NOT_STARTED` | `MISSING` | `MISSING — participants, accepted daily windows, survey responses, telemetry coverage, missingness, exclusions, and stop-condition state` | `UNKNOWN` | `MISSING_PHASE4_EVIDENCE` |
| Phase 5 fleet verdict | `MISSING` | `NOT_ISSUED` | `MISSING` | `MISSING — cited fleet-readiness evidence and unresolved risks` | `UNKNOWN` | `MISSING_FLEET_VERDICT` |
| Phase 5 persona verdict for each recommended persona | `MISSING` | `NOT_ISSUED` | `MISSING` | `MISSING — capacity waterfall and persona-specific evidence distribution` | `UNKNOWN` | `MISSING_PERSONA_VERDICT` |
| Procurement configuration lock and substitution state | `MISSING` | `NOT_ISSUED` | `MISSING` | `MISSING — exact envelope, quantity/scope, quote currency, and known component identity` | `UNKNOWN` | `MISSING_PROCUREMENT_ENVELOPE` |
| Bundle semantic validation and leadership claim-chain validation | `MISSING` | `NOT_RUN` | `MISSING` | `MISSING — validator release, input digest, reason codes, and zero unresolved errors` | `UNKNOWN` | `MISSING_SEMANTIC_VALIDATION` |

The packet is not ready if any required row is `NOT_ISSUED`, `NOT_RUN`, `NOT_STARTED`, `UNKNOWN`, `STALE`, `HOLD`, or `FAIL`. `INCONCLUSIVE` also blocks unless the portable deadline rule resolves to the exact governed, scope-bounded, expiring risk-exception path; that path remains visibly inconclusive and may authorize only its written scope. An exception never converts evidence to `QUALIFY`.

## Current fleet portfolio and selected incumbent cohort — [fleet-portfolio, incumbent evidence-release, and cohort record IDs required]

This section answers both questions without mixing their scopes. The issued, privacy-approved fleet-portfolio projection summarizes the current managed estate by model/configuration, persona allocation, age/warranty, platform baseline, lifecycle state, issue prevalence, coverage, missingness, and unknown configuration. The highlighted row is the exact incumbent configuration and persona cohort used by the candidate decision. The portfolio remains a derived index; the linked released evidence records remain authoritative.

| Fleet-portfolio control | Required projection |
|---|---|
| Snapshot, scope, and query/join policy | `MISSING — fleet-portfolio record, snapshot/window, versioned query-pack and join-policy digests, privacy-policy/release refs, and aggregation floor` |
| Estate reconciliation | `MISSING — source-record, unique-device, duplicate, planned, observed, missing, excluded, stale, retired, offline, unhealthy, join-eligible, joined, unjoinable, matched, unmatched, and unknown-component counts; method/result/evidence; exact arithmetic` |
| Configuration and persona allocation | `MISSING — model/configuration cohorts, counts, persona allocations, and unassigned counts` |
| Lifecycle and platform coverage | `MISSING — age/warranty, Windows/BIOS/driver/security baseline, lifecycle state, and evidence refs` |
| Issue prevalence | `MISSING — issue evidence by configuration/cohort, coverage, and attribution boundary` |
| Selected incumbent row | `MISSING — fleetPortfolioCohortPointer matching the current-fleet incumbent, cohort, and recommended persona` |

| Decision-relevant dimension | Incumbent fleet/cohort observation | Distribution and denominator | Coverage, missingness, and exclusions | Baseline and observation window | Provenance, tool/query-pack version, and artifact hash | Evidence reference and freshness |
|---|---|---|---|---|---|---|
| Qualified model and configuration envelope | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Persona, cohort, population, and observation coverage | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Device age, warranty, and support state | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Windows, BIOS, driver, firmware, and security-agent baseline | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Physical capacity, corporate floor, reserve, and workload headroom | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Resource pressure and representative workload timing | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Application failure and compatibility state | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Battery and standby | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Dock attach, detach, sleep, and resume reliability | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Provisioning, update, compliance, and management state | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Incidents, repairs, support contacts, and support effort | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Regions and work patterns represented | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Source provenance, query/join policy, and artifact integrity | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |
| Outliers, exclusions, limitations, freshness, and requalification triggers | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING / UNKNOWN` |

Do not expose an employee, device, tenant, group, ticket, storage location, or direct cohort identity. Use approved public aliases and governed aggregate record IDs. A low-count or otherwise disclosive cohort remains private and is reported here as `WITHHELD_BY_PRIVACY_RULE` with the privacy-rule reference; it is not reported as zero.

## Rollout and monitoring — [pilot authorization or final verdict, rollout-monitoring record, and observed-state readback IDs required]

**Rollout state:** `BLOCKED — required authorization and readback records are missing.`

| Rollout control | Governed requirement | Observed/readback state | Coverage or scope | Owner role | Stop/rollback reference | Record ID, freshness, and blocking result |
|---|---|---|---|---|---|---|
| Authorized stage and ring | `MISSING — PILOT or PRODUCTION and public ring alias from authorization` | `UNKNOWN` | `MISSING — approved population/assignment scope` | `Windows deployment owner` | `MISSING` | `MISSING / UNKNOWN / BLOCKED` |
| Persona eligibility | `MISSING — persona-verdict and procurement-envelope pointers` | `UNKNOWN` | `MISSING — eligible/ineligible/missing counts` | `qualification operations authority` | `MISSING` | `MISSING / UNKNOWN / BLOCKED` |
| Verified package and desired-state revision | `MISSING — package-verification record/digest, signer/trust/revocation result, Git revision, rendered-stack digest, and approved plan digest` | `UNKNOWN` | `MISSING — target objects and assignments` | `IaC operator` | `MISSING` | `MISSING / UNKNOWN / BLOCKED` |
| Pre-write authorization | `MISSING — attested authorization ID, single-use nonce, issuance/expiry, exact plan/package/writer/object/scope/approval bindings, and consumption record` | `NOT_AUTHORIZED` | `MISSING — observed population, approved maximum, exclusions, membership snapshot, group rule and filter digests` | `protected environment authority` | `MISSING` | `MISSING / EXPIRED / REVOKED / REPLAYED / BLOCKED` |
| Independent observed-state readback | `MISSING — Graph readback contract and expected digest` | `NOT_RUN` | `MISSING — objects, assignments, and device-state coverage` | `Windows endpoint engineering owner` | `MISSING` | `MISSING / UNKNOWN / BLOCKED` |
| Pilot safety controls | `MISSING — incident-rate, severity, evidence-coverage, and other frozen stop thresholds` | `UNKNOWN` | `MISSING — monitored population and window` | `pilot operations owner` | `MISSING — approved rollback plan` | `MISSING / UNKNOWN / BLOCKED` |
| Production promotion | `MISSING — completed pilot, final verdict, procurement envelope, and approved persona scope` | `NOT_AUTHORIZED` | `MISSING` | `Windows deployment owner` | `MISSING` | `MISSING / UNKNOWN / BLOCKED` |
| Production monitoring contract | `MISSING — semantic validation/input, decision claim, leadership render manifest; Git/canonical Atmos stack render/Terraform/package/ring binding; query pack; baseline; frozen floors and thresholds` | `NOT_AUTHORIZED` | `MISSING — all ten governed signal classes, telemetry cohort/coverage, primary alert, independent dead-man` | `monitoring owner` | `MISSING — exact stop, rollback, and requalification pointers` | `MISSING rollout-monitoring record / BLOCKED` |

| Monitoring signal | Governed trigger/threshold | Source/tool and version | Evaluation cadence or event SLA | Coverage/missingness rule | Alert owner role and route | Current state, evidence ref, and freshness |
|---|---|---|---|---|---|---|
| Package, configuration, assignment, or portal drift | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `IaC configuration owner — private alert route ref required` | `UNKNOWN / MISSING` |
| Graph write/readback mismatch or partial operation | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `Graph automation owner — private alert route ref required` | `UNKNOWN / MISSING` |
| Pilot stop condition | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `pilot operations owner — private alert route ref required` | `UNKNOWN / MISSING` |
| Evidence, verdict, condition, or exception staleness | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `qualification governance owner — private alert route ref required` | `UNKNOWN / MISSING` |
| BIOS, firmware, driver, Windows, agent, dock, app, support, advisory, or component trigger | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `requalification owner — private alert route ref required` | `UNKNOWN / MISSING` |
| Incident, repair, support-effort, or compliance threshold | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `fleet operations owner — private alert route ref required` | `UNKNOWN / MISSING` |

An apply, assignment, or API success is not rollout success. The displayed state changes only after an independent read-after-write result matches the authorized revision, scope, assignment, and device state. Missing or mismatched readback remains `BLOCKED`.

## Conditions and residual risks — [phase5-final verdict-record ID required]

| Record item | Exact governed text and scope | Owner role | Compensating control or mitigation | Expiration / closure evidence | Current status and freshness | Effect on this decision |
|---|---|---|---|---|---|---|
| Condition | `MISSING — copy from verdict record or state NONE_RECORDED with record pointer` | `MISSING — public role` | `MISSING` | `MISSING` | `UNKNOWN` | `NOT_READY until resolved or validly accepted` |
| Exception | `MISSING — owner, reason, scope, and evidence required for closure` | `MISSING — public role` | `MISSING` | `MISSING` | `UNKNOWN` | `NOT_READY until a current authority record is cited` |
| Residual risk | `MISSING — copy from verdict record` | `MISSING — public role` | `MISSING` | `MISSING` | `UNKNOWN` | `NOT_READY until disposition is record-backed` |
| Component substitution | `MISSING — exact proposed identity and qualified-envelope comparison` | `procurement qualification owner` | `MISSING — observable-equivalence or delta-qualification reference` | `MISSING` | `UNKNOWN` | `HOLD when identity is unknown or delta qualification is pending` |

Delete placeholder rows only when the cited final verdict positively records that no item exists in that category. Silence is not `NONE_RECORDED`. An expired condition or exception, unknown component identity, pending delta qualification, or unresolved critical risk keeps the packet `NOT_READY`. A date-only expiration is an exclusive boundary, so an item dated on the packet evaluation day is already expired. A persona/fleet conflict cannot render an unconditional recommendation: it needs retained `verdict-conflict` arbitration plus current conditional assignment and procurement records, or it remains blocking.

## Claim appendix — [derived-packet render-manifest ID required]

Create one appendix row for every headline, table statement, number, comparison, risk, cost, and recommendation displayed above. A claim without a row must not render.

| Claim ID | Exact displayed claim and location | Claim class | Canonical record ID and JSON pointer | Evidence refs and provenance | Tool, query-pack, test-pack, and renderer versions | Baseline, condition, cohort, and window | Distribution, coverage, missingness, outliers, and exclusions | Freshness, staleness dependencies, and limitations | Independent verification |
|---|---|---|---|---|---|---|---|---|---|
| `MISSING` | `MISSING` | `persona need / current fleet issue / candidate-control result / delta / cost / recommendation / risk / rollout` | `MISSING` | `MISSING — T0/T1/T2; every T2 needs a resolvable T0/T1 corroboration ref` | `MISSING` | `MISSING` | `MISSING` | `UNKNOWN — missing freshness prevents rendering` | `MISSING — verifier role, validation record, and time` |

## Publication check — [semantic-validation and privacy-release record IDs required]

All answers must be `YES` before status may change from `NOT_READY`:

- [ ] Is the exact decision ask copied from a current governed authorization or verdict pointer?
- [ ] Does every recommended persona have a complete persona-need, current-fleet-issue, candidate/control, cost/business-effect, and recommendation chain?
- [ ] Are candidate, incumbent, and sibling/alternative projections from one frozen manifest, and does each cover the exact same frozen condition set, protocol, baseline stratum, and test pack?
- [ ] Does every displayed number retain unit, denominator, observation window, distribution, coverage, missingness, exclusions, and evidence reference?
- [ ] Are T2 records corroborated by a resolvable T0 or T1 record supporting the same claim?
- [ ] Are all gate, evidence, verdict, procurement, condition, exception, and rollout-readback references current and semantically valid?
- [ ] Is the recommendation copied without strengthening its outcome, scope, conditions, or expiration?
- [ ] Does the semantic-input digest bind all direct source records and decision-relevant release members, distributions, T2 corroboration records, source verdicts, and quotes?
- [ ] Are direct employee, device, tenant, group, ticket, and evidence-store identities absent from the public packet?
- [ ] Is every headline and recommendation represented in the claim appendix and independently verified?
- [ ] Does the render manifest bind this packet to its exact input-record digests and renderer version?
- [ ] Did every field pass context-aware Markdown/HTML/URL/CSV encoding, safe-link, active-content, control-character, length, and spreadsheet-formula checks?

If any answer is `NO`, `UNKNOWN`, or unsupported by a governed record, publish only as an unissued `NOT_READY` draft and show the blocking reason codes. Do not replace missing evidence with narrative.
