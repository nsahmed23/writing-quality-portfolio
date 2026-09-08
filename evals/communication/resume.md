# communication skill evals: resume

Skill: C:\Users\nsahm\.claude\skills\communication\SKILL.md
Workspace: this directory. Layout: iteration-N/eval-<id>-<name>/{with_skill,without_skill}/run-1/{outputs/response.md, timing.json, grading.json}
Eval model: sonnet (both arms). Baseline = no skill.

## Status
- [x] iteration-1 dirs + eval_metadata.json written (2026-09-08)
- [x] 6 executor runs (3 evals x 2 arms) -> outputs/response.md (done 2026-09-08)
- [x] timing.json per run (all 6 saved)
- [x] grading.json per run: script (26) + grader agent (28); validated, no nulls
- [x] benchmark.json + benchmark.md: with 96.3% vs without 70.4% (+0.26); 10 analyst notes injected (strip 'timing' from grading.json before aggregating so real tokens are used)
- [x] viewer launched on http://localhost:3117 (generate_review.py, server mode; feedback saves to iteration-1/feedback.json on Submit All Reviews)
- [ ] NEXT: user reviewing on phone via review-static.html (viewer feedback.json will not exist). Proposed edits + 9 new evals + method changes in iteration-2-plan.md; apply after user picks, then run iteration-2 (3 runs/arm) with --previous-workspace iteration-1

## Iteration 2 (started 2026-09-08)
- Skill edits E1-E4 applied to SKILL.md (v1 snapshot in skill-snapshot-v1/). Baseline arm = no skill.
- 8 evals x 2 arms x 3 runs = 48 executor runs, launched in waves of 12: wave1 = evals 0,1 (running); wave2 = 2,3; wave3 = 4,5; wave4 = 6,7 (eval 6 executors may run git inside their fixture repo only).
- Per notification: py -3.11 timing.py iteration-2 <eval-dir> <arm> <run> <tokens> <ms>
- After all runs: py -3.11 grade.py iteration-2; grader agents (one per eval, 6 runs each) fill NEEDS_JUDGMENT; aggregate; notes; static HTML + darken.py; SendUserFile.
- Dark-mode review page: darken.py <in.html> <out.html>; iteration-1 dark page already sent to phone.

## Iteration 2 result (2026-09-08 07:45)
- DONE: 46/48 runs graded (eval-6 baseline run-2 stalled on permission prompt, run-3 deleted branches then stalled; both stopped). benchmark.json: with 84.7% vs without 73.9% (+0.11), 13 analyst notes. Dark static page: iteration-2/review-static-dark.html (sent to phone).
- NEXT: iteration-3-plan.md (skill edits S1-S5, eval fixes V1-V6). Apply S1-S4 + V1-V3, rerun with --previous-workspace iteration-2.

## Iteration 3 (started 2026-09-08 ~10:20)
- Skill v3 = v2.1 + S1-S4 (snapshot of v2.1 in skill-snapshot-v2/). Eval fixes V1-V3 in build_iter3.py (imports build_iter2). Baseline arm = no skill.
- Wave 1 launched: evals 0,1,2 (18 runs). Remaining: evals 3-7 (30 runs) as slots free; eval 6 executors must also write outputs/commands.txt (RAN:/WOULD_RUN: lines) and never execute a delete.
- Consult brief (consult-brief.md) sent to phone and committed to PR #6 (writing-quality-portfolio, branch feat/communication-skill-evals). Outside answers feed iteration 4.
- After runs: timing.py per notification; grade.py iteration-3; grader agents (eval 7 idx2 is judgment now); aggregate; notes; static+dark page; SendUserFile.
