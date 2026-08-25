---
name: sentence-clarity
description: Repair sentence-level actor-action alignment, buried actions, misleading grammatical subjects, and obstructive subject-verb separation. Use for “clarify this sentence,” “who is doing what?”, abstract or bureaucratic clauses, or the clarity stage of a coordinated edit. Do not use merely to shorten prose, repair paragraph flow, vary syntax, structure a memo, classify documentation, or decide disputed usage.
---

# Sentence Clarity

Make the smallest revision that lets readers identify the central actors, actions, and relationships. Treat characters-and-actions as a diagnostic heuristic, not a universal sentence template. [WB-CLA-01–07]

## Route the request

- Run this skill alone for a targeted clarity question.
- For a broad edit, diagnose first and edit only assigned sentence-level clarity faults; follow `references/portfolio-routing.md` if it is present.
- Hand word-count and redundancy faults to `concision`; cross-sentence old/new flow to `cohesion-emphasis`; purposeful syntax choices to `sentence-variety`.
- Do not activate for a clean sentence that merely contains a passive, nominalization, long sentence, abstract subject, or form of *be*.

## Diagnose before revising

1. State the sentence’s intended proposition in neutral terms. Preserve its scope, certainty, negation, conditions, agency, and technical vocabulary.
2. Underline the finite verbs. Identify the story’s central action or state and every relevant actor, affected entity, or cause.
3. Ask whether a central action is hidden in a noun while a semantically light verb occupies the predicate. Suffixes such as *-tion* or *-ment* are clues only; morphology never proves a fault. [WB-CLA-02]
4. Ask whether the grammatical subject names a useful topic/actor or an abstract shell that makes agency hard to recover. A nonhuman or abstract subject can be exact and should remain when it is the established topic. [WB-CLA-03]
5. Check whether a long, movable interruption separates a subject from its finite verb or delays the main clause enough to miscue the reader. Complexity alone is not a fault. [WB-CLA-06]
6. Test the passive by function: retain it when the affected entity is the established topic, the agent is unknown/irrelevant/appropriately suppressed, or the register expects it. Flag it only when hiding the agent or action causes the reader problem. [WB-CLA-05]
7. Stop if the reader can recover the intended relationships promptly and no listed fault changes interpretation or effort.

## Revise

1. Put a central action in a finite verb when that exposes the proposition.
2. Put the responsible actor in subject position when agency matters and doing so does not break topic continuity.
3. Recover a suppressed agent only when the text supports it; never invent responsibility.
4. Move a long interrupting modifier after the verb, recast it, or split the sentence only when the original attachment or dependency is hard to follow.
5. Rebuild agreement, tense, modality, complements, and references after changing clause structure.
6. Compare the revision against the preservation checklist, then reread it in context. Prefer the original if the revision is merely different.

## Keep marked forms when they work

- Keep nominalizations that name a term of art, established topic, event, result, or useful conceptual object: *authentication*, *migration*, *the decision*.
- Keep light-verb constructions that express a distinct conventional meaning, aspect, politeness, or collocation.
- Keep passives that improve flow or appropriately background an agent.
- Keep stative and existential clauses when existence, identity, location, or condition is the point.
- Keep periodic syntax, deliberate suspense, and technical noun phrases when their function outweighs local processing cost.

## Preserve meaning

Do not change facts, quantities, attribution, evidence, citations, technical terms, legal effect, scientific caution, hedges, exceptions, negation, temporal order, or voice unless the user asks. Do not replace an unknown agent with *we*, *they*, or another guess. [WB-ETH-01]

## Return proportionate output

- **Targeted review:** verdict, reader problem (if any), one diagnostic explanation, and at most two revisions.
- **Direct revision:** revised text first; brief note only for a material choice.
- **Fault explanation:** identify finite verb, story action, subject/topic, and the exact mismatch.
- **Whole-document audit:** report only repeated or consequential patterns, with representative locations and a triaged edit list.
- **Broad polish:** return only this pass’s changes and deferrals; do not imitate adjacent skills.

Use the label set: `buried action`, `misleading subject`, `missing agent`, `obstructive subject–verb gap`, `misattached opener`, or `no clarity fault`. Never use `nominalization` or `passive` alone as a fault label.

## Consult references

- Read `references/principles.md` for the decision rules and `references/exceptions.md` for preservation cases.
- Read `references/examples.md` for original cross-register examples.
- Read `references/evidence-map.md` when auditing provenance or changing the method.
- Read `tests/fixtures.yaml` when validating activation, minimal intervention, or regressions.
