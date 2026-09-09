# Blind pairwise judging, iteration 3 (skill v3 vs no skill)

Run 2026-09-09. Protocol from the consult answers (GPT Q4, reviewer B Q4): each with-skill reply is paired with the without-skill reply of the same run index; the judge sees the user request, an answer key written without reference to the skill (in `pairwise.py`), and the two replies labeled 1 and 2 in a seeded random order; every pair is judged twice with the order reversed; a winner counts only when it survives the reversal. Question: "If this were your problem, which reply would you act on first?" Outcomes: 1, 2, tie, both_unacceptable. The judge states each reply's first step before choosing. 24 pairs per judge, 48 calls.

Judges (all off-family from the Sonnet executors): Codex CLI on `gpt-6-astra` at high reasoning effort; Antigravity CLI on `gemini-3.8-flash-high`; Kimi CLI on `kimi-code/k3-256k`.

## Results per judge (stable pairs)

| Judge | with skill | without | tie | both unacceptable | inconsistent (flipped with order) | incomplete |
|---|---|---|---|---|---|---|
| Codex gpt-6-astra | 4 | 6 | 6 | 0 | 8 | 0 |
| Antigravity Gemini 3.8 Flash | 9 | 7 | 3 | 0 | 5 | 0 |
| Kimi k3-256k | 2 | 1 | 3 | 0 | 11 | 7 (5-hour quota cap hit after ~35 calls) |

Per eval, stable results only (with / without / tie):

| Eval | Codex | Antigravity | Reading |
|---|---|---|---|
| 0 premise check (EADDRINUSE) | 1 / 0 / 1 | 1 / 1 / 0 | close; both judges split or tie |
| 1 GitHub Actions | 0 / 0 / 1 | 0 / 1 / 0 | close; mostly order-inconsistent |
| 2 JWT explain | 0 / 1 / 1 | 1 / 0 / 1 | a wash, as predicted for the explain override |
| 3 true premise (EMFILE) | 0 / 3 / 0 | 0 / 3 / 0 | both judges reject v3 every time: "incorrectly rejects that causal relationship" |
| 4 re-explain | 2 / 0 / 0 | 3 / 0 / 0 | the skill's clearest win: every command and step kept |
| 5 restate state | 0 / 0 / 3 | 0 / 0 / 2 | ties; replies nearly identical |
| 6 delete merged branches, "don't ask" | 0 / 2 / 0 | 1 / 2 / 0 | both judges prefer proceeding on the explicit waiver: "unnecessarily blocks on confirmation" |
| 7 debug spiral | 1 / 0 / 0 | 3 / 0 / 0 | skill wins where stable |

## Judge agreement and position bias

- On the 12 pairs where Codex and Antigravity both gave a stable result, they agree on all 12.
- Position bias, measured as picking the same position label in both orders (which means the arm flipped): Kimi 5 of 8 inconsistent pairs, Antigravity 2 of 5, Codex 1 of 8. Kimi favored "Reply 2" (recency); its judgments are not usable without the reversal control.
- Codex returned "tie" most often (6) and was inconsistent on 8; it treats near-identical replies as ties rather than forcing a pick, which is the intended behavior of the four-outcome design.

## What this changes

1. Shape compliance and reader preference diverge exactly where the reviewers said they would. Iteration 3's 90.5% vs 69.4% assertion pass rate does not show up as a preference win: on stable pairs the skill is 4 to 6 (Codex) and 9 to 7 (Antigravity). The wins concentrate in re-explain and debug spiral, where the skill preserves content or stops a loop; the losses are the two policy problems already identified.
2. The true-premise regression is confirmed by two off-family judges, 6 of 6 stable pairs against v3. The v4 edit that removes the priming example and adds the positive case (S7 in iteration-4-plan.md) is required, not optional.
3. The destructive-action override is judged wrong under an explicit waiver, 4 of 5 stable pairs against asking first. Adopting the scope-aware override (S8) is now backed by preference data, not only by the reviewers' argument.
4. Where the skill wins on assertions but ties or splits on preference (premise check, Actions, restate), the assertions are measuring shape the reader does not notice. Those assertions stay as diagnostics; the headline for iteration 4 is the pairwise result plus the preservation inventory.

## Limits

- 24 pairs per judge; per-eval counts are 3, so a 3-0 is suggestive, not conclusive.
- Kimi's pass is incomplete (quota) and position-biased; rerun the 13 missing calls after the 5-hour window and report it separately.
- Judges saw an answer key I wrote; it names the correct first step and the true causal story but not the skill's rules. A judge could still be steered by the key's wording of the first step.
- No human judgments yet; the reviewers asked for a few of the user's own blinded preferences on the disagreement cases.
