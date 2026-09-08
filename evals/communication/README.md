# `communication` eval workspace

Everything produced while evaluating `skills/communication` on 2026-09-08 with the Claude Code skill-creator harness. Summary and caveats: `skills/communication/references/eval-summary.md`. This directory is the raw material.

## Layout

```
iteration-1/                 skill v1, 3 prompts, 1 run per arm
iteration-2/                 skill v2, 8 prompts, 3 runs per arm
  eval-<id>-<name>/
    eval_metadata.json       prompt + assertions
    with_skill/run-N/        outputs/response.md, grading.json, timing.json, eval_metadata.json
    without_skill/run-N/     same, no skill loaded
  benchmark.json / .md       aggregate pass rates, time, tokens, analyst notes
  review-static*.html        standalone review pages (light and dark) built by generate_review.py
  prompts/                   exact prompt text handed to executors
skill-snapshot-v1/           the skill as uploaded, before any edit
iteration-2-plan.md          findings from iteration 1 and the edits applied for v2
iteration-3-plan.md          findings from iteration 2 and the planned v3 edits and eval fixes
resume.md                    checkpoint log
build_iter2.py               writes evals.json, eval dirs, metadata, and the git fixtures for the branch-deletion eval
grade.py                     mechanical grader; writes grading.json with NEEDS_JUDGMENT for grader-agent items
timing.py                    records subagent token and duration figures from task notifications
darken.py                    dark-mode post-processor for the static review page
finish_iter2.py              injects analyst notes, writes plans and checkpoint
```

The git fixture repositories (`iteration-2/eval-6-destructive-confirm/*/run-N/inputs/repo`) are not committed; `build_iter2.py` regenerates them. Without them, `grade.py` reports the fixture-state assertion for that eval as "fixture repo not found".

## Reproducing a run

1. Copy `skills/communication` to `~/.claude/skills/communication` and this directory to `~/.claude/skills/communication-workspace` (the scripts use those absolute paths).
2. `py -3.11 build_iter2.py` to scaffold `iteration-2` (or edit its `EVALS` list for a new iteration).
3. Dispatch executors: one subagent per run, with the prompt in `eval_metadata.json`; the with-skill arm is told to read `SKILL.md` first and write only the reply to `outputs/response.md`. The exact executor briefs are in `resume.md` and the plan files.
4. On each completion, `py -3.11 timing.py <iteration> <eval-dir> <arm> <run> <total_tokens> <duration_ms>`.
5. `py -3.11 grade.py <iteration>`; then a grader agent fills every `NEEDS_JUDGMENT` entry using `agents/grader.md` from the skill-creator plugin plus the interpretation guide in the plan file.
6. From the skill-creator directory: `py -3.11 -m scripts.aggregate_benchmark <workspace>/<iteration> --skill-name communication`.
7. `PYTHONUTF8=1 py -3.11 eval-viewer/generate_review.py <workspace>/<iteration> --skill-name communication --benchmark <...>/benchmark.json --static <...>/review-static.html`, then `py -3.11 darken.py in.html out.html`.

## Caveats recorded during the runs

- Grading judgments came from Sonnet subagents, one per eval, with a shared interpretation guide; eval 6 was graded inline by the orchestrating session because its baselines stalled. Grader outputs, including their critiques of the assertions, are in each `grading.json` under `eval_feedback`.
- Two iteration-2 baseline runs of the branch-deletion eval stalled on the sandbox permission prompt after attempting `git branch -d`; one had already executed the deletion. Both were stopped and excluded; see their `executor_report.md`.
- `benchmark.json` "tokens" are subagent totals from task notifications, which accumulate per tool turn; they are not reply length. Reply length in characters is `execution_metrics.output_chars` in each `grading.json`.
- The opener and closer assertions passed 100% in both arms in both iterations because the user-level `CLAUDE.md` already forbids them; they are labeled `[sanity]` in iteration 2.
