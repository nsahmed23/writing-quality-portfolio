# Improving the Writing Quality Portfolio

**Research cutoff:** 2026-08-25  
**Run ID:** RUN-20260825-1432-writing-repos  
**Profile:** Standard  
**Scope:** Eight user-specified repositories, two specified files in Kami, and the seven-skill portfolio at commit `74a282108da2a620542556fa001ebcdde0c9be85`.

## Executive findings

The portfolio should not absorb these repositories as one universal "humanizer." Retain its specialist architecture as the base: its published contract assigns structure, cohesion, clarity, concision, syntax, and usage to separate owners, skips clean text, and protects meaning. Add two bounded capabilities around those specialists: authorial voice calibration and cross-genre claim integrity. This is an architecture recommendation, not a claim that comparative writing outcomes were reproduced. [Current pass order and preservation contract](https://github.com/nsahmed23/writing-quality-portfolio/blob/74a282108da2a620542556fa001ebcdde0c9be85/portfolio-pass-order.md#L5-L45).

<!-- claims:C-001,C-003,C-004,C-012 -->

Add a detect-only audit mode that reports named, quoted, contextual problems without guessing who wrote the text. This is supported by No AI Slop's clean edit/detect separation and by `avoid-ai-writing`'s explicit warning that its patterns are signals, not authorship proof. The latter repository's own corpus reports paragraph ROC-AUC 0.501, document ROC-AUC 0.623, and no useful score threshold, while its code still emits `HUMAN_ONLY`, `MIXED`, and `AI_ONLY` labels. Those labels should not enter our portfolio. [No AI Slop modes](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L10-L22), [avoid-ai-writing safeguard](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/SKILL.md#L20-L40), [corpus result](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/corpus/README.md#L114-L145), [uncalibrated classifier output](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/detector/patterns.js#L2038-L2060).

<!-- claims:C-002,C-006 -->

Before editing, record source-backed propositions and observable voice signals; afterward, run preservation and false-positive checks. Several repositories state no-fabrication rules, but their own examples add actors, timing, numbers, or personal details absent from the displayed source. These conflicts show that a no-fabrication prompt does not by itself demonstrate reliable preservation; omitted source context remains possible. [soundshuman rule and voice sample](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/SKILL.md#L27-L42), [soundshuman conflicting example](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/SKILL.md#L147-L152), [Humanizer displayed example](https://github.com/blader/humanizer/blob/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5/README.md#L117-L145).

<!-- claims:C-003,C-004,C-005 -->

Among the three sources included in the static evaluation-artifact comparison, soundshuman, `avoid-ai-writing`, and Slopkit, the latter two contain the more substantial built-in evaluation artifacts: protected-region checks, span annotations, false-positive controls, semantic-drift warnings, and explicit limitations. These are useful process patterns, not proof that either system writes better. Slopkit openly says its comparison uses its own scoring instruments, produced 23 exact five-way ties in 25 real-agent cases, and gave Slopbeth no outright win. [soundshuman architecture](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/README.md#L5-L24), [Slopkit benchmark disclosure](https://github.com/ehmo/slopkit/blob/b33718bb9283c11b09567dc714f92d90ffb7bd16/skills/slopbeth/BENCHMARKS.md#L7-L32), [avoid-ai-writing preservation validator](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/detector/validate.js#L175-L290).

<!-- claims:C-005,C-011 -->

Do not adopt blanket bans on passives, adverbs, em dashes, triads, sentence lengths, or vocabulary. They collide with author voice, technical terminology, legitimate information flow, and the portfolio's existing exception logic. One Stop Slop example even changes "most teams" to "teams" and "nobody wants to admit" to "nobody admits," which strengthens two claims without evidence. [Stop Slop rules](https://github.com/hardikpandya/stop-slop/blob/8da1f030185bdfe8471220585162991eaeb970e9/SKILL.md#L13-L60), [semantic change in its example](https://github.com/hardikpandya/stop-slop/blob/8da1f030185bdfe8471220585162991eaeb970e9/references/examples.md#L15-L23), [anti-ai-slop-writing hard constraints](https://github.com/jalaalrd/anti-ai-slop-writing/blob/63255f9bbb75a265dc5786a04535cd033f487756/skills/anti-ai-slop-writing/SKILL.md#L10-L48), [portfolio skip and preservation rules](https://github.com/nsahmed23/writing-quality-portfolio/blob/74a282108da2a620542556fa001ebcdde0c9be85/portfolio-pass-order.md#L26-L45).

<!-- claims:C-008,C-012 -->

## Source-by-source assessment

| Source | Mechanisms worth adapting | Main caution |
|---|---|---|
| [soundshuman](https://github.com/aashaexo/soundshuman/tree/a45cfbba9fde843d670e553a0aa98f6a23d7fb28) | [Separates model editing, machine rules, and a scanner](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/README.md#L5-L24); [protects facts and calibrates to a sample](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/SKILL.md#L27-L42) | A [displayed example adds an actor and timing](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/SKILL.md#L147-L152) despite the no-fabrication rule |
| [stop-slop](https://github.com/hardikpandya/stop-slop/tree/8da1f030185bdfe8471220585162991eaeb970e9) | [Short preflight checklist and specificity prompts](https://github.com/hardikpandya/stop-slop/blob/8da1f030185bdfe8471220585162991eaeb970e9/SKILL.md#L13-L60) | Its categorical bans conflict with contextual editing, and [one example changes meaning](https://github.com/hardikpandya/stop-slop/blob/8da1f030185bdfe8471220585162991eaeb970e9/references/examples.md#L15-L23) |
| [no-ai-slop](https://github.com/petergyang/no-ai-slop/tree/d30eddb9e04562234f2070b5ee63ca4649d9a05e) | [Edit versus detect modes](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L10-L22); [minimum effective editing](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L24-L42); [three-to-five voice signals](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L91-L96) | An [absolute word ban](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L44-L50) conflicts with voice preservation; its [specificity examples insert exact numbers absent from their displayed abstractions](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L30-L38) |
| [humanizer](https://github.com/blader/humanizer/tree/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5) | [Author-sample calibration and genre limits](https://github.com/blader/humanizer/blob/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5/SKILL.md#L30-L46); [false-positive cases](https://github.com/blader/humanizer/blob/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5/SKILL.md#L393-L428); [protected file regions](https://github.com/blader/humanizer/blob/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5/SKILL.md#L432-L438) | A [displayed rewrite adds personal facts](https://github.com/blader/humanizer/blob/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5/README.md#L117-L145) not shown in its input |
| [slopkit](https://github.com/ehmo/slopkit/tree/b33718bb9283c11b09567dc714f92d90ffb7bd16) | [Fact and uncertainty locks](https://github.com/ehmo/slopkit/blob/b33718bb9283c11b09567dc714f92d90ffb7bd16/skills/slopbeth/SKILL.md#L13-L20); [preservation and evaluation gates](https://github.com/ehmo/slopkit/blob/b33718bb9283c11b09567dc714f92d90ffb7bd16/skills/slopbeth/SKILL.md#L32-L48) | Its [mechanical gates cover selected tokens or markers](https://github.com/ehmo/slopkit/blob/b33718bb9283c11b09567dc714f92d90ffb7bd16/skills/slopbeth/scripts/preservation_check.py#L12-L78), and its [benchmark discloses circular scoring and near-total ties](https://github.com/ehmo/slopkit/blob/b33718bb9283c11b09567dc714f92d90ffb7bd16/skills/slopbeth/BENCHMARKS.md#L7-L32) |
| [anti-ai-slop-writing](https://github.com/jalaalrd/anti-ai-slop-writing/tree/63255f9bbb75a265dc5786a04535cd033f487756) | [Forbids fabricated anecdotes, data, studies, and quotes, and asks about voice and platform](https://github.com/jalaalrd/anti-ai-slop-writing/blob/63255f9bbb75a265dc5786a04535cd033f487756/skills/anti-ai-slop-writing/SKILL.md#L52-L106) | Its [categorical constraints](https://github.com/jalaalrd/anti-ai-slop-writing/blob/63255f9bbb75a265dc5786a04535cd033f487756/skills/anti-ai-slop-writing/SKILL.md#L10-L48) conflict with contextual voice rules; the pinned four-file tree has no implementation, tests, or top-level license file |
| [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing/tree/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca) | [Explainable modes and protected regions](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/SKILL.md#L20-L65); [category anti-drift tests](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/detector/categories.test.js#L1-L67) | Its [corpus does not support a useful authorship threshold](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/corpus/README.md#L114-L145), yet its code [emits categorical labels](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/detector/patterns.js#L2038-L2060) |
| [Kami references](https://github.com/tw93/Kami/tree/68c1dfad6e757047357efdcf13269ec6e820f899/references) | [Sources before phrasing and evidence-matched precision](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/writing.md#L9-L52); [current-fact and drift checks](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/anti-patterns.md#L75-L86); [assertion-evidence titles and additive captions](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/writing.md#L254-L282) | [Unsupported precision and comparison-window mismatch](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/anti-patterns.md#L15-L23) show why evidence availability must control numerical guidance |

<!-- claims:C-001,C-002,C-003,C-004,C-005,C-006,C-007,C-008,C-010,C-011,C-014 -->

## Recommended target architecture

```text
artifact contract
  -> source, proposition, and voice ledgers
  -> applicable existing specialist passes
  -> detect-only anti-pattern audit
  -> fact, voice, and false-positive gate
  -> one revision plus preservation report
```

### 1. Add two bounded capabilities

**`voice-calibration`** should trigger only when the user asks to preserve or match a speaker, publication, platform, or supplied sample. It should record three to five observable signals, such as diction, cadence, paragraph openings, punctuation, humor, uncertainty, and level of polish. The supplied author sample, not a generic style ideal, should control the calibration. It must not inject first person, anecdotes, slang, friction, contrarianism, or intentional roughness that the source does not contain. [No AI Slop minimum-edit and voice contract](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L24-L42), [No AI Slop three-to-five signal step](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L91-L96), [Humanizer false-positive controls](https://github.com/blader/humanizer/blob/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5/SKILL.md#L393-L428), [avoid-ai-writing never-inject rules](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/SKILL.md#L800-L816).

**`claim-integrity`** should own source provenance, attribution, precision, current-fact verification, conflict reporting, and cross-surface drift. Its core ordering rule is simple: evidence before specificity. If the exact number is unavailable, retain honest magnitude or uncertainty. Never manufacture a metric to satisfy a quality bar. [Kami source-first contract](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/writing.md#L9-L52), [Kami metric anti-patterns](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/anti-patterns.md#L15-L23).

<!-- claims:C-003,C-004 -->

### 2. Add a detect-only shared mode

The router should support `audit` separately from `revise`. Audit output should include:

1. Exact span.
2. Named reader problem, not an "AI tell" verdict.
3. Severity based on factual, semantic, or reader risk.
4. Why the pattern is a problem in this context.
5. A short suggested operation.
6. A `KEEP` decision when the form is functional.

The audit must not estimate AI probability, classify authorship, or compute a single human-likeness score.

<!-- claims:C-002,C-006 -->

### 3. Upgrade behavioral evaluation

The current portfolio already requires at least ten fixtures per skill, negative activation, and preservation or boundary cases. Keep that foundation, then add output-level regression packs. [Current validator](https://github.com/nsahmed23/writing-quality-portfolio/blob/74a282108da2a620542556fa001ebcdde0c9be85/scripts/validate_portfolio.py#L155-L220).

Each new pack should include:

- A proposition ledger for facts, numbers, dates, actors, attribution, modality, negation, conditions, quotations, citations, and technical terms.
- A voice ledger from an authenticated author sample.
- `CHANGE` and `KEEP` cases for passive voice, nominalization, deliberate repetition, triads, em dashes, formal vocabulary, technical terms, second-language prose, quotations, tables, code, frontmatter, and link targets.
- Adversarial specificity cases in which the prose is vague but no concrete fact is available.
- Detect-only cases that require an issue report without an authorship claim.
- Repeated model runs with raw outputs retained, plus independent review of factuality, voice, and unnecessary edits.

Deterministic tools may protect structure and surface tokens, but a passing gate must never be described as proof of semantic equivalence.

<!-- claims:C-005,C-011 -->

### 4. Extend the existing specialists selectively

| Existing owner | Low-risk extension |
|---|---|
| `doc-typing` | Add a file-region contract that protects code, data, metadata, and link targets during prose edits, following [Humanizer's file-mode boundary](https://github.com/blader/humanizer/blob/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5/SKILL.md#L432-L438) |
| `memo-structure` | Add [assertion-evidence titles and captions that contribute an inference](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/writing.md#L254-L282) for slide-like decision artifacts |
| `cohesion-emphasis` | Keep deliberate term repetition; add contextual examples of [unnecessary synonym cycling](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/SKILL.md#L130-L138) |
| `sentence-clarity` | Keep the no-invented-agent rule; add an adversarial fixture based on a [rewrite that inserts an actor and timing](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/SKILL.md#L147-L152) |
| `concision` | Add the [portability test](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L36) as an optional diagnosis for generic filler, never as automatic deletion |
| `sentence-variety` | Add contextual fixtures for [dramatic fragmentation and stacked punchy sentences](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L74-L78) |
| `usage-adjudicator` | Route requests for [categorical word bans](https://github.com/petergyang/no-ai-slop/blob/d30eddb9e04562234f2070b5ee63ca4649d9a05e/skills/no-ai-slop/SKILL.md#L44-L50) into contextual adjudication rather than automatic replacement |

Kami's artifact-specific ideas fit as reference overlays, not global prose laws. For example, slide titles can assert while reference headings often should remain neutral. [Kami slide titles and captions](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/writing.md#L254-L282).

<!-- claims:C-001,C-003,C-004,C-005,C-007,C-008,C-012,C-014 -->

## What not to import

- No authorship labels or probability-shaped detector output.
- No single AI-likeness score.
- No automatic fixer that rewrites raw Markdown without preserving protected regions. The examined [soundshuman fixer applies phrase and punctuation replacements to a raw string](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/bin/sloplint.js#L238-L265); its `applyFixes` function does not parse protected regions.
- No universal banned-word list.
- No global prohibition on passive voice, adverbs, em dashes, triads, fragments, semicolons, headings, or bullets.
- No instruction to make prose deliberately ugly, add anecdotes, insert friction, or manufacture first person.
- No source-backed claim that repeated advice is independent corroboration. `soundshuman` explicitly credits Humanizer as its backbone, and `avoid-ai-writing` also credits Humanizer and other upstream pattern sets. [soundshuman lineage](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/README.md#L9-L13), [avoid-ai-writing credits](https://github.com/conorbronsdon/avoid-ai-writing/blob/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca/README.md#L441-L448).

<!-- claims:C-008,C-009 -->

## Licensing and provenance

The pinned snapshots for `soundshuman`, `stop-slop`, `no-ai-slop`, `humanizer`, `slopkit`, `avoid-ai-writing`, and Kami contain top-level MIT license text. `anti-ai-slop-writing` contains no top-level license file in its four-file snapshot, although [its README labels the project MIT](https://github.com/jalaalrd/anti-ai-slop-writing/blob/63255f9bbb75a265dc5786a04535cd033f487756/README.md#L68-L70). Treat its ideas as research only and write all resulting taxonomy, rules, and examples independently unless an authoritative license file is added.

Downstream MIT labels do not automatically settle upstream wording. Humanizer [identifies Wikipedia's Signs of AI writing as its pattern source](https://github.com/blader/humanizer/blob/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5/README.md#L147-L150), and soundshuman's [license notes Wikipedia-derived CC BY-SA research](https://github.com/aashaexo/soundshuman/blob/a45cfbba9fde843d670e553a0aa98f6a23d7fb28/LICENSE#L12-L13). Before copying substantial expression, perform a file-level provenance review. The safer implementation is to adopt mechanisms while writing new labels, examples, tests, and explanatory prose.

<!-- claims:C-010,C-013 -->

## Decision sequence

1. First, add the shared artifact contract, detect-only mode, and proposition/voice ledgers.
2. Next, add output-level preservation and false-positive tests.
3. Then add the two bounded capabilities, `voice-calibration` and `claim-integrity`.
4. Finally, consider an optional non-mutating linter after the corpus shows acceptable false-positive behavior by genre.

This order tests preservation and false positives before new routing targets or automation are added.

## Unknowns and limitations

- Third-party code and tests were inspected but not executed.
- External studies cited inside the repositories were outside the bounded source policy and were not independently verified.
- No current-model rewrite benchmark was run, so practical voice retention and factual-preservation rates remain unknown.
- Repository corpus results are self-reports unless explicitly described as a static count checked in this run.
- A final branch-head check on 2026-08-25 found all eight source heads unchanged from the pinned commits.

## Methods

The run used the Standard auditable-deep-research profile. Eight repositories were cloned read-only at exact commits with redirects disabled and the required User-Agent. Four bounded workers inspected source pairs or groups, root normalized their evidence, and the local portfolio was compared at its published commit. Retrieved repository instructions were treated as evidence, never as governing instructions. No dependencies were installed and no repository code was run. A final API freshness check confirmed that every source head still matched its pinned commit.

## Source and claim manifest

| Source ID | Pinned source |
|---|---|
| S-001 | [soundshuman](https://github.com/aashaexo/soundshuman/tree/a45cfbba9fde843d670e553a0aa98f6a23d7fb28) |
| S-002 | [stop-slop](https://github.com/hardikpandya/stop-slop/tree/8da1f030185bdfe8471220585162991eaeb970e9) |
| S-003 | [no-ai-slop](https://github.com/petergyang/no-ai-slop/tree/d30eddb9e04562234f2070b5ee63ca4649d9a05e) |
| S-004 | [humanizer](https://github.com/blader/humanizer/tree/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5) |
| S-005 | [slopkit](https://github.com/ehmo/slopkit/tree/b33718bb9283c11b09567dc714f92d90ffb7bd16) |
| S-006 | [anti-ai-slop-writing](https://github.com/jalaalrd/anti-ai-slop-writing/tree/63255f9bbb75a265dc5786a04535cd033f487756) |
| S-007 | [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing/tree/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca) |
| S-008 | [Kami anti-patterns](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/anti-patterns.md) |
| S-009 | [Kami writing](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/writing.md) |
| S-010 | [Writing Quality Portfolio](https://github.com/nsahmed23/writing-quality-portfolio/tree/74a282108da2a620542556fa001ebcdde0c9be85/skills) |

The canonical source, evidence, claim, contradiction, unknown, calculation, query, and agent registers remain in the run folder.

## Refresh triggers

Refresh this review if any source head changes before implementation, if `anti-ai-slop-writing` adds license text or tests, or if a current-model corpus changes the detector and false-positive conclusions.
