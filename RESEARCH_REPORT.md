# Writing-Quality Portfolio: Research Report

**Version:** 1.0.0  
**Research cutoff:** 2026-08-19 23:59 America/Chicago  
**Retrieval and validation date:** 2026-08-25  
**Controlling evidence records:** `source-access-ledger.csv`, `source-coverage-ledger.csv`, `principle-registry.json`, and `claim-to-source-ledger.csv`

This report distinguishes three different meanings of completion. The **artifact set is complete**: seven skill packages, routing, references, machine-readable ledgers, tests, results, and the negative-control dossier are present. The **accessible-source extraction is complete**: every lawfully inspected full text and every visible section of a partial source is accounted for. The **copyrighted-book corpus is not fully inspected**: the package does not disguise tables of contents, snippets, reviews, or derivative teaching materials as complete books.

## Part I: Executive synthesis

### What the authorities contribute

| Authority | Distinct contribution | Portfolio disposition |
|---|---|---|
| Williams and Bizup | Diagnosable relations among actions, characters, subjects, verbs, cohesion, emphasis, concision, sentence shape, elegance, and ethical clarity | The local clarity kernel belongs to `sentence-clarity`; economical expression to `concision`; cross-sentence flow and stress to `cohesion-emphasis`; shape/elegance remain constrained shared references |
| Lanham | A conspicuous, procedural way to mark padded institutional prose, recover action, revise, and check rhythm | Guarded paramedic workflow in `concision`, never an automatic deletion or active-voice mandate |
| Gopen and Swan | A reader-expectation model for topic, stress, subject–verb continuity, hierarchy, and paragraph movement | Editorial heuristics in `cohesion-emphasis`, expressly not universal cognitive laws |
| Virginia Tufte | A functional catalogue of syntactic resources, from phrase and clause constructions to branching, balance, inversion, and symbolism | Form-to-purpose reference architecture for `sentence-variety`; no length quotas or decorative rewriting |
| Barbara Minto | Governing answer, vertical question/answer logic, horizontal grouping, order, introductions, problem definition, analysis, and presentation | Document/argument architecture in `memo-structure`, gated by genre and reader task |
| Daniele Procida / Diátaxis | Four user-need contracts—tutorial, how-to, reference, explanation—and a documentation architecture based on activity and knowledge state | `doc-typing`, including typed sections inside legitimate mixed containers |
| Bryan A. Garner | A contextual usage-adjudication method, a five-stage Language-Change Index, grammatical terminology, and a broad A–Z usage architecture | Compact `usage-adjudicator` method plus a searchable, extensible issue layer and a current-evidence protocol |
| Strunk and White | Memorable maxims, historical influence, and a useful stress test for vague or inaccurate style commands | Negative control only; every useful reminder is either superseded, owned elsewhere, or retained solely as context |

The six new skills remain separate because they operate on different objects and answer different questions. Document purpose is not argument hierarchy; paragraph flow is not sentence actor/action alignment; wordiness is not syntactic monotony; usage status is not revision style. Combining them would make every broad description an indiscriminate trigger and would erase the conditions under which a marked form—passive, nominalization, repetition, qualification, mixed documentation—should remain.

The existing `sentence-clarity` skill changed most in its boundaries. It no longer treats a nominalization suffix, passive, abstract subject, form of *be*, long sentence, or nonconcrete subject as a fault by itself. It tests a specific reader problem; preserves topic continuity and legitimate agent suppression; never invents an agent; hands old/new flow, excess, and syntactic choice to their owners; and can return `no clarity fault` without rewriting.

The portfolio uses one diagnosis and selective global-to-local passes. `doc-typing` and `memo-structure` are conditional gates; `cohesion-emphasis` precedes local syntax because flow may determine subject and voice; `sentence-clarity` establishes the proposition; `concision` removes residual excess; `sentence-variety` adjusts form only after cutting; `usage-adjudicator` resolves genuine questions in the wording that will remain. No pass runs merely because it exists.

Strunk and White does not justify an eighth skill. “Omit needless words” is less reproducible than the Williams/Lanham diagnostics; “use the active voice” is unsafe without discourse context; the book's passive identifications have documented grammatical problems; many usage claims age rapidly; and White's stylistic counsel is deliberately personal. Useful reminders survive only under stronger diagnostics and cited ownership.

The major evidence limitation is decisive: six core copyrighted books and the White-revised fourth edition were only partially accessible. Consequently, no claim of complete book-level extraction, complete Tufte form inventory *as Tufte presents it*, or complete Garner headword inventory is made. The package is nevertheless implementation-complete for every principle supported by the inspected evidence.

## Part II: Bibliographic and source-access manifest

The controlling bibliographic manifest is `source-manifest.md`; the row-level audit is `source-access-ledger.csv`. Key resolutions follow.

- *Style: The Basics of Clarity and Grace*, fifth edition, is the baseline product. Pearson metadata supports print publication in 2014, a 2015 copyright, and ISBN 9780321953308. The thirteenth edition of *Style: Lessons in Clarity and Grace* is a related product, not a sixth edition of *Basics*. [Pearson, *Basics*](https://www.pearson.com/en-us/subject-catalog/p/style-the-basics-of-clarity-and-grace/P200000002141/9780134109749)
- *Revising Prose*, fifth edition, was published by Pearson Longman in 2006 with a 2007 copyright and ISBN 9780321441690. [Pearson, *Revising Prose*](https://www.pearson.com/en-us/subject-catalog/p/revising-prose/P200000002251/9780321441690)
- *The Sense of Structure* is recorded as the 2004/2005 first edition. The companion article, “The Science of Scientific Writing,” was inspected in full through a permission-reprinted copy.
- Graphics Press and library metadata support one substantiated 2006 edition of *Artful Sentences*. Edward Tufte's own announcement calls Virginia Tufte his mother; USC's memorial record corroborates the relationship. [Edward Tufte announcement](https://www.edwardtufte.com/notebook/artful-sentences-syntax-as-style-by-virginia-tufte-now-published/)
- Minto requires two records: the 1996 author-designated expanded edition and Pearson's publisher-numbered third edition, published in 2026. The evidence does not support treating their chapter structures as equivalent. [Pearson third edition](https://www.pearson.com/en-gb/subject-catalog/p/the-pyramid-principle/P200000015259/9781292763255)
- Diátaxis is a living site, not a fixed edition. All 18 English navigation pages visible in the cutoff-era site were inspected. News dated August 4 and 6, 2026 predates the cutoff, but the absence of an official timestamp on every page leaves a small temporal caveat. [Diátaxis](https://diataxis.fr/)
- *Garner's Modern English Usage*, fifth edition, Oxford University Press, 17 November 2022, 1,312 pages, ISBN 9780197599020, was the latest substantiated edition at cutoff. [OUP](https://global.oup.com/academic/product/garners-modern-english-usage-9780197599020)
- Strunk's 1918 and 1920 texts were inspected in full. Strunk/White fourth-edition prose was not; publisher metadata and the complete table of contents were inspected. [Pearson fourth edition](https://www.pearson.com/en-au/subject-catalog/p/elements-of-style-the/P200000002160/9780205309023)
- Current official OpenAI documentation requires a skill directory with `SKILL.md` containing `name` and `description`; `agents/openai.yaml`, references, scripts, and assets are optional. Description-driven implicit activation and explicit invocation are supported. Multiple related skills can be distributed as a plugin. [OpenAI, “Build skills”](https://learn.chatgpt.com/docs/build-skills), [OpenAI, “Skills in ChatGPT”](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)

Because the build page is undated and was retrieved six days after the cutoff, the platform claim is date-stamped **current as retrieved 2026-08-25, high confidence for the 2026-08-19 cutoff but not an archival proof of exact-cutoff text**.

## Part III: Complete source-coverage ledger

`source-coverage-ledger.csv` contains 321 data rows. Nothing visible in the inspected structures is silently omitted.

| Source | Coverage rows | Full-text status | Coverage unit |
|---|---:|---|---|
| WB5 | 12 | Partial | Preface, ten lessons, index |
| WBL13 | 26 | Partial related work | Preface/front matter, five parts, twelve lessons, appendices/back matter |
| LAN5 | 12 | Partial | Preface, eight chapters, terms, exercises, index |
| GOPEN | 37 | Partial | Six chapters and visible subheadings |
| GS90 | 17 | Full | Article concepts/sections |
| TUF | 16 | Partial | Fourteen chapters, bibliography, index |
| MIN96 | 19 | Partial | Four parts, twelve chapters, three appendices |
| MIN26 | 13 | Partial | Current-edition visible parts/chapters/appendix |
| DIA | 18 | Full current site | Every English navigation page |
| GAR5 | 34 | Partial | Front matter, LCI, support sections, A–Z category buckets |
| STR18 | 23 | Full | Intro, eighteen rules, form/usage/spelling, exercises |
| STR20 | 23 | Full | Intro, seven usage rules, eleven composition rules, form/usage/spelling, exercises |
| SW4 | 48 | Partial | Intro, visible rules/chapters, 21 White reminders, afterword, glossary |
| PULLUM | 12 | Full author manuscript | Argument sections and references |
| PLAT | 11 | Full current docs/local schema | Format, packaging, activation, metadata, validation |

“Accounted” does not mean “extracted from unseen prose.” Partial-source rows identify the visible location, access limit, supported disposition, owner, and note. Principles derived from an accessible companion or related edition carry that source's ID and are not falsely cited to an unread fifth-edition page.

## Part IV: Source-by-source analytical extraction

### 1. Williams and Bizup

The visible fifth-edition architecture progresses from understanding style through actions, characters, cohesion/coherence, emphasis, global coherence, concision, shape, elegance, and ethics. This sequence matters: the method is not merely “remove nominalizations.” It joins local grammatical choices to information flow, sentence form, writer responsibility, and deliberate opacity.

**Local clarity.** The operational kernel asks whether the sentence's important action or state appears in a finite verb and whether the grammatical subject gives readers a useful actor or topic. A nominalization is a morphological category, not a defect. It becomes diagnostically relevant when it hides a central action while a semantically light predicate carries the clause. Likewise, an abstract or nonhuman subject can be exact; the fault is a misleading shell or suppressed relationship. Passive voice is functional: retain it for topic continuity, unknown or irrelevant agents, appropriate responsibility management, or conventional scientific description; revise it when agent suppression causes the reader problem.

**Complexity and shape.** Readability often improves when a subject reaches its verb without a long movable interruption and when manageable material precedes heavy material. These are probabilistic placement heuristics, not commands for universally short subjects or sentences. Coordination presents ideas as comparable; subordination ranks them. Cumulative, periodic, balanced, and parallel structures can embody relations and rhythm when the information warrants them.

**Cohesion, emphasis, and global coherence.** Accessible openings help readers connect backward; endings can carry new, complex, or important material; topic strings and consistent framing support local continuity; sections require an identifiable point and ordered support. Old/given information, grammatical subject, topic position, and character are not synonyms. The portfolio therefore gives cross-sentence ordering and stress to `cohesion-emphasis`, while `sentence-clarity` may consult local context only to avoid damaging flow.

**Concision.** Operational categories include redundant pairs, implied modifiers, metadiscourse that narrates the writer rather than the subject, empty framing, inflated diction, and stacks of hedges or intensifiers that contribute no distinct scope. Deletion is licensed only after a proposition ledger distinguishes verbal padding from evidence, courtesy, legal effect, and epistemic caution.

**Elegance and ethics.** Formal symmetry, controlled length, resonant closure, and deliberate departure can strengthen prose, but they are form-to-purpose options rather than scoring rules. Clear syntax is ethically relevant because writers can obscure agency or manufacture certainty. The revision contract therefore protects attribution, uncertainty, conditions, technical terms, and citations and prohibits invented agents.

**Disposition.** Lessons 2–3 primarily support `sentence-clarity`; lessons 4–6 support `cohesion-emphasis`; lesson 7 supports `concision`; lessons 8–9 inform `sentence-variety` and shared references without creating style quotas; lesson 10 supplies the cross-portfolio preservation rule. Lesson 1 and the index are reference/control locations. Every lesson has a ledger row; full fifth-edition chapter-level completeness is not claimed.

### 2. Lanham

The fifth edition's visible structure—Action, Attention, Voice, Skotison, Business Prose, Professional Prose, Electronic Prose, and Why Bother?—shows that the paramedic method is a teaching and attention technology embedded in a larger diagnosis of institutional style. “Skotison” names intentional obscurity; the genre chapters test how social and professional incentives produce “official” prose; the closing rationale connects revision effort to reader attention and voice.

The reconstructed eight-step procedure is:

1. Circle prepositions.
2. Circle forms of *is*/*be*.
3. Identify the central action and “who is kicking whom.”
4. Put the action in a simple, preferably active finite verb when that accurately exposes agency.
5. Get the sentence moving promptly by removing empty throat-clearing.
6. Read the revision aloud.
7. Mark rhythmic units and repair cadence after cutting.
8. Mark sentence lengths and inspect meaningful pattern rather than enforce a quota.

The portfolio wraps those markings in two safeguards. First, prepositions, *be*, passive clauses, and nominalizations are candidate signals, never deletion commands. Second, a semantic audit precedes and follows cutting. Scientific qualifiers, legal conditions, politeness, evidential attribution, conventional collocations, and technical action nouns survive when they encode a distinct proposition. The “lard factor” records the percentage removed; it is not a target, quality score, or incentive to overcut.

Lanham and Williams overlap but play different roles. Williams supplies the finer functional diagnosis and exceptions; Lanham supplies a memorable marking sequence, an institutional-prose lens, and an aloud/rhythm check. `sentence-clarity` repairs actor/action alignment first when the proposition is obscure; `concision` then removes residual padding. This avoids using deletion to fossilize a badly represented proposition.

### 3. Gopen and Swan

The complete 1990 article describes conventional structural locations that readers may use to infer a sentence's function. The opening “topic position” links backward and provides context; the closure or “stress position” tends to receive emphasis; given/accessibly recoverable material often belongs before new material; subject and finite verb should not be needlessly separated; important action is normally clearer in the main clause and verb; topic strings support continuity; paragraph structure should develop rather than merely accumulate.

The model separates several dimensions that editing folklore often collapses:

- **Topic position** is a structural region, not necessarily the grammatical subject.
- **Given information** is discourse-accessible, not merely repeated wording.
- **Stress position** concerns default closure emphasis, not every final word.
- **End weight** concerns structural complexity, not importance or newness.
- **Clause hierarchy** tells readers which proposition governs, whereas typography cannot reliably repair a syntactically subordinated main point.

A sentence can therefore be grammatical yet misdirect attention: it may open on an unlinked concept, interrupt the subject–verb dependency, place background in the stress position, or subordinate the intended conclusion. The revision operations are structural: restore a backward link, select an established topic as subject when useful, place the principal action in the governing clause, move new/technical complexity into an interpretable location, and make paragraph progression explicit through topic strings and logical linkage.

The article's title does not establish experimental science. It reports no controlled study and repeatedly frames its principles as tendencies rather than rules. The package therefore labels the reader-expectation claims as rhetorically influential heuristics consistent with established information-structure observations, not universal cognitive laws. Reliability varies with genre, prosody, marked focus, language variety, reader expertise, and purposeful suspense. Scientific examples motivated the article, but the editorial tests transfer cautiously to professional prose; they do not license claims about every English reader.

*The Sense of Structure* visibly expands the model across six chapters: sentence complexity and tools; structural anatomy; emphasis, motion, and connection; paragraph issue/point and document extension; critique of simplistic “write as you speak” advice; and punctuation as structural control. The book's 37 visible chapter/subheading locations are accounted for, but its prose was not fully accessible. The full article supplies the directly inspected core; it is not presented as a complete substitute for the book.

### 4. Virginia Tufte

The 14-chapter catalogue organizes syntax by functional resources rather than by sentence-length variation: short sentences; noun phrases; verb phrases; adjectives/adverbs; prepositions; conjunctions/coordination; dependent clauses; openers/inversion; free modifiers and branching; appositives; interrogative, exclamatory, fragmentary, and other special forms; parallelism; cohesion; and syntactic symbolism.

The derived operational catalogue in `skills/sentence-variety/references/syntax-catalog.md` covers appositives, absolutes, participial and infinitive phrases, prepositional frames, relative/adverbial/noun clauses, coordination, subordination, parallelism, balance, antithesis, repetition, ellipsis, inversion, delayed subjects and predicates, cumulative and periodic movement, left/right/mid-branching, loose and suspended syntax, fragments, questions, parenthesis, asyndeton, polysyndeton, punctuation controls, short contrastive sentences, architected long sentences, and mixed patterns. Each row records structure, purpose, information placement, register, risk, original professional/technical/failure examples, and interaction with adjacent skills.

The catalogue carefully labels provenance. A form named by a visible Tufte chapter is source-grounded at that level. A requested seed that could not be verified in inaccessible chapter prose is marked **derived/compatible**, not falsely attributed as Tufte's term or taxonomy. This is the strongest copyright-conscious and evidence-honest form of comprehensive representation available under the access limit.

The skill diagnoses repeated opener and clause architecture, unbroken SVO sequences that flatten relations, choppy independence, uncontrolled sprawl, or a mismatch between form and rhetorical job. It then chooses a construction for a reason: an appositive defines, subordination ranks, coordination equates, a cumulative tail elaborates, a periodic sentence delays a governing claim when suspense or conditions warrant, a fragment isolates only where register permits, and parallelism makes comparable items legible. It stops when repetition supports procedure, comparison, cadence, topic continuity, or voice. Virginia Tufte was Edward Rolf Tufte's mother, not his wife.

### 5. Barbara Minto

The 1996 expanded edition visibly spans four linked domains. **Logic in writing** covers why pyramids work, internal substructures, construction, introductions, deduction, and induction. **Logic in thinking** covers ordering and summarizing grouped ideas. **Logic in problem solving** covers problem definition and structuring analysis. **Logic in presentation** covers page, screen, and prose realization. Three appendices address structureless situations, introduction patterns, and key points. Pearson's 2026 third edition is current by publisher numbering, but the package does not assert an unverified one-to-one chapter correspondence.

Operationally, a memo begins with the reader's governing question and a responsible answer at the highest useful level. Each higher claim must invite a question that its children collectively answer—vertical logic. Siblings must share one kind of relationship—horizontal logic—and follow an explicit order: chronology, structural order, or degree/ranking. Inductive groups summarize comparable evidence; deductive chains connect premises and implication without disguising intermediate assumptions. A heading is not a governing thought, and a label such as “three issues” is not a synthesis.

SCQ/SCQA is an introduction logic, not a mandatory template. A stable situation makes the topic recognizable; a complication creates tension; the implicit or explicit question motivates the answer. The current Minto site foregrounds the term “SCQ Framework,” so the package defines SCQ and uses SCQA only as a transparent portfolio shorthand for the answer. Executive summaries and recommendations normally answer early because decision readers need orientation; exceptions include diplomacy, bad-news sequencing, genuinely exploratory inquiry, narrative evidence, and cases in which a conclusion without minimal context would mislead.

MECE is a practical test of an analytical partition: categories should avoid decision-relevant double counting and cover the claim's stated scope. It is not proof that reality has nonoverlapping natural kinds. When categories legitimately overlap, the editor declares the overlap, changes the dimension, or narrows the claim instead of forcing false exclusivity.

Top-down construction works when the governing question and answer are known. Bottom-up construction clusters observations, finds the relationship, writes a synthesis, and iterates upward. Issue trees and diagnostic frameworks belong to analysis; the prose or slide deck should present the reasoning needed by the audience, not every branch explored. The skill preserves uncertainty, counterevidence, dependencies, and confidence instead of making the pyramid cleaner than the evidence.

`memo-structure` owns memos, briefs, recommendations, decision emails, argument-led reports, and analogous deck logic. It does not own tutorials, direct reference, chronological incident records, narratives, or open-ended notebooks. Page formatting and slide design remain reference material unless they reveal the hierarchy.

### 6. Diátaxis

The complete inspected site consists of Home, Start here, Applying Diátaxis, the four type pages, The compass, Workflow, Understanding Diátaxis, Foundations, The map, Quality, Tutorials and how-to guides, Reference and explanation, Colophon, Help translate, and News & Updates. The central map uses two axes: **action ↔ cognition** and **acquisition ↔ application**. These yield four needs/forms, not four arbitrary content labels.

| Type | Reader activity/state | Enforceable contract | Must not become |
|---|---|---|---|
| Tutorial | Learner acquires competence through a managed, successful experience | Promise a meaningful destination; control prerequisites/environment; lead action step by step; show observable progress; minimize choice and detours; verify completion | A menu of alternatives, exhaustive reference, conceptual lecture, or isolated task recipe |
| How-to guide | Competent user applies knowledge to achieve a real goal | Start from the goal and circumstances; provide adaptable ordered directions; state prerequisites, branches, verification, and troubleshooting relevant to the task | A teaching journey, product tour, conceptual essay, or API inventory |
| Reference | User looks up exact information while working | Describe scope completely and neutrally; mirror the product/system; use consistent schemas, terminology, signatures, parameters, errors, and constraints; keep examples illustrative | A narrative lesson, persuasive explanation, or goal-specific recipe masquerading as specification |
| Explanation | Reader develops understanding through reflection and connection | Explain causes, relations, alternatives, history, constraints, and tradeoffs; permit multiple perspectives and links outward | A procedure, quickstart, or exhaustive specification |

Classification starts from the reader's task and knowledge state, never the title or filename. A quickstart is usually tutorial-like when it manages a first success, but can be a how-to for an already competent user. Authentication can be a conceptual explanation, a setup how-to, a reference schema, or a container with explicitly typed sections. Endpoint pages are predominantly reference; recipes are how-to; architecture concepts are explanation; migration guides are how-to with scoped explanation; runbooks are how-to/reference hybrids; troubleshooting usually begins as goal-oriented how-to with diagnostic reference.

The framework does not ban mixed pages. It warns against unmarked mixing that changes the reader contract midstream. A container may intentionally host a conceptual overview, task recipe, and parameter table if the dominant contract and section boundaries are explicit, navigation supports each need, and each section obeys its local type. Migration therefore proceeds by inventorying user needs, typing sections, splitting only harmful mixtures, relinking types, and testing whether users can find the right contract.

Quality is type-specific: tutorial success and learner confidence; how-to goal completion under real variations; reference accuracy, consistency, and scope; explanation coherence and insight. Maintenance follows the same architecture: product-schema changes demand reference updates; workflow changes affect how-to; onboarding changes affect tutorials; conceptual model changes affect explanation and cross-links.

### 7. Garner

Garner fifth is both a usage dictionary and a meta-method. Its support architecture includes a list of essay entries, abbreviations, pronunciation key, the Language-Change Index key, a grammatical/rhetorical glossary, a usage-book timeline, a select bibliography, and A–Z entries. The complete A–Z corpus was subscription-restricted, so the 26 letter buckets are accounted for without pretending that their unseen headwords were extracted.

The Language-Change Index (LCI) tracks prescriptive acceptance in five stages:

1. a novel form is generally rejected;
2. it spreads but remains widely unacceptable in edited prose;
3. it becomes common but still attracts substantial resistance;
4. it is broadly accepted, with some residual opposition;
5. it is fully accepted in edited standard usage.

An LCI stage is neither grammaticality nor raw frequency. The skill separately records Garner's edition-dated judgment, the construction actually at issue, register, geography/dialect, field, and current evidence. It can return `standard`, `nonstandard`, `accepted but contested`, `informal`, `formal`, `archaic`, `regional`, `emerging`, `skunked`, `context dependent`, or `unresolved`.

The complete question taxonomy spans grammar/syntax; diction and semantic distinction; confusables; idiom/collocation; spelling/hyphenation/capitalization; punctuation; pronunciation; redundancy/pleonasm; jargon and euphemism; innovation and archaism; dialect/region/English variety; legal or specialist usage; inclusive or dated language; hypercorrection; folklore rules; skunked terms; and authority disagreement. This taxonomy is complete as a routing architecture, not as a copyrighted headword substitute.

The adjudication procedure is:

1. Quote or isolate the exact form, construction, sense, punctuation, or convention.
2. Distinguish attested meaning from the user's intended meaning.
3. Classify the question—grammar, usage, register, house style, geography, field convention, or preference.
4. Record Garner's fifth-edition treatment and LCI only when directly verified.
5. Check current reputable dictionaries, contemporary edited corpora, specialist authorities, and relevant regional evidence when the issue is time-sensitive.
6. Interpret corpus counts comparatively; do not equate frequency with formal acceptance.
7. Explain material disagreement and audience risk.
8. Recommend for the actual audience/register; admit uncertainty and offer a low-risk recast when useful.

`skills/usage-adjudicator/references/issue-index.csv` is a searchable schema with a small set of directly verified seed issues, not a fabricated complete Garner inventory. New rows require edition/page verification and a current-evidence date. This limitation is intentional: reproducing or closely paraphrasing the A–Z work would be both evidentially unsupported here and copyright-inappropriate.

### 8. Strunk and White negative control

Strunk's complete 1918/1920 book includes seven usage rules, eleven composition principles, matters of form, commonly misused and misspelled words, and exercises. The White-revised fourth edition retains and expands the rule structure, adds/updates usage material and 21 personal reminders under “An Approach to Style,” and includes an afterword and glossary. Only its visible structure, publisher metadata, and lawfully quoted/critically documented claims are used; unseen fourth-edition prose is not represented as read.

The strongest maxims point toward real problems but lack sufficient diagnostics. “Omit needless words” does not identify which words encode uncertainty or scope. “Use the active voice” ignores topic continuity and legitimate agent suppression. “Use definite, specific, concrete language” can help examples and attribution but cannot replace necessary abstraction or terms of art. Advice about qualifiers and adverbs can prompt an excess check but cannot make a part of speech culpable. Paragraph and related-words advice is useful only after its contextual qualifications are restored.

Pullum's grammatical critique is especially important. The book's discussion misidentifies passives, treats unrelated constructions as evidence, and presents preferences or contested folklore as grammar. Pullum also documents places where the authors' effective prose violates their own categorical wording. This is not hypocrisy evidence; it shows why real rhetorical purposes outrank literal maxims.

The complete rule-level disposition appears in `negative-control/strunk-white-exclusion-dossier.md`. No Strunk/White rule enters a skill unless an independently stronger source supplies the diagnostic and receives the principle ID. The negative control may trigger a test, never an edit rule.

## Part V: Principle registry

`principle-registry.json` and `.csv` contain **252** field-complete entries:

| Source ID | Entries |
|---|---:|
| WB5 | 36 |
| LAN5 | 18 |
| GS90 | 10 |
| TUF | 29 |
| MIN96 | 25 |
| DIA | 39 |
| GAR5 | 46 |
| STR18/STR20 lineage | 18 |
| SW4 | 21 |
| PLAT | 10 |

Every row includes the required identity, location, terminology, writing level, fault class, reader problem, signal/question, operation/procedure, conditions, exceptions, risks, counterexamples, evidence/empirical status, owner/secondary owner, reference/exclusion disposition, examples, tests, and confidence. Page fields use page numbers only where inspected evidence supports them; otherwise they use exact chapters, site page titles, article locations, or an explicit “TOC/metadata” location.

The registry treats normative advice, grammatical description, rhetorical heuristic, empirical/corpus observation, platform requirement, and taste as different evidence types. Every row has an explicit disposition. `claim-to-source-ledger.csv` separately records high-consequence edition, platform, and synthesis claims.

## Part VI: Cross-source conflict and overlap analysis

The controlling record is `conflict-ledger.md`. The principal resolutions are:

- **Actor-first vs topic-first:** cohesion controls when an established affected entity provides the backward link; agency controls when responsibility or causation would otherwise disappear.
- **Active vs passive:** neither wins categorically. Information flow, accountability, evidence about the agent, and register determine the form.
- **Directness vs responsible suppression:** restore a supported relevant agent; never invent one or expose a legitimately protected identity.
- **Concision vs qualification:** a word is not needless if it changes certainty, scope, legal effect, courtesy, attribution, or conditions.
- **Concision vs artful expansion:** remove empty expansion first; preserve or select syntax that expresses a real relation, cadence, or emphasis.
- **Simple kernel vs periodic form:** clarity controls when dependencies fail; rhetorical preparation controls when conditions/suspense are manageable and purposeful.
- **Variety vs consistency:** alter repeated architecture only when it obscures relations or produces unintended monotony; retain procedure, comparison, cohesion, and deliberate refrain.
- **Stress vs chronology:** chronology controls instructions and evidentiary event sequences; local syntax can create emphasis without falsifying order.
- **Minto vs Diátaxis:** type the reader contract first. A tutorial is not an answer-first memo; reference is not SCQA.
- **MECE vs natural overlap:** specify the analytic dimension or acknowledge intersections; do not coerce reality into false partitions.
- **Williams vs Gopen:** Williams supplies reason-based clarity/cohesion tests; Gopen supplies a position-oriented heuristic. The canonical glossary keeps subject, topic, actor, given material, topic position, stress, and end weight distinct.
- **Williams vs Lanham:** Williams owns the functional diagnosis and safeguards; Lanham supplies marking, provocation, and rhythm. Clarity precedes residual cutting.
- **Garner vs corpus:** report the edition-dated prescriptive judgment and current evidence separately. Neither raw frequency nor one authority alone settles every register.
- **Strunk/White vs portfolio:** the owning diagnostic always controls; the maxim is at most a mnemonic or negative-control assertion.

Each ledger row records whether the conflict is real/apparent, scope, sequence, exception, owner, and a fixture ID.

## Part VII: Portfolio architecture

### Levels and ownership

| Level/problem | Owner |
|---|---|
| Documentation purpose, user need, page/section typing, information architecture | `doc-typing` |
| Governing question/answer, evidence hierarchy, grouping, analytic order | `memo-structure` |
| Paragraph/sentence continuity, given/new flow, stress, clause hierarchy, reference | `cohesion-emphasis` |
| Sentence actor/action/dependency clarity | `sentence-clarity` |
| Redundant or padded expression | `concision` |
| Purposeful syntactic architecture and unintended monotony | `sentence-variety` |
| Word/construction/convention status in context | `usage-adjudicator` |

### Validated pass order

The tested order is: (1) `doc-typing` when relevant; (2) `memo-structure` when genre-appropriate; (3) `cohesion-emphasis`; (4) `sentence-clarity`; (5) `concision`; (6) `sentence-variety`; (7) targeted `usage-adjudicator`. It differs from seven automatic full rewrites: diagnosis assigns one owner to each fault; empty passes are skipped; only changed spans flow downstream. The invalidation and feedback rules appear in `portfolio-pass-order.md`.

### Trigger resolution

Explicit narrow wording overrides inferred broad routing unless it would produce an unsafe or incoherent edit. “Clarify this sentence” activates clarity; “make this shorter” concision; “paragraphs do not flow” cohesion; “same structure” variety; “executive memo” memo; “tutorial or how-to” doc typing; “accepted in formal English?” usage. Ambiguous “simplify” or “organize” requires an observable fault class or one short question. Broad “edit/polish” invokes coordinated diagnosis, not every skill by default. `trigger-matrix.csv` and `portfolio-routing.md` specify strong, weak, negative, dual, and sequencing cases.

### Preservation and stop rule

Every pass protects factual scope, quantities, negation, conditions, justified uncertainty, attribution, citations, technical terms, legal effect, relevant agency, useful repetition, chronology, and authorial voice. A clean span is an asset. Stop when the assigned reader problem is absent or when a proposed change is merely different.

### Hypotheses tested

| # | Verdict | Evidence-based refinement |
|---:|---|---|
| 1 | Validated | Williams replaces several maxims with functional diagnostics, but accessible-book limits prevent claiming this for every unseen passage |
| 2 | Validated | Lanham is more procedural than “omit needless words”; guards are required |
| 3 | Validated | Gopen complements Williams; claims remain heuristics rather than universal science |
| 4 | Validated with access caveat | Tufte provides a broad syntax organization; the exact complete form inventory is not claimed without the chapter prose |
| 5 | Validated | Minto primarily operates on document/argument/analysis levels |
| 6 | Validated | Diátaxis operates on user need, page/section contract, and information architecture |
| 7 | Validated | Garner operates on words, constructions, conventions, register, and change status |
| 8 | Validated | Strunk/White is useful as context and control, not an independent diagnostic skill |
| 9 | Validated | Global-to-local minimizes invalidated edits; targeted feedback loops remain |
| 10 | Validated | Broad requests need one coordinated diagnosis; narrow requests need one owner |
| 11 | Validated | Nominalizations are forms; only some create reader problems |
| 12 | Validated | Passives are functional choices, not inherent faults |
| 13 | Validated | Variety serves rhetorical purpose and can be harmful as decoration |
| 14 | Validated | Necessary qualification is semantic content |
| 15 | Validated | Accessible-topic flow can outrank actor-first alignment when agency remains recoverable |
| 16 | Validated | Distinct fault classes, gates, and negative triggers keep the six new skills separate without uncontrolled collision |

## Part VIII: Existing sentence-clarity audit

The full line-item audit, change IDs, and semantic redline are in `defect-and-change-report.md` and `skills/sentence-clarity/references/baseline-semantic-diff.md`. The highest-consequence defects were:

- a description that claimed tightening, simplification, de-jargoning, any readability review, and all final polishing, thereby swallowing three adjacent skills;
- absolute claims about how readers parse and a preference for short concrete subjects;
- morphology presented as a “reliable” nominalization fault signal;
- a list of *be*, *have*, *do*, *make*, *occur*, and similar verbs presented without functional tests;
- old-before-new embedded as a local clarity step rather than owned by cohesion;
- no positive functional account of passive voice or agent evidence;
- a rigid “subject and verb alone” success test unsuitable for stative, existential, technical, and discourse-linked clauses;
- one inflexible output format, no activation/negative/collision fixtures, and an underspecified “leave clean sentences alone” safeguard;
- primary/secondary provenance blurred among Williams/Bizup, Turabian, and a teaching module.

The revised canonical skill narrows activation to actor/action and dependency faults, uses suffixes only as clues, tests the passive by function, protects terms of art and topic continuity, prohibits invented agents, returns proportionately, maps instructions to principle IDs, and includes regression/negative/adversarial fixtures. Old/new flow is a context check only to avoid damage; its positive repair belongs to `cohesion-emphasis`.

## Part IX: Six complete new skill packages

Each folder contains a concise canonical `SKILL.md`, official interface metadata in `agents/openai.yaml`, operational references, evidence maps, original examples, and YAML fixtures.

### `doc-typing`

Diagnoses reader task and knowledge state; types pages or sections; applies the four contracts; distinguishes accidental from intentional mixing; supports API/SDK quickstarts, authentication, endpoint reference, architecture, troubleshooting, recipes, migration, and runbooks. It does not classify from headings alone.

### `memo-structure`

Recovers the governing question/answer; tests vertical question/answer logic and horizontal grouping; chooses chronology, structure, or degree; applies SCQ/SCQA when useful; checks practical MECE; preserves uncertainty and counterevidence; rejects unsuitable tutorial/reference/narrative conversions.

### `concision`

Builds a proposition-preservation ledger; diagnoses empty framing, repeated meaning, redundant modification, inflated diction, and weak-verb/action-noun excess; applies a guarded paramedic method; reads aloud and repairs rhythm; keeps necessary scientific/legal/evidentiary hedges and technical nouns.

### `sentence-variety`

Diagnoses form-purpose mismatch rather than length statistics; uses a structured syntax catalogue to select constructions for definition, hierarchy, sequence, comparison, contrast, suspense, elaboration, or cadence; preserves deliberate repetition and clean prose; avoids ornamental imitation.

### `cohesion-emphasis`

Tracks topic strings and references; checks accessible-before-new ordering, backward linkage, stress, end weight, subject–verb continuity, clause hierarchy, paragraph issue/point, and logical gaps; preserves passives and nominalizations that support established topics; prefers structural repair over empty transitions.

### `usage-adjudicator`

Isolates the issue; separates grammar, usage, style, preference, register, geography, and field; reports Garner/LCI only when verified; runs a dated current-evidence protocol; explains disagreement; issues a context-conditioned recommendation or uncertainty rather than an unsupported binary verdict.

## Part X: Shared references

- `glossary.md` supplies one canonical vocabulary and preserves meaningful distinctions.
- `portfolio-routing.md` defines narrow, weak, broad, and dual-skill routing.
- `portfolio-pass-order.md` defines dependencies, invalidation, skips, and feedback.
- `conflict-ledger.md` resolves overlap at rule and test level.
- `source-manifest.md`, `claim-to-source-ledger.csv`, and the two source ledgers provide bibliographic and access traceability.
- `trigger-matrix.csv` states strong, weak, negative, dual, and explicit-override behavior for every skill.

The shared contract is infrastructure, not an eighth skill. The OpenAI package therefore places seven independently valid skill folders under `skills/` and declares a multi-skill plugin in `.codex-plugin/plugin.json`.

## Part XI: Test suite and results

The suite contains per-skill positive, negative, boundary, semantic-preservation, collision, regression, and adversarial fixtures plus portfolio-level routing and three staged end-to-end documents. It explicitly covers technical nominalizations, legitimate passives, necessary hedges, deliberate repetition, intentional mixed docs, register-dependent usage, citation/term/voice preservation, and Strunk/White negative controls.

`tests/end-to-end-fixtures.md` shows the initial diagnosis, selected order, ownership, intermediate text after each applied pass, final text, semantic audit, and rejected edits for:

1. a mixed API page with an unmarked conceptual detour, broken flow, buried action, padding, monotony, and a usage question;
2. an executive recommendation with missing governing answer, overlapping supports, buried emphasis, wordiness, and necessary uncertainty;
3. a scientific/analytical report with passive topic continuity, technical nominalizations, cautious inference, paragraph linkage, and a disputed formal usage.

`validation-results.md` records static and behavioral results. Behavioral tests are declarative fixtures plus deterministic schema/evidence/routing checks; they are not represented as a statistically independent language-model evaluation.

## Part XII: Strunk and White exclusion dossier

The controlling artifact is `negative-control/strunk-white-exclusion-dossier.md`. It maps every accessible Strunk rule and every visible White reminder to one of the required dispositions: superseded, already covered, vague, taste, register-specific, grammatically mistaken, internally contradicted, historical, compact reminder, or irrelevant. It documents Pullum's critique, edition limits, effective rule-breaking, and the no-smuggling rule. No `elements-of-style` skill exists.

## Part XIII: Defect and change report

`defect-and-change-report.md` is the controlling change ledger. It records change ID, artifact, original problem, source evidence, change, consequence, fixture coverage, and residual uncertainty for the baseline, every new skill, the shared architecture, source records, registry, negative control, and validation artifacts. The semantic diff distinguishes moved ownership from deleted advice and preserves useful baseline behavior.

## Part XIV: Completion statement

### Sources fully inspected

- Gopen and Swan, “The Science of Scientific Writing” (complete permission-reprinted article).
- The 18-page current English Diátaxis site as retrieved.
- Strunk's 1918 and 1920 public-domain texts.
- Pullum's complete author manuscript and publisher metadata.
- Current official OpenAI build/help documentation and the official local schema as retrieved.

### Sources partially inspected

- Williams and Bizup, *Style: The Basics of Clarity and Grace*, fifth edition.
- Lanham, *Revising Prose*, fifth edition.
- Gopen, *The Sense of Structure*.
- Tufte, *Artful Sentences*.
- Minto, 1996 expanded and 2026 third editions.
- Garner, *Garner's Modern English Usage*, fifth edition.
- Strunk and White, *The Elements of Style*, fourth edition.

Exact gaps—chapter prose, pages, or the A–Z corpus—are recorded row by row. No inaccessible section is marked read.

### Artifacts complete

All seven canonical skills, their metadata, references, evidence maps, examples, and fixtures; plugin package; routing/pass order/glossary/conflict ledger; access and coverage ledgers; 252-entry principle registry in CSV/JSON; claim ledger; trigger matrix; baseline audit/diff; negative-control dossier; portfolio/end-to-end fixtures; validation results; and versioned archive.

### Claims remaining uncertain

- Complete operational coverage of the six partially accessible copyrighted authorities and White fourth edition.
- Exact content-level differences between Minto's 1996 expanded edition and Pearson's 2026 third edition.
- A complete Tufte-authorized form taxonomy beyond visible chapter architecture.
- Garner's complete headword inventory, individual uninspected classifications, and any post-2022 change not directly checked.
- Exact-cutoff identity of an undated OpenAI build page retrieved six days later.

### Acceptance criteria

| Criterion | Result |
|---|---|
| All seven positive sources have access records | **Pass** |
| Negative control analyzed | **Pass** |
| Every accessible/visible chapter, section, framework page, or category accounted | **Pass** |
| Existing skill audited and revised | **Pass** |
| Six new canonical skills complete | **Pass** |
| Every skill has references, evidence map, examples, and fixtures | **Pass** |
| Trigger collisions and pass order resolved/tested | **Pass** |
| Machine-readable principle registry and explicit dispositions | **Pass** |
| No placeholder, future-work section, or eighth skill | **Pass** |
| Garner searchable architecture present | **Pass**, with a verified seed index rather than a fabricated complete headword list |
| Tufte catalogue represented comprehensively without reproducing book | **Pass**, with provenance/access labels |
| Full-text extraction of every requested copyrighted book | **Fail—source access criterion not met** |
| “Every operational principle from the complete source corpus” | **Not claimable** for the partial sources; **pass** for the fully inspected corpus |

The package is build-ready and internally auditable. Its one material acceptance failure is the one evidence cannot cure: complete lawful access to every copyrighted primary edition was not available. That failure is reported rather than converted into unsupported certainty.
