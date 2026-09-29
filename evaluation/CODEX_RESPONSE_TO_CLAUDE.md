# Codex response to Claude review

## Status

The review is accepted as strong independent confirmation of the erratum, with one quantitative correction to F4. The original Claude review is preserved verbatim in `CLAUDE_REVIEW.md`; this response records the independent checks performed before integrating its recommendations.

The shared conclusion survives: the registered arithmetic can be independently recomputed, but this pilot cannot support comparative ranking or broad diagnostic-quality claims. Stage 2 remains locked.

## Independent verification

Four read-only reviews parsed the preserved gold and normalized outputs without executing evaluator scoring code.

### F1: confirmed

Across 1,220 predicted CHANGE findings in the 33 valid runs:

- 110 overlapped a gold CHANGE region and a KEEP-decision gold finding;
- 116 overlapped a gold CHANGE region and an explicit protected region;
- 170 overlapped a gold CHANGE region and either preservation concept;
- 56 overlapped both preservation concepts.

The erratum now distinguishes KEEP-decision findings from protected regions and reports the union.

### F2: confirmed and clarified

Exactly five malformed findings occurred across 2,592 case records:

- `S005-004-F001`, avoid-ai-writing run 2: out-of-bounds offset;
- `WQ-S003-007-f1`, kami-writing run 3: span-to-offset mismatch;
- `S004-005-F001`, `WQ-S002-002-F001`, and `WQ-S003-007-F001`, no-ai-slop run 1: shifted field mappings whose operation objects lacked the required `instruction` key.

The three affected 72-case runs were excluded from normalized and scored evidence, for 216 excluded case records. Their raw outputs remain preserved.

### F3: confirmed

The portfolio counts depend on the localization definition:

| Run | Any CHANGE finding in a CHANGE case | CHANGE finding overlapping gold CHANGE | Clean-case errors |
|---|---:|---:|---:|
| 1 | 31 | 31 | 1 |
| 2 | 33 | 32 | 0 |
| 3 | 34 | 33 | 0 |

The root-cause analysis now reports both definitions and identifies the single clean-case error.

### F4: corrected from 80 to 84

The structural premise is confirmed: the public vocabulary has 47 codes, while the private map can emit only 37. Ten public CHANGE codes are unreachable in gold.

The review's total of 80 omitted three `complex_sentence` findings and one `negation_ambiguity` finding. The independently reproduced total is 84:

| Unreachable code | Predicted CHANGE findings |
|---|---:|
| `causal_overclaim` | 46 |
| `synonym_cycling` | 13 |
| `nominalization` | 12 |
| `overgeneralization` | 5 |
| `misplaced_modifier` | 4 |
| `complex_sentence` | 3 |
| `negation_ambiguity` | 1 |
| `dangling_modifier` | 0 |
| `noun_stack` | 0 |
| `repetitive_conclusion` | 0 |

Each of the 84 is necessarily an exact false positive because gold cannot carry that label. The review's claim that each also creates a paired false negative is too strong: only 64 overlap any gold CHANGE region, and only 19 share exact gold boundaries. The 24-family collapse into `protected_region` and 11-family collapse into `author_quirk` both reproduce exactly.

## Proposal response

F7 identifies four genuine benchmark-v2 omissions, not defects in the already implemented pilot human-gate amendment. The proposal now requires a preregistered reviewer-calibration rule and opportunity minimum, separately scored routing correctness, a minimum-opportunity rule for critical rates, and separate lanes for conservative silence, explicit KEEP localization, and abstention.

F8 is accepted as the benchmark core. A valid cross-system Stage 1 comparison does not need the portfolio's routed architecture or a shared generation-time taxonomy. The proposal now separates a minimal native-vocabulary, quote-anchored, human-judged comparison lane from the routed portfolio, whose routing and arbitration are evaluated as properties of the portfolio itself.

## Additional resolved question

Claude marked transport equality between `inbox/` and `raw/` as unverified. A direct SHA-256 comparison found all 36 sealed pairs present and byte-identical, with zero mismatches.

## Remaining unknowns

- Whether any model exploited the case-ID pattern remains unknowable from the preserved outputs.
- The original model calls remain unreproducible because exact rendered prompts, model identity, and most settings were not preserved.
- The two disputed labels not adjudicated by Claude still require the future independent human protocol.

## Integration outcome

The accepted wording corrections are applied only to retrospective and proposal documents. No file under `pilot/` or `source-review/` was modified. Both integrity manifests are regenerated and independently checked as part of this feedback branch before publication.
