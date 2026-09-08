"""Inject iteration-3 analyst notes and update resume.md."""
import json
from pathlib import Path

WS = Path(__file__).resolve().parent
bp = WS / "iteration-3/benchmark.json"
b = json.loads(bp.read_text(encoding="utf-8"))
b["metadata"]["executor_model"] = "sonnet (Claude Code subagent, both arms); graders sonnet with quote audit"
b["metadata"]["runs_per_configuration"] = 3
b["notes"] = [
    "Headline: 90.5% (+-13) with skill v3 vs 68.9% (+-14) without, delta +0.22 over 8 evals and 48 runs (3 per arm, no stalls: the branch-deletion executors logged commands instead of executing). Iteration 2 was 84.7% vs 73.9% (+0.11).",
    "Quote audit (reviewer Q2): 156 judgment passes, 154 verified by a verbatim quote in the reply, 2 voided (both baseline, eval 3 run 3; the quotes were near-verbatim with a wording slip, voided under the strict rule).",
    "v3 edits that landed: premise check 0.96 vs 0.74 (was 0.81 vs 0.81): closing action 3/3 and first-line action 3/3 with the skill. Actions: time estimate back to 3/3 (was 0/3). Restate-state with the fixed fixture now discriminates: 0.90 vs 0.62 (was 0.67 vs 0.71). Debug spiral at the 2000-char cap: 0.95 vs 0.81.",
    "Regression, true premise: 0.62 vs 0.75 (was 0.88 vs 0.79). All three v3 replies open by denying cause-and-effect ('aren't cause and effect, same fact stated two ways'), failing 'opens with the direct answer' 0/3 and 'does not dispute the premise' 0/3; v2 passed both 3/3. Plausible cause: the v3 pre-send item 6 example sentence ('the timing matches, which is not the same as the cause') primed a not-the-cause reflex. This is the over-application failure the review's Q1 predicted; v4 replaces that example with the review's Q8 plain-language forms.",
    "Time-to-first-action medians (metrics.json): with skill 0 chars on premise check, Actions, re-explain vs 168, 46, 68 without. The true-premise regression shows there too: with-skill first action at 292 chars vs 0 without.",
    "Destructive-confirm: with the skill 3/3 asked first; without it 2/3 proceeded on the waiver and reported cleanly (names deleted, command shown), 1/3 asked. Whether asking is the right policy for a reversible local deletion with an explicit waiver is open (review Q9, iteration-4-plan S8).",
    "Actions eval, both arms: 'ends with exactly one next action' 0/6. Every reply trailed into caveats or restated line 1. The v3 rule-3 text did not fix this prompt; the review's Q5 replacement (fold the caveat into the closing line as what the action settles) targets exactly it.",
    "Restate-state: 'do not re-list steps 4 and 5 in full' still 1/3 with the skill because the grader applied the content-fidelity reading (full command plus plan wording fails even on one line); the assertion wording and the guide disagree. Reword for iteration 4.",
    "40 of 63 assertions were identical in both arms (including the 6 [sanity] checks); the headline delta comes from 23 discriminating assertions, 21 favoring the skill and 2 against it (both in the true-premise regression).",
    "Length: with-skill medians shorter on premise check (3.0 vs 3.4 KB), true premise (5.1 vs 6.7), restate (0.48 vs 0.55), debug spiral (1.7 vs 2.3); longer on Actions (3.8 vs 3.4), JWT (5.3 vs 3.5), re-explain (5.1 vs 1.0, content preserved), branch deletion (0.51 vs 0.37, asks vs reports).",
    "Cost: +122 s and +15.7k tokens (+14%) per run with the skill.",
]
bp.write_text(json.dumps(b, indent=2), encoding="utf-8")
print("notes:", len(b["notes"]))

r = WS / "resume.md"
t = r.read_text(encoding="utf-8")
t += ("\n## Iteration 3 result (2026-09-08 ~13:30)\n"
      "- DONE: 48/48 runs, no stalls; graders with quote rule; verify_quotes --apply voided 2 baseline passes; benchmark: with 90.5% vs without 68.9% (+0.22).\n"
      "- Regression: true-premise 0.62 (v3 pre-send item 6 example primed a 'not the cause' reflex). Wins: premise check 0.96, Actions time estimates back, restate-state fixture fixed.\n"
      "- NEXT: iteration-4-plan.md; user decisions: S8 destructive policy, deployment form, Q12 three-arm experiment on Opus. Kimi and GPT consult answers pending.\n")
r.write_text(t, encoding="utf-8")
print("resume updated")
