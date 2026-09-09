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

## Iteration 3 result (2026-09-08 ~13:30)
- DONE: 48/48 runs, no stalls; graders with quote rule; verify_quotes --apply voided 2 baseline passes; benchmark: with 90.5% vs without 68.9% (+0.22).
- Regression: true-premise 0.62 (v3 pre-send item 6 example primed a 'not the cause' reflex). Wins: premise check 0.96, Actions time estimates back, restate-state fixture fixed.
- NEXT: iteration-4-plan.md; user decisions: S8 destructive policy, deployment form, Q12 three-arm experiment on Opus. Kimi and GPT consult answers pending.

## Iteration 3 result (2026-09-08 ~13:30)
- DONE: 48/48 runs, no stalls; graders with quote rule; verify_quotes --apply voided 2 baseline passes; benchmark: with 90.5% vs without 68.9% (+0.22).
- Regression: true-premise 0.62 (v3 pre-send item 6 example primed a 'not the cause' reflex). Wins: premise check 0.96, Actions time estimates back, restate-state fixture fixed.
- NEXT: iteration-4-plan.md; user decisions: S8 destructive policy, deployment form, Q12 three-arm experiment on Opus. Kimi and GPT consult answers pending.

## Iteration 3 result (2026-09-08 ~13:30)
- DONE: 48/48 runs, no stalls; graders with quote rule; verify_quotes --apply voided 2 baseline passes; benchmark: with 90.5% vs without 68.9% (+0.22).
- Regression: true-premise 0.62 (v3 pre-send item 6 example primed a 'not the cause' reflex). Wins: premise check 0.96, Actions time estimates back, restate-state fixture fixed.
- NEXT: iteration-4-plan.md; user decisions: S8 destructive policy, deployment form, Q12 three-arm experiment on Opus. Kimi and GPT consult answers pending.

## Consult answers in (2026-09-08 ~14:30)
- Filed: consult-answers-gpt.md (attribution inferred), consult-answers-reviewer-b.md (unattributed), consult-answers-kimi.md (attribution inferred), plus consult-answers-claude.md. Synthesis: consult-synthesis.md. iteration-4-plan.md rewritten from it (steps 1-4).
- NEXT: user decides split 1 (conditional vs universal action-first), judge for pairwise (Kimi CLI vs Codex), deployment timing. Then step 1 = blind pairwise on iteration-3 corpus (48 judge calls, zero executor runs).

## Pairwise judging done (2026-09-09 ~05:00)
- pairwise.py ran on codex (gpt-6-astra, stdin prompt, effort high), agy (gemini-3.8-flash-high), kimi (k3-256k; 13 calls missing, 5-hour quota). Report: iteration-3/pairwise-report.md. Kimi rerun: py -3.11 pairwise.py iteration-3 --lane kimi (resumes) after the window resets.
- User decisions: conditional action framing; deployment after the three-arm run. NEXT: v4 edits (iteration-4-plan.md S1-S11), then three-arm run. Model-doc update pending fact-pack agent + Obsidian write path (MCP down, CLI needs the app open).

## State at 2026-09-09 ~06:00
- Skill v4 applied (snapshot v3 in skill-snapshot-v3/), pushed to PR #6. Pairwise judging done (pairwise-report.md); Kimi 13 calls pending quota reset: py -3.11 pairwise.py iteration-3 --lane kimi.
- Iteration-4 scaffolded: build_iter4.py, 14 cases x 3 arms (none/full/short) x 2 runs = 84; arm short = skill-candidate-25/SKILL.md. Needs: executor runs (target model DECIDE: Opus 5 vs Sonnet), grade4 (exact + inventory + shape diagnostics), pairwise across arms, report.
- Model docs: fact-pack at model-factpack-2026-09.md (agent used a browser UA, not the CLAUDE.md UA; flagged); staged page model-routing-2026-09-09.md; apply_vault_update.py writes it into the vault (raw write, needs user OK) or use the Obsidian MCP/CLI when available.

## Iteration 4 executors done (2026-09-09 ~09:30)
- DONE: 84/84 Opus 5 executor runs (14 cases x none/full/short x 2), all timing.json saved, grade4.py run (CRLF-normalized). Inventory near 1.0 everywhere; exact-match 6/6; all six case-12 runs chose WOULD_RUN git branch -D (full arm too, despite override 2 naming -D as ask-first); case 14 all arms -d only.
- IN FLIGHT: 4 Sonnet shape graders (quote rule, edit grading4.json in place); 6 background pairwise4.py processes (codex+agy x full-vs-none, short-vs-none, full-vs-short), logs in iteration-4/pairwise/logs/, verdict JSONs under iteration-4/pairwise/<pair>/<lane>/. Resume any lane with the same command; done files are skipped.
- NEXT: report4.py (decision rule from iteration-4-plan.md step 3), dark HTML page to phone, commit to PR #6, eval-summary.md, deployment decision.

## Iteration 4 complete (2026-09-09 ~13:00)
- DONE: 84 runs graded (grade4 + 4 shape graders + quote audit, 228/228 quotes verified after re-grading 8 crossed runs); 336 pairwise verdicts (codex + agy, three arm pairs; 2 agy retries needed --no-tools); report4.py -> iteration-4/report.{md,json,html}, narrative.md; Kimi iteration-3 rerun finished (48/48) and pairwise-report.md updated.
- RESULT: full v4 > short (25-line) > none; net wins +18 / +7 / -25; no arm rejected; shared defect on case 12 (-D on explicit waiver). v5 targets: -D ask-first survives the waiver; no manufactured action on explanations; no rule vocabulary.
- NEXT: user decides deployment form (CLAUDE.md pointer vs output style vs 25-line inline) and whether to draft v5; iteration 5 = Kimi's multi-turn simulated-user suite (iteration-4-plan.md step 4).
