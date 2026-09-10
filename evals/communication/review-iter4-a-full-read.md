# Review of the iteration-4 report: full read of the 84 replies (reviewer A, unattributed)

Received 2026-09-09, forwarded by the user. Verbatim.

---

What I read: every reply in all 14 cases, every per-run grader note, every pairwise verdict line, the arm and pairwise tables, and the summary. I re-tallied the pairwise tables from the per-case verdict lines. I did not re-run anything.

## 1. The tables are right; one number in the prose is not

The per-case verdict lines add up to the tables exactly: full vs none under Codex 15/1/7/4/1, under Gemini 9/6/4/2/7; the net score of +18, +7, -25 follows. One narrative sentence is wrong: "Preference, full vs none. Gemini 3.8 Flash: 7 wins, 6 losses" should read 9 wins. The held-out figure (6 to 6) is consistent with 9, since all three of Gemini's full wins that are not held-out sit on the two regression cases. The decision does not move.

## 2. Correctness is the unmeasured dimension, and it varies inside arms

Nothing in the harness checks whether a reply is true. The inventory checks presence, the assertions check shape, the judges read for usefulness against a key. Reading the replies turned up seven errors or contradictions that none of those layers touched. They fall on all three arms.

- Case 13, full run-2: after raising the limit from 1024 to 65535 with a linear leak, the app "dies at eighteen hours instead of six." The ratio is 64, so about sixteen days; full run-1 and none run-2 get that arithmetic right.
- Case 13, full run-2 vs full run-1: run-2 says EMFILE from `accept()` becomes an unhandled `'error'` event that exits the process; run-1 and short run-1 say libuv reserves a spare descriptor so `accept()` degrades and the fatal error comes from application code. The second account is the libuv behavior. Same arm, opposite claims, two runs apart.
- Case 4, truncating a vector clock: none run-2 and full run-2 say truncation fails safe (false conflicts only); full run-1 and short run-2 say it can flip the ordering and let an older version overwrite a newer one, and full run-1 gives the worked example. Both stories ship inside the full arm.
- Case 1, short run-1: a certificate without a SAN "can never satisfy verify-full." libpq falls back to the Common Name when no SAN is present, which full run-2 states correctly.
- Case 3, `--natural-primary`: three replies include the flag with no warning (none run-2, full run-1, short run-1), two warn against it because `auth.User` defines a natural key and user ids get renumbered (none run-1, short run-2), one includes it with the caveat (full run-2). That is divergent advice on a data-integrity flag, and the inventory scored all six at 1.0.
- Case 12, none run-1: the force-deleted commit "stays reachable from the reflog for about 30 days." `git branch -D` deletes the branch's reflog; the other five replies correctly say the commit becomes unreachable and survives only until gc prunes it, about two weeks by default.
- Case 5, short run-2: "the third packet usually carries the client's first request." In practice it is usually a bare ACK, as full run-1 says.

None of these cost a pairwise verdict, because the judges had no way to see them either. The report's decision rule has a rejection clause for "critical correctness failure," but no layer feeds that clause. Two cheap additions would: the case author writes three to five falsifiable traps per case (the claims a plausible reply gets wrong) and a grader checks each reply against them; and a cross-run contradiction check flags any point on which run-1 and run-2 of the same arm assert opposites. The cases above would all have been caught by one of the two.

## 3. The inventory misses are string-matching artifacts

Three of the four inventory misses in the workspace are correct replies scored as incomplete: case 1 short run-2 ("missing: brew install postgresql," the command is `brew install $PG` with `PG=postgresql@18`), case 2 both full runs ("missing: kid," a valid two-secret design the report already notes), and case 12 full run-1 ("missing: main..feat/wip1," when its command log shows `git log --oneline main..feat/wip1` and the reply names the lost commit). On substance the three arms tie at 1.0 on preservation; the 0.976 in the arm table is the matcher, not the skill. Match on the fact, not the spelling, or accept a variable-bearing form.

## 4. Where shape compliance and judge preference part ways, and why

Case 2 (JWT rotation) is the clearest read. Full scored 6/6 on shape in both runs, with the shortest replies in the case (4.4k and 6.1k characters), and lost four of six stable pairs to replies that were less compliant and more complete: a `kid` header design, the leak-versus-hygiene branch, the rolling-deploy hazard, the logging line that turns the wait into a measurement. Judges rewarded completeness on a procedure whose failure modes are subtle. Case 1 and case 3 went the other way, with full's action-first opening and check-closing winning under Codex. So the shaping rules earn preference on procedures where the steps are the content, and lose it where the omitted branches are the content. That is consistent with the v4 brevity edit not yet having removed the compression tendency on the full arm; two runs is too few to call it, but it is the hypothesis the JWT case supports.

## 5. "A third of the length" holds for explanations, not procedures

Median characters (full 4.1k, none 5.1k, short 2.7k) hide a split. On the three ordered procedures short was as long as or longer than full: case 1 9.3k to 9.6k vs 8.9k to 9.2k, case 2 7.3k to 8.3k vs 4.4k to 6.1k, case 3 7.9k to 8.3k vs 5.4k to 5.9k. Short's length advantage comes from the explanations (case 4, 5, 6) and the recovery cases. The cost argument for the short deployment form is therefore a cost argument about explanations, where the judges tied or leaned short anyway.

## 6. Case-level notes the summary condenses

- Case 12: every one of the six runs inspected `git log main..feat/wip1` before deleting; the command logs show it. What was missing was the pause, not the inspection. The v5 fix is the one already proposed: the ask-first list is absolute, a waiver applies only outside it, and reflog recovery does not count as reversible.
- Case 11: the same skill produced both outcomes. Full run-1 opened with local reproduction and closed with an offer ("Want me to lay out the target tree...") and lost both run-1 pairs; full run-2 opened with trace capture and won both run-2 pairs. Run variance, not arm, decided this case.
- Case 4 run-1 and case 11 run-1: the full arm closed with an offer question. Rule 10 names offers as closers; the pre-send check should treat a closing "Want me to..." as one.
- Case 13: the reframing the none and short arms opened with ("EMFILE is the name of the event, not a consequence") is not false, it is pedantic, and it displaces the mechanism the reader asked for. The judges' verdict against it is reasonable. none run-2 still carries the best single diagnostic idea in the case, the leak-rate arithmetic; the full arm's advantage is placement, not content.
- Case 6: the "mechanism" flag on full run-1 ("with reason 1 or 2 above as the mechanism") is ordinary English use; the "sequence, not a cause" flag on run-2 is the real leak. The v5 wording distinguishing labels applied to the reader's claim from ordinary use handles both.
- Grader consistency: on case 13 "ends with one next action" failed full run-2 for naming two commands back to back and passed none run-2 and both short runs for asking the reader to send back several outputs. Small, but it is the same construction scored two ways.

## 7. What changes in the recommendation

Nothing in the ranking. Three things in what to build next:

1. Add the correctness layer before iteration 5. Author traps per case, plus the cross-run contradiction check. Until then "no arm is rejected by the critical-failure clause" means the clause was never tested.
2. Fix the inventory matcher, then recompute the arm table; full and short tie on preservation.
3. Re-read the JWT case when v5 lands: if the full arm still drops the `kid` design and the leak branch, the closed-list brevity text is not holding on procedures with branches, and rule 2 needs the "keep the branch the reader needs" clause repeated inside it, not only in rule 9.

Unverified by me: the fixture facts themselves (the prompts, repos, and answer keys are not in the report), and the executors' environment. My correctness calls in section 2 rest on my own knowledge of libpq, libuv, Django's serializer, and git, each stated as a specific claim you can check.
