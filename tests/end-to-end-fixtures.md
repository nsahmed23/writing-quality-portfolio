# End-to-end portfolio fixtures

Research cutoff: 2026-08-19 23:59 America/Chicago.

These fixtures validate diagnosis, routing, ownership, pass order, minimal intervention, and semantic preservation. Each intermediate state records only the delta produced by that pass; all unquoted text carries forward unchanged. The final text is complete.

## Acceptance protocol

For each fixture, the evaluator must:

1. Inventory protected propositions, quantities, conditions, uncertainty, citations, technical terms, agency, chronology, and voice.
2. Diagnose once by writing level and assign one primary owner to each fault.
3. Run only the selected passes in dependency order.
4. Apply downstream passes only to changed spans or still-open faults.
5. Compare the final text with the preservation inventory.
6. Record proposed changes rejected because they violate genre, evidence, meaning, or an adjacent skill's ownership.

## Fixture E2E-API-01 — Mixed API documentation

### User request

> Polish this API page. It is supposed to help a developer submit a first job, but readers say that it mixes too many things and sounds bureaucratic.

### Input

````markdown
# Tutorial: Jobs API

The Jobs API is based on asynchronous processing. This is a design choice that was made because synchronous requests can exceed the gateway's 30-second timeout. The service queues work. The service returns immediately. The service isolates regional failures.

The following information is provided for the creation endpoint. `POST /v1/jobs` is utilized for the creation of a job. The request is validated by the gateway before it is placed in the queue. The body is comprised of `name`, `region`, and `mode`. A missing `name` produces `422 Unprocessable Entity`.

To create a job, you create a file named `job.json`. You put the following content in the file:

```json
{"name":"nightly-index","region":"us-central","mode":"safe"}
```

You send the request in order to create the job:

```bash
curl -i -X POST https://api.example.test/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data @job.json
```

At this point in time, you should receive `202 Accepted` and a `job_id`. You then poll `GET /v1/jobs/{job_id}` until `status` is `succeeded` or `failed`. Do not start dependent work while the status is `queued` or `running`.
````

### Initial diagnosis by level

| Level | Reader problem | Primary owner |
|---|---|---|
| Document | A page headed “Tutorial” interrupts a novice's first-success path with explanation and endpoint inventory. | doc-typing |
| Section | The page has no explicit boundary between guided learning, lookup facts, and design rationale. | doc-typing |
| Paragraph | The endpoint paragraph presents fields before the learner has a reason to use them; the polling sentence lacks a strong backward anchor. | cohesion-emphasis |
| Sentence | “Is utilized for the creation” hides the action; “information is provided” is an abstract shell. | sentence-clarity |
| Phrase | “The following information is provided,” “in order to,” and “at this point in time” add no meaning. | concision |
| Passage syntax | Three explanation sentences repeat the same subject–verb architecture although the ideas form one sequence. The repeated imperatives in the procedure are useful and are not a fault. | sentence-variety |
| Usage/convention | In formal API prose, “is comprised of” is contested and distracts from a simple part–whole statement. | usage-adjudicator |

### Selected pass order

1. doc-typing
2. cohesion-emphasis
3. sentence-clarity
4. concision
5. sentence-variety
6. usage-adjudicator

`memo-structure` is skipped: this is a learning-and-lookup artifact, not a decision argument.

### Expected intermediate edits

#### After doc-typing

- Make the tutorial the dominant contract: a novice submits one known-good request and observes success.
- Keep the procedure in `Submit your first job`.
- Move endpoint fields and errors behind an explicit `Endpoint reference` boundary.
- Move the timeout rationale behind an explicit `Why jobs are asynchronous` boundary.
- Do not create four mechanical top-level pages; three locally coherent sections are sufficient.

Expected section order:

```text
Submit your first job
  Before you begin
  Create the request body
  Submit the job
  Check the result
Endpoint reference
Why jobs are asynchronous
```

#### After cohesion-emphasis

- Place the expected `202 Accepted` result immediately after submission.
- Open the next step with the now-given `job_id`: “Use that `job_id` to poll …”.
- Keep “The request is validated …” passive in reference material because the request is the established topic and the gateway agent is already supplied.
- End the tutorial on the consequential warning about dependent work.

#### After sentence-clarity

```diff
- The following information is provided for the creation endpoint. `POST /v1/jobs` is utilized for the creation of a job.
+ `POST /v1/jobs` creates a job.
```

No change is expected to “The request is validated by the gateway …”; the passive preserves the endpoint/request topic and does not conceal accountability.

#### After concision

```diff
- You send the request in order to create the job.
+ Submit the job.

- At this point in time, you should receive `202 Accepted` and a `job_id`.
+ The API returns `202 Accepted` and a `job_id`.
```

The safety warning, status values, field names, error status, command, and authentication header remain protected.

#### After sentence-variety

```diff
- The service queues work. The service returns immediately. The service isolates regional failures.
+ The service queues work and returns immediately, isolating regional failures.
```

Do not vary the procedure's imperatives merely for surface diversity; their parallel form supports execution.

#### After usage-adjudicator

```diff
- The body is comprised of `name`, `region`, and `mode`.
+ The body contains `name`, `region`, and `mode`.
```

Expected verdict: recast for unambiguous formal API usage; do not call every attested use of “comprised of” ungrammatical and do not invent a Garner Language-Change Index stage without the entry.

### Final expected result

````markdown
# Submit your first job

This tutorial submits one job and checks its result.

## Before you begin

Set `TOKEN` to a valid API token.

## Create the request body

Create `job.json`:

```json
{"name":"nightly-index","region":"us-central","mode":"safe"}
```

## Submit the job

```bash
curl -i -X POST https://api.example.test/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data @job.json
```

The API returns `202 Accepted` and a `job_id`.

## Check the result

Use that `job_id` to poll `GET /v1/jobs/{job_id}` until `status` is `succeeded` or `failed`. Do not start dependent work while the status is `queued` or `running`.

## Endpoint reference

`POST /v1/jobs` creates a job. The body contains `name`, `region`, and `mode`. A missing `name` produces `422 Unprocessable Entity`. The request is validated by the gateway before it is placed in the queue.

## Why jobs are asynchronous

Synchronous requests can exceed the gateway's 30-second timeout. The service therefore queues work and returns immediately, isolating regional failures.
````

### Semantic-preservation audit

| Protected item | Result |
|---|---|
| Endpoint and method: `POST /v1/jobs` | Preserved |
| Fields: `name`, `region`, `mode` | Preserved |
| Error: missing `name` → `422 Unprocessable Entity` | Preserved |
| Success: `202 Accepted` plus `job_id` | Preserved |
| Polling endpoint and terminal/intermediate statuses | Preserved |
| 30-second gateway timeout rationale | Preserved |
| Gateway validation and queue order | Preserved; passive retained |
| Bearer token, JSON header, body, and command | Preserved exactly |
| Safety warning about dependent work | Preserved |

### Rejected changes

- Reject “The gateway validates every request” as a mandatory active-voice rewrite; the original passive is coherent and identifies the gateway.
- Reject deletion of the dependent-work warning as “repetition” or “extra detail.”
- Reject four empty documentation buckets; explicit local boundaries solve the reader problem.
- Reject answer-first memo structure; no executive decision is being argued.
- Reject random variation of the numbered imperatives.
- Reject an unsupported claim that “comprised of” is universally ungrammatical or has a verified Garner stage.

## Fixture E2E-MEMO-01 — Weak executive recommendation

### User request

> Edit this for the executive committee. Put the recommendation first, make the logic easy to scan, and preserve the uncertainty and compliance caveats.

### Input

```text
Subject: Regional failover decision

This memorandum is being provided for the purpose of giving an update about the regional failover matter and the decision that is needed by Friday. During the 30-day pilot, there was an observation of a 5–8% reduction in median recovery time, although the pilot does not establish that the option will cause less failover incidents during a full year. Option A is the cheapest option. Option A fails the Canadian residency requirement. Option B costs 12% more. Option B passed the preliminary residency review. The security team has not completed its tabletop exercise.

There are a number of reasons that are relevant. Resilience is important, performance improved in the pilot, compliance is a requirement, and the rollout can be stopped. The finance model says that Phase 1 can be kept below $1.2 million [Finance model F-17, rev. 3]. It is our recommendation that an approval of Option B for Phase 1 be given, but Canadian traffic should not be moved until the residency test passes by September 30.
```

### Initial diagnosis by level

| Level | Reader problem | Primary owner |
|---|---|---|
| Document/argument | The requested decision and conditional answer arrive last. Supporting reasons mix benefits, constraints, and a recommendation. | memo-structure |
| Section/paragraph | Option comparisons and conditions lack explicit backward links and a stable progression. | cohesion-emphasis |
| Sentence | “There was an observation” and “an approval … be given” hide actions. | sentence-clarity |
| Phrase | Empty memorandum framing, “a number of,” repeated “option,” and “is important” add weight without content. | concision |
| Passage syntax | Four equal short “Option” sentences conceal contrast; recommendation conditions benefit from deliberate parallel form. | sentence-variety |
| Usage/convention | Formal edited prose normally distinguishes countable “incidents” with “fewer,” not “less.” | usage-adjudicator |

### Selected pass order

1. memo-structure
2. cohesion-emphasis
3. sentence-clarity
4. concision
5. sentence-variety
6. usage-adjudicator

`doc-typing` is skipped because the artifact is an executive decision memo.

### Expected intermediate edits

#### After memo-structure

Governing question: **Should the committee approve a first-phase regional failover rollout, and under what conditions?**

Governing answer: **Approve Option B for Phase 1, capped at $1.2 million, but do not move Canadian traffic until the residency test passes by September 30 and do not expand beyond Phase 1 until the security tabletop is complete.**

Key-line support:

1. Pilot evidence supports a limited trial, not a full-year reliability claim.
2. Option B is the viable compliance candidate despite its 12% premium; Option A fails the Canadian requirement.
3. The cap and two gates make the decision reversible and expose unresolved risk.

The groups are not forced into false MECE categories: the residency and security gates are both constraints and risk controls, and that overlap is disclosed.

#### After cohesion-emphasis

- Lead with the conditional decision.
- Follow with evidence, then option comparison, then gates.
- Use “That result” to link the 5–8% observation to its limitation.
- End on the action/deadline: approval is needed Friday.

#### After sentence-clarity

```diff
- During the 30-day pilot, there was an observation of a 5–8% reduction in median recovery time.
+ During the 30-day pilot, median recovery time was 5–8% lower.

- It is our recommendation that an approval of Option B for Phase 1 be given.
+ Approve Option B for Phase 1.
```

The first revision reports the measured comparison without converting it into a causal annual claim; the following sentence retains the evidentiary limitation.

#### After concision

```diff
- This memorandum is being provided for the purpose of giving an update about the regional failover matter and the decision that is needed by Friday.
+ Decision requested by Friday.

- There are a number of reasons that are relevant.
+ [delete]
```

Do not delete the 30-day duration, 5–8% range, 12% cost premium, $1.2 million cap, source citation, September 30 deadline, or incomplete tabletop.

#### After sentence-variety

```diff
- Option A is the cheapest option. Option A fails the Canadian residency requirement. Option B costs 12% more. Option B passed the preliminary residency review.
+ Option A is cheapest but fails the Canadian residency requirement. Option B costs 12% more and has passed the preliminary residency review.
```

Retain parallel imperatives for the two rollout gates; the repetition makes conditions scannable.

#### After usage-adjudicator

```diff
- The pilot does not establish that Option B will cause less failover incidents over a full year.
+ The pilot does not establish that Option B will cause fewer failover incidents over a full year.
```

Expected verdict: `fewer` is the low-risk choice for a count plural in a formal US executive memo. The edit does not strengthen the claim.

### Final expected result

```text
Subject: Approve a gated Phase 1 failover rollout

Recommendation

Approve Option B for Phase 1, capped at $1.2 million. Do not move Canadian traffic until the residency test passes by September 30, and do not expand beyond Phase 1 until the security tabletop is complete. Decision requested by Friday.

Why a limited approval is warranted

- During the 30-day pilot, median recovery time was 5–8% lower. That result supports a limited rollout, but it does not establish that Option B will cause fewer failover incidents over a full year.
- Option A is cheapest but fails the Canadian residency requirement. Option B costs 12% more and has passed the preliminary residency review.
- Phase 1 can remain below $1.2 million [Finance model F-17, rev. 3], and the rollout can be stopped before expansion.

Conditions

- Keep Canadian traffic on the current system until the residency test passes by September 30.
- Complete the security tabletop before any expansion beyond Phase 1.
```

### Semantic-preservation audit

| Protected item | Result |
|---|---|
| Recommendation: Option B, Phase 1 only | Preserved and surfaced |
| Approval deadline: Friday | Preserved |
| Pilot duration and measured 5–8% result | Preserved |
| No established annual incident reduction | Preserved; hedge not weakened |
| Option A cheapest but fails Canadian residency | Preserved as contrary evidence |
| Option B 12% premium and preliminary review status | Preserved; “preliminary” retained |
| $1.2 million cap and Finance citation | Preserved exactly |
| September 30 residency gate | Preserved |
| Incomplete security tabletop | Preserved as expansion gate |
| Reversibility | Preserved |

### Rejected changes

- Reject “Option B will improve reliability by 5–8%”; it confuses recovery time with reliability and removes uncertainty.
- Reject deletion of Option A because it is contrary evidence needed to explain the choice.
- Reject a claim that the three supports are perfectly MECE.
- Reject a full SCQA preamble; the executive decision is urgent and interpretable answer-first.
- Reject removal of “preliminary,” the citation, either gate, or the cost premium for concision.
- Reject ornamental variation of the parallel gate bullets.
- Reject a Strunk-and-White-style active rewrite of every passive regardless of information flow.

## Fixture E2E-SCI-01 — Scientific analytical report

### User request

> Polish this results section for a journal that treats *data* as plural. Keep the statistics, citations, methods emphasis, and cautious conclusion.

### Input

```text
Pilot analysis of cache warming

For the purpose of evaluating cache warming, the randomization of 48 samples into four blocks was performed, and the samples were frozen at −80 °C within 20 minutes. An analysis of request latency was then conducted with a mixed-effects model.

There was an observation of a 6.1% reduction in median latency. The 95% confidence interval was −0.8% to 12.7%, and p = .08. The model showed a small site effect. The model showed no treatment-by-site interaction. This may possibly reflect batch imbalance, and it does not establish causation (Lee et al., 2024).

The data is consistent with a modest benefit, but it is our belief that additional sampling would potentially be needed before deployment could be recommended.
```

### Initial diagnosis by level

| Level | Reader problem | Primary owner |
|---|---|---|
| Document | This is a bounded scientific report, not a decision memo or a Diátaxis documentation page. | routing: skip doc-typing and memo-structure |
| Paragraph | The numerical result needs an explicit link to the interval and the cautious interpretation; “This” has a broad possible antecedent. | cohesion-emphasis |
| Sentence | “An analysis … was conducted” hides the action. The methods passives and technical nominalization “randomization” are legitimate and should remain. | sentence-clarity |
| Phrase | “For the purpose of,” “may possibly,” “it is our belief,” and “would potentially be needed” stack framing or hedges. | concision |
| Passage syntax | Two consecutive “The model showed” sentences express parallel findings that can be coordinated without changing their status. | sentence-variety |
| Usage/convention | The target journal requires plural agreement with *data*. | usage-adjudicator |

### Selected pass order

1. cohesion-emphasis
2. sentence-clarity
3. concision
4. sentence-variety
5. usage-adjudicator

`doc-typing` and `memo-structure` are skipped. The report's cautious conclusion must not be converted into an executive recommendation.

### Expected intermediate edits

#### After cohesion-emphasis

- Open the result paragraph with the population/context: “Across 48 samples …”.
- Make “This 6.1% estimate” the backward link to the confidence interval.
- Replace ambiguous “This may possibly reflect …” with “The small site effect may reflect …”.
- End the paragraph on the causal limitation and citation.

#### After sentence-clarity

```diff
- An analysis of request latency was then conducted with a mixed-effects model.
+ A mixed-effects model estimated request latency.
```

Retain “The 48 samples were randomized … and frozen …” because the samples/methods are the discourse topic and the operators are irrelevant. Retain `randomized`/`randomization` terminology where method reporting requires it.

#### After concision

```diff
- For the purpose of evaluating cache warming,
+ To evaluate cache warming,

- may possibly reflect
+ may reflect

- it is our belief that additional sampling would potentially be needed
+ additional sampling may be needed
```

The single evidentiary hedge `may`, the confidence interval, `p = .08`, the causal limitation, and the deployment threshold remain protected.

#### After sentence-variety

```diff
- The model showed a small site effect. The model showed no treatment-by-site interaction.
+ The model showed a small site effect but no treatment-by-site interaction.
```

This coordination marks contrast between two equal model findings. Do not add a decorative periodic sentence or change the methods passives merely for variety.

#### After usage-adjudicator

```diff
- The data is consistent with a modest benefit.
+ The data are consistent with a modest benefit.
```

Expected verdict: both mass-noun singular and count/plural practices occur across registers and fields; the specified journal convention controls here. Do not present the choice as a universal grammatical truth.

### Final expected result

```text
Pilot analysis of cache warming

To evaluate cache warming, 48 samples were randomized into four blocks and frozen at −80 °C within 20 minutes. A mixed-effects model estimated request latency.

Across the 48 samples, median latency was 6.1% lower. This 6.1% estimate had a 95% confidence interval of −0.8% to 12.7% (p = .08). The model showed a small site effect but no treatment-by-site interaction. The small site effect may reflect batch imbalance; the analysis does not establish causation (Lee et al., 2024).

The data are consistent with a modest benefit, but additional sampling may be needed before deployment can be recommended.
```

### Semantic-preservation audit

| Protected item | Result |
|---|---|
| 48 samples and four randomization blocks | Preserved |
| Freezing at −80 °C within 20 minutes | Preserved; passive retained |
| Mixed-effects model | Preserved |
| 6.1% median-latency estimate | Preserved without causal upgrade |
| 95% CI −0.8% to 12.7% and `p = .08` | Preserved exactly |
| Small site effect and no interaction | Preserved |
| Batch imbalance as possibility, not fact | Preserved with `may` |
| No causal conclusion | Preserved |
| Citation `(Lee et al., 2024)` | Preserved exactly |
| Additional sampling before deployment recommendation | Preserved |
| Target-journal plural *data* convention | Applied |

### Rejected changes

- Reject “Cache warming reduced latency by 6.1%”; it falsely implies established causation.
- Reject deletion of the confidence interval, p-value, citation, or negative interaction finding.
- Reject replacement of all passives with an invented human agent.
- Reject removal of technical method terminology merely because it is nominalized.
- Reject “The data prove a benefit”; it violates the statistical evidence and hedge contract.
- Reject answer-first memo conversion and an operational deployment recommendation.
- Reject syntactic ornament that makes the methods section less conventional or precise.

## Portfolio-level result criteria

The three fixtures pass only if:

- global changes precede local edits;
- skipped passes remain skipped;
- one owner controls each fault;
- passive voice, nominalization, hedging, repetition, chronology, and mixed documentation survive when functional;
- no pass rewrites clean spans merely to demonstrate activity;
- usage decisions remain register-, field-, and evidence-conditioned;
- the final texts preserve every item in their semantic inventories; and
- rejected changes are not reintroduced by a downstream pass.
