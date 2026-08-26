# Writing-quality comparative evaluation

Status: **Stage 1 provisionally complete; Stage 2 not run**

## Outcome

None of the 12 evaluated diagnostic surfaces passed every frozen Stage 1 objective gate. Stage 2 therefore remains locked, exactly as the protocol required.

This is not evidence that the external sources are useless, or that the current portfolio is better. It is evidence that no tested surface was precise, complete, and stable enough under this strict exact-span benchmark to justify automated rewriting. The normalized union also failed to improve on the current portfolio.

The result remains `PILOT_UNADJUDICATED`. Human agreement, factual-meaning risk, reviewer preference, clarity, and voice retention have not been measured by real reviewers and are not claimed here.

## Execution plan and status

| Stage | Planned control | Status |
|---|---|---|
| 0. Preregister | Freeze sources, systems, output schema, metrics, thresholds, split, seed, and stop rules | Complete |
| 1. Build evaluator | Write failing tests first, implement strict validation, immutable raw storage, matching, scoring, blinding, and evidence binding | Complete |
| 2. Freeze corpus | Build 90 cases, separate generator input from provisional gold, and hash the development and sealed splits | Complete |
| 3. Validate adapters | Test every surface on development cases; retire contaminated or underspecified batches | Complete; development v1 and v2 retired, v3 passed schema-readiness checks |
| 4. Run sealed diagnostics | Execute three first-response runs for every surface under the same registered model settings and preserve failures without repair | Complete; 36 jobs |
| 5. Score objective gates | Reconstruct all scores from hash-bound cases, gold, jobs, raw outputs, and predictions; use the least favorable run | Complete; 0 of 12 passed |
| 6. Human diagnostic review | Blind every finding and the provisional gold for two real reviewers plus one separate adjudicator | Not started; no real roster was supplied or frozen |
| 7. Stage 2 rewriting | Run controlled and end-to-end rewrites only for surfaces that pass Stage 1 | Locked and not run |
| 8. Audit and deliver | Reconcile evidence, test on two Python versions, measure coverage, and obtain independent code and security reviews | Complete for the Stage 1 path |

## What was tested

The corpus contains 90 independently adapted cases: 18 development cases and 72 sealed cases. It includes 51 structured files and 47 factual traps.

Coverage includes:

- Genuine diagnostic targets derived from all nine supplied source artifacts.
- Clean KEEP controls for legitimate passives, em dashes, triads, technical terms, deliberate repetition, fragments, and author quirks.
- Factual traps involving numbers, attribution, modality, negation, dates, actors, conditions, and causal status.
- Technical, executive, personal, marketing, reference, and second-language writing.
- Structured Markdown containing code fences, inline code, tables, links, quotations, URLs, paths, blockquotes, and YAML frontmatter.

Each finding was required to provide an exact Unicode span, CHANGE or KEEP, named problem, contextual explanation, severity, and suggested operation. Native problem names were retained while also mapping into one frozen normalized taxonomy.

## Compared surfaces

The three requested tracks became 12 execution surfaces:

1. The current seven-skill portfolio as one ordered diagnostic system.
2. Ten authored external surfaces from the nine supplied source artifacts. Slopkit contributed separate Slopbeth and Slopgent surfaces; Kami contributed separate anti-patterns and writing surfaces.
3. One normalized union of the external mechanisms using the shared detect-only output contract.

Adapted detect-only surfaces retained their authored diagnostic mechanisms. They did not receive safeguards from the union unless those safeguards already appeared in the source. Third-party repository code was not executed.

## Frozen objective gates

A surface needed all of the following before Stage 2:

- Three of three schema-valid sealed runs.
- Exact-match precision of at least 0.80.
- Exact-match recall of at least 0.60.
- KEEP accuracy of at least 0.90.
- Critical miss rate no greater than 0.05.
- No sized genre or author-profile slice below 0.65 precision.
- Zero critical meaning-risk operations after real-human review.
- Complete review by two real people and adjudication by a third person.
- No evidence-integrity, gold-leakage, or identity-leakage failure.

Objective gates use the least favorable of three runs, not an average. Strict primary matching requires the same case, CHANGE decision, exact span, and normalized issue family. Overlap-based matching is retained only as a sensitivity analysis.

## Provisional objective results

The table below lists fully schema-valid surfaces in descending worst-run exact precision. `Important missed` is the largest count seen in one valid run. `Span accuracy` and `clean-case FPR` are the least favorable valid-run values.

| Surface | Valid runs | Exact precision | Exact recall | KEEP accuracy | Critical miss | Important missed | Exact-span accuracy | Clean-case FPR | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| stop-slop | 3/3 | 0.294 | 0.270 | 0.920 | 0.500 | 12 | 0.164 | 0.028 | FAIL |
| Slopkit Slopbeth | 3/3 | 0.243 | 0.243 | 0.920 | 0.500 | 13 | 0.138 | 0.028 | FAIL |
| Slopkit Slopgent | 3/3 | 0.231 | 0.243 | 0.955 | 0.500 | 11 | 0.134 | 0.028 | FAIL |
| soundshuman | 3/3 | 0.222 | 0.216 | 0.920 | 0.500 | 13 | 0.123 | 0.028 | FAIL |
| anti-ai-slop-writing | 3/3 | 0.222 | 0.216 | 0.898 | 0.500 | 12 | 0.123 | 0.056 | FAIL |
| Current seven-skill portfolio | 3/3 | 0.216 | 0.216 | 0.932 | 0.500 | 12 | 0.121 | 0.028 | FAIL |
| humanizer | 3/3 | 0.176 | 0.162 | 0.909 | 0.500 | 14 | 0.092 | 0.000 | FAIL |
| Normalized union | 3/3 | 0.176 | 0.162 | 0.909 | 0.500 | 13 | 0.092 | 0.028 | FAIL |
| Kami anti-patterns | 3/3 | 0.071 | 0.054 | 0.909 | 0.750 | 15 | 0.032 | 0.028 | FAIL |

Three authored surfaces had one invalid first response and therefore failed the 100 percent schema-compliance gate. Their preregistered gate bundle conservatively records zero objective performance, so it should not be interpreted as a direct quality estimate:

| Surface | Valid first responses | Invalid response | Reason |
|---|---:|---:|---|
| no-ai-slop | 2/3 | Run 1 | Required suggested-operation instruction was absent |
| avoid-ai-writing | 2/3 | Run 2 | Finding offsets failed validation |
| Kami writing | 2/3 | Run 3 | Reported span did not match the source text |

No invalid response was repaired, regenerated, or replaced.

## Interpretation

The current portfolio did not establish diagnostic readiness. Its least favorable run had 0.216 exact precision and recall, 0.932 KEEP accuracy, and a 0.500 critical miss rate. It passed the aggregate KEEP threshold but failed the precision, recall, critical-miss, and slice requirements.

stop-slop produced the highest registered exact precision and recall among fully valid surfaces, but both values remained far below the frozen minimums. Its result does not establish general superiority, especially before human review of the benchmark and explanations.

The normalized union did not produce the expected gain. Its worst-run precision was 0.176 versus 0.216 for the current portfolio, with the same 0.162 recall as humanizer. Combining more heuristics appears to have added breadth without enough contextual discrimination.

High KEEP accuracy did not compensate for weak issue detection. Several surfaces avoided many false edits but still missed half of the four critical opportunities in their least favorable run. Kami anti-patterns missed three of four.

Strict exact matching is intentionally demanding. A system received no primary credit when it identified a nearby symptom, selected the wrong issue family, or returned an inexact span. The machine-readable report preserves overlap sensitivity and per-genre and per-author details so this strictness can be audited rather than hidden.

## Why Stage 2 was not run

The protocol says rewriting begins only after diagnostic precision is acceptable. Running rewrites now would test systems that frequently select the wrong text, misname the problem, or miss important issues. That would blur diagnosis quality with rewrite quality and expose factual meaning and voice to edits that the diagnostic gate did not justify.

Accordingly, no before-and-after rewrite examples, reader-preference claims, voice-retention scores, or factual-preservation scores were generated in this run.

## Human review boundary

The evaluator can prepare four isolated role packages after a roster is frozen: diagnostic reviewers, diagnostic adjudicator, provisional-gold reviewers, and provisional-gold adjudicator. The packet identity binds the run, exact cases, predictions, item digests, roster, and scoring amendment. Cross-packet replay, altered text, incomplete panels, and system self-review are rejected.

No real reviewer roster was created. Human review could still identify benchmark mistakes, estimate agreement, and audit whether explanations or operations change meaning. It cannot make any of these 12 surfaces Stage 2 eligible because each already failed at least one objective gate.

The legitimate path to Stage 2 is a new preregistered diagnostic iteration: use these misses and false findings to revise mechanisms, freeze a new test panel, and rerun Stage 1 without changing thresholds after seeing results.

## Verification

- Output evidence reconciled to 36 jobs: 33 valid, three invalid, and no retries.
- Schema compliance across jobs: 91.67 percent.
- Python 3.11: 198 tests passed, with two Windows privilege-dependent skips.
- Python 3.14: 198 tests passed, with the same two skips.
- Standard-library trace coverage: 84.01 percent, or 5,784 of 6,885 executable production lines.
- Independent final code review: approved with zero findings for Stage 1.
- Independent final security review: passed with zero findings for Stage 1.
- Targeted security suite: 69 tests passed.
- Immutable provisional artifact: exactly the report and its tree manifest.

The two skipped cases require Windows symbolic-link privileges. Equivalent junction, reparse-point, hard-link, and path-boundary tests passed.

## Evidence anchors

| Evidence | SHA-256 |
|---|---|
| Sealed cases | `e0b2071dae4e383efdeb8ce8e26e657a5978d98ffc324fe196332a98a2e7916f` |
| Corpus freeze | `a583433921a732140b53de300506775fef29a729024909c910d0fe3dde9a2197` |
| Jobs manifest | `9d0423ea80217581bd516be9e5dcf7367bddefea99828ab8f5b88d13983b245a` |
| Execution order | `525f1f8dccc6e7f4ad9610d8cdc5e452b355d5119db900ce618c4eb45be52a94` |
| Model settings | `bec7d1e51a868786a6c9b440a15a5367b396ba0d49c9229911ae255fd3a1cb67` |
| Provisional gold | `f31a5b7aaa2e98df98f0dcd0afe0c7729962e2fc1b60face6883c59d184b2253` |
| Raw-output anchor | `154d6ff70fe367c09250e21d188aa1a6ddb92c944e66124f701ee81fb0122739` |
| Scoring amendment | `2091c6bf01a0570bbb6fe6c497242d95cbffa67140e936f2b8d2b4d2220974ff` |
| Provisional report | `2959e43b1c2a4f6fd640b549fdd1ec15def5c8dd78548dd554f00e93b02eb49e` |
| Artifact tree manifest | `4989a41cb2f2ea7a315f0503c71216dea4fbf16963af8f13883be7e3df004097` |

## Limitations

- The reference annotations are provisional until independent real-human review.
- Exact-match scoring may under-credit partially correct or differently framed diagnoses; overlap results remain secondary by preregistration.
- Some authored sources are related, so repeated mechanisms are not independent confirmation.
- Detect-only projections of rewrite-oriented sources are not equivalent to native authored software behavior.
- Synthetic voice controls can test preservation mechanics but cannot establish retention of a real person's voice.
- The current Stage 2 helper is not trusted for publication until rewrite bytes, assignments, and human ratings receive the same complete evidence binding as Stage 1.

The published writing-quality portfolio was not modified or pushed during this evaluation. Its recorded baseline remains `74a282108da2a620542556fa001ebcdde0c9be85`.
