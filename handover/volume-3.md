# Zero-Context Handover Report

**Volume 3 of 6: Work in Progress, Backlog, Open Questions, Risks, Continuation Plan**

Report: Zero-Context Handover Report, Enterprise Windows Endpoint IaC Program and Laptop Qualification Workload, v1.0, created 2026-08-27. Series TOC in Volume 1. Identifiers continue from Volumes 1 and 2.

## 11. Work in Progress

**WIP-001: G2a qualification run (the first real execution of the method)**

| Field | Content |
|---|---|
| Objective | Take the in-hand HP ZBook 8 G2a through Playbook Phases 0 to 5 and produce the first filled buying recommendation |
| Completed | Intake facts exist informally (FACT-020..033); research stream verified with corrections (TASK-003); persona routing logic drafted (ART-010) |
| Remaining | Instantiate candidate-manifest.json from ART-012; run the collector (ART-007) on the unit; resolve the WLAN module via Device Manager (Q-009); check driver and BIOS currency via HP CMSL and HPIA; capture the settled corporate floor after a 45 to 60 minute settle; Phase 2 gates: agent-vendor support statements for the new silicon, Citrix and Omnissa VDI client compatibility, security posture decisions on the NPU, Copilot+ features, and Windows Recall; then Phase 3 controlled testing against an incumbent control unit |
| Blockers | No lab bench or control units; threshold and reserve values unset (Q-004); agent-classification.json unfilled (Q-008) |
| Owner | User executes on hardware; assistant produces runbooks and processes outputs |
| Priority | High; it is the proof copy for leadership |
| Deadline | None recorded |
| Continuation instruction | Deliver the user a step-ordered runbook: collector invocation, settle procedure, CMSL commands, what to photograph or paste back. The assistant cannot touch the device; never imply otherwise |
| Definition of done | A verdict record validating against ART-006, with evidence records for every claim, and ART-016 filled end to end |

**WIP-002: Decision ledger (DEC-024)**

| Field | Content |
|---|---|
| Objective | Grade every recommendation's pre-registered predictions post-rollout; publish the cross-decision hit rate as a leadership artifact |
| Completed | Proposal made with rationale (it is the structural defense against confident-but-wrong pyramids) |
| Remaining | User yes or no; if yes, a small ledger schema plus one section in ART-017 |
| Blocker | User decision, the live question at cutoff |
| Definition of done (if approved) | Ledger schema in the package; ART-017 gains a grading step; Phase 6 reports write ledger rows |

**WIP-003: This handover series.** Volumes 1 to 3 delivered; Volumes 4 to 6 pending on "continue." Volume 5 is the bulk item: embedding the full text of all 19 package files plus the two inline research prompts.

**WIP-004: Persona-pain data path.** Section 2 of every recommendation needs SysTrack persona cohorts joined with Graph inventory age and warranty and ServiceNow clusters. Nothing is built; it is design-complete inside ART-016/017. Blocked on Q-006 (persona definitions and mappings) and corporate data access.

**WIP-005: Methodology-validation research loop.** ART-022 (the research prompt) was delivered; the user has not returned results. If results arrive, process them per the prompt's own output spec: confirm, extend, or contradict each program practice; adopt the top findings; list unsupported house inventions honestly.

## 12. Backlog and Future Work

E = explicitly requested by user; P = proposed by assistant, unopposed; C = conditional.

| ID | Task | E/P/C | Why it matters | Trigger or prerequisite | Expected output | Complexity | Risk |
|---|---|---|---|---|---|---|---|
| BKL-001 | Fleet Baseline Report spec | E in substance (T-027 "here is our current fleet"), P as artifact | Part 1 of the leadership story; doubles as the control evidence Phase 3 needs | None; spec can be written now | Field-level spec: Graph inventory queries, SysTrack cohort metrics, ServiceNow clusters with caveat, regeneration cadence | Medium | Corporate data access needed to populate, not to spec |
| BKL-002 | Check-automation matrix | E (T-027), blocked | Converts the team's existing checks into four lanes (collector, bench, pipeline, human-attested); "percent automated" becomes the maturity metric; guarantees no check silently disappears | The team's current checklist (Q-005) | A matrix mapping every existing check to a lane, owner, and automation status | Low once input exists | Building it from invented checks would be worthless; wait for the real list |
| BKL-003 | Phase 1 Intune read-path spec | P | First platform demo: Graph snapshot of all Intune state into git, drift visibility, no write permissions needed | None | Pipeline spec, repo layout, CI validation rules | Medium | Graph permission scoping on the corporate side |
| BKL-004 | Phase 2 write path with CI gates | P (DEC-018) | Git becomes source of truth; PR review becomes change control | Phase 1 proven | Apply pipeline plus policy checks | High | Write-scope risk; rings needed first |
| BKL-005 | Rings and waves as code | P (DEC-018) | Model-and-persona-keyed rings; quarantine-by-default for out-of-envelope devices | Phase 2 | Terraform dynamic groups plus promotion criteria files | High | |
| BKL-006 | Compliance as code | P, the stated destination (T-026) | Baselines as versioned rules; fleet state evaluated continuously in Fabric; audit evidence generated | Phases 1 to 3 plus Fabric pipeline | Rule sets, evaluation jobs, evidence generator | High | |
| BKL-007 | Closed-loop remediation | P (DEC-018) | Drift triggers Remediations, re-verifies, writes evidence | Phase 4 | | High | |
| BKL-008 | G2a walked end to end through ART-017 as the proof copy | P | Demonstrates the whole system to leadership on a real decision | WIP-001 progress plus Q-006 data | A filled ART-016 document | Medium | |
| BKL-009 | Decision ledger build | C on DEC-024 approval | See WIP-002 | User yes | Schema plus pipeline section | Low | |
| BKL-010 | Truths and principles page as a package file | P (TASK-014 caveat) | The twelve truths currently live only in conversation | None | One-page principles doc | Low | |
| BKL-011 | SysTrack-to-ServiceNow device-anchoring fix | P, corporate-side prerequisite | Lifts incident data above the sub-50-percent join floor (FACT-042); reopens DEC-011 | Corporate data engineering | Reliable device join | High, not assistant-executable | |
| BKL-012 | Fabric evidence pipeline | P | Immutable raw zone with hash manifests; the join point for Intune releases, SysTrack, Graph, capture bundles | Fabric workspace access (Q-016) | Landing spec plus normalization jobs | Medium-High | |
| BKL-013 | Run ART-022 research externally | E-adjacent (user created the ask), user-side | Validates or falsifies house methods against literature | User runs it | Results per the prompt's output spec | User effort | |
| BKL-014 | Fill agent-classification.json | User-side | Collector's agent attribution depends on it | User knowledge of the corporate stack | Populated classification file | Low | |
| BKL-015 | Doc-lint CI checks | P (ART-017 mechanical checks) | Enforces claim headers, decision-context line, evidence links | Phase 2 CI exists | Lint rules | Low | Premature before any CI exists |

Do not treat P items as commitments to the user; they are offers on the table. E items and DEC-020 outrank everything.

## 13. Open Questions and Unknowns

UIR = user input actually required. For every question, the receiving LLM should do the "without asking" column's work rather than blocking.

| ID | Question | Why it matters | Known / hypothesis | UIR | How to resolve; what can proceed without asking |
|---|---|---|---|---|---|
| Q-001 | Are there any deadlines: procurement cycle, leadership readout, refresh window? | Prioritization and the pipeline's Step 1 | Nothing recorded | Yes, eventually | Proceed on specs; ask only when scheduling a deliverable |
| Q-002 | Decision ledger: adopt or not? | The live question at cutoff; shapes ART-017 | Proposal made; user's last relevant signal was asking for honesty, then requesting handover | Yes | This is the one question to ask first, alone |
| Q-003 | Who is the qualification authority (verdict arbitration, deadline exceptions)? | ART-013 ask; Phase 5 arbitration | Hypothesis: one of PERSON-002/003/004 | Yes | Leave as a named blank in documents; do not guess |
| Q-004 | Threshold and reserve values with rationale | Every gate and the capacity waterfall | None set; schema fields exist | Yes | Build everything with explicit placeholders; never invent values |
| Q-005 | The team's current device checklist | BKL-002 input | Explicitly requested, not provided | Yes | Do not fabricate checks |
| Q-006 | Persona definitions with SysTrack cohort and AD group mappings | Section 1 and 2 of every recommendation | The G2a target is "high-memory technical roles," informal | Yes | Draft a persona-definition template the user can fill |
| Q-007 | Pilot privacy owner | Phase 4 requirement REQ-050 | None named | Yes | Blank until pilot planning |
| Q-008 | agent-classification.json contents | Collector attribution | Fallback exists: unclassified-thirdparty | Helpful | Collector runs without it; results just classify less |
| Q-009 | Exact WLAN module (MediaTek RZ616 vs MT7925) | Driver-wave planning; envelope pinning | Both plausible (FACT-028) | Yes, needs device | One Device Manager screenshot resolves it; include in the WIP-001 runbook |
| Q-010 | Canonical NPU TOPS figure (50 vs 55 vs 60) | Spec accuracy; Copilot+ eligibility claims | HP datasheet says up to 55 for the family, 60 top SKU (FACT-027) | No | Resolvable at T1 from HP's datasheet if web access exists; else mark unresolved, exclude from claims |
| Q-011 | Does an air-gap constraint bind the current program? | Where corporate data may be processed | Historical practice from the prior project; current status unknown | Yes, before any corporate data handling | Assume conservatively: corporate data stays on corporate systems |
| Q-012 | Is the 38,129 fleet count current? | Any denominator claim | From SRC-003, months old | No | Re-pull from Graph inventory when access exists; until then label it dated |
| Q-013 | Budget, per-seat costs, pilot size | Brief and template placeholders | None recorded | Yes | Keep placeholders; costs never invented |
| Q-014 | Have any briefs been delivered to leadership? | Whether documents are live or drafts | No delivery recorded | Yes, when relevant | Treat all as drafts |
| Q-015 | Did the user run ART-022 and get results? | WIP-005 | Unknown | Yes, when relevant | Nothing blocks on it |
| Q-016 | Does a Fabric workspace exist with an access model for this program? | BKL-012 | Fabric confirmed as the data layer (DEC-002); provisioning state unknown | Yes, at build time | Spec the landing zone regardless |

## 14. Risks, Failure Modes, and Watchouts

Probability and impact stated qualitatively. "Occurred" means it already happened at least once in this engagement.

| ID | Risk | Prob | Impact | Warning signs | Mitigation | Occurred |
|---|---|---|---|---|---|---|
| RISK-001 | Reframing the work as DEX lineage or targeting Brooks | Med | High: repeats a double-corrected error | Capstone vocabulary in briefs; "as the DEX work showed" phrasing | REQ-003; ART-015 scoping; this report's repeated flags | Yes, twice, corrected |
| RISK-002 | Silently joining evidence across BIOS, driver, OS, or agent baselines | Med | High: corrupt comparisons | Comparisons without baseline fields | REQ-007; evidence-record baseline block | No |
| RISK-003 | Generalizing the single in-hand unit to fleet claims | Med | High | "The G2a draws X" without n=1 label | REQ-040; sampling floors in ART-001 | No |
| RISK-004 | Answer-first documents built before evidence exists | Med | High: the exact Minto failure mode the user's own rule names | A recommendation drafted with no verdict record | DEC-004 freeze; ART-017 Step 3 rule; DEC-024 ledger if adopted | No |
| RISK-005 | Acting on stale facts: driver versions, fleet count, warranty data | High | Med | Dates older than the action they inform | RV flags in §6; staleness dependencies in test-plan schema | No |
| RISK-006 | Loss of the artifact package (session workspace resets; zip lives only on the user's machine) | Med | High | A new session lacking the files | Volume 5 embeds full text of all 19 files; ask the user to re-upload the zip rather than reconstructing from memory when fidelity matters | Structural |
| RISK-007 | Asking the user to restate context he already gave | Med | Med: trust cost with this specific user | Questions answerable from this report | This report; REQ-022 one-question rule | No |
| RISK-008 | Resurrecting the deleted general document standard (ART-020) | Low | Med | A "writing standard for all docs" reappearing | DEC-021a marked SUPERSEDED; §20 in Volume 4 | No |
| RISK-009 | Incident or ticket data deciding a verdict | Med | High | Per-model incident claims without the anchoring caveat | DEC-011; FACT-042/043 | No |
| RISK-010 | Scope drift away from the four-part goal | Med | Med | Platform work crowding out DEC-020 deliverables | DEC-020 marked governing; DEC-018/019 marked tentative | Mild (T-028 was the user pulling focus back) |
| RISK-011 | The receiving LLM claiming access it lacks (device, corporate systems, the zip) | Med | High: fabrication | "I ran the collector" without a run record | State access limits plainly; produce runbooks for the user instead | No |
| RISK-012 | Pyramid polish masking thin evidence | Med | High | Confident recommendations, weak evidence links | Gap rules, ship gate, honest-limits sections; the ledger proposal exists precisely for this | No |
| RISK-013 | Checklist conversion silently dropping checks | Low | Med | Matrix rows fewer than the source list | Four-lane rule: every check lands somewhere or carries a recorded reason | No |
| RISK-014 | Inventing thresholds, costs, persona definitions, or checklist items to fill placeholders | Med | High | Numbers with no Q-ID or evidence reference | Q-004/005/006/013 discipline: placeholders stay placeholders | No |

## 25. Recommended Continuation Plan

### Immediate next action

Ask the user exactly one question, alone: adopt the decision ledger or not (DEC-024). Inputs: WIP-002. Method: one short message, no bundled asks. Expected output: yes or no. Completion test: DEC-024 status changes to Approved or Rejected. User input necessary: yes, by definition.

### Next three actions, in order

1. **Fleet Baseline Report spec (BKL-001).** Inputs: ART-016 section 2 fields, FACT-040..047 constraints, DEC-002 sources. Method: field-level spec naming each Graph query, SysTrack cohort metric, and ServiceNow cluster with its caveat, plus regeneration cadence; deliver as a package file. Completion test: every section-2 field of ART-016 maps to a named source and query. No user input required.
2. **Phase 1 Intune read-path spec (BKL-003).** Inputs: DEC-002, DEC-018, REQ-031..033. Method: snapshot pipeline design (Graph read scopes, export format, git repo layout, CI validation rules, drift-diff behavior). Completion test: a corporate engineer could implement it without further design. No user input required.
3. **WIP-001 runbook for the G2a.** Inputs: ART-007 invocation modes, ART-001 Phase 2 and 3 requirements, Q-009. Method: step-ordered instructions the user executes on the unit, including the Device Manager WLAN check, CMSL and HPIA currency, settle procedure, and what to paste back. Completion test: user can run it start to finish without questions. User input required only as execution.

### Near-term work

Check-automation matrix the moment Q-005's checklist arrives. Threshold-policy instance the moment Q-004 values arrive. Persona-definition template offered against Q-006. Truths page (BKL-010) as a low-effort package addition. Volume 4 to 6 of this series on "continue."

### Conditional branches

- DEC-024 yes: build the ledger schema and ART-017 grading step before other work; it is small and shapes Phase 6 reporting.
- DEC-024 no: proceed identically but keep prediction grading inside per-decision Phase 6 reports only; do not re-pitch the ledger.
- Checklist arrives: BKL-002 jumps the queue; it is fast and unlocks the "automated or in IaC" leadership claim.
- Corporate access materializes (Graph, SysTrack, Fabric): shift from specs to builds, starting with the read-path snapshot because it is read-only and lowest risk.
- User goes quiet on inputs: continue down the no-user-input column (specs, runbook, truths page, this series) and never block.

---

**End of Volume 3.** Volume 4 continues at **§15 Stakeholders, People, and Organizations**, then §16 Systems and Tools, §17 Technical Architecture, §18 Research and Evidence Base, §19 Calculations, §20 Rejected Directions, §21 Communication History.
