---
name: usage-adjudicator
description: Adjudicate a specific disputed word, construction, spelling, punctuation, pronunciation, or convention by separating grammar from style and checking Garner’s classification, Language-Change Index, register, dialect, geography, field, audience, dictionaries, and current corpus evidence. Use for “which is correct?” or formal-acceptance questions. Do not use for general rewriting or unsupported right/wrong verdicts.
---

# Usage Adjudicator

Return a contextual status and practical recommendation, not an edict. Garner is a primary usage authority, not a substitute for current corpus, dictionary, dialect, or field evidence. [GAR-META-01–09]

## Frame the exact issue

1. Quote the smallest disputed form and its syntactic context.
2. Classify the question: grammaticality, word sense, collocation/idiom, confusable, spelling, punctuation, pronunciation, redundancy, register, dialect/region, jargon, bias/dating, or house style.
3. Record audience, medium, formality, variety of English, field, publication date, and risk tolerance. Ask only for missing context that changes the recommendation.
4. Separate attested variation from a demonstrable grammatical error and from a preference about style.

## Consult evidence in order

1. Check the searchable reference layer for the exact Garner issue and edition/page.
2. If Garner assigns a Language-Change Index stage, report the stage as his measure of acceptance—not as frequency, grammaticality, or timeless truth:
   - Stage 1: rejected
   - Stage 2: widely shunned / spread but nonstandard
   - Stage 3: widespread but avoided in careful usage
   - Stage 4: ubiquitous but still opposed by some careful users
   - Stage 5: fully accepted
3. Check at least one current authoritative dictionary with usage labels/notes.
4. For time-sensitive or contested issues, query a register-appropriate corpus. Compare normalized frequencies, contexts, dates, and regions; do not treat raw web hits or an Ngram line as acceptance.
5. Check specialist or house guidance when the field controls.
6. Record disagreement and evidence date. [GAR-LCI-01–07; GAR-EV-01–08]

## Decide and label

Choose one or more labels: `standard`, `nonstandard`, `accepted but contested`, `informal`, `formal`, `archaic`, `regional`, `emerging`, `skunked`, `context dependent`, or `unresolved`.

Then report:

1. **Status in the stated context**
2. **Garner:** classification/stage if verified, with edition/page
3. **Current evidence:** dictionary/corpus/field findings and retrieval date
4. **Recommendation:** use, avoid, recast, or follow house style—with the reason
5. **Confidence/disagreement:** what could change the verdict

Never infer a Garner stage. “Common” does not entail “formal standard”; dictionary inclusion does not confer approval; absence does not prove nonexistence. Avoidance can be pragmatic when a term is skunked even if one sense is defensible. [GAR-DEC-01–08]

## Preserve varieties and people

Do not stigmatize dialect speakers or label a regional form illogical. Distinguish edited-standard conventions from language competence. Flag dated or biased terminology with attention to referent, community preference, legal/technical constraints, and quotation fidelity.

## Current-evidence protocol

Use COCA for genre-balanced contemporary American evidence, NOW for recent news change, GloWbE for cross-regional web English, Google Books Ngram for diachronic print trends, and dictionaries for labels and sense history. State each corpus’s coverage and limitations. Inspect concordance context; do not compare unnormalized counts across corpora. [GAR-EV-02–08]

## Stop conditions

Stop when the exact construction and context are fixed, the recommendation follows from cited evidence, disagreement is disclosed, and no authority is presented as universally controlling.

## Return proportionate output

- **Targeted review:** the five-part adjudication above.
- **Direct revision:** chosen form in context plus one-sentence rationale.
- **Fault explanation:** grammar/style/register distinction and evidence.
- **Whole-document audit:** only repeated or high-risk usage issues; do not line-edit everything.
- **Broad polish:** run after wording stabilizes and only on genuine usage questions.

Consult `references/principles.md`, `references/language-change-index.md`, `references/usage-taxonomy.md`, `references/current-evidence-protocol.md`, `references/issue-index.csv`, `references/examples.md`, `references/evidence-map.md`, and `tests/fixtures.yaml`.
