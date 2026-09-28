# Benchmark v2: readiness and next steps

**Status: development-only. Not ready for a sealed benchmark or a quality verdict. Stage 2 remains locked.**

The [foundation](../benchmark_v2/README.md) implements exact quote resolution, strict JSON ingestion, per-finding rejection, exact-duplicate rejection, and deterministic case-text and raw-response hashes. It has no provider integration, model runner, scorer, taxonomy mapper, router, arbitration layer, or benchmark-readiness gate. Ingestion acceptance means a finding is structurally valid and its quote resolves; it does not mean a human accepts the diagnosis.

## Pending prerequisites

| Input | Required work |
|---|---|
| Independent human gold | Real reviewers independently propose issues before seeing system responses. Human adjudicators resolve validity, protected regions, severity, allowed operations and disputed cases. The old pilot's provisional labels are not approved v2 gold. |
| Equivalent anchors | Humans approve genuinely equivalent boundary alternatives. Literal anchor resolution cannot decide diagnostic equivalence. |
| Reviewer roster and calibration | Confirm real identities and independence outside the evaluator; preregister training, calibration, the reliability rule, minimum eligible opportunities and the resolution path if that rule fails. Local hashes cannot prove identity. |
| Thresholds and opportunity floors | Approve and freeze numerical acceptance gates, minimum opportunities for every rate, and uncertainty reporting. The old pilot's prospective 0.80 human-acceptance amendment is historical and is not a v2 rule. Agreement and complete finding acceptance remain distinct. |
| Metadata leakage assessment | Freeze a probe method, approved labels, exposure policy and leakage ceiling before model evaluation. Opaque request IDs alone cannot demonstrate absence of leakage. |
| Fresh holdout | Create a genuinely new sealed set and keep its contents inaccessible until harness decisions are frozen. The published pilot can never become a blind holdout again. |
| Execution provenance | Freeze the exact prompt/request contract and model/provider settings, including unsupported settings. Persist rendered prompt bytes before sending, first raw response bytes before parsing, and versions/settings alongside hashes. Enforce one case per fresh request. The current in-memory module neither sends requests nor stores these artifacts. |
| Blinded review | Obtain actual human judgments of native problem, span, explanation, severity and operation validity. Any future Stage 2 needs verified diagnostic gates plus blinded human voice, clarity and preference judgments. |

No pending value is filled by a model-generated attestation, example label or inherited pilot setting. Synthetic software fixtures exercise code behavior and are not benchmark gold.

## Next tasks after this foundation

1. Have the benchmark owner and human reviewers settle the core protocol and pending human inputs above. The minimal comparison uses native vocabulary and quote anchors; clean-case false positives measure conservative silence. Explicit KEEP localization is a separate optional lane. Rewrite-only surfaces are not diagnostic-ranking participants.
2. Build human-adjudicated development and calibration material, then implement the request/artifact runner and preregistered metadata probe. Preserve exact bytes and provenance. A future readiness checker must fail closed on missing prerequisites.
3. Implement decomposed scoring only after its human-approved contracts exist. Track localization, boundaries, native-problem acceptance and other components separately. The adapter's duplicate policy must not silently become a recall or precision policy.
4. Freeze benchmark decisions, then conduct the proposed sealed Stage 1 repetitions and blinded real-human review. Routing and arbitration belong to the portfolio system under test and can be developed separately; they are not prerequisites for the minimal cross-system comparison. Consider Stage 2 only after its verified gates pass.

See the historical [reoptimization proposal](../docs/reoptimization-proposal.md) for the wider sequence and the [integration verification record](2026-09-28-integration-verification.md) for observed software checks. Passing those checks establishes software behavior within their scope, not diagnostic quality or benchmark eligibility.
