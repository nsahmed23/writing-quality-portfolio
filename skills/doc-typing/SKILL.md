---
name: doc-typing
description: "Classify and repair technical or API documentation by the reader’s task and knowledge state using Diátaxis: tutorial, how-to, reference, or explanation. Use for type ambiguity, mixed pages, documentation architecture, quickstarts, endpoint docs, recipes, troubleshooting, migrations, SDK docs, and runbooks. Do not use for memo logic, sentence polish, or a heading-only classification."
---

# Documentation Typing

Classify from what the reader is doing and needs now, never from a filename or heading. Apply the framework at page, section, or sentence scale, and permit explicit boundaries between intentionally combined types. [DIA-FND-01–04]

## Establish the user contract

1. Identify the reader’s immediate activity: learning through guided action, accomplishing a real task, looking up facts, or building understanding.
2. Identify knowledge state: novice under guidance, competent practitioner at work, user needing authoritative description, or reader reflecting on concepts.
3. Identify the promised outcome and who owns judgment. Ask one clarifying question only when two materially different contracts remain plausible.
4. Classify each meaningful unit with the compass:
   - acquisition + action → **tutorial**
   - application + action → **how-to guide**
   - application + cognition → **reference**
   - acquisition + cognition → **explanation**
5. Mark confidence and any intentional secondary type. [DIA-CMP-01]

## Enforce the type contract

### Tutorial

Create a safe, repeatable learning experience in which the learner performs meaningful steps and sees results early and often. Supply a complete path, expected outcomes, and observable cues. Minimize optional branches, exhaustive alternatives, reference catalogues, and extended theory; link to them instead. Test the path with learners or explicitly state that it is unverified. [DIA-TUT-01–07]

### How-to guide

Lead a competent user from a real-world goal through an adaptable sequence. State prerequisites and the goal, keep attention on action, allow conditional branches that the task requires, and omit teaching or exhaustive description. The user owns choices and judgment. [DIA-HTG-01–06]

### Reference

Describe the machinery accurately, neutrally, consistently, and completely for the defined scope. Mirror the product’s structure when useful; use stable patterns, explicit constraints, types, parameters, errors, and short illustrative examples. Do not turn lookup material into a journey or argumentative essay. [DIA-REF-01–07]

### Explanation

Develop understanding: context, causes, tradeoffs, connections, alternatives, history, and limits. Bound the topic and support reflection. Do not disguise a procedure or fact catalogue as explanation. [DIA-EXP-01–06]

## Diagnose mixing

1. Mark each block by reader activity, not surface wording.
2. Treat a switch as harmful only when it interrupts the primary contract, makes navigation unpredictable, or prevents completeness.
3. For accidental mixing, move content, split the page, or replace a digression with a link.
4. For legitimate mixed documents, add explicit headings and boundaries, preserve a dominant contract, and make each embedded type locally coherent. Quickstarts may link to reference; endpoint pages may include brief explanatory notes; migration guides often combine a goal-driven procedure with scoped compatibility tables.
5. Do not create four sites or four pages mechanically. Diátaxis is a guide to user needs, not an implementation constraint. [DIA-APP-01–04]

## Technical/API defaults

- Quickstart: tutorial if it teaches a first successful experience; how-to if it assumes competence and solves deployment.
- Authentication guide: how-to for setup; reference for schemes, scopes, and header fields; explanation for trust models.
- Endpoint page: reference, with examples only as illustration.
- Troubleshooting: how-to organized by user goal/symptom; link to causal explanation.
- Recipe, runbook, migration guide: usually how-to; preserve reference tables behind clear boundaries.
- Conceptual architecture: explanation.
- SDK symbol pages: reference; SDK onboarding: tutorial.

## Preserve and stop

Preserve technically correct content, commands, schemas, warnings, version scope, and links. Do not restructure merely to make labels symmetrical. Stop when the reader contract is explicit, every block supports it or has a clear boundary, and navigation exposes rather than hides the four needs.

## Return proportionate output

- **Targeted review:** classification, confidence, reader/task evidence, and one mismatch if present.
- **Direct revision:** revised page/section with type boundaries; concise change note.
- **Fault explanation:** reader contract, intruding type, resulting failure, repair.
- **Whole-document audit:** page/section map, gap/mix findings, migration actions, acceptance checks.
- **Broad polish:** run only when documentation purpose or architecture is in scope; hand off prose faults.

Consult `references/principles.md`, `references/type-contracts.md`, `references/examples.md`, `references/evidence-map.md`, and `tests/fixtures.yaml` as needed.
