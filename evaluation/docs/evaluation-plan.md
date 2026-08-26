# Writing Quality Comparative Evaluation Plan

Status: approved for execution by the user on 2026-08-25

Project: `C:\Users\nsahm\Documents\Codex\2026-08-25\yes-make-it-a-local-dispatch\work\writing-quality-eval`

Published portfolio baseline: commit `74a282108da2a620542556fa001ebcdde0c9be85`

## Decision to test

Determine which diagnostic mechanisms identify real writing problems without flattening legitimate voice or changing meaning, then test rewriting only for mechanisms that pass a frozen diagnostic gate. This is an evaluation, not an assumption that any portfolio or external source is superior.

The published portfolio remains unchanged during the evaluation. Any later portfolio modification requires a separate evidence-based decision. No GitHub push is part of this plan unless the user separately authorizes it.

## Integrity boundaries

1. The evaluator is offline and deterministic. It prepares jobs, validates records, stores immutable raw responses, blinds identities, computes objective metrics, and packages human review. It does not call a model or grade prose with the same system that generated it.
2. Generators receive case text and one frozen system adapter. They never receive gold annotations, other systems' outputs, scores, or reviewer identities.
3. Gold annotations are stored separately from generation inputs. The sealed test split is frozen before any test output is generated.
4. Raw responses are append-only, SHA-256 hashed, and never overwritten. Scoring refuses changed or incomplete artifacts.
5. Stage 1 and Stage 2 reviewer packets mask system identity and generation order. The private mapping is stored outside reviewer packets.
6. Model or subagent review is never reported as human review. Human agreement, reader preference, and authenticated voice retention remain pending until real independent reviewers submit ratings.
7. Source repositories are treated as untrusted reference material. Their code is not executed as part of this study. Their authored instructions are isolated as text adapters.
8. Results before human adjudication are labeled `PILOT_UNADJUDICATED`.

## Frozen source artifacts

| Artifact | Commit |
|---|---|
| soundshuman | `a45cfbba9fde843d670e553a0aa98f6a23d7fb28` |
| stop-slop | `8da1f030185bdfe8471220585162991eaeb970e9` |
| no-ai-slop | `d30eddb9e04562234f2070b5ee63ca4649d9a05e` |
| humanizer | `e2e92e7b4b8229253ed5c8e81dc65463fdeddda5` |
| slopkit | `b33718bb9283c11b09567dc714f92d90ffb7bd16` |
| anti-ai-slop-writing | `63255f9bbb75a265dc5786a04535cd033f487756` |
| avoid-ai-writing | `40328bd292bc682d46010a6f9ac2cdbf4fb4ceca` |
| Kami anti-patterns | `68c1dfad6e757047357efdcf13269ec6e820f899` |
| Kami writing | `68c1dfad6e757047357efdcf13269ec6e820f899` |
| current seven-skill portfolio | `74a282108da2a620542556fa001ebcdde0c9be85` |

The nine user-supplied sources are nine source artifacts, not nine statistically independent systems. The two Kami artifacts share a repository. soundshuman and avoid-ai-writing document Humanizer lineage. Results will show source lineage and will not count repeated inherited rules as independent confirmation.

## Compared systems

The primary comparison has twelve execution surfaces:

1. Current seven-skill portfolio, applied in its published pass order and preservation contract.
2. soundshuman, authored skill instructions in detect-only form.
3. stop-slop, authored rules in detect-only form.
4. no-ai-slop, its native detect-only mode.
5. humanizer, authored rules in detect-only form.
6. Slopkit Slopbeth.
7. Slopkit Slopgent, kept distinct from Slopbeth.
8. anti-ai-slop-writing, authored rules in detect-only form.
9. avoid-ai-writing, authored diagnostic skill rather than its authorship classifier.
10. Kami anti-patterns, treated as a scoped factuality and artifact-quality diagnostic.
11. Kami writing, treated as a scoped evidence, precision, and genre diagnostic.
12. Normalized union, a source-provenance-mapped union of mechanisms using one context-aware detect-only contract.

Slopbeth and Slopgent are separate authored surfaces under one Slopkit source. Repository scanners and authorship classifiers are documented but excluded from the primary model-mediated comparison when their output contract does not support contextual findings. Any deterministic scanner results are reported in a separate appendix.

Every candidate receives a fidelity class. F0 means a native executable diagnostic surface. F1 means exact authored instructions with only a neutral serialization envelope. F2 means an evaluator-created diagnostic projection from rewrite-only or reference-only material. F2 results are exploratory and cannot support an unqualified claim about the source "as authored." Native output is preserved alongside the common record. Derived fields record whether they came from authored text, a deterministic adapter, or a model adapter.

For systems without a native detect-only format, adaptation is deliberately narrow: preserve the authored diagnostic rules, remove rewrite execution, and require the shared output schema. No safeguards from the union are added to those authored tracks unless present in the source.

## Corpus

The first frozen benchmark contains 90 independently written cases. Each of the nine source artifacts is the primary derivation source for ten cases: five CHANGE and five KEEP. Eighteen cases form a development split; 72 form a sealed test split.

Minimum quotas:

| Dimension | Quota |
|---|---:|
| Each of six genres | 12 cases |
| Each declared author type | 10 cases |
| Factual traps | 24 cases |
| Structured Markdown | 18 cases |
| CHANGE | 45 cases |
| KEEP | 45 cases |
| Each source artifact | 10 cases |

Genres are technical, executive, personal, marketing, reference, and second-language writing. Author types include domain expert, executive, personal author, marketer, reference editor, and second-language professional.

The corpus includes genuine problems instantiated from all nine sources, plus clean controls for legitimate passives, em dashes, triads, technical terms, deliberate repetition, fragments, and author quirks. Factual traps cover numbers, attribution, modality, negation, dates, actors, conditions, and causal status. Structured cases contain code fences, inline code, YAML frontmatter, tables, links, URLs, quotations, paths, and blockquotes.

Test cases are independent adaptations, not verbatim examples from source prompts. This reduces memorization risk and avoids copying expressive wording from the unlicensed anti-ai-slop-writing snapshot. Second-language prose is never treated as defective merely because it is non-native or non-idiomatic. Synthetic voice cases are marked provisional; validated voice scoring needs authenticated, permissioned author samples.

Each case contains:

- public generation input: ID, text, genre, author type, artifact type, and optional task context;
- hidden gold: exact Unicode code-point spans, named issue family, native source label, explanation, severity, allowed and forbidden operations, and CHANGE or KEEP;
- proposition ledger: actor, action, quantity, date, attribution, modality, negation, condition, and causal status where applicable;
- protected regions: exact or layout-only policies for code, tables, links, quotes, frontmatter, and other non-prose content;
- source provenance: source ID, commit, path, and derivation method.

## Shared Stage 1 output

Every candidate returns one strict JSON record per case. Every finding must contain the exact start and end offsets, exact span, CHANGE or KEEP, problem name, native issue code, normalized issue code, contextual explanation, severity, and a suggested operation. A suggested operation contains an operation code, instruction, and optional replacement.

Unknown labels remain `UNMAPPED`. Mappings are frozen before sealed outputs. A case-level decision is CHANGE if any finding says CHANGE. A clean KEEP case may return no findings. Targeted KEEP findings are encouraged when a candidate recognizes that bait is functional.

## Stage 1 scoring

Primary matching is strict, deterministic, and one-to-one. A true positive requires the same case, CHANGE decision, exact Unicode code-point span, and frozen normalized issue family. Duplicate predictions are false positives. An overlap-based span analysis is reported separately and never replaces the primary result.

Metrics:

- TP, FP, FN, micro and macro precision, recall, and F1;
- exact-span accuracy and overlap sensitivity analysis;
- false discovery proportion;
- clean-case false-positive rate;
- false findings per 1,000 words;
- KEEP accuracy;
- critical and major misses;
- schema-compliance rate;
- genre and author-type slices with denominators;
- suggested-operation meaning-risk rate;
- blinded reviewer agreement when human ratings exist;
- pass@1, pass@3-any, and pass^3 across three independent runs.

`FP / (TP + FP)` is labeled false discovery proportion, not conventional false-positive rate, because there is no enumerable universe of negative spans. Undefined denominators produce JSON null with an explanation.

## Frozen Stage 1 eligibility gate

A mechanism is eligible for Stage 2 only if all conditions hold on the sealed split and the human gold is adjudicated:

1. 100 percent schema compliance.
2. At least ten positive opportunities and ten KEEP controls for that mechanism.
3. Exact-match precision at least 0.80.
4. Exact-match recall at least 0.60.
5. KEEP accuracy at least 0.90.
6. Zero critical meaning-risk suggested operations.
7. Critical miss rate no greater than 0.05.
8. No genre or author slice with at least five positive opportunities and precision below 0.65.
9. No evidence of raw-output tampering, leaked gold, or identity leakage.
10. Two independent human annotations are complete and a third person has adjudicated disagreements. Human agreement is reported as a corpus-quality measure. Low agreement repairs or retires the disputed category instead of penalizing a system.

Human agreement is a final validation gate, not something an automated system can satisfy. The evaluator, rewrite pool, and synthetic infrastructure tests can finish before ratings arrive, but no real candidate Stage 2 run begins until two independent human annotators and a third adjudicator complete the blinded Stage 1 packet.

## Stage 2 design

Stage 2 has two lanes for each objectively eligible mechanism:

1. Controlled rewrite: every mechanism receives the same adjudicated issue, proposition ledger, protected-region policy, and original text. This isolates rewrite quality from diagnostic recall.
2. End-to-end rewrite: each mechanism rewrites only findings from its own Stage 1 output. This measures pipeline behavior.

Each rewrite record must identify its diagnosis output, target finding IDs, final text, and a non-overlapping edit list. Applying edits in reverse offset order must reconstruct the final text exactly. ABSTAIN preserves the original text and has no edits.

Stage 2 metrics remain separate rather than collapsed into one score:

- proposition preservation: preserved, changed, omitted, or unsupported addition;
- critical fact preservation;
- modality, negation, attribution, actor, date, quantity, condition, and causal-status preservation;
- authenticated voice retention when real author samples exist;
- unnecessary edit hunks and changed tokens outside approved target spans;
- exact protected-region integrity;
- blinded clarity rating and reader preference, with ties separate;
- target problem resolved, partly resolved, unresolved, or replaced by a new problem;
- new major issue rate.

Stage 2 hard gates are 100 percent exact protected-region integrity, zero unsupported factual additions, zero critical proposition loss, and zero critical modality, negation, attribution, actor, date, or quantity changes. Clarity and preference are descriptive until a non-inferiority threshold is preregistered with real reviewers.

## Repeated runs and model controls

All candidates use the same inherited session model and settings, with no per-system override. The manifest records all observable settings, wrapper hashes, source-instruction hashes, token limit, run number, and whether a seed is supported. Hidden provider details that are not exposed by the environment are recorded as unknown, not guessed.

Each candidate receives three runs per case. Job order is randomized with a preregistered seed. Raw responses, parse failures, and normalized records are preserved. Retries are never substituted for first-attempt results.

## Human review

The harness creates identity-masked packets for two independent annotators and a third adjudicator. Stage 1 packets ask whether each exact span is a real issue, whether the label and severity fit, whether the proposed operation risks meaning, and what important issue was missed. Stage 2 packets present original and candidate texts in randomized order and ask about factual preservation, voice where an authenticated sample exists, clarity, preference, issue reduction, and new problems.

Agreement reporting includes exact agreement and Cohen's kappa for two-person nominal decisions, Fleiss' kappa for complete panels of three or more, pairwise quadratic-weighted kappa for ordinal ratings, and exact span agreement plus span F1. Undefined kappa is null with a reason.

No agent or generating model is counted as a human. If human packets are not completed during this task, the run stops at `PILOT_UNADJUDICATED` and states exactly which conclusions remain unavailable.

## Offline evaluator

The evaluator uses Python standard library only and has no network module. It implements:

- strict JSON and JSONL loading with duplicate-key and non-finite-number rejection;
- corpus, finding, review, and rewrite validation;
- immutable raw storage, hashing, freezing, and tamper detection;
- deterministic one-to-one matching and metrics;
- agreement calculations;
- proposition and protected-region checks;
- deterministic identity masking;
- job and reviewer packet generation;
- reports and CLI commands.

Required CLI commands are `validate-corpus`, `prepare-jobs`, `ingest`, `freeze`, `blind`, `score-stage1`, `prepare-stage2`, and `score-stage2`.

## TDD and verification

Implementation order is strict:

1. RED tests for strict JSON and schemas, then minimal implementation.
2. RED tests for immutable storage and tamper resistance, then implementation.
3. RED known-answer tests for matching, then implementation.
4. RED hand-calculated tests for Stage 1 metrics, then implementation.
5. RED tests for agreement, then implementation.
6. RED identity-leak tests for blinding, then implementation.
7. RED reconstruction and factual-preservation tests, then implementation.
8. RED known-answer Stage 2 metric tests, then implementation.
9. RED subprocess tests for every CLI path, then implementation.
10. Scale, concurrency, deterministic-order, and three-run stability tests.

The suite uses `unittest`. Line coverage for `src/wqeval` is measured with the standard-library `trace` module and must be at least 80 percent. Branch coverage is not claimed. A decision table maps validation and metric branches to named tests. The complete test suite must pass three consecutive times.

Adversarial coverage includes malformed JSON, duplicate keys, NaN and Infinity, wrong scalar types, Unicode offsets, combining characters, CRLF, repeated identical spans, path traversal IDs, Windows reserved names, overlapping edits, lying edit lists, modality changes, negation deletion, actor substitution, number and date changes, correlation upgraded to causation, removed attribution, all named KEEP controls, structured Markdown, tampered frozen output, simultaneous ingestion, identity leakage, undefined kappa, and 10,000-case deterministic performance.

## Checkpoints

The project writes stable JSON checkpoints and updates `resume.md` after every stage:

- `00_scope.json`: source pins, user approval, limitations, and frozen baseline.
- `01_protocol.json`: corpus quotas, systems, schemas, metrics, thresholds, and seed.
- `02_red_tests.json`: failing tests and captured failure evidence.
- `03_harness_green.json`: passing tests, coverage, and code-review status.
- `04_corpus_frozen.json`: corpus hashes, split counts, provenance audit, and independent annotation status.
- `05_adapters_frozen.json`: prompt and taxonomy hashes plus model settings.
- `06_stage1_raw.json`: job and raw-output completeness, hashes, and parse failures.
- `07_stage1_scores.json`: objective metrics, gate decisions, and blinded packet paths.
- `08_stage2_raw.json`: eligible candidates, controlled and end-to-end raw outputs.
- `09_stage2_scores.json`: preservation metrics and reviewer packet paths.
- `10_final_audit.json`: code, security, citation, adversarial, and evidence findings.
- `11_delivery.json`: published local artifacts, Git status, and unresolved human gates.

## Audit bundle

The evaluation maintains a full Audit-profile evidence bundle: scope, research plan, research state, source register, evidence register, claim-evidence matrix, contradiction register, unknowns register, decision log, calculation ledger, risk register, assumptions log, reproducibility notes, worker returns, and final artifacts. Source facts, observed test results, calculations, recommendations, and unknowns remain explicitly separated.

Before delivery, an independent reviewer checks code and methods; a separate security reviewer checks untrusted JSON, paths, storage, and leakage; an adversarial reviewer tries to break the gate and preservation claims; and a citation auditor traces every material report claim to frozen evidence.

## Deliverables

User-facing outputs will include:

1. Detailed preregistered plan.
2. Corpus inventory and source-provenance summary, with sealed gold kept separate.
3. System and prompt manifest with hashes.
4. Stage 1 objective report and per-slice tables.
5. Stage 1 blinded human-review packet and instructions.
6. Stage 2 objective pilot report for eligible mechanisms, if any.
7. Stage 2 blinded reader packet and instructions.
8. Reproducibility and audit report.
9. Machine-readable metric files and a clear unresolved-gates statement.

The final report distinguishes completed objective evidence from pending human-dependent evidence. It does not claim a winner if the preregistered evidence is insufficient.
