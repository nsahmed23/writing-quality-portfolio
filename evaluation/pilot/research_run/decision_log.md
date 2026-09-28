# Decision log

## D-001: Isolated project

Keep the published portfolio frozen and create a separate evaluation project. Reason: avoid contaminating the baseline or interpreting fixture presence as performance.

## D-002: Confirmatory corpus size

Use 90 Stage 1 cases, balanced five CHANGE and five KEEP per source artifact, with 18 development and 72 sealed cases. Reason: the requested genre, author, factual, and structured slices need more support than a 36-case pilot.

## D-003: Offline evaluator

The evaluator does not call a model. It prepares jobs and scores only immutable returned artifacts. Reason: preserve raw evidence, prevent accidental self-grading, and comply with the exact HTTP header constraint by making no network request.

## D-004: Human boundary

Agents and model judges are not human reviewers. Human-dependent results remain pending. Reason: avoid fabricating agreement or reader preference.

## D-005: No single composite score

Report diagnostic, preservation, voice, protected-region, clarity, and preference measures separately. Reason: a composite can hide critical factual harm.

## D-006: Repair slice-gate config before sealed generation

Replace the development config's `sized_slice_min_n: 8` with `sized_slice_positive_opportunities_min: 5`. The approved plan gates a genre or author slice only when it contains at least five positive opportunities, not eight cases. This discrepancy was found during development after two development outputs and before any sealed output. No result was reclassified, and the sealed protocol now matches the approved plan.

## D-007: Retire contaminated development batch

Retire `runs/stage1-dev-v1` from all performance conclusions. Its generator cases exposed `features`, `primary_source_id`, and `source_refs`, including labels such as clean control and genuine defect. Preserve its three completed raw artifacts as failed-development evidence, but never merge them into scores. Rebuild public case projections and jobs as `stage1-dev-v2` before sealed generation.

## D-008: Remove invalid conventional false-positive rate

Remove `false_positive_rate = FP / (FP + explicit KEEP matches)`. Explicit KEEP findings are optional, so that denominator is not an enumerable negative universe and changes with reporting style. Retain false discovery proportion, clean-control case false-positive rate, KEEP-opportunity accuracy, and explicit KEEP recognition as separately named measures.

## D-009: Keep the provisional-gold map evaluator-private

Do not include `taxonomy/native-map.json` in generator jobs. Despite its filename, it maps provisional gold issue families to normalized codes and would expose the answer vocabulary for individual annotations. Generators receive only `taxonomy/problem-families.json`, the public normalized vocabulary. Ingestion enforces membership in that vocabulary or `UNMAPPED`; gold mapping remains private to corpus construction and scoring.

## D-010: Retire development v2 after a hidden KEEP invariant surfaced

Retire `runs/stage1-dev-v2` from performance conclusions. The frozen common envelope required a structured suggested operation but did not specify the validator's literal `operation_code: "preserve"` and null replacement for KEEP findings. Two generators therefore produced semantically non-editing KEEP operations that strict ingestion rejected. Preserve all three completed raw artifacts and the one valid normalized artifact as protocol-debug evidence. Do not repair, rescore, or compare them. Stop the remaining v2 jobs and add the literal invariant to the common envelope before creating development v3.

## D-011: Treat all pre-v3 outputs as contract tests only

Development v1 leaked answer-like corpus cues. Development v2 contained a hidden serialization rule, and two interrupted jobs also received that rule outside the frozen packet. Neither batch can support writing-system claims. Development v3 is the first batch eligible to validate adapter behavior, and only a later three-run sealed batch can support provisional comparative results.

## D-012: Exclude an accidental private-path review read

During the consolidated read-only code review, one broad text search mistakenly included the private directory and returned truncated matched lines. The reviewer stopped immediately and did not parse, score, hash, or cite the content. Exclude every observation from that accidental output from review evidence. Continue the review only against public code, tests, configuration, and metadata, and retain this incident in the audit ledger.

## D-013: Apply Stage 1 thresholds to the worst sealed run

For each system, require all three schema-valid runs. Apply precision, recall, KEEP accuracy, critical-miss, and sized-slice thresholds to the least favorable observed run, not the mean and not pooled predictions. Report means, ranges, pass-at-1, any-run detection, and all-run detection descriptively. Reason: a mechanism should not qualify for rewriting when one of three identical-setting runs falls below the diagnostic safety gate, and averaging could conceal an unstable false-positive or miss pattern. This rule was frozen before any sealed output was scored.

## D-014: Bind scoring and gating to detached corpus and output evidence

Do not accept caller-selected gold, cases, predictions, or metric dictionaries in the production scoring gate. Verify the frozen corpus manifest from its detached SHA-256, verify the sealed output anchor from its detached SHA-256, reconstruct every run, compute the gate bundle from those exact bytes, and bind human packets to the same complete case, gold, and prediction payloads. Reason: otherwise favorable metrics can be fabricated by substituting gold, dropping predictions or slices, or mixing unrelated review artifacts.

## D-015: Separate diagnostic review from provisional-gold review

Give diagnostic reviewers every preserved CHANGE finding with the exact source case, but remove system identity, native system labels, finding identity, and gold. Give the gold reviewers a separate case-complete packet that includes zero-finding cases. Restore the original evidence only through a hash-bound private crosswalk after ratings are returned. Reason: one packet cannot both hide gold from prediction reviewers and let independent reviewers approve the provisional reference standard.

## D-016: Amend the human diagnostic gate before ratings exist

Require a diagnostic finding to pass all six human-reviewed fields: exact span, named problem, contextual explanation, severity, suggested operation, and CHANGE or KEEP. Define `finding_valid` as the conjunction of the five component-validity judgments beyond the CHANGE or KEEP decision, and require complete human acceptance of at least 0.80. Report each component separately and report null rates when a system produced no CHANGE findings. This prospective amendment closes a silent-failure path found before any human forms or ratings existed; it does not alter frozen objective scores.

## D-017: Bind every human packet to one verified roster anchor

Do not create review forms until the exact identities and roles of two real reviewers and one separate adjudicator are frozen in a run-bound roster anchor. Bind the packet manifest to the roster digest, scoring-amendment digest, case bytes, prediction bytes, item digests, and run identity. A caller-provided roster or self-consistent replacement digest is not sufficient. Until that anchor exists, materialize only the provisional objective report.

## D-018: Stop at Stage 1 after the objective gate fails

All 12 surfaces failed at least one preregistered worst-run objective threshold. Publish the result as `PILOT_UNADJUDICATED`, keep human agreement and factual-meaning judgments pending, and do not execute any rewrite candidate. Human review may audit the benchmark and diagnostic explanations, but it cannot convert an objective failure into Stage 2 eligibility.
