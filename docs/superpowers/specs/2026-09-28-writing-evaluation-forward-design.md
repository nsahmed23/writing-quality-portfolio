# Writing evaluation: integration and development foundation

## Intent and selected milestone

The owner requested the best course of action on `main` and the three writing-evaluation review branches, followed by execution with subagents. The immediate deliverable is one reviewable integration branch with reproducible verification and a small, offline foundation for the proposed replacement benchmark.

The four source commits are:

| Role | Commit |
|---|---|
| Current main | `28454c197246e6147da952b72d044273f6bb192f` |
| Original audit, PR #1 | `5d1f2b4cf83c54b5b70e5d10f16a85cbc07b9ba4` |
| Feedback, PR #2 | `7aac10137397a7f001b47b2ebeaeff8a632c73ea` |
| Final review, PR #3 | `ac6d52e1c57c71d43070884bb56335ee3176888f` |

## Alternatives considered

1. Merge the three old PRs one at a time. This preserves their sequence but leaves integration with newer communication work to the first PR and does not address repeatable verification.
2. Integrate the final review tip into current main, preserve both histories, add integrity verification, and implement only the deterministic quote/ingestion portion of benchmark v2. **Selected.** It resolves the immediate branch problem and delivers reusable code before human calibration.
3. Build the entire routed portfolio and run a new comparative benchmark. Deferred until a valid human-adjudicated protocol exists; doing it now would combine too many unfinished decisions.

## Boundaries

- `skills/`, `evals/communication/`, the existing portfolio fixtures, and the existing portfolio validator retain current-main bytes.
- Every existing file under `evaluation/` retains final-review-tip bytes. In particular the pilot, original report, review records, and checkpoints are historical evidence. New code and documents go in new paths.
- `evaluation/` is the editing-skills pilot. `evals/communication/` is a later, separate set of reply-shape experiments. Neither supplies human gold for the other.
- Stage 2 remains locked. This milestone issues no comparative ranking, human adjudication, sealed-run readiness, or quality verdict.
- No paid model requests, external source execution, new human identities, invented labels, or invented thresholds.
- Changes are delivered on a new branch and draft PR. The original branches and PRs remain available for review and provenance.

## Integration and integrity

Merge the final review tip into main with a merge commit. Regenerate the root manifest over the exact Git-tracked file set, excluding itself. Preserve `evaluation/MANIFEST.sha256` unchanged: it remains a historical manifest for the original evaluation bundle, not a manifest for new development files.

Add a standard-library Python verifier that accepts GNU SHA-256 text and binary markers, validates safe relative paths, detects malformed rows, duplicate paths, missing files, byte mismatches, and unexpected tracked paths. Root coverage is exact except for the root manifest itself. Evaluation coverage is exact for its original file set; new development subtrees are expressly outside that historical manifest and are covered by the root manifest.

Provide an explicit root-only regeneration command. Verification must not rewrite files or silently normalize bytes. Preserve CRLF files already present; make checkout behavior reproducible across Linux and Windows with a small documented Git attributes policy.

Add read-only GitHub Actions validation for Linux and Windows using Python 3.11 and 3.14, the portfolio validator, existing evaluator tests, new foundation tests, and integrity checks. Use minimal permissions and no secrets. Pin action revisions and the existing PyYAML dependency. Remote CI outcomes remain pending until actually observed.

## Benchmark-v2 development module

Use a separate Python standard-library package at `evaluation/benchmark_v2/`.

### Quote anchors

`resolve_anchor(text: str, quote: str, *, occurrence: int | None = None, left_context: str | None = None, right_context: str | None = None) -> tuple[int, int]`

- Offsets are Python Unicode code-point indexes with an exclusive end.
- Quote matching is literal: no whitespace, Unicode, punctuation, or line-ending normalization.
- Find overlapping matches. `occurrence` is one-based among all literal matches before context filtering; reject booleans, zero, negative, or out-of-range values.
- Optional context must match immediately adjacent text. Without occurrence, context may select one otherwise repeated quote.
- Exactly one candidate must survive; absent or ambiguous anchors raise `AnchorError` with a stable reason code.
- Reject empty quotes, invalid input types, and invalid context types.

### Response ingestion

`ingest_response(case_id: str, text: str, response_bytes: bytes) -> dict`

- Preserve exact raw-response provenance via SHA-256 of the supplied bytes; also return case ID and SHA-256 of UTF-8 case text. Never write or call a model.
- Parse strict UTF-8 JSON, rejecting duplicate object keys and nonfinite numbers. The top-level contract is an object containing only `findings`, a list.
- A finding requires nonblank string `native_label`, `quote`, and `explanation`; optional fields are `occurrence`, `left_context`, and `right_context`. Reject unknown fields locally. Native labels are retained without taxonomy mapping or quality judgment.
- Return accepted findings with computed offsets and original finding index, plus rejected findings with original index and stable error code. One malformed finding must not erase valid siblings. Never manufacture missing fields.
- Exact duplicate accepted findings are rejected locally with `DUPLICATE_FINDING`; distinguish labels and explanations in the duplicate key, so separate diagnoses are not silently discarded. This is ingestion hygiene and does not establish a scoring policy.
- Empty findings are valid abstention. Whole-response syntax or envelope failures produce a response-level error and zero accepted findings.
- Invalid caller arguments raise `ValueError`; malformed model content is represented in the result.
- Always label output `development_only`; there is no readiness or Stage 2 unlock in this module.

Tests must exercise repeated and overlapping quotes, emoji and combining characters, literal CRLF and code/table text, ambiguous and missing anchors, invalid occurrences, duplicate JSON keys, nonfinite JSON, wrong types, partial rejection, deduplication, abstention, and deterministic provenance.

## Documentation and next human gate

Provide a current status/read-order page, an integration verification record, and a benchmark README with a runnable offline example. Record independently verified counts separately from historical test reports. List the next human-owned inputs: reviewer roster/calibration, independent gold and adjudication, accepted boundary alternatives, numeric thresholds and opportunity floors, fresh holdout, and exact model/prompt/request provenance policy. The existing reoptimization proposal remains historical; new status documents state how much has actually been implemented.

## Success criteria

Both original lines of work are present, required historical paths are byte-identical to their anchors, manifests verify with exact coverage, portfolio validation passes, legacy evaluator tests have no failures with skips reported, new behavioral tests pass, independent review finds no unresolved important defect, and a draft PR contains precise commands and remaining limitations.
