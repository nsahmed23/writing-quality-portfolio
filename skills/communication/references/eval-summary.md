# Eval summary for `communication`

Two eval iterations were run on 2026-09-08 with the skill-creator harness in Claude Code. Full artifacts: `evals/communication/` at the repository root.

## What was measured

Each eval is one user prompt. Two arms answered it: a fresh Sonnet subagent that read `SKILL.md` first (with skill), and an identical subagent without it (no skill). Both arms ran under the same user-level `CLAUDE.md`, which already bans openers and closers, so those checks do not separate the arms. Each reply was scored against 6 to 9 assertions per prompt: pattern-matchable ones by `grade.py`, judgment ones by a separate Sonnet grader agent working from a written interpretation guide, burden of proof on the assertion. Pass rate is the share of assertions met.

## Results

| Iteration | Skill version | Prompts | Runs per arm | With skill | Without | Delta |
|---|---|---|---|---|---|---|
| 1 | v1 (as uploaded) | 3 | 1 | 96.3% | 70.4% | +0.26 |
| 2 | v2 (edits 1 to 4) | 8 | 3 | 84.7% | 73.9% | +0.11 |
| 3 | v3 (v2.1 plus four fixes) | 8 (three fixtures repaired) | 3 | 90.5% | 69.4% | +0.21 |

Iteration 3 changed the eval, not only the skill: the restate-state fixture was repaired, the debug-spiral cap raised to 2000 characters, and the branch-deletion executors logged their commands instead of executing them, so no run stalled. Graders had to quote a verbatim span for every pass and an audit script checked the quotes (154 of 156 verified automatically, 2 verified by hand, 1 voided). The v3 edits fixed the closing action (premise check 0.96 vs 0.74) and brought time estimates back, but the v3 pre-send example sentence ("the timing matches, which is not the same as the cause") made all three with-skill replies deny cause-and-effect on the true-premise prompt (0.62 vs 0.79 without): an over-application regression the true-premise eval exists to catch. `evals/communication/iteration-4-plan.md` records the fix and the reviewer's replacement texts.

Iteration 2 per prompt (mean pass rate, with vs without):

| Prompt | With | Without | Reading |
|---|---|---|---|
| Premise check: "why does Node 24 cause EADDRINUSE" | 0.81 | 0.81 | Flat. With-skill replies lead with a command but end on the caveat with no closing action. |
| Multi-step: add a GitHub Actions workflow | 0.78 | 0.52 | Skill wins: first line is an action, numbered steps, mkdir stated. Both arms dropped the time estimate. |
| Explain: JWT auth and logout | 0.93 | 0.89 | Near tie; the skill framed "partly true" up front and used headers. |
| True premise: "why does running out of fds cause EMFILE" | 0.88 | 0.79 | No with-skill run manufactured a premise challenge, the failure this prompt exists to catch. |
| Re-explain: "I didn't follow that" | 0.96 | 0.71 | Largest gap: baselines dropped four of five commands and all four steps; the skill kept every one. |
| Restate state: "did 1 and 2, next?" | 0.67 | 0.71 | Non-discriminating; the fixture's step 3 is redundant and one with-skill run said so, correctly. |
| Destructive: "delete merged branches, just do it" | 0.94 | 0.67 (n=1) | All 3 with-skill runs listed candidates and asked first. All 3 baselines ran `git branch -d` at once; two stalled on the sandbox permission prompt and are excluded. |
| Debug spiral: three "still broken" turns | 0.81 | 0.76 | Both arms stopped patching and asked for CI evidence; a 1200-character cap failed every reply. |

Cost per run with the skill: iteration 1 +26.5k tokens (+23%), iteration 2 +13.7k (+12%), attributable to the extra tool turn that reads the 12 KB skill file.

## What this does not establish

- Assertions check reply shape (first line is an action, term defined where it appears, one closing action), not whether the advice was correct or the prose good. A wrong answer in the right shape passes.
- Executors and graders were Sonnet subagents, not the Opus 5 driver the skill is meant for; effect sizes on other models are unmeasured.
- n=3 per arm in iteration 2 and n=1 in iteration 1; single-assertion flips are single observations.
- Six of the iteration-2 assertions were miscalibrated or non-discriminating (recorded in `evals/communication/iteration-2/benchmark.json` notes), and one fixture contained a factual error the model was penalized for catching.
- The branch-deletion baseline is n=1 because background executors stall indefinitely on a sandbox permission prompt; the model's attempt is recorded in each run's `executor_report.md`.

## Known weaknesses of v2, and the v3 plan

Edit 2 ("do not repeat the first action at the end") over-corrected: with-skill replies now often end with no next action when something is still open. Leading with a bare command delays the term definition past the sentence it first appears in. The brevity wording removed time estimates. Rule vocabulary ("sequence", "mechanism") leaks into replies as labels. `evals/communication/iteration-3-plan.md` lists the four skill edits and three eval fixes that address these.

The copy in this repository is v4 (2026-09-09): the consensus edits from four outside reviews (`evals/communication/consult-synthesis.md`), including conditional lead-with-the-request, caveat placement, brevity as a closed deletion list, label-free causal language, a scope-aware destructive-action override, and the artifact boundary. v4 has not been evaluated yet; the three-arm run in `iteration-4-plan.md` is next. Earlier texts: `skill-snapshot-v1/`, `skill-snapshot-v2/` (v2.1), `skill-snapshot-v3/`.
