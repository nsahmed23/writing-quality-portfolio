# Portfolio pass order

Research cutoff: 2026-08-19 23:59 America/Chicago. This is a derived architecture supported by dependency testing, not an ordering stated by any one source.

## Validated order

1. **doc-typing** — only for technical/documentation artifacts whose user contract or architecture is in scope.
2. **memo-structure** — only for memos, briefs, recommendations, argument-led reports/decks/emails, or decision artifacts.
3. **cohesion-emphasis** — order paragraphs/sentences; repair topic, reference, given/new, hierarchy, and stress.
4. **sentence-clarity** — repair local actor/action and dependency faults without undoing flow.
5. **concision** — remove residual padding after meaning and information order are stable.
6. **sentence-variety** — repair form-purpose mismatch after cutting has stabilized architecture and rhythm.
7. **usage-adjudicator** — resolve only genuine usage questions after wording is stable.

## Why this order controls

| Earlier pass | What it can invalidate downstream | Why it precedes |
|---|---|---|
| doc-typing | page boundaries, content moves, reader contract | Sentence edits on material that will move or be deleted are wasteful |
| memo-structure | section order, governing claims, evidence grouping | Local flow depends on the final argument hierarchy |
| cohesion-emphasis | sentence order, subjects/topics, active/passive choice, clause hierarchy | Flow can require a passive or nominalization that a local pass might otherwise remove |
| sentence-clarity | clause kernel, actor/action wording | Cutting a still-unclear sentence can preserve the wrong structure |
| concision | clause count, modifier architecture, cadence | Syntax/rhythm choices should follow deletion |
| sentence-variety | final surface construction | Usage must be adjudicated in the form that will actually remain |

## Feedback and invalidation rules

- If a local pass exposes a missing premise, return only to the nearest necessary earlier pass; do not rerun all seven automatically.
- A document/argument reorganization invalidates all downstream edits in moved or rewritten material.
- A cohesion change invalidates clarity, concision, variety, and usage checks for that passage.
- A clarity change invalidates later passes locally, not document structure globally.
- A concision change invalidates variety and usage locally.
- A usage substitution normally requires only a sentence reread unless it changes reference, emphasis, or logic.

## Skip rules

- Skip every pass with no observable fault.
- Skip `doc-typing` for non-documentation genres and for docs with a stable user contract when the request is local.
- Skip `memo-structure` for tutorials, reference, narratives, chronology-as-evidence, and open exploration.
- Skip `sentence-variety` when repetition is purposeful or earlier edits already produce fitting syntax.
- Skip `usage-adjudicator` unless an exact word/construction/convention is disputed or high-risk.

## Broad-polish orchestration

Diagnose once by level, assign each problem one primary owner, apply the owner’s pass, and pass only changed spans downstream. Maintain a preservation ledger for propositions, uncertainty, citations, technical terms, voice, agents, conditions, and evidence. Return a single integrated revision, not seven competing rewrites.
