# Zero-Context Handover Report

**Volume 4 of 6: Stakeholders, Systems and Tools, Technical Architecture, Research Base, Calculations, Rejected Directions, Communication History**

Report: Zero-Context Handover Report, Enterprise Windows Endpoint IaC Program and Laptop Qualification Workload, v1.0, created 2026-08-27. Series TOC in Volume 1. Identifiers continue from prior volumes.

## 15. Stakeholders, People, and Organizations

**Current program people**

| ID | Name | Role and relationship | Authority | Open actions |
|---|---|---|---|---|
| PERSON-001 | Nazeer | The user. Windows Endpoint Engineer, new-hardware team. Owns execution on hardware and corporate systems; the assistant's sole channel | Directs all work | Six input items (Q-002..008 family); runs WIP-001 on the unit |
| PERSON-002 | Mike Green | Leadership line, exact title unrecorded | Approves program and spend (with 003, 004) | Receive ART-013 when user chooses |
| PERSON-003 | Kyle Campbell | Leadership line, exact title unrecorded | Same | Same |
| PERSON-004 | Javier Robles | Leadership line, exact title unrecorded | Same | Same |
| PERSON-005 | Justin Brooks | Prior DEX capstone sponsor. NOT a stakeholder of this program (REQ-003) | None here | None; do not target or cite |

Disambiguation: the capstone record mentions a readout to "Mike's and Sean Bradley's organizations." That "Mike" being PERSON-002 is an INFERENCE, unconfirmed.

**Historical people from SRC-003 (capstone era; current relevance UNKNOWN; do not contact or cite without user direction)**

| ID | Name | Historical role | Possible future relevance |
|---|---|---|---|
| PERSON-006 | Justin Gehman | SysTrack platform administrator | High if SysTrack cohort work (Q-006) proceeds |
| PERSON-007 | Chris Duntzee | Asset management | Possible for fleet inventory and warranty data (BKL-001) |
| PERSON-008 | Howie Cho | C-SAT and persona data owner | Low; capstone-specific |
| PERSON-009 | Seth White Law | Architect, incident history | Possible for ServiceNow anchoring (BKL-011) |
| PERSON-010 | Stacey Brown | Capstone executive sponsor | None known |
| PERSON-011 | Nitin Tandon | Global CIO, capstone readout attendee | Context only |
| PERSON-012/013 | Sana Azhar, Taylor Huston | Capstone teammates | None known |
| PERSON-014 | Sean Bradley | Org leader at a capstone readout | Context only |

**Organizations**

| ID | Name | Relationship |
|---|---|---|
| ORG-001 | Vanguard | Employer; the enterprise whose fleet this is |
| ORG-002 | GTO Workplace Services | The user's division |
| ORG-003 | New-hardware team | The user's team; runs device suitability checks today |
| ORG-004 | HP | Candidate-device vendor; source of CMSL, HPIA, datasheets, product-change notifications |
| ORG-005 | AMD | Candidate silicon vendor ("Gorgon Point" family) |
| ORG-006 | Lakeside Software | SysTrack vendor |
| ORG-007 | Microsoft | Intune, Graph, Fabric, Windows, Autopatch, Power Platform |
| ORG-008/009 | Omnissa, Citrix | iPad UEM (Omnissa) and VDI (both) |
| ORG-010 | ServiceNow | ITSM vendor |
| ORG-011 | ZScaler | Zero-trust network vendor shaping the fleet's egress path |

## 16. Systems, Products, Tools, and Environments

Access status is from the assistant's seat: the assistant has NO access to any corporate system; the user is presumed to have corporate access, unverified per system.

| ID | System | Purpose in program | Status and limitations | Next action |
|---|---|---|---|---|
| SYS-001 | Microsoft Intune | Sole management and deployment plane; every tested system is Intune-built; future state-as-code target | Operational corporately; no program integration yet | BKL-003 read-path spec |
| SYS-002 | Microsoft Graph API | Read and eventually write path for Intune state; inventory; Endpoint Analytics telemetry leg | Permission scopes undefined (Q-016-adjacent) | Define read scopes in BKL-003 |
| SYS-003 | SysTrack (Lakeside) | Fleet experience telemetry; persona cohorts; pilot measurement | Hard limits: active-time-only impact counting (FACT-040), Windows-tuned calibration (FACT-041), 30-day per-device history cap noted in SRC-003 | Persona cohort mapping (Q-006) |
| SYS-004 | ServiceNow | Incident and repair signal | Sub-50-percent device anchoring (FACT-042); caveat mandatory | BKL-011 is the corporate fix |
| SYS-005 | Terraform / OpenTofu | Declarative IaC for the surrounding plane: groups, identities, workspace | Not yet used | Enters at BKL-004/005 |
| SYS-006 | Atmos | Stack and configuration organization over Terraform | Not yet used | Same |
| SYS-007 | Microsoft Fabric / OneLake / Power BI | Data layer: immutable hash-manifested raw bundles, downstream normalization, dashboards | Workspace existence unknown (Q-016) | BKL-012 landing spec |
| SYS-008 | Ansible | Lab bench post-provisioning and instrumentation only (REQ-034) | No lab exists yet | With bench setup |
| SYS-009 | Power Platform | Approvals and routing app for verdicts and exceptions | Not designed | Later phase |
| SYS-010 | Omnissa Workspace ONE | iPad UEM under BYOD User Enrollment; VDI publisher | iPad lane ruled unmeasurable (FACT-046); VDI client is a Phase 2 gate | Client compatibility check in WIP-001 |
| SYS-011 | Citrix | VDI alternative; Phase 2 gate; persona routing branch | Same gate | Same |
| SYS-012 | HP CMSL and HPIA | Driver and BIOS currency, softpaq state, T1 facts | Commands go in the WIP-001 runbook | Runbook |
| SYS-013 | ZScaler ZTNA | The corporate network path all machines ride (FACT-033) | A capstone-era blocker note exists: an AWS_CA_BUNDLE environment variable for ZScaler interception; current relevance UNKNOWN | Flag if API scripting resumes |
| SYS-014 | The G2a unit | The physical candidate; the only hardware environment | n=1; imaged 2026-08-10; drivers aging | WIP-001 |
| SYS-015 | Assistant session workspace | Linux container holding the package and stage; resets between sessions | RISK-006; durable copies are the user's zip and Volume 5 | Re-request zip upload when fidelity matters |
| SYS-016 | Git and CI (planned) | Future home of Intune state, contracts, doc-lint | Does not exist yet | BKL-003 defines it |
| SYS-017 | Windows Autopatch and Endpoint Analytics | The gated change stream and Graph's second telemetry leg | Named in bindings; not designed | Phase 3 era |
| SYS-018 | OPA / Conftest (planned) | Policy-as-code gates enforcing the contract schemas in CI | Not built | BKL-015 |
| SYS-019 | Pester | PowerShell test framework for the collector | Unit tests written; seven integration scenarios skipped pending bench | Run at bench setup |
| SYS-020 | Credential vault (capstone-era) | Held seven canonical keys including SYSTRACK_DVT_READWRITE and M365_INTEGRATION_SECRET | [ALL VALUES REDACTED: obtain from the user's authorized secret store]. Whether this vault serves the current program is UNKNOWN | Confirm before any API work |

## 17. Technical Architecture or Process Model

**Model A: qualification workload evidence flow (designed, unbuilt beyond the collector script)**

```
manifest + test-plan + threshold-policy (frozen at Phase 0)
        |
G2a unit --Get-EvalEvidence.ps1--> evidence bundle (JSON + raw files + SHA-256 manifest)
bench workloads ------------------^
        |
Fabric raw zone (immutable, hash-manifested)  <-- SysTrack cohorts, Graph inventory, ServiceNow (caveated)
        |
normalization --> evidence-records --> verdict-record (Phase 5)
        |                                   |
Power BI dashboards            buying-recommendation (ART-016 via ART-017)
                                            |
                              Phase 6 monitor grades pre-registered predictions
```

Prose: contracts are frozen first; the collector produces tamper-evident bundles on the device; corporate telemetry joins in Fabric; nothing reaches a verdict without validating against the schemas; the recommendation renders from verdict and evidence records; Phase 6 re-measures against the predictions the document registered. Security boundaries: serial redaction at collection; aggregate-only experience claims; privacy owner gate before any pilot join. Testing state: Pester unit tests only. Technical debt: collector unexecuted on target; schemas never validated against real instances; no pipeline exists.

**Model B: platform target (five phases, DEC-018, design only)**

```
git repo (Intune state, rules, thresholds)
   Phase1: Graph read --> snapshot to git --> drift diffs
   Phase2: PR merge --> CI gates (schema, assignment safety, OPA) --> Graph write --> Intune
   Phase3: rings as code (Terraform dynamic groups by model+persona; quarantine by default)
           update waves promote on telemetry gates, not install success
   Phase4: baselines as versioned rules; Graph+SysTrack state --> Fabric --> continuous evaluation
           audit evidence generated from pipeline
   Phase5: drift --> Remediations --> re-verify --> evidence record (closed loop)
   every applied change emits a baseline-release record --> staleness automation
```

Prose: the loop closes on measured state and, at ring gates, on experience, not on "policy applied." The Intune repo doubles as the corporate floor's bill of materials: agent assignments carry declared floor budgets that CI checks against the reserve policy. Failure points: Graph write scope risk (Phase 2 onward), gate thresholds unset (Q-004), Fabric access (Q-016).

## 18. Research and Evidence Base

| ID | Stream | Question | Method | Findings and quality | Open |
|---|---|---|---|---|---|
| RES-001 | G2a device research | Everything decision-relevant about the device | Assistant-authored prompt (ART-021) executed by the user on an external deep-research tool; results returned T-004; assistant triangulated contested claims against TechPowerUp, NotebookCheck, ServeTheHome, HP datasheet | Primary outcome: press "Gen5" claim FALSIFIED, platform is PCIe 4.0 (high confidence, three-source convergence); TDP 35 W and 64 GB ceiling and single M.2 confirmed; NPU TOPS and WLAN module left ambiguous. Quality: T2 corrected toward T1; external pages not re-fetched this session | Q-009, Q-010 |
| RES-002 | Methodology validation | Do published practices confirm, extend, or contradict the house method? | Assistant-authored prompt (ART-022) covering fleet reliability, benchmarking rigor (SPEC, MLPerf class), experiment design, DEX telemetry, provenance (in-toto, SLSA class), config-as-code and GitOps (OPA, IntuneCD, M365DSC), physical devices under CI; output spec demands confirm/extend/contradict per practice, top-10 adoptions, and an honest list of unsupported house inventions | Not executed; no results returned | Q-015 |
| RES-003 | Corpus recontextualization | What does the prior project's record teach this program? | Searches across the attached project files and 20 prior chats (T-022..024) | Five corrections adopted (DEC-011..015 basis); telemetry limits grounded (FACT-040..047); Omnissa-not-Jamf corrected. Quality: internal historical record, high relevance, capstone-era dates; figures restricted by ART-015 | Q-012 staleness |
| RES-004 | Primary device evidence | Ground truth on the unit | User screenshots (T-002) read directly | T0 grade for FACT-020..033; n=1 | WIP-001 extends |

Primary evidence: RES-004. Secondary: RES-001 press layer (corrected), RES-003 historical corpus. No fabricated sources exist in the record; every external claim above carries its correction state.

## 19. Calculations, Models, and Metrics

**CALC-001 Capacity waterfall (program formula).** usable = physical − corporate floor − reserve. Illustrative memory instance on the G2a: 64 GB physical − ~19 GB observed floor − reserve = ~45 GB minus reserve. Units GB. Inputs: FACT-022 (physical), FACT-030 (floor, n=1, light load with Teams open, home-Wi-Fi-over-ZTNA egress). Reserve: UNSET (Q-004). Sensitivity: floor varies with agent state (scan and patch windows raise it) and load; the 19 GB is a single settled-ish observation, not a distribution. Confidence: formula high, instance illustrative only. RV before any leadership use.

**CALC-002 Disk position.** 477 GB formatted − 106 GB consumed pre-user-data = 371 GB effective start, on a 17-day image (2026-08-10 to 2026-08-27 capture window). Basis of the 1 TB ordering recommendation (DEC-025) given the single M.2 slot. n=1.

**CALC-003 Package arithmetic.** 14 top-level files + 5 schemas = 19 files; zip shows 20 entries (directory entry included). Verified by listing 2026-08-27.

**CALC-004 Sampling rule.** Regression-derived claims require n ≥ 10 × fitted parameter count (DEC-013). No program regression has run yet.

**CALC-005 Maturity metric (defined, no data).** percent automated = automated checks ÷ total checks in the four-lane matrix, trended quarterly. Blocked on Q-005.

**Historical models, restricted use (SSC, governed by ART-015; never program framing).** The prior project's score: DEX = 1 − Σ(weight_i × severity_i), weights from OLS regression against customer-satisfaction ground truth; holdout R² 0.908 (n=104); a telemetry-augmented v2 failed honestly at holdout R² −1.902 (n=39, k=18), retained as a negative result. Relevance here is methodological only: derived transparent weights beat asserted scores, and honest negatives stay in the record.

## 20. Rejected, Superseded, or Abandoned Directions

| ID | Direction | Why considered | Why rejected or superseded | Reconsider when |
|---|---|---|---|---|
| REJ-001 | Framing the program as DEX lineage | Real methodological ancestry | User: "This has not much to do with Dex"; wrong reporting line and mission | Never; permanent (REQ-003) |
| REJ-002 | Brooks as leadership audience | Prior-project habit | Wrong stakeholder; line is Green/Campbell/Robles | Never |
| REJ-003 | General document-authoring standard for all program docs (ART-020) | Plausible reading of the T-029 paste | User meant the pyramid bound to the buying decision itself; ART-020 deleted, content absorbed into ART-017 where relevant | Only on explicit user request |
| REJ-004 | "PCIe Gen5 SSD" as a device fact | Press coverage asserted it | Falsified by three-source convergence; platform is PCIe 4.0 | Never for this silicon |
| REJ-005 | Jamf as the iPad UEM | Common industry default | Corpus shows Omnissa Workspace ONE under BYOD User Enrollment | Never for this estate |
| REJ-006 | Marketing-toned persona sheet as the leadership document ("A memory-first machine tuned for silence and battery life") | First draft framing | User: "This doc is not ready for leadership"; split into desk sheet plus exec brief | n/a; split stands |
| REJ-007 | Device-first recommendation ordering | Natural for a device eval | User's four-part goal is persona-first (DEC-020) | Never; governing |
| REJ-008 | Incident data as standalone verdict evidence | It exists and is queryable | Under-filing by workaround culture plus sub-50-percent device anchoring | BKL-011 join fix lands |
| REJ-009 | iPad experience-scoring lane | Fleet completeness | iPadOS forbids agent telemetry; ruled structurally unmeasurable | Apple or Omnissa platform change |
| REJ-010 | Ansible as a production management plane | It is present in the estate | User confined it to lab post-provisioning; Intune is the sole plane | Explicit user reversal |

## 21. Communication and Interaction History

Pivotal exchanges, verbatim where wording governs interpretation. Speaker is the user unless noted; all 2026-08-27.

| Ref | Exchange | Effect |
|---|---|---|
| COMM-001 (T-006, T-025) | Approvals arrive terse: "Yes to both"; "Go" | Execute without re-confirmation (REQ-023) |
| COMM-002 (T-008) | "We need to be able to tell a story about this laptop and who can use it and what they can expect their experience to use it and when it would be a Bad experience or who would be a bad person to use it bc it's too powerful or too slow" | Origin of persona-fit including wrong-fit honesty |
| COMM-003 (T-011) | "This doc is not ready for leadership:" | Frustration signal; audience split (DEC-008) |
| COMM-004 (T-013) | "You didn't consider the 24.7 running agents and daemons that usually there on an enterprise device" | The central material correction (DEC-006) |
| COMM-005 (T-021) | "Ansible for post provisioning config as well but let's focus on intune for management tool that need to be deployed, enterprise windows machines are the thing that is being configured, systrack and graph api for telemetry sources, terraform f[or IaC...]" | Stack lock (DEC-002) |
| COMM-006 (T-025) | "Go and brooks is not relevant here majority. It's mostly Mike green and Kyle campell and Javier Robles" | Stakeholder retarget (DEC-016) |
| COMM-007 (T-026) | "This has not much to do with Dex, I'm working under Mike Kyle and Javier as a windows endpoint engineer trying to build out iac and eventually compliance as code for the windows machines. The reason I added you here is bc I wanted you to have historical understanding" | Mission reset (DEC-017); defines the corpus's role |
| COMM-008 (T-028) | "But like dont forget, the specific goal is to create a process where leadership can quickly look at data backed statements of This is our buying recommendation based on 1. Which persona this is for 2. Rigorous testing and research on new device recommendation product 3. Current issues facing persona fleet 4. How it all ties in together" | The governing goal (DEC-020) |
| COMM-009 (T-030) | "No I meant we should apply that to the buying decision pipeline. Like answer whom are buying this for, etc" | Correction of the assistant's misread; DEC-021a superseded |
| COMM-010 (T-031) | "It doesn't sound like you think my idea was very good? Feel free to be honest and present a better one" | Expectation of explicit evaluative honesty; led to the ledger proposal (DEC-024) |
| COMM-011 (assistant, T-031) | Assistant asked whether to adopt the decision ledger | UNANSWERED at cutoff; the live question |
| COMM-012 (assistant, T-027 era) | Assistant requested the team's current checklist | UNANSWERED (Q-005) |
| COMM-013 (T-032..034) | Handover requests: six-section report, then the exhaustive template, then "Continue" twice | This series; Volumes 5 and 6 committed |

Outstanding commitments by the assistant: Volumes 5 and 6; the specs and runbook in §25 once DEC-024 is answered. Outstanding requests to the user: DEC-024 answer, Q-005 checklist, Q-004 thresholds, Q-006 personas.

---

**End of Volume 4.** Volume 5 continues at **§22 Artifact Inventory**, then §23 Embedded Source Pack (the full text of all 19 package files plus the two inline research prompts) and §24 Reference Registry. Volume 5 is the largest in the series and will span more than one response.
