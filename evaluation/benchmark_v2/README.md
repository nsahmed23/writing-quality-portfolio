# Benchmark-v2 offline foundation

This Python standard-library package implements deterministic quote anchors and diagnostic-response ingestion. Every result is labeled `development_only`. There is no provider integration, scorer, router, taxonomy mapping, quality verdict or Stage 2 unlock. See [current status](../status/README.md) and [pending readiness inputs](../status/benchmark-v2-readiness.md).

## Interfaces

```python
resolve_anchor(text, quote, *, occurrence=None, left_context=None, right_context=None)
ingest_response(case_id, text, response_bytes)
```

`resolve_anchor` returns `(start, end)` using Python Unicode code-point indexes with an exclusive end. Matching is literal, including whitespace, line endings, punctuation and combining characters. Occurrences are one-based among all literal matches, including overlaps, before context filtering. Optional contexts must match immediately adjacent text. Exactly one match must survive. Missing, ambiguous, empty or invalid anchors raise `AnchorError` with a stable reason code.

`ingest_response` accepts a case ID, unmodified case text and raw response bytes. The response must be strict UTF-8 JSON with only this top-level field:

```json
{"findings": [{"native_label": "example-label", "quote": "exact text", "explanation": "The stated diagnostic reason."}]}
```

Each finding requires nonblank `native_label`, `quote` and `explanation` strings. Only `occurrence`, `left_context` and `right_context` are optional. Unknown fields and invalid anchors reject that finding while preserving valid siblings. Native labels remain unchanged. Exact duplicate accepted findings are rejected locally as `DUPLICATE_FINDING`; different labels or explanations remain distinct. This is ingestion hygiene, not a scoring policy.

An empty findings list is valid abstention. Duplicate JSON keys, nonfinite numbers, invalid UTF-8, malformed JSON and invalid top-level envelopes produce a response-level error with no accepted findings. An invalid caller argument raises `ValueError`.

The result contains `status`, `case_id`, `text_sha256`, `response_sha256`, `accepted_findings`, `rejected_findings`, and `response_error`. Accepted findings include their original zero-based `index` and resolved `start`/`end`; rejected findings retain their index and an error code. `response_error` is null for a valid envelope, including one with rejected findings.

`response_sha256` hashes the exact supplied raw bytes; `text_sha256` hashes the case text encoded as UTF-8. The function does not write either artifact. A future runner must preserve the bytes separately, along with exact prompts and execution metadata; hashes alone cannot reconstruct them or prove how a model was run.

## Offline example

From the repository root, save the following as a temporary Python file there and run it with `python FILE.py`, or paste it into a Python session launched there. It makes no model request. The label and explanation are synthetic transport fixtures, not human gold.

```python
import hashlib
import json

from evaluation.benchmark_v2 import ingest_response, resolve_anchor

text = "A blue box. A blue box."
raw = b'{"findings":[{"native_label":"example-repeat","quote":"blue box","explanation":"Synthetic finding for the second occurrence.","occurrence":2},{"native_label":"example-missing","quote":"red box","explanation":"Synthetic missing-anchor check."}]}'

assert resolve_anchor(text, "blue box", occurrence=2) == (14, 22)
result = ingest_response("opaque-demo-request", text, raw)
assert result["status"] == "development_only"
assert result["response_error"] is None
assert result["response_sha256"] == hashlib.sha256(raw).hexdigest()
assert result["text_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
assert len(result["accepted_findings"]) == 1
assert len(result["rejected_findings"]) == 1
finding = result["accepted_findings"][0]
assert finding["index"] == 0
assert (finding["start"], finding["end"]) == (14, 22)
assert text[finding["start"]:finding["end"]] == "blue box"
print(json.dumps(result, ensure_ascii=False, indent=2))
```

The first finding resolves to the second literal occurrence. The missing quote rejects only the second finding. The example ID demonstrates the caller contract; this package does not generate opaque IDs or certify their independence from labels.

## Verification

From the repository root:

```sh
python -m unittest discover -s tests -p 'test_*.py'
python scripts/verify_manifests.py
python scripts/validate_portfolio.py
```

The [status page](../status/README.md#local-verification) includes explicit-root manifest usage, the portfolio dependency and the separate legacy evaluator test commands. Check the [integration verification record](../status/2026-09-28-integration-verification.md) for actual results and environment. A successful software test does not adjudicate a finding, freeze a benchmark or supply human review.
