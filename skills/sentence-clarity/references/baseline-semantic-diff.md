# Appendix A → canonical `sentence-clarity` semantic diff

Research cutoff: **2026-08-19 23:59 America/Chicago**  
Audit/retrieval date: **2026-08-25**

This is a semantic redline, not a claim that the baseline and canonical files have stable line numbers. It records every meaningful baseline instruction, what happened to it, why, and the regression contract. Change IDs refer to `defect-and-change-report.md`; baseline audit IDs are `BL-*` there.

## Contents

- Evidence and confidence boundary
- Metadata redline
- Core-principle redline
- Diagnostic-sequence redline
- Nominalization and light-verb redline
- Example redline
- Conflict and ownership redline
- Exception redline
- Revision and preservation redline
- Output-contract redline
- Regression contract
- Canonical artifact consequences
- Residual uncertainty

## Evidence and confidence boundary

- Williams and Bizup, *Style: The Basics of Clarity and Grace*, 5th ed. (Pearson, print 2014, ©2015): official metadata/TOC plus selected lawful secondary teaching material; the ten lessons were **not available in full**. No fifth-edition page number is invented. [WB-CLA-01–07; WB-ETH-01]
- Gopen and Swan, “The Science of Scientific Writing,” *American Scientist* 78.6 (1990), 550–558: full permission-reprinted article. It supports functional passive/topic decisions and explicitly treats its proposals as principles, not rules. [GS-RE-01–10]
- Turabian and Amy Bennett-Zendzian are secondary provenance from the baseline, not members of the seven-source primary corpus.
- Source-derived instructions and portfolio design inferences are distinguished in `evidence-map.md` and the package claim ledger.

Status key: **KEEP** preserves behavior; **QUALIFY** retains it under a functional test; **MOVE** assigns it to another skill; **REMOVE** rejects it; **ADD** fills a missing decision/safety rule.

## Metadata redline

```diff
 name: sentence-clarity
-description: Sentence-level clarity editing using the Williams "characters and actions" method. Make the story's characters the grammatical subjects and their actions the verbs. Use whenever the user asks to clarify, tighten, simplify, de-jargon, or fix awkward, wordy, or bureaucratic prose; whenever reviewing or revising any draft ...; or ... as a final clarity pass ...
+description: Repair sentence-level actor-action alignment, buried actions, misleading grammatical subjects, and obstructive subject-verb separation. Use for “clarify this sentence,” “who is doing what?”, abstract or bureaucratic clauses, or the clarity stage of a coordinated edit. Do not use merely to shorten prose, repair paragraph flow, vary syntax, structure a memo, classify documentation, or decide disputed usage.
```

| Semantic unit | Status | Canonical meaning | Reason / evidence | Change and fixtures |
|---|---|---|---|---|
| Canonical name | **KEEP** | Remains `sentence-clarity`. | Valid official `name` field; distinct fault class. [PLAT-01–03] | SC-001; static metadata check |
| “characters and actions” as entire method | **QUALIFY** | A central diagnostic, not the capability definition or universal template. | Williams’s method also requires reason, context, shape, passive judgment, and ethics; access remains partial. [WB-CLA-01–07] | SC-002; `sc-boundary-technical-noun` |
| “tighten,” “wordy,” “bureaucratic” | **MOVE** | Residual verbal excess belongs to `concision`; clarity activates first only if actor/action recovery is independently needed. | Williams Lesson 7 and Lanham paramedic/official-style methods. [WB-CON-01–08; LAN-PM-01–10; LAN-OFF-01–04] | SC-001, CO-001; `sc-negative-shorter`, `co-bureaucratic` |
| “simplify,” “de-jargon,” “awkward” | **QUALIFY** | Weak triggers require an observable clarity fault or one clarifying question; they do not automatically activate. | Official implicit activation uses description; portfolio needs noncolliding semantic faults. [PLAT-03, PLAT-06] | SC-001; shared trigger matrix |
| “reviewing or revising any draft” | **REMOVE** | A local skill never claims every draft. Broad polish uses coordinated diagnosis and skips empty passes. | Minimal intervention [WB-CLA-07]; shared routing is a derived design rule. | SC-001; `sc-clean-email` |
| “final clarity pass” | **QUALIFY** | In broad edits clarity follows structure/cohesion and precedes residual concision/variety/usage. | Dependency-based portfolio pass order. | SC-001; `sc-regression-old-new`, `sv-after-cutting` |
| Negative triggers | **ADD** | Do not activate merely for shortening, paragraph flow, syntax variety, memo/doc structure, usage, or a marked form in clean text. | Boundary/collision analysis [WB-CLA-07]. | SC-001; `sc-negative-shorter`, `sc-negative-flow` |

## Core-principle redline

```diff
-Readers parse an English sentence through its subject and verb.
-A sentence reads as clear when the main characters ... are the grammatical subjects and their key actions are the verbs.
-Most awkward professional prose breaks this alignment.
+Make the smallest revision that lets readers identify the central actors, actions, and relationships.
+Treat characters-and-actions as a diagnostic heuristic, not a universal sentence template.
```

| Baseline semantic claim | Status | Canonical rule | Why | Change and fixtures |
|---|---|---|---|---|
| Subject and verb are the route through which all readers parse English. | **REMOVE** | Inspect the finite predicate and its subject because they are consequential structural positions, while testing the whole proposition in context. | Baseline phrasing was empirically universal; Gopen–Swan call their reader-position proposals principles rather than rules. [GS-RE-01–02, GS-RE-10] | SC-002–03; claim audit |
| Character-as-subject + action-as-verb is sufficient for clarity. | **QUALIFY** | Alignment is useful when it exposes the proposition; it can lose to established topic, affected-entity focus, state/identity, conventional register, or unknown/irrelevant agent. | [WB-CLA-01–07; GS-RE-04–10] | SC-002, SC-005–06; `sc-boundary-passive-topic` |
| Most awkward professional prose has this fault. | **REMOVE** | Diagnose only the submitted text; make no prevalence claim. | No inspected corpus evidence supports “most.” | SC-002; `sc-clean-email` |
| “WHO is doing WHAT?” | **KEEP + EXPAND** | State the proposition; identify central action **or state**, supported actors, affected entities, and causes. | Event clauses are not the whole language. [WB-CLA-01, WB-CLA-03] | SC-003; `sc-positive-question`, `sc-boundary-unknown-agent` |
| Characters can be nonhuman (API, team, court). | **KEEP** | An actor/character can be animate, institutional, technical, or abstract. It is not automatically the grammatical subject, semantic agent, discourse topic, or given information. | [WB-CLA-03; GS-RE-04–05] | SC-005; glossary; `sc-boundary-technical-noun` |
| A good subject must be short and concrete. | **REMOVE** | Ask whether the subject is a useful topic/actor and whether the dependency is recoverable; exact abstract or technical topics can be best. | [WB-CLA-03, WB-CLA-06–07] | SC-005, SC-007; `sc-boundary-technical-noun` |

## Diagnostic-sequence redline

```diff
-1. Find the actual verbs ... the tensed verbs.
-2. Name the characters and their actions.
-3. Spot nominalizations.
-4. Revise: characters become subjects, actions become verbs.
-5. Check the opening ... subject and verb ... first few words ... never let a long phrase separate them.
-6. Check flow ... old before new.
-Confirm ... who-did-what from the subject and verb alone.
+1. State the intended proposition and protect scope, certainty, negation, conditions, agency, and technical vocabulary.
+2. Identify finite verbs, central action/state, and relevant actors, affected entities, or causes.
+3. Diagnose a buried action only when a light predicate hides the central action; morphology is a clue.
+4. Test subject/topic function and agent relevance.
+5. Test only obstructive windups or subject–verb separations.
+6. Test passive by topic, agent, accountability, and register function.
+7. Stop if relationships are promptly recoverable in context.
```

| Baseline operation | Status | Canonical operation | Reason / evidence | Change and fixtures |
|---|---|---|---|---|
| Start by finding verbs. | **QUALIFY** | First capture meaning; then underline finite verbs and compare grammatical structure to story/action/state. | Prevents a surface edit from changing scope or agency. [WB-CLA-01; WB-ETH-01] | SC-003, SC-009; `sc-hedge`, `sc-citation` |
| Call them “tensed verbs.” | **REPLACE** | Use “finite verbs.” | Modals and nonfinite complements make *tensed* an unreliable operational label. | SC-003; terminology audit |
| Name characters and actions. | **KEEP + EXPAND** | Include state, affected entity, and cause; distinguish supported from guessed actor. | [WB-CLA-01, WB-CLA-03, WB-ETH-01] | SC-003, SC-006; `sc-boundary-unknown-agent` |
| Spot nominalizations before proving a fault. | **QUALIFY** | Search for candidates, then ask whether a central action is hidden beside a semantically light predicate and whether the noun serves a useful conceptual/topic role. | [WB-CLA-02, WB-CLA-07] | SC-004; `sc-positive-buried-action`, `sc-boundary-technical-noun` |
| Always convert characters/actions to subject/verb. | **REPLACE** | Promote only when doing so exposes the proposition, preserves discourse flow, and does not invent responsibility. | [WB-CLA-02–05; GS-RE-04–10; WB-ETH-01] | SC-004–06; passive/unknown-agent fixtures |
| Put a short concrete subject and verb in the first few words. | **REPLACE** | Test whether a long, movable windup miscues attachment or delays the kernel enough to impair recovery. | [WB-CLA-04, WB-CLA-06–07] | SC-007; `sc-opener` |
| Never separate a subject and verb with a long phrase. | **REPLACE** | Move, compress, promote, or split only an obstructive movable interruption; keep essential or controlled modifiers. | [WB-CLA-06–07; GS-RE-02, GS-RE-10] | SC-007; long-but-clear example |
| Old-before-new as step 6. | **MOVE** | `cohesion-emphasis` owns cross-sentence topic strings, given/new, context position, stress, and paragraph progression; clarity must respect its decision. | [WB-COH-01–08; WB-EMP-01–06; GS-RE-03–10] | SC-008; `sc-negative-flow`, `sc-regression-old-new` |
| Recover who-did-what from subject/verb alone. | **REPLACE** | Stop when intended relationships are promptly recoverable in context and no listed clarity fault changes interpretation or effort. | [WB-CLA-01, WB-CLA-07; GS-RE-10] | SC-002, SC-009; `sc-clean-email` |
| Passive decision procedure absent. | **ADD** | Retain passive for established affected-entity topic, unknown/irrelevant/appropriately suppressed agent, or expected register; flag only reader/accountability harm. | [WB-CLA-05; GS-RE-04–10] | SC-006; `sc-boundary-passive-topic`, `sc-boundary-unknown-agent` |
| Stop condition absent beyond rereading. | **ADD** | Stop before revision when relationships are already recoverable; after revision compare and prefer the original if merely different. | [WB-CLA-07] | SC-002, SC-009; `sc-clean-email` |

## Nominalization and light-verb redline

```diff
-Two reliable signals: suffixes ... and empty verb + action noun pairs.
-Verbs that signal a buried action nearby: occur, happen, take place, exist, be, have, do, make, conduct, perform, provide, achieve.
+Suffixes and light verbs are search clues only; morphology or a verb form never proves a fault.
+Revise only when a central action is functionally hidden and the marked noun/construction is not doing useful conceptual, discourse, aspectual, conventional, or politeness work.
```

| Baseline item | Status | Canonical disposition | Reason / evidence | Change and fixtures |
|---|---|---|---|---|
| Noun derived from verb/adjective is a nominalization. | **KEEP as morphology, not verdict** | The derivational label can aid search; fault status is independent. | [WB-CLA-02, WB-CLA-07] | SC-004 |
| Every noun-position gerund “counts too.” | **QUALIFY** | Treat it as a noun-like action candidate; do not infer reader harm. | Functional rather than morphological diagnosis. | SC-004; technical-noun boundary |
| Suffixes are “reliable signals.” | **REMOVE** | Suffixes are clues only. | They overgenerate and cannot show discourse function. | SC-004; `sc-boundary-technical-noun` |
| Forms of *be/have/do/make/occur* are “empty.” | **REMOVE** | Decide whether the predicate is semantically light **in this construction**; retain identity, state, existence, possession, aspect, causation, and conventional collocation. | [WB-CLA-02, WB-CLA-07; LAN-PM-02] | SC-004; stative exception |
| Conversion pairs are automatic (`make a decision` → `decide`). | **QUALIFY** | Use as candidate compression only if aspect, emphasis, collocation, topic function, scope, and register remain equivalent. | [WB-CLA-02; WB-CON-05] | SC-004; `sc-positive-buried-action` |
| Nominalization is faulty only when paired with an empty verb. | **QUALIFY** | That is one major pattern; sentence clarity also covers misleading subject, missing relevant agent, obstructive subject–verb gap, and misattached opener. | [WB-CLA-01–07] | SC-002, SC-010; complete label set |

## Example redline

| Baseline example/lesson | Status | Canonical replacement or safeguard | Why | Change and fixtures |
|---|---|---|---|---|
| “It is our requirement that a review … be done” → “We require that **you** review …” | **REMOVE** | Never supply *you*, *we*, *they*, or another agent unless the context supports it. State the evidence gap if agency matters. | The revision invents the reviewer and may change deontic scope. [WB-ETH-01] | SC-006, SC-009, SC-011; `sc-boundary-unknown-agent` |
| Platform-team investigation example | **REPLACE with original examples** | Use professional/API/security/architecture/email/research examples in `examples.md`; separate clarity edit from later residual cutting. | Portfolio requires original examples and one owner per operation. | SC-011; `sc-positive-buried-action` |
| Little Red Riding Hood opener | **REPLACE with original professional case** | Test a long conditions/review opener for attachment and dependency; retain a purposeful conditional opener. | Avoids source-distinctive pedagogy and a blanket split. [WB-CLA-04, WB-CLA-06–07] | SC-007, SC-011; `sc-opener` |
| “Authentication precedes authorization.” | **KEEP as canonical negative case** | No actor-action mismatch; both nouns are precise established technical concepts. | [WB-CLA-02–03, WB-CLA-07] | `sc-boundary-technical-noun` |
| “The request enters the gateway. It is validated…” | **ADD as passive-for-flow negative case** | Retain passive when *the request/it* is the topic string. | [GS-RE-04–10; WB-CLA-05] | `sc-boundary-passive-topic`, `sc-regression-old-new` |
| Cautious research passive | **ADD** | “A weak association was observed…” can remain when observer is irrelevant and caution/citation are functional. | Preservation and register rule. | `sc-citation` |

## Conflict and ownership redline

| Baseline concern | New owner | `sentence-clarity` obligation | Sequence / test |
|---|---|---|---|
| Who/what does what in one sentence | `sentence-clarity` | Diagnose actor/action/state/relationship and local dependency. | Local invocation; `sc-positive-question` |
| Old/given-before-new, topic continuity, stress, paragraph flow | `cohesion-emphasis` | Do not undo the established topic or passive-for-flow choice. | Cohesion → clarity; `sc-regression-old-new`, `ce-passive-topic` |
| Empty framing, repeated meaning, redundant modifiers, measured shortening | `concision` | Clarify first only if actor/action is independently obscure; defer residual excess. | Clarity → concision; `sc-negative-shorter`, `co-collision-clarity` |
| Purposeful periodic/cumulative/parallel/marked syntax | `sentence-variety` | Do not flatten a working structure merely to start faster. | Concision → variety; `sc-opener`, `sv-after-cutting` |
| Disputed acceptability or grammar/style/register status | `usage-adjudicator` | Do not convert a usage question into a general rewrite. | Usage last; `ua-negative-rewrite` |
| Memo hierarchy, document type | `memo-structure`, `doc-typing` | Skip; local clarity runs only after global structure stabilizes. | Portfolio order |

## Exception redline

| Baseline safeguard | Status | Canonical expansion | Coverage |
|---|---|---|---|
| Keep a nominalization that refers backward. | **KEEP** | Preserve event/result/topic nouns that create a backward link; cohesion controls. | `ce-nominalization-topic` |
| Keep a term of art or concept treated as a thing. | **KEEP** | Explicitly includes technical topics such as *authentication*, *authorization*, and *migration*. | `sc-boundary-technical-noun` |
| Keep a nominalization that avoids a clumsy clause. | **QUALIFY** | Keep when it improves packaging without hiding a central action; if the only issue is excess, defer to concision. | Minimal-intervention rule |
| Old-before-new can outrank characters/actions. | **KEEP + MOVE** | Cohesion owns the decision; passive and *be* may be the best form. | `sc-regression-old-new`, `ce-passive-topic` |
| Passive exception implicit only. | **ADD explicit** | Topic continuity, affected-entity focus, unknown/irrelevant/appropriately suppressed agent, and expected register. | `sc-boundary-passive-topic`, `sc-boundary-unknown-agent` |
| State/existence exception absent. | **ADD** | Keep *be* and existential structures when identity, existence, location, or condition is the proposition. | `exceptions.md`; `sc-clean-email` |
| Periodic/technical complexity exception absent. | **ADD** | Keep manageable purposeful delay and exact technical noun phrases. | `sc-opener`; long-but-clear example |
| Light-verb conventional meaning absent. | **ADD** | Keep constructions that encode distinct aspect, politeness, or collocation. | `exceptions.md` |

## Revision and preservation redline

```diff
-Preserve the writer's meaning, hedges, and voice.
+Before revising, preserve facts, quantities, attribution, evidence, citations, technical terms, legal effect, scientific caution, scope, modality, hedges, exceptions, negation, temporal order, relevant agency, and voice.
+Never invent responsibility.
+After rebuilding grammar and references, compare in context and prefer the original if the revision is merely different.
```

| Added guardrail | Reason | Change and fixtures |
|---|---|---|
| Capture the intended proposition before changing grammar. | Surface alignment is unsafe without a semantic baseline. [WB-ETH-01] | SC-003, SC-009; `sc-hedge`, `sc-citation` |
| Recover an agent only when text supports it. | Prevents the baseline’s invented-*you* error and false accountability. | SC-006, SC-009; `sc-boundary-unknown-agent` |
| Preserve negation, modality, quantities, conditions, citations, technical terms, legal/scientific effect. | These features can be erased by a “clearer” active/direct rewrite. | SC-009; `sc-hedge`, `sc-citation` |
| Rebuild agreement, tense, modality, complements, and references after recasting. | A conceptually right rewrite can still be grammatically or referentially broken. | SC-003, SC-009; static review |
| Compare and revert a merely different version. | Makes “leave clean sentences alone” executable. [WB-CLA-07] | SC-002, SC-009; `sc-clean-email` |

## Output-contract redline

```diff
-For each flagged sentence: fault type, original, one revision.
+Targeted review: verdict, reader problem if any, one explanation, at most two revisions.
+Direct revision: revised text first; note only a material choice.
+Fault explanation: finite verb, action/state, subject/topic, exact mismatch.
+Whole-document audit: repeated or consequential patterns only.
+Broad polish: this pass's changes and deferrals only.
```

| Baseline behavior | Status | Canonical behavior | Change and coverage |
|---|---|---|---|
| Fixed three-item report for every flagged sentence | **REPLACE** | Output scales to user intent and text scope. | SC-010; targeted/direct/audit contracts |
| Fault labels include `nominalization`, `passive`, `new-before-old` as if form alone were fault | **REPLACE** | Labels are `buried action`, `misleading subject`, `missing agent`, `obstructive subject–verb gap`, `misattached opener`, or `no clarity fault`. | SC-010; all `sc-*` |
| Rewrites only flagged sentences | **KEEP + STRENGTHEN** | Report repeated/consequential patterns, preserve clean spans, and stop on no fault. | SC-009–10; `sc-clean-email` |
| One revision only | **QUALIFY** | At most two for targeted review; direct revision returns one integrated text; no alternatives when unnecessary. | SC-010 |

## Regression contract

The canonical skill is defective if any of these assertions fails:

| Fixture | Required behavior | Baseline benefit/failure guarded |
|---|---|---|
| `sc-positive-buried-action` | Activate and expose the supported actor/action. | Preserves the core Williams diagnostic. |
| `sc-positive-question` | Activate for “Who is actually doing what?” | Preserves strong semantic trigger. |
| `sc-negative-shorter` | Defer a pure percentage-shortening request to concision. | Repairs metadata collision. |
| `sc-negative-flow` | Defer paragraph flow to cohesion-emphasis. | Completes old/new ownership move. |
| `sc-boundary-technical-noun` | Return `no clarity fault`; keep the technical nominalizations. | Strengthens nominalization exception. |
| `sc-boundary-passive-topic` | Retain passive that maintains the request as topic. | Blocks active-at-all-costs. |
| `sc-boundary-unknown-agent` | Do not invent an agent. | Blocks baseline’s invented-*you* error. |
| `sc-hedge` | Preserve *may* and the load qualification. | Expands semantic preservation. |
| `sc-citation` | Preserve citation and cautious association claim. | Protects evidence/attribution/register. |
| `sc-regression-old-new` | Do not force active voice; cohesion controls. | Preserves the baseline’s best conflict insight under correct ownership. |
| `sc-opener` | Diagnose only an actual opener/gap problem and preserve conditions. | Replaces a word-position prohibition with a dependency test. |
| `sc-clean-email` | Make no change. | Makes “leave clean sentences alone” binding. |

## Canonical artifact consequences

| Artifact | Semantic role after revision |
|---|---|
| `SKILL.md` | Compact trigger-bearing local method with functional diagnostics, preservation, stop conditions, routing, and proportionate output. |
| `references/principles.md` | Observable signals, diagnostic questions, operations, and exceptions for WB-CLA-01–07 and WB-ETH-01. |
| `references/exceptions.md` | Established-topic, term-of-art, passive, unknown-agent, state, periodic, hedge, and accountability cases. |
| `references/examples.md` | Original professional, API, security, architecture, memo, research, email, clean, passive-flow, and long-but-clear examples. |
| `references/evidence-map.md` | Primary/secondary provenance, source locations, access limitations, cutoff/retrieval dates. |
| `references/portfolio-routing.md` | Global-to-local order and adjacent-skill handoffs. |
| `tests/fixtures.yaml` | Positive, negative, boundary, preservation, collision, and regression specification. |
| `agents/openai.yaml` | Official optional interface metadata only; no invented trigger-schema fields. |

## Residual uncertainty

1. No claim in this diff converts the unavailable Williams/Bizup fifth-edition lesson prose into full access. The operational core is conservative and evidence-bounded.
2. Gopen–Swan’s full article supports important discourse heuristics but does not establish a universal cognitive law; the portfolio uses probabilistic language.
3. Reader effort, topic status, agency relevance, and purposeful periodic delay remain contextual judgments. The skill therefore uses stop/revert rules instead of numeric thresholds.
4. Static fixture coverage specifies required behavior but cannot guarantee identical implicit activation across every model or host.

These uncertainties require candor and minimal intervention; they do not justify restoring the baseline’s categorical form-based rules.
