# Validation results

**Package:** writing-quality-portfolio 1.0.0  
**Validated:** 2026-08-25  
**Research cutoff:** 2026-08-19 23:59 America/Chicago

## Result summary

| Validation area | Result | Evidence |
|---|---|---|
| Official per-skill static validation | **Pass: 7/7** | OpenAI skill validator accepted every canonical `skills/*` directory |
| Plugin manifest | **Pass** | name/version/skills path validated |
| Root artifact inventory | **Pass: 21/21 required** | Research report, ledgers, routing, audit, dossier, tests, results, hash manifest, and plugin files present |
| Source access records | **Pass: 15 rows** | Every positive, companion/related, negative-control, criticism, and platform source has access/date/confidence fields |
| Source coverage | **Pass: 321 rows** | Every visible chapter, section, framework page, A–Z bucket, edition structure, criticism section, and platform requirement accounted |
| Principle registry | **Pass: 252 unique IDs** | All required fields present; writing levels valid; dispositions/confidence nonblank; CSV and JSON aligned |
| Skill-local references | **Pass** | Every backtick-linked `references/`, `tests/`, or `agents/` path in a core exists |
| Per-skill fixtures | **Pass: 84 schema/expectation checks** | Unique IDs; ≥10 fixtures per skill; positive, negative, boundary/preservation coverage; expected behavior present |
| Portfolio fixtures | **Pass: 44 schema/expectation checks** | Unique IDs; routing, cross-skill, negative-control, register-usage, and end-to-end categories present |
| End-to-end cases | **Pass: 3 staged specifications** | API docs, executive memo, and scientific/analytical report show diagnosis, pass order, intermediate edits, final, semantic audit, rejected changes |
| Trigger matrix | **Pass: 8 rows** | Seven skill owners plus coordinated portfolio pass; strong/weak/negative/sequence/explicit rules present |
| Report structure | **Pass: Parts I–XIV** | All required report parts and completion disclosures present |
| Unfinished markers | **Pass** | No `TODO`, `TBD`, or “to be completed” marker in any skill core/reference |
| Full copyrighted-book extraction | **Fail by access** | Six core copyrighted books and White fourth were partial; no test converts that gap into “read” status |

## Static checks executed

```text
python scripts/validate_portfolio.py .
VALIDATION PASSED
- root_artifacts=21
- plugin_manifest=valid
- principles=252
- principle_csv_json=aligned
- coverage_rows=321
- access_rows=15
- skills=7
- skill_fixtures=84
- portfolio_fixtures=44
- trigger_rows=8
- report_parts=14
```

The official OpenAI quick validator then returned `Skill is valid!` for `cohesion-emphasis`, `concision`, `doc-typing`, `memo-structure`, `sentence-clarity`, `sentence-variety`, and `usage-adjudicator`.

## Behavioral coverage by skill

| Skill | Positive activation | Negative activation | Required boundaries/collisions |
|---|---|---|---|
| sentence-clarity | buried action; “who is doing what?” | shortening; flow; clean email | technical nominalization, legitimate passive, unknown agent, hedge, citation, old/new ownership, obstructive opener |
| doc-typing | tutorial/how-to/reference/explanation; harmful mix | memo request; clean typed page | heading trap, advanced tutorial, intentional mix, API/runbook, code preservation |
| memo-structure | recommendation, hierarchy, bottom-up synthesis | tutorial, chronology, clean memo | false MECE, uncertainty, contrary evidence, compact email, paragraph-flow handoff |
| concision | wordy/bureaucratic prose | actor/action-only; clean imperative | legal/scientific hedges, passive, technical nouns, courtesy, safety repetition, lard-factor non-target, rhythm repair |
| sentence-variety | repeated SVO, choppiness, sprawl | length-only; clean procedure | deliberate repetition, technical terms, passive, fragment, false parallelism, concision-first sequence |
| cohesion-emphasis | broken flow, buried point | isolated clarity; clean progression | passive/nominalization topic continuity, logical gap, pronoun ambiguity, chronology, hedge, empty-transition rejection |
| usage-adjudicator | exact formal/grammar/register dispute | general rewrite | dialect ethics, unverified LCI, raw-hit fallacy, singular *they*, who/whom, unresolved evidence, proportional audit, time-sensitive change |

## Cross-skill and negative-control outcomes

The declarative fixtures resolve each requested collision with one owner and sequence. In particular:

- cohesion retains a passive when it maintains an established topic;
- clarity never invents an unknown agent;
- concision preserves `may`, ranges, conditions, citations, and field terms;
- variety retains deliberate procedural/contrastive repetition;
- doc typing prevents Minto structure from distorting a tutorial or reference page;
- memo structure discloses overlapping categories rather than forcing false MECE;
- usage reports an unverified Garner entry as unverified and separates 2022 judgment from current evidence;
- no Strunk/White maxim overrides the stronger diagnostic owner.

## Semantic-preservation results

Each end-to-end fixture inventories propositions before editing and audits the final result. Across the three cases, the expected final texts preserve endpoints and code, quantities/ranges, chronology, technical names, measured effects, uncertainty, compliance gates, citations, responsible/passive agency, and deliberate repetition. Rejected edits are recorded whenever deletion, active conversion, decorative variation, answer-first structure, or a binary usage verdict would change meaning or genre.

## Interpretation limit

These results establish package integrity, traceability, deterministic fixture completeness, and expected behavior. They are not represented as a blinded empirical evaluation of every possible model invocation. More importantly, no behavioral result can cure missing full-text access. The precise corpus-access failure remains an explicit acceptance failure in `RESEARCH_REPORT.md` Part XIV.
