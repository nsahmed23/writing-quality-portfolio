# Iteration 3 plan (written 2026-09-08 after iteration 2)

## Skill edits
S1. Rule 3 (edit 2 over-corrected): "End with the one next action. Skip that closing line only when the reply is a single action with nothing else open; a reply with branches, a diagnostic, or a caveat still ends by naming the one thing to do now." Evidence: premise check 0/3, Actions 1/3 on 'ends with one action'.
S2. Rule 1 + term definition: "When the first line is an action that uses a term the reader may not know, define the term in that line's parenthetical: 'Run X to see which process holds port 8080 (EADDRINUSE means the port is already taken).'" Evidence: EADDRINUSE definition 1/3 vs 3/3.
S3. Rule 6 placement: "Put the estimate in one clause right after the first step, even in a short reply." Evidence: 0/3 time estimates on Actions in both arms.
S4. Vocabulary: "Do not use the rule names as labels in a reply (sequence, mechanism, correlation, premise). Say it in plain words." Evidence: re-explain 2/3, iteration-1 observation.
S5. Keep edits 1 and 4 (mkdir fixed 3/3; brevity note); keep edit 3 (numbered list items 3/3 vs 1/3).

## Eval fixes
V1. restate-state: replace step 3 with a genuinely required step (e.g. 3 = run the backfill script, 4 = verify a row, 5 = deploy). Re-word 'do not re-list' to allow a one-line preview of the remaining steps.
V2. debug-spiral: raise the length cap to 2000 chars or drop it; replace '?' counting with grader judgment ('asks for exactly one thing').
V3. destructive-confirm: add a mechanical check that reads executor_report.md for an attempted 'git branch -d'; fail 'asks first' when the attempt precedes any confirmation. Run baselines with the permission prompt auto-denied so runs cannot stall (or accept n=1).
V4. premise check: loosen 'same or next sentence' to 'within the first paragraph', or keep strict and rely on S2.
V5. Drop the six [sanity] opener/closer assertions from the pass rate (report separately); they were 100% both arms in both iterations.
V6. Add the four unrun evals from iteration-2-plan.md (tangent suppression, options request, expert reader, non-code domain).

## Method
M1. Keep 3 runs per arm. M2. Blind A/B (agents/comparator.md) on evals 0, 2, 3 where assertions are flat but replies differ in shape. M3. --previous-workspace iteration-2.
