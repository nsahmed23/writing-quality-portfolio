# Live automated evaluation record, 2026-09-30

This is the first live run of the automated proxy evaluator; the [2026-09-28 verification note](2026-09-28-automated-verification.md) recorded that none had been done. Three live judge calibrations ran on 2026-09-30 and none qualified a judge pair. The stages that need a qualified pair therefore did not run: no skill was compared, no metric pack was produced, and the rubric optimizer was never called. All times are UTC.

Read the three calibrations as an end-to-end pipeline smoke test on public synthetic controls. They are not a verdict on any skill, and this note makes no claim about the quality of `concision` or any other skill. The [Limits](#limits) section gives the reasons.

Calibrations 1 and 2 ran at repository commit `d4cf7381fdbb842a92ac8097ad363492d7f801fc`. Calibration 3 ran at `689c7ae1928ae9d7b9671af07e52abc13fadb2cc` (PR #10, which hardened the prompt argument adapter for agy). The operator was a Claude Code subagent (claude-sonnet-5-5) working for an orchestrating session, after the owner approved the run. Apart from that one adapter, the suite, rubric, runner, scoring code and Codex adapter were byte-identical in all three runs (hashes below).

## Result

A calibration sends each of 8 labeled controls (over 4 documents) to each judge in both presentation orders, which is 32 calls. A judge is eligible only if all 16 of its calls return valid judgments, it covers at least 8 labeled controls on at least 4 documents, and both scores reach 0.90. Accuracy is the share of controls where the judge gave the labeled verdict in both orders. Order stability is the share where it gave the same verdict in both orders. With 8 controls, one miss scores 0.875 and fails. A run is eligible only if it is complete and every judge is eligible, and `compare` refuses to start without an eligible live calibration.

| Cal | Commit | Judge (family, pinned model) | Accuracy | Order stability | Complete | Eligible |
|---|---|---|---|---|---|---|
| 1 | `d4cf738` | `codex-astra-judge` (openai, `gpt-6-astra`, effort high) | 0.875 | 0.875 | yes | no |
| 1 | `d4cf738` | `agy-gemini-judge` (google, `gemini-3.1-pro-high`) | 1.0 | 1.0 | yes | yes |
| 2 | `d4cf738` | `codex-sol-judge` (openai, `gpt-5.6-sol`, effort high) | 0.875 | 0.875 | no | no |
| 2 | `d4cf738` | `agy-gemini-judge` (google, `gemini-3.1-pro-high`) | 1.0 | 1.0 | yes | yes |
| 3 | `689c7ae` | `codex-sol-judge` (openai, `gpt-5.6-sol`, effort high) | 0.875 | 0.875 | no | no |
| 3 | `689c7ae` | `agy-gemini38-judge` (google, `gemini-3.8-flash-high`) | 1.0 | 1.0 | yes | yes |

Run-level results are below. Each run received 32 of 32 expected records, with none missing, duplicated or unexpected, and had zero literal check failures on either candidate.

| Cal | Run complete | Run eligible | Invalid records | Abstentions | Order disagreements | Ties | Both bad |
|---|---|---|---|---|---|---|---|
| 1 | yes | no | 0 | 1 | 1 | 1 | 0 |
| 2 | no | no | 2 | 1 | 0 | 0 | 0 |
| 3 | no | no | 2 | 1 | 0 | 0 | 0 |

The run-level metrics (`calibration_accuracy`, `order_stability`) are the lower of the two judges' scores, 0.875 in all three runs. No judge returned a stable wrong verdict on any control in any run. Every miss was a control without two matching valid answers: a disagreement between the two orders in calibration 1, and two invalid answers in each of calibrations 2 and 3.

## What failed

These are the recorded facts; the causes marked as diagnosis were not tested by asking a model.

**Calibration 1, one order flip by the OpenAI judge.** `codex-astra-judge` (`gpt-6-astra`) judged `edit-economy-control` (document `cal-doc-2`, labeled `b`) correctly in presentation order 1: winner B, with quotes for both candidates. In order 2 the candidates are swapped, so A was the concise sentence "We are considering a delay." and B was the wordy one. It returned `both_bad` with the reason "Both preserve the tentative delay but omit the Chicago-office scope belonging to the same notice. A is concise; B also retains redundant phrasing." The response was valid and quoted both candidates. The other five judge runs on this control (Gemini in calibrations 1 to 3, Sol in calibrations 2 and 3) answered `b` in both orders. See [the task flaw below](#known-task-flaw-edit-economy-control).

**Calibrations 2 and 3, empty evidence on a tie.** `codex-sol-judge` (`gpt-5.6-sol`) answered 7 of 8 controls correctly and identically in both orders, in both runs. On `comm-unchanged-control` (document `cal-doc-4`, two identical candidates, labeled `tie`) all four responses (calls 29 and 30 in each run) were `winner: tie` with `evidence: []`. Call 29's response is byte-identical across the two runs; its reason reads "A and B are identical and exactly preserve the requested draft-availability sentence without adding content." The verdict was right. The validator rejected it with "evidence must be nonempty".

Diagnosis: the validator and the adapter's prompt and schema disagree about what a tie needs. `scoring.py` (lines 46 to 48) rejects an empty evidence list for every winner, `tie` included, and separately (lines 64 to 65) requires quotes from both candidates for every other winner. `adapters/codex_adapter.py` defines `evidence` as an array with no minimum length (lines 44 to 47) and asks for quotes "for both candidates when decisive or both_bad" without saying what a tie needs (lines 71 to 75). `adapters/generic_json_adapter.py` (lines 14 to 18) words it the same way. The automated README says "a tie may cite one" (line 36), which agrees with the validator. Astra in calibration 1 and both Gemini models quoted evidence on the same tie.

Counterfactual, not a result: had the validator accepted an empty-evidence tie, Sol would have scored 8 of 8 (1.0 and 1.0) in both runs and calibration 3 would have been eligible. Under the shipped code the runs are ineligible, and no validator, prompt, schema, rubric or control was changed in this run.

**No infrastructure failures.** All 96 calibration calls exited 0 with no adapter error, timeout or malformed JSON. The only invalid records are the two empty-evidence ties in each of calibrations 2 and 3.

**Reading the report fields.** `abstentions`, `ties` and `both_bad` count controls by the two judges' combined verdict: a control is an abstention when either judge has no settled verdict or the two judges differ. `order_disagreements` counts judge-and-control pairs with two valid answers that differ. The `by_lane` block in a calibration report is computed from those control decisions; it is not a skill result and should be ignored here. A check's `message` states the rule the check applies, not what happened: a passing `live_execution` check carries the text "demo is software smoke evidence only" (`scoring.py`, line 226).

## Known task flaw: `edit-economy-control`

This is recorded, not fixed: the control is unchanged in this run (suite hash below). Its prompt says "Revise the policy notice sentence; preserve its tentative schedule while removing redundant phrases." The source text it revises opens with "This policy applies to the Chicago office.", and the rubric's `meaning` criterion asks whether the text preserves "specified facts, scope, and uncertainty". Neither candidate mentions the Chicago office, and the prompt never says whether that scope must be kept. The labeled answer (`b`, the concise sentence) therefore holds only if the omitted scope is not required, and the task does not say which. A task whose grader checks something the task never stated fails the test in Anthropic's "Automating eval design and hillclimbing with Claude" (2026-09-28), as the orchestrating session relayed it; the operator did not read the article.

The observed cost is one miss: `codex-astra-judge` returned `both_bad` in one order in calibration 1 and named the omitted scope as its reason. Five other judge runs chose `b` in both orders, so this is a stability risk with one observed miss, not a pattern. The sibling control `edit-scope-control` (same document) does state its scope requirement in its prompt. Fixing this control changes the suite hash and is a post-result change; the natural moment is the fresh calibration that any suite edit would need anyway.

## Who changed what

| Change | Decided by | Basis | Used in |
|---|---|---|---|
| OpenAI judge `codex-astra-judge` (`gpt-6-astra`) replaced by `codex-sol-judge` (`gpt-5.6-sol`) | The orchestrating session, after calibration 1 failed, under the owner's general instruction to continue. The owner did not name this swap. | Declared before the run as a judge-qualification step, not a retry: one attempt, and no further judge swaps, re-runs or rubric or control edits, whatever the outcome. | Calibrations 2 and 3 |
| Google judge `agy-gemini-judge` (`gemini-3.1-pro-high`) replaced by `agy-gemini38-judge` (`gemini-3.8-flash-high`) | The owner, relayed by the orchestrating session | The owner's stated preference: Gemini 3.8 is better than 3.1 Pro. Not a rescue, because Gemini 3.1 Pro had scored 1.0 and 1.0 in calibrations 1 and 2. | Calibration 3 |
| Worktree moved from `d4cf738` to `689c7ae` | The orchestrating session | PR #10 was current `main`, and the docs branch must apply cleanly to it. `prompt_arg_adapter.py` differs between the two commits, so calibrations 1 and 2 ran agy through the earlier adapter and calibration 3 through the hardened one. The calibration signature does not cover adapter code. | Calibration 3 |
| Optimizer `codex-sol-optimizer` to `codex-astra-optimizer` (`gpt-6-astra`) | Requested by the orchestrating session; denied by Claude Code's permission check (reason "Modify Shared Resources") | The aim was that no model both proposes rubric changes and judges them. The denial was not retried or worked around. The optimizer stayed `gpt-5.6-sol`, the same model as the OpenAI judge. It was never called, so no result depends on it. | Never |
| Plan narrowed to `concision` only, with no optimizer stages | The orchestrating session, after reviewing the article cited above | See [Limits](#limits). Calibration 3 was ineligible, so the narrowing changed nothing that ran. | Never |

The two local config copies (the run worktree's and the main clone's) therefore differ in the OpenAI judge entry, although they were meant to stay identical. Only the worktree copy was read by any run or probe.

Both judge changes came after results were seen. Calibrations 2 and 3 are not independent replications of calibration 1, and the single-attempt rule limits the selection effect without removing it. Astra failed on a different control than Sol did, so the two OpenAI failures are different defects.

## Commands, exit codes and timing

Commands ran from the repository root in a detached worktree (`git worktree add --detach <worktree> d4cf738`, exit 0; the rubric, controls and skill files the runs read were checked to be LF), on Windows 11 Pro 10.0.26200 with `py -3.11` (Python 3.11.9). The git-ignored local adapter config was copied in. Each calibration used one command, with `N` set to 1, 2 and 3:

```text
py -3.11 -m evaluation.benchmark_v2.automated calibrate --suite evaluation/benchmark_v2/automated/data/controls.json --rubric evaluation/benchmark_v2/automated/data/rubric.json --config evaluation/benchmark_v2/automated/adapters/local-config.json --out .eval-runs/calibration-N
```

| Run | Exit | Start to end | Wall time | OpenAI judge call time, mean (max) | Google judge call time, mean (max) |
|---|---|---|---|---|---|
| `calibration-1` | 0 | 15:41:34 to 15:51:24 | 590 s | 8.2 s (13.2 s) | 28.7 s (84.0 s) |
| `calibration-2` | 0, inferred | 16:10:38 to 16:17:32 | 414 s | 9.1 s (13.1 s) | 16.8 s (31.0 s) |
| `calibration-3` | 0 | 16:48:36 to 16:54:34 | 358 s | 9.3 s (12.6 s) | 13.1 s (46.5 s) |

Exit 0 means the command finished and wrote a report, not that the run was eligible; `calibrate` returns 0 whenever it completes, and eligibility is the `eligible` field of `report.json`. The wrapper script that launched calibration 2 hung after the run finished and never wrote its result file (cause unconfirmed; it was stopped by hand at about 16:44Z, with no child processes and no output). Calibration 2's exit code is therefore inferred to be 0 from the code path and from the complete report on disk, and its times come from file timestamps (first request, last call metadata).

Three single-call probes ran outside any calibration, through the runner's own call function and one calibration control (`edit-deadline-control`, order 1). Each exited 0 with a valid judgment and the labeled winner: an agy preflight at about 15:41Z (17.5 s), `codex-sol-judge` from 16:09:29Z to 16:09:40Z (10.2 s), and `agy-gemini38-judge` from 16:47:50Z to 16:48:03Z (12.7 s). The probe script is a throwaway kept outside the repository.

Total: 99 model calls (3 probes and 96 calibration calls), 49 to the OpenAI family and 50 to the Google family, and about 1,362 s (22.7 minutes) of calibration run time.

| Stage | Status | Reason |
|---|---|---|
| `compare` for `skills/concision` and every other skill | Not run | No eligible live calibration exists, and `compare` requires one (`runner.py`, lines 116 to 120). The plan had also been narrowed to `concision` only. |
| Metric pack (`analyze`) | Not run | It reads a finished comparison report, and none exists. |
| Optimizer probe, `prepare-optimize`, `optimize --rounds 2` | Not run | The gate did not open, and the narrowed plan excluded these stages: with no `development` split, the optimizer would select a rubric on the same eight calibration controls it is shown. |

## Models, pins and tool versions

| Role | Id | Model pin in the command | Called |
|---|---|---|---|
| Judge | `codex-astra-judge` | `gpt-6-astra`, reasoning effort high | Calibration 1 (16 calls) |
| Judge | `codex-sol-judge` | `gpt-5.6-sol`, reasoning effort high | Calibrations 2 and 3 (32 calls) and one probe |
| Judge | `agy-gemini-judge` | `gemini-3.1-pro-high` | Calibrations 1 and 2 (32 calls) and one preflight probe |
| Judge | `agy-gemini38-judge` | `gemini-3.8-flash-high` | Calibration 3 (16 calls) and one probe |
| Writer | `claude-sonnet-5-5-writer` | `claude-sonnet-5-5`, effort high, with a settings override of the inherited effort variable | Never |
| Optimizer | `codex-sol-optimizer` | `gpt-5.6-sol`, reasoning effort high | Never |

A pin is what the command asked for. A model's output does not say which model served it, so the served models are unverified. The Codex banner printed during the Sol probe showed `gpt-5.6-sol`, effort high, sandbox read-only and approval never, which echoes the request. `agy models` listed `gemini-3.8-flash-high` (Gemini 3.8 Flash (High)) and `gemini-3.1-pro-high` (Gemini 3.1 Pro (High)) at 16:48:21Z and 17:02:59Z, so both slugs existed in the catalog. The full commands, with local executable paths, are in the git-ignored local config.

Every recorded reading of `agy --version`, `codex --version` and `claude --version` was agy 1.2.14, codex-cli 0.156.0 and Claude Code 2.1.281: before and after calibration 3 (16:48:36Z and 16:54:34Z), before and after the Sol probe (16:09:29Z and 16:09:40Z), before and after the Gemini 3.8 probe (16:47:50Z and 16:48:03Z), and single readings at 16:01:25Z, 16:28:54Z and 16:45:55Z, with agy alone again at 17:02:59Z. Two gaps remain. Calibration 1 had no version logging; the agy binary's file time is 15:41:04Z, 30 seconds before its first call, so its agy calls ran on 1.2.14 by inference, not by a recorded reading. Calibration 2 has no run-start or run-end reading; the nearest are 16:09:40Z and 16:28:54Z. agy itself moved during the day: the adapter's isolation behavior was measured on 1.2.12 on 2026-09-29, the 15:41Z preflight saw 1.2.13, and calibration 1 onward ran on 1.2.14. Other tools: Python 3.11.9, git 2.50.1.windows.1, gh 2.78.0.

## Evidence hashes

SHA-256 of each calibration's report and records file (lowercase, over the file bytes):

| Cal | File | SHA-256 | Bytes |
|---|---|---|---|
| 1 | `report.json` | `db93e685cd27395ece9287eff6e66dbcbad67f0d8ce8bc7b1dee3e8ee81ffbc1` | 2060 |
| 1 | `records.json` | `b063a7788382d9b42941909bca1a9bea65788ad40434824174688b5c4b0fa23b` | 6029 |
| 2 | `report.json` | `30e8cf01c6b3457ad78d7a7eadbfccac98f6786d559eb4d2eea40a9fa5470e92` | 2056 |
| 2 | `records.json` | `573b455f96b86bd7d732d4c5768ec98c0487130367e374dd60b1167b3b273739` | 6062 |
| 3 | `report.json` | `85cdba486845ccd0b8293879b5355d5331be0aa707ef0355b46e9d003820a380` | 2062 |
| 3 | `records.json` | `bd2c9b7e8da771c4ac0ce904a87f1359a0abb212da86c36a167be66dc5ab98f1` | 6094 |

Provenance fields each report records:

| Cal | `config_sha256` | `judge_signature` |
|---|---|---|
| 1 | `83f6df78e4a9f15a30668e538fc68b3d4aca13c772360b87641029a90d19c226` | `d7809bf222654109d0e45425981c5ffde973f1269391da19dd53c95f01ee9cbb` |
| 2 | `342d880e332087f190794e03d6ac6a42e9df2e743aabf54ca553e8a62b31f232` | `ff99c049a793c4168a46da9f9ba4d2d319bfbd4be95528b1054f428370c7e8df` |
| 3 | `302690d0bcd548e12858bc022b1aa75ad0ce37f17cab350621a23c7d42c199b4` | `4e157b3828ce0ae756a565d40b734e117dc42d0334136b6ac03de7ce2c6b5b76` |

All three reports record `rubric_sha256` `ac0f82baa64ceae37ae9c5cdc41e13e8b87fbcc50c12ac0a64a4caa0e59138ef` and `suite_sha256` `6431398aa1ba73702d65e204824a52562c77377416c26157e8b744c756a1ccb5`, with `candidate_skill_sha256` null and `recommendation` `not_applicable`. The local config is git-ignored, so it is not in the repository; `config_sha256` is the hash of the bytes each run read. The main clone's copy, which no run read, hashes to `4e35ad1f05efe8fa8c2987e3f072cab24367983af525fcb3c375207d8d4121b1`.

The code and data the runs used match the rows of the root `MANIFEST.sha256` at each commit. Paths are under `evaluation/benchmark_v2/automated/`:

| File | SHA-256 |
|---|---|
| `__main__.py` | `fccd0475a4e2a41bcb359e80b16b70f80832e66f358f1e8781923f34c8b1e61c` |
| `runner.py` | `77cca36a776355cf13fa4fad877f7c628ee1a6094bd0d9832f8e71867194b046` |
| `scoring.py` | `6068abcc42cd196df640aeadb13c28e5f000f35c3822b71582f354db372766fc` |
| `adapters/codex_adapter.py` | `8de464b54d45fa4f610d7fb8fd28bafe3b5d697c3477e3e7f7dd4cfc546a635e` |
| `adapters/generic_json_adapter.py` | `1e421252e3232620d23961838c2995030f762502332924ebee604019d905f7df` |
| `adapters/prompt_arg_adapter.py` at `d4cf738` | `6f4504de472b2fdb9f80d3ece5bde9b5a611c670a282b8cb06c2bbca6063e999` |
| `adapters/prompt_arg_adapter.py` at `689c7ae` | `85b6d4dea7dec41fa2b53f3ec4f2b72e29d0a4c05e9525d7b11bc23f1a9f5d47` |

The other rows are identical at both commits, as are `data/rubric.json` and `data/controls.json` (the two hashes above).

## Limits

**Not a verdict, and not a holdout.** The controls are public synthetic checks, so even a passing calibration would not be an expert or held-out quality result (the automated README says the same). Four further reasons the runs cannot support a verdict on any skill, as the orchestrating session gave them after reviewing the article the owner shared:

1. The tasks do not mirror how the skills are used. That is the orchestrating session's judgment from reviewing the tasks; this note did not test it.
2. With one repetition there is no noise estimate. Every call ran once, and the planned comparison used `--repetitions 1`.
3. There is no held-out split. The suite has `calibration` and `test` splits and no `development` split.
4. Rubric optimization would score on the same 8 controls it tunes against. `optimize.py` shows the optimizer the calibration controls as examples (lines 33 and 51) and, with no development split, selects a rubric by accuracy on those same controls (lines 60 to 61). It was not run, in addition to the closed gate.

With 8 controls over 4 documents, one miss moves a score by 0.125, so the 0.90 threshold in practice requires 8 of 8.

**Residual exposure.** Two global instruction files on the operator's machine still reached the judge calls. The Codex adapter cannot skip `~/.codex/AGENTS.md`, and agy offers no option to skip `~/.gemini/GEMINI.md` or its built-in skills listing; the automated README lists both as residual exposure. Both files exist on this machine (481 and 558 bytes, last modified 2026-08-21, before this run). They hold an outbound HTTP User-Agent rule, and the agy file adds one line about running commands; neither contains writing-style or quality guidance. The Codex isolation options were measured on Codex CLI 0.156.0, the version used here. The agy isolation was measured on agy 1.2.12 and was not rechecked on 1.2.14 or with Gemini 3.8. The agy prompt, which contains the text under review, is a command-line argument that any local process can read while agy runs.

**Provenance.** The calibration signature hashes each judge's id, family and command, including model and effort flags. It does not cover the writer or optimizer commands, tool versions, adapter code, or a provider changing behavior behind unchanged arguments. All of those apply here: agy changed version during the day, PR #10 changed `prompt_arg_adapter.py` between calibrations 2 and 3, and the pins are requests rather than verified served models. `CLAUDE_CODE_EFFORT_LEVEL=max` was set in the operator's shell. The writer command overrides it, but the writer never ran, so that override was not exercised.

## Open decision

This note does not choose. Each option needs a fresh calibration under a new `--out`, and each is a change after seeing results, to be disclosed like the two judge changes.

1. Change the validator to accept a tie with empty evidence, and change the automated README (line 36, "a tie may cite one") to match.
2. Change the Codex and generic adapter prompts, and the Codex output schema, to require at least one quote for a tie.
3. Replace the tie control with another labeled control. Dropping it leaves 7 labeled controls, below the 8-control minimum, and any replacement changes the suite hash.
4. Use a different OpenAI-family judge, which repeats the judge-selection issue described above.

Options 1 and 2 change shipped code or prompts and need review. The `edit-economy-control` flaw could be fixed in the same fresh calibration, which would be a further change to disclose.

## Where the evidence is

The run directories `.eval-runs/calibration-1`, `.eval-runs/calibration-2` and `.eval-runs/calibration-3` hold the request, response, stderr and metadata bytes of all 96 calls. They are git-ignored and are not part of this change. They exist in the run worktree and in a copy outside the repository; `git worktree remove` deletes ignored files along with the worktree, so keep the copy. The hashes above identify each report and records file.

## Local verification of this change

This change adds this note, adds one sentence to `evaluation/status/README.md`, and regenerates the root `MANIFEST.sha256`. No code, data, rubric, control or workflow file changed. The checks below ran on Windows 11 Pro 10.0.26200 with Python 3.11.9 after the last edit.

| Command | Result |
|---|---|
| `py -3.11 scripts/verify_manifests.py` | Exit 0. |
| `py -3.11 scripts/validate_portfolio.py` | Exit 0: 252 principles, 7 skills, 84 skill fixtures, 44 portfolio fixtures, 8 communication evals. |
| `py -3.11 -m unittest discover -s tests -p 'test_*.py'` | 102 tests ran; 99 passed and 3 skipped (one test that needs POSIX signals, and two symlink tests that need a Windows privilege this machine lacks, WinError 1314). |

Local checks do not establish remote CI. The pull request's own checks (Ubuntu and Windows, Python 3.11 and 3.14) are the remote record.
