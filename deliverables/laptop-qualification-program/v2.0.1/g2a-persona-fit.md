# HP ZBook 8 G2a: Persona Fit v2

**Status:** UNISSUED derived view. This sheet cannot authorize assignment, a pilot, or procurement. Populate it only from cited evidence releases and an approved Phase 5 verdict record.

## Corporate environment baseline

**Corporate baseline release/version:** [required baseline release ID and version]

The corporate stack is part of the effective hardware specification. Read the measured floor and approved reserves before considering a persona.

| Baseline item | Value | Evidence record |
|---|---:|---|
| Memory floor | [X] GB | [T0 record ID] |
| Corporate image | [Y] GB | [T0 record ID] |
| Idle CPU, median / p95 | [Z]% / [Z95]% | [T0 record ID] |
| Battery cost of the stack | [measured range and units] | [T0 clean/corporate comparison record ID] |
| Memory reserve | [R1] GB | Threshold policy [ID/version] |
| Storage reserve | [R2] GB | Threshold policy [ID/version] |

Do not combine a floor with candidate evidence from a different BIOS, driver, Windows, image, agent, or test-pack baseline. If the release above is missing or stale, capacity fit is INCONCLUSIVE.

## Capacity waterfall

Complete one waterfall for every intended persona and every approved configuration.

| Capacity line | Memory | Storage | Evidence or rule |
|---|---:|---:|---|
| Physical / formatted capacity | [64 GB observed on captured unit] | [477 GB observed on captured unit] | [T0 identity/storage record IDs] |
| Corporate floor / image | − [X] GB | − [Y] GB | Corporate baseline release above |
| Required operating reserve | − [R1] GB | − [R2] GB | Threshold policy [ID/version] |
| **Remaining workload headroom** | **[H-memory] GB** | **[H-storage] GB** | Calculated before persona workload |
| Persona requirement / working set | [P-memory] GB | [P-storage] GB | Persona evidence release [ID] |
| Post-assignment balance | [H-memory − P-memory] GB | [H-storage − P-storage] GB | Calculated |
| **Pass or shortfall** | **[PASS / shortfall GB]** | **[PASS / shortfall GB]** | Verdict record [ID] |

The observed 64 GB installation is a point-in-time unit fact. It is not evidence of a supported or qualified memory ceiling, future ordering option, or upgrade limit.

The routing question is:

> Does this employee’s workload require additional capacity beyond the measured corporate floor and the approved operating reserve?

## Source and gate references

| Required source | Reference | Status |
|---|---|---|
| Candidate manifest / exact configuration | [manifest ID/version] | [current / stale / missing] |
| Threshold policy | [policy ID/version] | [current / stale / missing] |
| Device-ground-truth release | [Phase 1 evidence release ID] | [current / stale / missing] |
| Compatibility/security approval | [Phase 2 approval ID] | [PASS / not passed] |
| Provisional lab verdict | [Phase 3 verdict record ID] | [outcome] |
| Pilot evidence release | [Phase 4 evidence release ID] | [current / incomplete / not started] |
| Fleet and persona verdicts | [Phase 5 verdict record ID] | [outcomes / not issued] |

An empty or stale reference does not inherit a pass from this sheet. Before Phase 5, all candidate-persona pairings below are hypotheses only.

## Persona hypotheses to test

| Candidate persona hypothesis | Frozen requirement needed | Evidence needed before a fit claim |
|---|---|---|
| Technical multitasking | [memory, storage, latency, sustained workload values] | Corporate-floor distribution; candidate/control workload distribution; pilot evidence |
| Data-heavy local work | [model/dataset working set and completion target] | Capacity waterfall; application matrix; sustained performance; pilot evidence |
| Local AI experimentation | [approved model, runtime, security posture, throughput target] | Phase 2 support/security approval; candidate/control measurements |
| Graphics- or accelerator-dependent work | [application and hardware/API requirement] | Official support plus compatibility and workload evidence |
| Long-running compute | [completion-time, thermal, acoustic, and battery limits] | Stabilized candidate/control distributions |
| Standard productivity | [measured standard-device headroom and experience target] | Incumbent comparison and representative pilot evidence |

Do not replace these numeric requirements with job titles or self-reported preference.

## Assignment rule

An employee may be routed to this device only when all of the following are true:

1. The Fleet verdict is QUALIFY or QUALIFY_WITH_CONDITIONS and its conditions permit this assignment.
2. The employee maps to a persona whose Phase 5 verdict is QUALIFY or QUALIFY_WITH_CONDITIONS.
3. The capacity waterfall passes using the current corporate baseline and reserve policy.
4. The exact ordered device falls inside the approved procurement envelope.
5. No exception or evidence reference needed for the assignment has expired.

Fleet HOLD or FAIL blocks every assignment. Persona FAIL blocks that persona. HOLD or INCONCLUSIVE is not converted to a recommendation by a positive narrative or a deadline.

## Issued routing rows

| Persona | Persona requirement release | Fleet verdict | Persona verdict | Conditions / expiration | Approved configuration | Verdict record |
|---|---|---|---|---|---|---|
| [persona] | [release ID] | [outcome] | [outcome] | [conditions / date] | [procurement-envelope entry] | [record ID] |

**Current routing result:** NOT ISSUED — insert only the result carried by the approved Phase 5 verdict record.
