# Benchmark-validity erratum

## Status and corrected conclusion

This document supersedes the comparative interpretation in `stage1-provisional-report.md`. It does not alter the original plan, labels, model outputs, normalized outputs, or frozen report.

The original arithmetic remains reproducible under its registered exact-match contract: none of the twelve evaluated surfaces passed every frozen worst-run objective gate. The benchmark is not valid for ranking those surfaces or concluding that they are generally poor writing diagnosticians.

The strongest supported statement is:

> None of the twelve surfaces met every frozen exact-match gate under the shared wrapper and contaminated, provisional gold.

Stage 2 remains locked. A redesigned and preregistered run is required before comparative performance claims or rewriting evaluation.

## Why this correction came after the original investigation

The source investigation asked what mechanisms the nine repositories contain and what should be adopted, rejected, or tested. The initial Stage 1 implementation review then emphasized schema enforcement, evidence hashes, blinding, immutable output handling, and arithmetic reproducibility. Those checks were useful, but they did not adversarially test whether generator-visible values predicted the labels, whether the annotation boundary was defensible, or whether the wrapper preserved each source's native task.

The later audit changed the decision because it asked different failure-oriented questions and inspected the actual case distribution and output disagreements. This was a real process failure, not new source evidence. The case-ID leak and scorer decomposition should have been mandatory preflight tests before the sealed run.

## Blocking defects

### 1. Case identifiers reveal the hidden decision

The corpus splitter groups cases by source and decision, then selects cases lexicographically. The public job retains `case_id`. Across all 90 cases, suffixes `001` through `005` are CHANGE and suffixes `006` through `010` are KEEP. The same rule predicts all 72 sealed decisions.

The leak checker in `pilot/src/wqeval/jobs.py` rejects forbidden key names but does not test value-derived proxies. Every system received all 72 sealed cases in one request, so the pattern was available inside a single context.

This invalidates case-level discrimination, clean-case false-positive claims, and any metric that can benefit from knowing which cases contain at least one issue. It does not prove that a model noticed or exploited the pattern. It also does not explain low exact scores, because the leaked signal is favorable.

### 2. Exact scoring combines distinct questions

A true positive requires the exact case ID, start offset, end offset, and normalized issue code. Independent recounting across the 33 valid runs produced:

| Matching rule | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Exact span and code | 307 | 913 | 914 | 0.252 | 0.251 |
| Overlapping span, same code | 604 | 616 | 617 | 0.495 | 0.495 |
| Overlapping span, any code | 1,041 | 179 | 180 | 0.853 | 0.853 |

The any-code result is not a valid performance estimate because the case IDs leaked the decision. The decomposition is still useful for locating disagreement. It shows that a large share of exact failure came from span and taxonomy alignment rather than absence of any diagnosis near the annotated issue.

All 297 additional same-code overlap matches were containment differences. In 199 cases the prediction enclosed the gold span; in 98 it was narrower. The shared envelope did not define punctuation, clause versus sentence scope, or whether adjacent defects should be split or bundled.

### 3. The critical-miss gate mostly measured exact alignment

Across valid runs there were 132 critical finding opportunities. A CHANGE finding overlapped the critical region in 128 opportunities. Only four had no overlapping diagnosis. Exact span and code agreement occurred in 70 opportunities.

The frozen gate allowed no critical exact miss because four critical gold items and a 0.05 maximum make one miss equal 0.25. This is mathematically consistent but not a robust measure of whether a critical problem was noticed.

### 4. The provisional gold is unadjudicated and contains disputed labels

The frozen files identify the labels as provisional. Examples that require human adjudication include:

- `S009-003`, labeled `actor_ambiguity` even though the sentence uses an explicit first-person actor and the apparent problem is conflicting role evidence.
- `WQ-S002-005`, labeled `generic_filler` although every valid run selected the public `generic_importance` family for an unsupported significance claim.
- `S008-004`, labeled `temporal_scope_missing` although the compared periods are stated.
- `WQ-S003-002`, labeled `formatting_artifact` where most runs diagnosed causal overclaim.
- `WQ-S002-002`, labeled as an actor-obscuring passive although the sentence names the compliance team.

These examples do not prove the predictions are correct. They prove that one exact label cannot be treated as settled ground truth without independent adjudication and an equivalence policy.

### 5. Protected regions were hidden while an empty public field remained

All public cases expose `protected_regions: []`. Private provisional gold contains 97 protected regions across 41 of the 72 sealed cases. Generators therefore received an affirmative-looking empty field while the scorer retained hidden KEEP regions.

Across valid outputs, 110 CHANGE findings overlapped both a gold CHANGE region and a separate KEEP region. Natural sentence-level findings could therefore incur an exact false positive, exact false negative, and KEEP penalty at once.

### 6. The shared taxonomy changed the task

Generators selected a public normalized issue code directly. Gold alone was converted through a private mapping. The public vocabulary includes overlapping families and codes that the private map never emits. It also exposed all shared family definitions as another diagnostic checklist.

This creates two problems:

1. plausible alternate labels are scored as a false positive plus false negative;
2. a source can appear to use mechanisms that were supplied by the wrapper rather than by its authored instructions.

The one-label contract had no alias, hierarchy, secondary label, or abstention mechanism.

### 7. Most external surfaces were adaptations

Only `no-ai-slop` and `avoid-ai-writing` were classified as native F1 diagnostic modes. Eight of ten external surfaces were F2 projections from rewriting, generation, or reference material. The current portfolio was also evaluated through an F2 projection. This is not a clean “as authored” comparison.

The adapter burden is part of what the pilot measured. A rewrite-only source should be marked not applicable for a native diagnostic ranking unless a separately defined projection is the intended object of study.

### 8. Five malformed records invalidated three full runs

One bad offset, one span mismatch, and three missing operations caused three 72-case runs to be marked invalid. Five malformed records out of 2,592 discarded 216 otherwise present records. The remaining valid runs for those systems still failed the exact thresholds, so this did not cause the universal failure. It did make worst-run summaries less informative about diagnostic content and serialization reliability.

### 9. Reproducibility metadata is incomplete

The pilot preserves component hashes, jobs, raw outputs, and output evidence, but not the exact rendered prompt bytes. The exact model identity and most generation settings were not available. A reviewer can run the unit tests and independently recompute reported counts from the preserved gold and normalized outputs. A fresh clone cannot run the fully verified evidence replay because frozen jobs require their original absolute artifact paths, including paths to intentionally omitted source clones. The original model calls cannot be reproduced as issued.

### 10. Two metric labels are misleading

The field called `exact_span_accuracy` is a finding-set Jaccard score, not the ordinary fraction of spans with exact boundaries. Macro F1 excludes zero cases, which can inflate it relative to a macro average over the complete case panel. These labels should be corrected or accompanied by explicit formulas in the next protocol.

## What remains supported

- The corpus, jobs, raw outputs, normalization artifacts, and original report are hash-bound and auditable.
- The exact scorer produced the recorded counts under its implementation.
- Three runs contained schema-invalid records.
- No surface met the frozen exact gates.
- Human review was not performed.
- Stage 2 was correctly withheld under the registered protocol.

## What is withdrawn or qualified

- Do not rank the twelve surfaces from this pilot.
- Do not say that all twelve are poor at detecting writing problems.
- Do not use case-level or clean-control performance as unbiased evidence.
- Do not treat overlap recounts as replacement performance scores.
- Do not interpret repeated rules across related repositories as independent confirmation.
- Do not expand the portfolio with a blanket anti-slop checklist based on this run.

## Required repair before a new sealed run

1. Move this entire pilot to development-only regression evidence.
2. Use opaque randomized request IDs and run a metadata-only leakage baseline.
3. Send one case per fresh request, or preregister another independence-preserving batch design.
4. Have independent humans create and adjudicate gold in native terms.
5. Support multiple defensible span anchors and label equivalence where justified.
6. Separate localization, boundary, taxonomy, explanation, operation, and serialization scores.
7. Preserve exact prompt and response bytes plus explicit model settings.
8. Score malformed items locally and report run reliability separately.
9. Separate native diagnostic surfaces from declared derived projections.
10. Freeze a new holdout only after the harness, adapters, thresholds, and reviewer protocol are final.
