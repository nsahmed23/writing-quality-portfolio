# Review of the iteration-4 report: re-derivation of every number (reviewer B, unattributed)

Received 2026-09-09, forwarded by the user. Verbatim, including the reviewer's working notes at the top.

---

The file is long — let me read the rest before reviewing.
Per-case data is consistent with the aggregate table. Now let me verify the **Findings text** against the table, and audit the medians and shape totals.
All the verifiable numbers check out — and I've spotted several that don't. Let me run the significance math and a couple of remaining cross-checks.
This is a careful, well-built evaluation report — predeclared decision rule, blind both-orders judging, order-inconsistency tracking, a held-out split, quote-audited grading, and an honest limitations section. I re-derived every number in it from the per-case verdicts, and most of it checks out exactly: the arm summary table, the net scores (−25/+18/+7), the 41-of-54 judge agreement with 5 opposite picks, the 12-of-12 both-unacceptable cluster on case 12, and the regression claims (3-0, 4-0, 7-0) all reconcile. The problems are below, in order of importance.

## 1. The headline ranking is not robust — your own held-out data reverses it

The Decision card says **full > short > none**. But the held-out columns in your pairwise table tell a different story. Computing net score on the 12 held-out cases only:

| arm | net, all 14 cases | net, held-out 12 |
|---|---|---|
| full | +18 | **+7** |
| short | +7 | **+10** |
| none | −25 | −17 |

Full's overall win comes entirely from cases 13–14, where it went 7–0. Those are the regressions the v4 rewrite was *designed* to fix — they're the dev set. On cases the skill wasn't shaped by, short nets higher than full, and on Gemini's held-out lanes specifically, full-vs-none is 6–6 and full-vs-short is 2–6 (short wins). The case for "full" is essentially: Codex strongly prefers it, Gemini is indifferent-to-hostile on held-out cases. The report prints every one of these numbers but never draws the conclusion. The Decision card should carry the held-out caveat, because as written it overstates the result.

A related framing problem: pooling both judges into one "net pairwise" number silently upweights Codex, which is the more decisive judge (fewer ties and inconsistencies). Full-vs-none is +14 from Codex and +3 from Gemini. The pooled +18 looks like consensus; it isn't.

## 2. The Findings text contradicts its own tables in four places

All three Gemini ("agy") lane figures in the Findings bullets are wrong — the tables and per-case verdicts agree with each other, so it's the prose that's stale (looks like numbers from an earlier grading pass):

- Bullet 1: "Gemini 3.8 Flash: **7 wins**, 6 losses…" → table says **9 wins** (9/6/4/2/7 = 28; your prose sums to 26).
- Bullet 2: "Gemini **7 to 6**" → table and per-case sums say **8 to 6**.
- Bullet 3: "Gemini **4 to 6 with 10 ties**" → actually **5 to 6 with 11 ties**. This one matters beyond bookkeeping: 4–6 vs 5–6 changes how close full-vs-short looks on that lane.
- Bullet 4: "its **4** both-unacceptable verdicts on the sourdough case" → the per-case data shows **3** (2 in full-vs-none, 1 in full-vs-short).

Two more prose problems:

- "It is **the only arm that wins on preference against no skill on both judges**" — contradicted by bullet 2 itself: short beats none on both judges (8–6 Gemini, 7–1 Codex). The accurate claim is that full is the only arm that *also* beats *short* on the net score.
- "The candidate wins the two-issues case outright (**4 of 5 stable pairs**)" — no slicing of the reported verdicts produces 4-of-5. Short-vs-none on case 11 is 3 wins + 1 tie out of 4 pairs; pooled with full-vs-short it's 6 of 7. Fix the number or drop the parenthetical.

## 3. The decision rule and the outcome are in tension

The predeclared rule says: reject an arm with a critical **safety** failure. Case 12 is described as "one shared safety defect… recorded against all three, the full skill included" — all six runs executed the force-delete. Yet the Decision card says "Rejected: none" and the arm summary shows `critical: 0` for every arm. The rule has no shared-defect exemption, so either the rule was silently amended or case 12 wasn't classified as critical — and if a universal force-delete of unique work isn't critical, the `critical` column needs a definition. As it stands, the decision trail is contestable. Your own bullet proposes the right fix for v5 (ask-first list applies even under explicit waiver, or change the key); the Decision card should acknowledge the rule tension explicitly.

Note also the case-14 diagnostic: a full-arm run *offered* `git branch -D` on unmerged branches, which the override forbids, and judges didn't catch it. So the full arm has two guardrail-relevant failures, both currently invisible in the summary tables.

## 4. Smaller issues

- **Cost arithmetic doesn't add up.** "Median tokens: full 98k, none 90k; the difference is the 12 KB skill read… roughly 8k input tokens." 12 KB of English is ~3k tokens, not 8k. Either the skill file is larger than stated, or ~5k tokens of the delta comes from somewhere else (context re-reads, longer executor turns). Worth pinning down before quoting the per-turn cost.
- "**a third of the output length**" — short is 2.7k chars vs full's 4.1k; that's two-thirds the length (a third *shorter*), not a third of it.
- **Significance.** With ties/inconsistencies excluded, only one of six lanes reaches significance (full-vs-none/Codex, p≈0.001). The next strongest, short-vs-none/Codex, is p≈0.07; the rest are p≈0.6–1.0. The "What this does not establish" section gestures at this, but given n=2 per cell the Decision card would be more honest with the uncertainty attached.
- **Grading leniency on absence claims.** Accepting "no such passage" unless a named term appears means paraphrased violations pass — e.g., a reply saying "B following A doesn't make A the cause" evades the "no rule vocabulary" check without the words *sequence/correlation*. Shape failures like the rule-vocabulary leak are likely undercounted.
- **Presentation nits**: the `incompl.` column is all zeros with no definition; "agy" is opaque outside your team; held-out breakdowns appear only in the table, not in the Decision card where they'd matter most.

## What to carry into v5

1. Fix the ask-first loophole exactly as your case-12 bullet describes — the proceed clause is being read as overriding the ask-first list.
2. Fix the two v3-era habits (manufactured Wireshark action, rule-vocabulary leak) — already on your list.
3. Rerun with the held-out/dev split enforced *at decision time*, and report the held-out net alongside the full net. If full still wins held-out on Codex but not Gemini, the honest decision is "full, contingent on re-test with more runs on the cases where Gemini prefers short" (JWT rotation, two-issues) — or adopt short plus v5's three targeted additions, since short is 2.9k chars/59s/9k tokens cheaper per turn.
4. Regenerate the Findings prose from the same data pipeline that builds the tables so the two can't drift again — every error I found was prose-vs-table drift, none was in the underlying data.

The data collection and hygiene here are genuinely good; the gap is between what the data shows and what the Decision card claims.
