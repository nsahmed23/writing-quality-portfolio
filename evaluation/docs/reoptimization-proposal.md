# Reoptimization proposal

## Decision

Repair the benchmark and build an executable routed portfolio before adding more anti-slop rules. Preserve the seven specialist contracts. Treat external mechanisms as candidates that must earn inclusion through human-adjudicated development tests.

This proposal is not implemented on this branch.

## Target architecture

```text
document
  -> deterministic structure and fact-token lens
  -> minimal router
  -> selected specialist owner or registered collision pair
  -> native diagnostic findings with quote anchors
  -> deterministic span and taxonomy adapter
  -> deterministic collision arbitrator
  -> canonical detect-only findings
```

### Router

Select one primary skill for each trigger span. Select a second only for a registered collision. Record the trigger, selected owner, reason, skipped skills, and context limitations. Do not fan out across all seven skills by default.

### Specialist return contract

Each specialist returns:

- native rule ID;
- quoted defect-bearing text;
- occurrence and nearby context for disambiguation;
- named problem;
- contextual explanation;
- severity;
- suggested operation;
- CHANGE or KEEP;
- any fact or protected-region constraint.

The specialist does not calculate offsets or invent a canonical taxonomy label.

### Deterministic adapter

Resolve `{quote, occurrence, left_context, right_context}` into exact Unicode offsets. Reject an ambiguous anchor locally without invalidating unrelated cases. Map native rule IDs through a versioned human-approved crosswalk. Preserve source revision, file, native rule, rendered prompt hash, response hash, and adapter version.

Never use another model to fill missing scored fields.

### Arbitrator

Implement the existing owner, pass-order, and collision rules in code. Deduplicate findings, enforce protected regions, and record every merge, rejection, or unresolved conflict. An unresolved CHANGE versus KEEP conflict becomes abstention or human escalation, not a guessed verdict.

### Narrow factual-integrity lane

A routed lane may cover numbers, dates, actors, attribution, modality, negation, and causal claims. It should activate only on evidence-bearing text and only after an ablation demonstrates incremental detection without excessive false positives or meaning risk.

## Benchmark v2

### Corpus and leakage controls

- Treat the entire first pilot as development-only.
- Create opaque request IDs independent of source, order, and decision.
- Run a metadata-only classifier before any model evaluation.
- Require its confidence interval to remain below a preregistered leakage ceiling.
- Use one case per fresh model request.
- Balance all exposed metadata by label.
- Keep future holdout content inaccessible until every harness decision is frozen.

### Gold construction

Real humans independently propose issues in native language before seeing system output. Adjudicators resolve validity, protected regions, severity, and allowed operations. Store multiple accepted exact anchors when boundaries are genuinely equivalent. Record disputed cases rather than forcing artificial certainty.

### Scoring decomposition

Report these separately:

1. case localization;
2. issue-region overlap;
3. exact boundary correctness;
4. native problem acceptance;
5. taxonomy mapping correctness;
6. explanation acceptance;
7. operation safety;
8. severity calibration;
9. explicit KEEP preservation;
10. serialization and run reliability.

Do not turn one mismatch into multiple hidden penalties without showing the decomposition.

### System fidelity

Create separate tracks for:

- native diagnostic systems;
- declared detect-only adaptations;
- rewrite-only systems marked not applicable for diagnostic ranking;
- the normalized union as an explicitly constructed new system.

No derived projection should be described as the source “as authored.”

### Reproducibility

Before a request is sent, persist exact rendered prompt bytes and their hash. Record model identity, provider, temperature, top-p, seed support, output limit, request ID, start time, and adapter versions. Preserve the first raw response bytes and hash before parsing.

Malformed items fail locally. Report whole-response reliability separately, but do not erase valid sibling items.

## TDD gates

Write each test before implementation.

- Renaming or shuffling IDs cannot change outputs or predict labels.
- Generator-visible metadata cannot beat the frozen leakage ceiling.
- Each request binds exact prompt and response bytes.
- Quote anchors round-trip across Unicode, repeated text, code, tables, links, quotations, and frontmatter.
- Ambiguous anchors fail only their own finding.
- One malformed record cannot erase valid records.
- Native and F2 tracks cannot be mislabeled.
- Router tests prove minimal activation, empty-pass skipping, and collision ownership.
- Arbitration tests preserve code, tables, links, quotations, facts, modality, negation, and author quirks.
- Duplicate findings cannot inflate recall.
- Stage 2 remains mechanically locked without a new sealed holdout and verified human gates.
- Production code maintains at least 80 percent branch-relevant coverage.

## Execution phases

1. Freeze this retrospective and prohibit rankings from the pilot.
2. Build human-adjudicated development and calibration sets.
3. Implement deterministic anchors, adapters, and decomposed scoring with TDD.
4. Implement routed ownership and arbitration with TDD.
5. Run development ablations for each external mechanism.
6. Freeze benchmark v2, thresholds, prompts, settings, and reviewer roster.
7. Run three sealed Stage 1 repetitions with blinded real-human review.
8. Run Stage 2 only for systems that pass both objective and human diagnostic gates.

## Human-only decisions

Agents cannot substitute for real reviewers. Humans must create and adjudicate gold, approve span equivalence and taxonomy mappings, judge explanation and operation validity, assess factual-meaning risk, and conduct blinded Stage 2 voice, clarity, and reader-preference review.
