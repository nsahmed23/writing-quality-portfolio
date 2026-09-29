# Common detect-only envelope

Apply only the candidate instructions named in the job. Diagnose the supplied text. Do not rewrite it.

Return one strict JSON object and no surrounding prose. The object must contain `schema_version`, `case_id`, `case_decision`, and `findings`.

Each finding must contain:

- `finding_id`
- `start`, `end`, and `span`, using Python Unicode code-point offsets
- `decision`, either `CHANGE` or `KEEP`
- `problem_name`
- `system_issue_code`
- `normalized_issue_code`, using the frozen public problem-family vocabulary or `UNMAPPED`
- `context_explanation`
- `severity`, one of `none`, `low`, `medium`, `high`, or `critical`
- `suggested_operation`, with `operation_code`, `instruction`, and nullable `replacement`
- `field_origin`, one of `authored`, `deterministic_adapter`, or `model_adapter`

The exact invariant is `text[start:end] == span`. Report a CHANGE only when the problem is contextual and material. Report KEEP when a suspicious-looking construction is functional and the candidate instructions provide a basis to preserve it. Every KEEP finding must use the literal `operation_code: "preserve"`, an instruction explaining why the span should remain unchanged, and `replacement: null`. A case with no justified findings returns `case_decision: KEEP` and an empty list.

Do not guess authorship. Do not add facts. Do not expose or request gold labels. Do not grade this output.
