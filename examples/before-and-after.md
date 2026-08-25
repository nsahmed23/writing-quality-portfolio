# Before and after: the seven skills in practice

These synthetic examples show what each skill changes and, just as importantly, what it leaves alone. Every revision preserves the stated facts, actors, quantities, timing, conditions, negation, technical terms, and uncertainty.

`CHANGE` means the skill found an observable fault within its scope. `KEEP` means the skill was applied and correctly declined to rewrite effective prose. The usage examples rely only on evidence packaged with this portfolio; they are demonstrations, not fresh live adjudications, and they do not infer a Garner classification or Language-Change Index stage.

## At a glance

| Skill | Change case | Keep case |
|---|---|---|
| [`doc-typing`](../skills/doc-typing/SKILL.md) | Mis-typed quickstart | Clearly bounded mixed page |
| [`memo-structure`](../skills/memo-structure/SKILL.md) | Buried conditional recommendation | Chronology retained as evidence |
| [`cohesion-emphasis`](../skills/cohesion-emphasis/SKILL.md) | Evidence and limitation reordered | Stable topic string retained |
| [`sentence-clarity`](../skills/sentence-clarity/SKILL.md) | Buried action with an unknown agent | Useful passive retained |
| [`concision`](../skills/concision/SKILL.md) | Process padding removed | Necessary condition and modality retained |
| [`sentence-variety`](../skills/sentence-variety/SKILL.md) | Operational sequence given hierarchy | Purposeful repetition retained |
| [`usage-adjudicator`](../skills/usage-adjudicator/SKILL.md) | Count-plural convention applied | Singular *they* retained |

## doc-typing

[Open the skill specification.](../skills/doc-typing/SKILL.md)

### Example DT-01: A quickstart that is really reference material

#### Verdict

CHANGE

#### Before

```markdown
# Queue API quickstart

`POST /v2/messages` enqueues a message. The body requires a string `topic`
for the message destination and an object `payload` for the message body.
The optional integer `ttl_seconds` ranges from 60 through 259200 and
defaults to 86400.

`GET /v2/messages/{id}` returns `queued`, `delivered`, or `expired`.
`DELETE /v2/messages/{id}` cancels a queued message. Delivered messages
cannot be cancelled.

A reused idempotency key returns `409` if the request body differs from
the original body. Message records are retained for 72 hours.

Queues isolate producers from consumers during load spikes.
```

#### After

```markdown
# Queue messages API reference

Authoritative behavior for Queue API v2.

## `POST /v2/messages`

Enqueues a message.

| Field | Type | Required | Constraint |
|---|---|---:|---|
| `topic` | string | yes | Message destination |
| `payload` | object | yes | Message body |
| `ttl_seconds` | integer | no | 60 through 259200; default 86400 |

A reused idempotency key returns `409` when its request body differs from
the original body.

## `GET /v2/messages/{id}`

Returns `queued`, `delivered`, or `expired`.

## `DELETE /v2/messages/{id}`

Cancels a queued message. Delivered messages cannot be cancelled.

## Retention

Message records are retained for 72 hours.

Related explanation: **Why queues isolate producers from consumers during
load spikes**.
```

#### Why

The reader is looking up endpoint behavior, fields, and constraints. The revision replaces the misleading tutorial promise with an explicit reference contract, applies a stable endpoint pattern, and moves the conceptual rationale behind a clear boundary.

#### Preservation check

All paths, fields, types, ranges, defaults, states, error conditions, cancellation rules, and the 72-hour retention period remain unchanged.

### Example DT-02: A legitimate mixed authentication page

#### Verdict

KEEP

#### Before

```markdown
# Configure workload identity

## Configure and verify

Prerequisites: CLI v4 and deployment-admin access.

1. Run `acme auth federation create --pool build --audience ci`.
2. Run `acme deploy update orders --identity-pool build`.
3. Run `acme auth test --service orders`.

Success prints `identity verified`.

## Token field reference

| Field | Meaning |
|---|---|
| `aud` | Intended service |
| `sub` | Workload identity |
| `exp` | Expiry time |

## Why tokens expire after 15 minutes

Short-lived credentials reduce exposure and simplify revocation.
```

#### After

```markdown
# Configure workload identity

## Configure and verify

Prerequisites: CLI v4 and deployment-admin access.

1. Run `acme auth federation create --pool build --audience ci`.
2. Run `acme deploy update orders --identity-pool build`.
3. Run `acme auth test --service orders`.

Success prints `identity verified`.

## Token field reference

| Field | Meaning |
|---|---|
| `aud` | Intended service |
| `sub` | Workload identity |
| `exp` | Expiry time |

## Why tokens expire after 15 minutes

Short-lived credentials reduce exposure and simplify revocation.
```

#### Why

The page has a dominant how-to contract and clearly bounded reference and explanation sections. Splitting it merely to produce three separate pages would not improve the reader's task.

#### Preservation check

The prerequisites, command order, success cue, field meanings, 15-minute lifetime, and security rationale remain intact.

## memo-structure

[Open the skill specification.](../skills/memo-structure/SKILL.md)

### Example MS-01: Put a conditional recommendation first

#### Verdict

CHANGE

#### Before

> The warehouse contract renews on October 31 at a 14% higher price. Oriole would reduce annual spend by $180,000, supports the two export formats Finance uses, and can finish migration by October 15 with a two-week parallel run. Security has not completed Oriole's penetration-test review, which is due September 20. We should switch providers. If the review does not close, the current provider will extend the contract for 60 days at the present rate.

#### After

> Switch to Oriole, subject to Security completing its penetration-test review. The review is due September 20. The current provider's renewal price will rise 14%, while Oriole would reduce annual spend by $180,000, preserve Finance's two export formats, and complete migration by October 15 with a two-week parallel run before the October 31 renewal. If the review has not closed by September 20, use the current provider's 60-day extension at the present rate.

#### Why

The governing decision was buried after mixed evidence. The revision leads with the conditional answer, groups the economic, operating, and timing support, and keeps the unresolved security review as a gate rather than another selling point.

#### Preservation check

The 14% increase, $180,000 estimate, two formats, October 15 migration date, two-week parallel run, September 20 security deadline, October 31 renewal, and 60-day fallback all remain visible. The review is not presented as complete.

### Example MS-02: Preserve chronology when sequence is evidence

#### Verdict

KEEP

#### Before

```text
02:14 Alert triggered for elevated checkout failures.
02:18 On-call confirmed failures in the payment adapter.
02:23 Traffic shifted to the secondary adapter.
02:31 Checkout success returned to baseline.
02:47 The primary adapter was removed from rotation.
```

#### After

```text
02:14 Alert triggered for elevated checkout failures.
02:18 On-call confirmed failures in the payment adapter.
02:23 Traffic shifted to the secondary adapter.
02:31 Checkout success returned to baseline.
02:47 The primary adapter was removed from rotation.
```

#### Why

This is an incident chronology, not a decision memo. Replacing the sequence with an answer-first pyramid would erase evidence about detection, diagnosis, mitigation, recovery, and removal.

#### Preservation check

Every timestamp, observation, intervention, and outcome remains in evidentiary order.

## cohesion-emphasis

[Open the skill specification.](../skills/cohesion-emphasis/SKILL.md)

### Example CE-01: Put evidence and limits before the decision

#### Verdict

CHANGE

#### Before

> Based on their review, engineers said the observability pilot may have reduced incident-detection time in two regions. The steering committee will decide in September whether to expand it. The review covered eight weeks of alerts, but the sample was too small to distinguish the pilot's effect from seasonal traffic.

#### After

> Engineers reviewed eight weeks of alerts from the observability pilot in two regions. Based on that review, they said the pilot may have reduced incident-detection time, but the sample was too small to distinguish the pilot's effect from seasonal traffic. Given that uncertainty, the steering committee will decide in September whether to expand the pilot.

#### Why

The decision appeared before the evidence and limitation needed to interpret it. The revision moves from evidence to tentative finding to limitation to decision; “that review” and “that uncertainty” provide explicit backward links.

#### Preservation check

Engineer attribution, the eight-week period, two-region scope, *may*, the sample limitation, the seasonal-traffic alternative, committee authority, and September timing all remain.

### Example CE-02: Keep a stable topic string

#### Verdict

KEEP

#### Before

> Each appeal enters review with a timestamped record. The appeal is checked against the filing deadline, assigned to two reviewers, and logged. The appeal remains open until both reviewers sign the disposition.

#### After

> Each appeal enters review with a timestamped record. The appeal is checked against the filing deadline, assigned to two reviewers, and logged. The appeal remains open until both reviewers sign the disposition.

#### Why

Repeating “the appeal” maintains topic continuity, the passives keep the affected entity in focus, and the final clause emphasizes the release condition. Synonyms or forced active voice would weaken the assurance sequence.

#### Preservation check

The processing order, filing-deadline check, two-reviewer assignment, logging requirement, and closure condition remain exact.

## sentence-clarity

[Open the skill specification.](../skills/sentence-clarity/SKILL.md)

### Example SC-01: Clarify without inventing an actor

#### Verdict

CHANGE

#### Before

> Recording of an unauthorized export of 412 customer records shortly after midnight was performed by the audit service, but identification of the initiating account was not possible from the record.

#### After

> The audit service recorded that 412 customer records were exported without authorization shortly after midnight, but the record does not identify the initiating account.

#### Why

This is a `buried action` fault. “Recording” and “identification” carry the important actions while the predicates obscure the distinction between the known recorder and the unknown exporter. The revision names the audit service only for the action the evidence supports.

#### Preservation check

The count, unauthorized status, timing, audit service's role, and unknown initiating account remain unchanged. No responsible exporter was guessed.

### Example SC-02: Keep a useful passive

#### Verdict

KEEP

#### Before

> The release candidate is quarantined until both scanners report clean results.

#### After

> The release candidate is quarantined until both scanners report clean results.

#### Why

There is `no clarity fault`. The release candidate is the useful topic, the condition matters more than the routine quarantining mechanism, and both scanner agents are already explicit where agency matters.

#### Preservation check

The quarantined state, two-scanner requirement, and clean-result release condition remain unchanged.

## concision

[Open the skill specification.](../skills/concision/SKILL.md)

### Example CN-01: Remove process padding

#### Verdict

CHANGE

#### Before

> For the purpose of completing the renewal process, tenants are required to submit a copy of the signed form by no later than Friday.

#### After

> To renew, tenants must submit a copy of the signed form by Friday.

#### Why

The revision removes empty purpose framing, official-style inflation, and redundant deadline wording. It reduces 24 words to 13 without producing telegram prose.

#### Preservation check

Mandatory force, the responsible party, copy and signature requirements, deadline, and relationship to renewal all remain.

### Example CN-02: Keep necessary modality and a condition

#### Verdict

KEEP

#### Before

> Access may be suspended if the account fails two consecutive identity checks.

#### After

> Access may be suspended if the account fails two consecutive identity checks.

#### Why

The sentence is already concise. “May” preserves discretion or uncertainty, “if” limits the rule, and “two consecutive” defines the threshold. Removing any of them would change the policy.

#### Preservation check

The possible consequence, triggering condition, count, and consecutiveness requirement remain exact.

## sentence-variety

[Open the skill specification.](../skills/sentence-variety/SKILL.md)

### Example SV-01: Give an operational sequence hierarchy

#### Verdict

CHANGE

#### Before

> The signing key expired at 02:00 UTC. Token validation failed. The retry queue grew to 18,000 jobs. The on-call engineer rotated the key. Processing resumed.

#### After

> After the signing key expired at 02:00 UTC, token validation failed and the retry queue grew to 18,000 jobs. The on-call engineer then rotated the key; processing resumed.

#### Why

Five short independent clauses gave every event equal weight. The subordinate opener establishes time, coordination keeps the two subsequent failures together, and the short final clause closes the recovery sequence without inventing causality.

#### Preservation check

The time, event order, queue size, responsible engineer, rotation, and recovery remain unchanged.

### Example SV-02: Keep purposeful repetition

#### Verdict

KEEP

#### Before

> No session token entered a log. No root key left KMS. No policy exception bypassed review.

#### After

> No session token entered a log. No root key left KMS. No policy exception bypassed review.

#### Why

The repeated negative declaratives give three assurance claims equal weight and make them easy to compare. The shared form serves clarity, cadence, and emphasis, so there is no form-purpose mismatch.

#### Preservation check

No ornamental variation was introduced, and the categorical force of all three assurances remains intact.

## usage-adjudicator

[Open the skill specification.](../skills/usage-adjudicator/SKILL.md)

### Example UA-01: Choose the low-risk count-plural form

#### Verdict

CHANGE

#### Before

> The pilot recorded 12% less incidents than the baseline.

#### After

> The pilot recorded 12% fewer incidents than the baseline.

#### Why

In a formal US memo, *fewer* is the conventional low-risk modifier for the count plural *incidents*. This is a context-specific recommendation, not a claim that every use of *less* with a plural is ungrammatical. No unverified Garner stage is reported.

#### Preservation check

The pilot, 12% magnitude, incident measure, and baseline comparison remain unchanged.

### Example UA-02: Keep singular they in workplace prose

#### Verdict

KEEP

#### Before

> Each maintainer must rotate their signing key before deployment.

#### After

> Each maintainer must rotate their signing key before deployment.

#### Why

Singular *they* is standard for indefinite reference in contemporary general workplace prose. It takes plural-form agreement and avoids inventing or presuming a maintainer's gender. A controlling house style could change the publication choice, but no such rule is present here.

#### Preservation check

The individual obligation, signing-key object, and pre-deployment deadline remain unchanged.

## Coordinated portfolio pass

[Open the validated pass order.](../portfolio-pass-order.md)

### Original passage

> With regard to the rollout, it is important to note that the Operations team has made a recommendation that phase one begin Monday. The regional failover test has not been completed. The accessibility retest has not been completed. Phase two should happen after those tests pass. The team recommends a staged rollout.

### Preservation ledger

- Operations owns the recommendation.
- Operations recommends that phase one begin Monday.
- Phase two remains conditional on both the regional failover test and the accessibility retest passing.
- Both tests are still incomplete.
- No date, test result, or approval is invented.

### Pass trace

| Order | Pass | Decision | Observable operation |
|---:|---|---|---|
| 1 | `doc-typing` | SKIP | This is an executive recommendation, not a technical documentation architecture problem. |
| 2 | `memo-structure` | APPLY | Put the staged recommendation first and expose the relationship between phases. |
| 3 | `cohesion-emphasis` | APPLY | Place both test conditions directly with phase two and keep the shared test status together. |
| 4 | `sentence-clarity` | APPLY | Change “has made a recommendation” to the finite verb “recommends.” |
| 5 | `concision` | APPLY | Remove empty framing and the duplicate recommendation. |
| 6 | `sentence-variety` | APPLY | Use one controlled recommendation sentence and one short status sentence. |
| 7 | `usage-adjudicator` | SKIP | No exact disputed usage remains after wording stabilizes. |

### Final integrated revision

> Operations recommends beginning phase one Monday and starting phase two only after the regional failover test and accessibility retest pass. Both tests remain incomplete.

This is one dependency-ordered edit, not seven competing rewrites. Only changed spans move to later passes, and skills without an observable fault are skipped.
