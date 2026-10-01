# Automated evaluation contract

This file fixes what the suite files, the harness (`contracts.py`, `scoring.py`, `runner.py`, `adapters.py`) and the reports it writes promise each other. A rule marked **Enforced** is rejected by code and pinned by a test. A rule marked **Specified** is a promise that a later phase implements; no code checks it yet. A rule changes only together with its test, and `tests/test_automated_contract.py` fails when a section or a quoted message here goes missing.

## Suites, splits and clusters

**Enforced** by `contracts.validate_suite`.

A suite is one JSON object with `schema_version` (the integer 1), `name`, and a nonempty list `cases`. A case has exactly these fields, and any other field is rejected ("invalid case fields"): `id`, `document_id`, `split`, `lane`, `prompt`, `context`, `a`, `b`, `expected`, `checks`, `provenance` and `cluster_id`. Every field except `cluster_id` is required, so a case with nothing to check or no labeled winner writes `checks` as `{}` and `expected` as `null`; leaving either key out is rejected with the same message.

`split` is one of `contracts.SPLITS`: `calibration`, `development` or `test`. Calibration cases that carry an `expected` winner are the labeled controls that measure a judge. Development cases are for tuning. Test cases are for the final comparison. `lane` is `editing` or `communication`.

Four rules keep related text on one side of a split:

1. A `document_id` belongs to one split ("document reused across splits"). Several cases may share a document id (repetitions); they count as one document.
2. `cluster_id` is optional and, when present, a nonblank string. It groups documents that share a source, such as the messages of one conversation or an original text and its later revisions. Whatever builds a suite assigns it; the harness only checks the rules below.
3. A document has one cluster: each of its cases carries the same `cluster_id`, or none of them carries one ("document assigned to more than one cluster").
4. A cluster never spans splits ("cluster spans splits").

A fifth rule stops copies. Two cases with the same prompt, context and unordered candidate pair, compared after Unicode NFC normalization and whitespace collapsing, must share a document id ("copied pair assigned to another document id"); `contracts.case_fingerprint(case)` computes that key. These checks catch exact copies and declared relations. They do not catch a paraphrase.

## Split selection

**Enforced** by `scoring.build_report` and `runner.compare`.

`calibrate` scores the labeled cases of the `calibration` split and refuses any other split ("calibrate scores the calibration split"); a calibration split with no labeled case is refused too ("calibrate requires labeled calibration cases"). `compare --split SPLIT` (default `test`) selects the cases that are written, judged and scored. An unknown split is refused ("invalid split") and a split with no cases is refused ("compare requires SPLIT cases", with the split name filled in); only `score` mode falls back to every case when its split has none. `scoring.build_report(..., split=None)` defaults to `calibration` for `calibrate` and to `test` for every other mode. The selected split is recorded as `provenance.split`; the report has no new top-level field for it.

## Certificates and the judge signature

**Enforced** by `runner.calibrate` and `runner.compare`.

`calibrate` writes a certificate: the run folder's `report.json` with `mode` `calibrate`. It is eligible when coverage is complete and valid and each judge meets the calibration thresholds in `README.md` (at least eight labeled controls across four documents, two presentation orders per judge, 0.90 for stable correctness and for order stability). `compare` accepts a certificate only if it is a live, complete, eligible `calibrate` report whose `rubric_sha256` and `judge_signature` equal the current run's and whose `provenance` records a `suite_sha256` (without it the leakage guard below cannot tell which suite issued the certificate). Otherwise it raises "matching eligible live calibration required" before it creates an output folder.

The judge signature is the SHA-256 of the canonical JSON of `{"judges": [{id, family, command}, ...], "adapters": {script name: SHA-256 of the script's text}}`, where the text is the file's bytes with each CRLF turned into LF. The three scripts are `codex_adapter.py`, `generic_json_adapter.py` and `prompt_arg_adapter.py` in the `adapters` folder next to `runner.py`. They are part of the judge: they build the judge prompt and set the output schema and the isolation flags. Editing one therefore invalidates every older certificate and needs a new calibration. The writer command and the tool versions are not in the signature; a run records them as provenance (next sections but one). Because CRLF is read as LF, a checkout that converts line endings (Windows with `core.autocrlf=true`) has the signature of an LF checkout; any other change to a script, a lone CR or trailing whitespace included, changes it. A certificate issued before this normalization, on a checkout whose files had CRLF line endings, no longer matches and needs a new calibration.

## Calibration-suite leakage guard

**Enforced** by `runner.compare` (`_check_calibration_suite`).

Every comparison records `provenance.certificate_suite_sha256`, the hash of the suite that issued the certificate. When that suite differs from the suite being scored, `compare` needs `--calibration-suite PATH` naming it, and refuses otherwise ("certificate was issued on another suite; pass --calibration-suite so leakage can be checked"). A file whose hash differs from the certificate's is refused too ("calibration suite does not match the certificate").

The guard then compares the selected cases with the certificate suite's labeled controls (calibration-split cases with an `expected` winner) and counts overlaps by document id, by cluster id and by copied pair. The counts are recorded as `provenance.calibration_overlap` with the integer keys `documents`, `clusters` and `pairs`. A `test` comparison is refused when any count is above zero: "comparison case CASE_ID overlaps a calibration control (document)", or "(cluster)", or "(copied pair)". `development` and `calibration` comparisons may overlap, because real-anchored controls are derived from development documents and share their source identities by design; the counts disclose it. An error line names only the case id and the kind of overlap, never a document id, a cluster id or text.

Limit: the guard sees identity (the same document, cluster or exact copy), not similarity. A paraphrased copy passes.

## Run provenance

**Enforced** by `runner.calibrate`, `runner.compare` and `adapters.tool_versions`.

Every report's `provenance` records `suite_sha256`, `rubric_sha256` and `config_sha256` (each hashed like an adapter script, with CRLF read as LF), `judge_signature`, `adapter_sha256` (script name to hash) and `candidate_skill_sha256` (null for a calibration; otherwise the hash of the raw `SKILL.md` bytes). A comparison adds `provenance.split`, `provenance.certificate_suite_sha256` and `provenance.calibration_overlap`.

When the config declares `version_commands` (a tool name mapped to an argv array that prints that tool's version), `calibrate` and `compare` run every command before the run and again after it, and record `provenance.tool_versions` as `before`, `after` and `changed` (a sorted list of the names whose version differs or could not be read the second time). The first element of each command is looked up on `PATH` (a bare `codex` finds `codex.cmd` on Windows) and the other elements are used as written. A command that fails before the run stops the run before any output folder exists. A change adds a failed `tool_versions_stable` check and sets `eligible` to `false`; in a comparison it also turns every recommendation into `inconclusive`. Version commands are not charged to `max_calls`. `optimize` records no versions. Without `version_commands` nothing is recorded.

## Judge output

**Enforced** by `scoring.parse_judgment`, and stated to the judges by the output schema and prompt in `adapters/codex_adapter.py` and by the prompt in `adapters/generic_json_adapter.py`. The agy bridge `adapters/prompt_arg_adapter.py` sends the generic prompt.

A judgment is one JSON object with exactly `winner`, `reason` and `evidence`. `winner` is `A`, `B`, `tie` or `both_bad`. `reason` is nonblank. `evidence` is a list of `{candidate, quote}` items, each with an optional positive integer `occurrence`; `candidate` is `A` or `B`, and `quote` is a literal excerpt of that candidate that resolves to one place in its text (or to the place `occurrence` picks).

Three rules govern the list:

1. It is never empty, whatever the winner ("evidence must be nonempty").
2. A decisive judgment (`A` or `B`) and a `both_bad` judgment quote both candidates ("decisive or both_bad judgment requires both candidate quotes").
3. A `tie` quotes at least one candidate. One quote is enough.

A judgment that breaks a rule is an invalid record. It is counted in `invalid_records` and keeps the run from being complete. The Codex output schema sets `minItems` to 1 on `evidence`, and both judge prompts say "A tie must quote at least one candidate; evidence is never empty." The validator did not change with that wording. Two live calibrations lost a control because a judge answered `tie` with an empty list and nothing had told it that the list must not be empty (`evaluation/status/2026-09-30-live-evaluation.md`, "Open decision", option 2).

## Literal checks

**Enforced** by `contracts.validate_suite` (the kinds and the `expected` rule) and by `scoring.build_report` through `scoring.literal_tallies` (the counts).

Every case has a `checks` field: `{}` when there is nothing to check, otherwise a map with any of `required` (strings that must appear), `forbidden` (strings that must not appear), `max_words` and `exact`. Each of those four keys is optional. The harness tests the candidate text (`b`) and the baseline text (`a`) of every scored case against them. What a miss means depends on the case's `provenance.kind`, which is `synthetic_control`, `published_reference` or `owner_session`; any other kind is refused ("invalid provenance kind").

A miss on a `synthetic_control` or `published_reference` case is a veto. It is counted in `counts.candidate_check_failures` (a miss in the candidate text) or `counts.baseline_check_failures` (a miss in the baseline text). A candidate miss fails the `candidate_checks` check and blocks a candidate recommendation in every lane; a baseline miss blocks a baseline recommendation. The veto stays because the author of such a case wrote the text and the literal strings a correct revision keeps or avoids.

A miss on an `owner_session` case is a diagnostic only. That case has no labeled answer, and a literal string is a weak stand-in for a judgment about a person's own text, so one miss must not cancel the judges' verdict. The misses are counted in `counts.candidate_check_diagnostics` and `counts.baseline_check_diagnostics`, and listed in the top-level `diagnostics` list. It lists only the documents and lanes that have at least one miss, one entry for each, with the keys `document_id`, `lane`, `candidate_misses` and `baseline_misses` (the misses summed over that document's cases), sorted by document id and then lane. A diagnostic is never a failed entry in `checks`, and it never changes a recommendation: the lanes' judge results decide.

A report with no `owner_session` misses, such as one for a suite with no `owner_session` case, still carries both diagnostics counts, equal to 0, and an empty `diagnostics` list.

An `owner_session` case must write `expected` as `null` ("owner session case cannot have expected winner"). Its `checks` field is required like any case's and may hold literal checks, although the harvest of owner sessions writes none by default. The metric-pack extension treats every failed check except `baseline_checks` as a veto, which is why a diagnostic must never appear as a failed check.

## Claims

**Specified**, not yet enforced. Phase 3.1 implements this section and may refine the outcome vocabulary before it does; any change is written here first. Until then `validate_suite` rejects a `claims` field as an unknown case field.

A claim is one statement in a case's source text that an edit must not lose or distort. A case may carry `claims`, a list of objects with exactly these fields:

- `id`: a nonblank string, unique within the case.
- `text`: the claim in one sentence.
- `support`: a nonempty list of spans, each `{"source": "prompt" or "context", "quote": "literal excerpt"}` with an optional integer `occurrence`. The anchoring rules are the ones judge evidence already follows: the quote must resolve to one place in that field of the case, or `occurrence` picks the place.

A claim whose `support` quotes the source and resolves is accepted without review. A claim whose `support` does not resolve is flagged for the owner, and only flagged claims go to the owner.

A judgment then gains an optional `outcomes` list: for each candidate and each claim, one object `{"claim_id": ..., "candidate": "A" or "B", "outcome": "kept", "changed" or "dropped", "evidence": [...]}`. For `kept` and `changed`, `evidence` is a nonempty list of `{"candidate", "quote"}` items in the judge-evidence format, quoting the candidate's own text. For `dropped` it is empty. Today `scoring.parse_judgment` accepts exactly `winner`, `reason` and `evidence`. Phase 3.1 adds `outcomes` there, to the output schema in `codex_adapter.py` and to the role instructions in `generic_json_adapter.py`, and requires it only for cases that have claims.
