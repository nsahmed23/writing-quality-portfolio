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

Every report's `provenance` records `suite_sha256`, `rubric_sha256` and `config_sha256` (each hashed like an adapter script, with CRLF read as LF), `judge_signature`, `adapter_sha256` (script name to hash) and `candidate_skill_sha256` (null for a calibration; otherwise the hash of the raw `SKILL.md` bytes). A comparison adds `provenance.split`, `provenance.certificate_suite_sha256`, `provenance.calibration_overlap`, `provenance.baseline_skill_sha256`, `provenance.candidate_snapshot_sha256`, `provenance.baseline_snapshot_sha256` (see "Treatment snapshot"), `provenance.repetitions` and `provenance.documents` (see "Plumbing and failure kinds").

When the config declares `version_commands` (a tool name mapped to an argv array that prints that tool's version), `calibrate` and `compare` run every command before the run and again after it, and record `provenance.tool_versions` as `before`, `after` and `changed` (a sorted list of the names whose version differs or could not be read the second time). The first element of each command is looked up on `PATH` (a bare `codex` finds `codex.cmd` on Windows) and the other elements are used as written. A command that fails before the run stops the run before any output folder exists. A change adds a failed `tool_versions_stable` check and sets `eligible` to `false`; in a comparison it also turns every recommendation into `inconclusive`. Version commands are not charged to `max_calls`. `optimize` records no versions. Without `version_commands` nothing is recorded.

## Treatment snapshot

**Enforced** by `runner._skill_snapshot` and `runner.compare`, and by `runs.merge` (the merge identity).

`compare --candidate-skill PATH` and `--baseline-skill PATH` each name a skill folder or the `SKILL.md` file inside one. The writer is not given `SKILL.md` alone. It is given the skill's snapshot: the `SKILL.md` text, then every file under the `references/` folder beside it, ordered by the file's forward-slash path relative to `references/` (compared as text, so every platform gives the same order). Each reference file follows a blank line and a header line, `=== references/<path> ===`, and its text starts on the line after the header. `SKILL.md` has no header, so a skill with no `references/` folder has its own `SKILL.md` text as its snapshot. Every file is read as UTF-8 with CRLF read as LF, so a checkout that converts line endings builds the same snapshot. A file that is not valid UTF-8 is refused ("skill NAME: FILE is not valid UTF-8", where FILE is `SKILL.md` or `references/<path>`).

A snapshot is at most 60,000 characters, headers included, counted as text and not as bytes. A larger one is refused before any output folder exists: "skill snapshot too large: NAME is N characters, over the limit of 60000". NAME is the name of the skill folder, so the message carries no skill text. The same rule builds the baseline when `--baseline-skill` is given.

With no baseline skill, the baseline writer's `instructions` are exactly `No additional instructions.` and never an empty string. The writer's role text tells the model to follow the instructions field, and an empty field leaves it nothing to follow. `instructions.json` records the text each writer was given and its hash.

Provenance records `candidate_snapshot_sha256`, the SHA-256 of the candidate's snapshot text as UTF-8 (it equals the candidate hash in `instructions.json`), and `baseline_snapshot_sha256`, the same for the baseline's snapshot, which is `null` with no `--baseline-skill`. `candidate_skill_sha256` and `baseline_skill_sha256` keep their meaning: each is the hash of the raw `SKILL.md` bytes. The metric pack checks `candidate_skill_sha256` against the target `SKILL.md` file, and `candidate-SKILL.md` and `baseline-SKILL.md` stay the raw `SKILL.md` bytes. Neither skill hash can see a changed reference file, so `merge` also requires both snapshot hashes to match across chunks ("chunk runs differ in candidate_snapshot_sha256", "chunk runs differ in baseline_snapshot_sha256").

The treatment is outside the certificate and `judge_signature` (neither hashes a skill or its references), so a certificate made before this rule stays valid for a snapshot comparison.

Limit: the snapshot is the skill's own files. A skill that sends the model to another skill or to a file outside its `references/` folder is evaluated without that file, so a comparison speaks for the snapshot and not for the routed portfolio.

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

## Plumbing and failure kinds

**Enforced** by `runner._judge_one` and `runner._judge_cases` (the records), `scoring.build_report` (the counts), `runner.compare` (`--documents` and `instructions.json`), `runs.merge` and `runs.rerun_failed`.

A judge call that does not give a valid judgment is written as an invalid record with a `failure_kind`. `plumbing` means the call produced no answer: it timed out (`error` is `timeout`), could not start (`launch_error: ...`) or exited nonzero (`process_exit_N`). `judgment` means the judge answered and the answer failed `scoring.parse_judgment`; `error` carries the validator's message. `skipped` means the pair was never sent: the judge command for it would have been longer than `MAX_COMMAND_LINE_UNITS` (32000 UTF-16 units), which only a judge that takes the prompt as an argument can reach. No call is made and nothing is charged to `max_calls`. The runner writes a `skipped` record for both orders and every judge of that case, so every judge scores the same documents; its `error` starts with `oversized_prompt:`. A valid record has neither `failure_kind` nor `error`, and an invalid record that predates `failure_kind` counts as `judgment`. The config defaults are `timeout_seconds` 300 (at most 600) and `max_calls` 2000; each command counts its own calls against `max_calls`, so a re-run counts only the calls it makes.

`counts` reports `plumbing_failures`, `judgment_failures`, `skipped_records` and `skipped_cases` separately from `invalid_records`. A skipped case leaves the scored set for every judge, so a run with skipped cases can still be complete, with fewer documents than planned; a lane whose every case was skipped stays in `by_lane` with zero documents and fails its `lane_documents_<lane>` check. The literal checks still read every case, skipped or not. A judged record for a skipped case counts as unexpected.

`compare --documents ID [ID ...]` runs only the named documents of the chosen split. An unknown name is refused by its position ("unknown document in documents"), never by its text, so a private document id cannot reach an error line. An empty or repeated list is refused ("documents must be a nonempty list of distinct document ids"). `provenance.documents` lists the documents run (sorted) and is null for a run of the whole split. `provenance.baseline_skill_sha256` and `provenance.repetitions` are recorded for every comparison, and every comparison writes `instructions.json`: the exact text the writer was given for the baseline and for the candidate (the skill's snapshot, see "Treatment snapshot"), each with its hash.

`merge` combines finished chunk runs into one report that `scoring.build_report` scores from their cases and records. It needs at least two runs ("merge needs at least two runs") and never changes a chunk folder. The report names each chunk in `provenance.merged_from` (the hashes of its report and records files, and its count of re-run calls), and `provenance.documents` lists every document. Every chunk must agree on the suite, rubric, config, judge signature, adapter hashes, candidate and baseline hashes (the `SKILL.md` hashes and the snapshot hashes), repetitions, split and certificate suite ("chunk runs differ in"), and must agree with the files on disk now ("chunk runs were made with a different"). A chunk with writer failures is refused ("has writer failures"), and so is a merged run ("is a merged run; merge the original runs"). Chunks that share a document are refused ("chunk runs overlap"). The instructions must be identical ("chunk runs differ in instructions"), and so must the tool versions, which must not have changed during a chunk ("chunk runs differ in tool versions", "a chunk run changed tool versions while it ran"). The merged folder holds `report.json`, `records.json`, `generated.json`, `instructions.json` and the candidate skill text; the chunks keep their own `calls` folders.

`rerun-failed --from RUN --out NEW_RUN` runs once more the `plumbing` records of a finished comparison, and only those. Each redone record carries `attempt` 2 and takes the place of the record it redid; `provenance.rerun` holds the hashes of the source report and records and `rerun_calls`. A `judgment` or `skipped` record is never redone ("the run has no plumbing failures to re-run" when nothing qualifies). A merged run or a re-run cannot be re-run ("a merged run or a re-run cannot be re-run"), so a pair has at most two attempts. A source with writer failures is refused; run those documents again as a new chunk. The tool versions must equal the source's, and the source must not have recorded a change ("tool versions changed since the run", "the run changed tool versions while it ran"). A re-run folder can be merged with other chunks, but not with its own source, which shares every document.

Limit: a document that one judge's command line cannot carry is left out of every judge's scoring, and that selects against long outputs. The `skipped` counts disclose it; they do not remove the bias.

## Private outputs and the export allowlist

**Enforced** by `private.require_private_output` (the guard) and `export.build_export` (the export).

A suite with any `owner_session` case holds the owner's own writing, so every run made from it must be written under one private folder, which `WQ_EVAL_PRIVATE_ROOT` names. `calibrate`, `compare`, `merge`, `rerun-failed`, `optimize` and `prepare-optimize` read the variable when they run, right after the suite loads and before any output folder or file exists, and refuse in three cases. The variable is unset or blank ("suite has owner_session cases; set WQ_EVAL_PRIVATE_ROOT to a private folder and write the run inside it"). It names something that is not an existing folder, so a typo cannot start a new private folder ("WQ_EVAL_PRIVATE_ROOT must name an existing folder"). Or the output path is not inside it ("suite has owner_session cases; the output path must be inside WQ_EVAL_PRIVATE_ROOT"). Both paths go through `os.path.realpath` and are compared with `os.path.commonpath` after `os.path.normcase`, so `..`, a symlink or a junction cannot lead out of the root, and a path on another drive counts as outside. The messages name the variable and never a path. A suite with no `owner_session` case is not checked, so `synthetic_control` and `published_reference` suites run anywhere as before. `demo` uses a built-in synthetic suite, `validate` writes nothing and `export` is public by design, so none of the three is guarded.

`export --report REPORT --out FILE` reads a finished `report.json` and writes a new JSON file that is safe to publish. It is built by copying named fields into a new object, never by deleting fields from a copy of the report, so a field the report grows later stays out until the export names it. The export holds:

1. `export_version` (the integer 1), `mode` (`calibrate`, `compare` or `score`), `execution` (`live` or `demo`), `complete`, `eligible` and `recommendation` (`candidate`, `baseline`, `inconclusive` or `not_applicable`).
2. `counts`, limited to `expected_records`, `received_records`, `missing_records`, `duplicate_records`, `invalid_records`, `unexpected_records`, `plumbing_failures`, `judgment_failures`, `skipped_records`, `skipped_cases`, `order_disagreements`, `abstentions`, `ties`, `both_bad`, `candidate_check_failures`, `baseline_check_failures`, `candidate_check_diagnostics` and `baseline_check_diagnostics`.
3. `by_lane`, with for each of `editing` and `communication` its `cases`, `documents`, `mean`, `ci_lower`, `ci_upper` and `recommendation`.
4. `checks`, each as its `name` (the report's check id) and `passed`.
5. `provenance`, limited to `candidate_skill_sha256`, `suite_sha256`, `rubric_sha256`, `config_sha256`, `judge_signature`, `baseline_skill_sha256`, `certificate_suite_sha256`, `candidate_snapshot_sha256` and `baseline_snapshot_sha256`; `adapter_sha256` for the three adapter scripts; `tool_versions` (`before`, `after` and `changed`); `merged_from` (per chunk `report_sha256`, `records_sha256` and `rerun_calls`); and `rerun` (`source_report_sha256`, `source_records_sha256` and `rerun_calls`).

No case id, document id, cluster id, prompt, context, candidate text, quote, reason or file path can reach the export. A value that is not the shape the export names is refused by field path and never by value ("report field counts.ties has an unexpected value" for a `ties` count that is negative or not an integer), so a refusal cannot echo owner text. A file that is not JSON is refused ("report is not valid JSON"), and so is JSON that is not an object ("report is not a JSON object") or an object that is not an automated proxy report of schema version 1 ("report is not an automated proxy report"). The export is built before the output file is opened, and the file is then created exclusively, so a refused report leaves no file and an existing file is never overwritten. The command also prints the export on standard output.

Limit: the guard decides by `provenance.kind` and by where this harness writes. Owner text labeled `synthetic_control` is not detected, and a judge or writer command can still write wherever its own program does. The report's `by_lane` entries carry no decisive counts or proportions, so the export has none; adding them means changing `scoring.build_report` and the export together.

## Claims

**Specified**, not yet enforced. Phase 3.1 implements this section and may refine the outcome vocabulary before it does; any change is written here first. Until then `validate_suite` rejects a `claims` field as an unknown case field.

A claim is one statement in a case's source text that an edit must not lose or distort. A case may carry `claims`, a list of objects with exactly these fields:

- `id`: a nonblank string, unique within the case.
- `text`: the claim in one sentence.
- `support`: a nonempty list of spans, each `{"source": "prompt" or "context", "quote": "literal excerpt"}` with an optional integer `occurrence`. The anchoring rules are the ones judge evidence already follows: the quote must resolve to one place in that field of the case, or `occurrence` picks the place.

A claim whose `support` quotes the source and resolves is accepted without review. A claim whose `support` does not resolve is flagged for the owner, and only flagged claims go to the owner.

A judgment then gains an optional `outcomes` list: for each candidate and each claim, one object `{"claim_id": ..., "candidate": "A" or "B", "outcome": "kept", "changed" or "dropped", "evidence": [...]}`. For `kept` and `changed`, `evidence` is a nonempty list of `{"candidate", "quote"}` items in the judge-evidence format, quoting the candidate's own text. For `dropped` it is empty. Today `scoring.parse_judgment` accepts exactly `winner`, `reason` and `evidence`. Phase 3.1 adds `outcomes` there, to the output schema in `codex_adapter.py` and to the role instructions in `generic_json_adapter.py`, and requires it only for cases that have claims.
