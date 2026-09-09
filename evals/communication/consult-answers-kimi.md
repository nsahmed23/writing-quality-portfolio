# Consult brief answers (Kimi, attribution inferred)

Provenance: forwarded by the user on 2026-09-08 as the third of three reviews in one message. Attribution to Kimi (k3) is inferred from the "Confident: / Guessing:" format the brief requested and the absence of repository citations; the user has not confirmed it. Reproduced verbatim below.

---

1. Partly sound, but only as an internal shape-compliance check. It tells you whether the skill changes reply geometry in the direction the rules specify. It does not tell you whether that geometry is useful, correct, or preferred. Automatable additions I would use:
   · Blinded pairwise preference judging on a sampled subset.
   · Command/task checks: for prompts that produce shell commands, parse and execute them in a sandbox and score correctness/paths.
   · A "next message confusion" classifier on multi-turn logs: after the reply, would the user still need to ask "what next?" or "what does that term mean?"
   · Report per-assertion deltas and drop non-discriminating assertions from the denominator.
     Confident: assertion pass rate is necessary but not sufficient. Guessing: pairwise preference will reveal more than pass rate.
2. Cheapest material change: use a different model family as the grader/judge, while keeping executors on Sonnet. That breaks the worst circularity for roughly one extra grading pass. If cost is tight, dual-grade a random 20% with an external model and escalate only disagreements. Also freeze the assertion guide before generation and have the examples written by someone other than the assertion author.
   Confident: changing the grader model family is the cheapest meaningful change. Guessing: dual-grading 20% is enough for this stage.
3. Drop:
   · "explain JWT auth, is it true you can't log out?" — near tie, non-discriminating.
   · 5-step plan, "did 1 and 2, next?" — redundant fixture step; the skill's disagreement was correct, but the eval is not measuring what it should.
   · Three "still broken" Playwright turns — the 1200-character cap invalidated the runs; after fixing that, it could return.
   Two missing prompts:
   · "My deploy returns 502 after I added caching. Is caching the cause, and what should I do first?" — tests sequence-vs-cause, unverified premise, and action-first under uncertainty.
   · "Set up local Postgres with SSL for Django on macOS. I've never done this." — tests multi-step folding, prerequisite commands, fallback branches, time estimates, and list caps.
4. Yes, worth it on a sample, not all 46 runs. Blind pairwise comparison measures preference rather than assertion compliance, which is closer to the skill's actual goal.
   Single judge question:
   "Which reply would you rather act on right now, and why?"
   Forced choice, plus a one-sentence reason.
   Confident: this is more informative than most current assertions. Guessing: human judges would be better but external-model judges are a good cheap first pass.
5. S2 is right. S1 is mostly right but overcorrects: it can force a next action even when the caveat makes that action unsafe or ambiguous.
   Exact replacement for S1:
   "End with the one next action. Put caveats immediately before it. If a caveat makes that action unsafe or ambiguous, end with the one diagnostic question instead."
   Confident: this removes the closing-action/unverified conflict. Guessing: S1 as written would still overforce actions in risky cases.
6. These 25 lines:

```text
1. Lead with the next action; if it uses an unfamiliar term, gloss it in the same line: "Run X to see which process holds port 8080 (EADDRINUSE means the port is already taken)."
2. Make multi-step work numbered actions: one bounded action per item, one line per item, not numbered headings with paragraphs.
3. Use the fewest steps that still work; folding a step keeps its command (e.g., `mkdir -p .github/workflows`).
4. Brevity removes filler and tangents, never commands, fallback branches, time estimates, or current state.
5. End with the one next action.
6. Skip the closing action only when the reply is one action with nothing else open; branches, diagnostics, and caveats still end by naming what to do now.
7. Put caveats immediately before the closing action; if a caveat makes that action unsafe, end with one diagnostic question.
8. Finish the first issue before offering a second; offer the second separately.
9. Restate state every turn: "Step 3 of 5 done."
10. Give a time estimate in concrete units in one clause right after the first step: "This takes about 5 minutes."
11. Make completed work visible concretely: "You will have a .github/workflows/ci.yml file."
12. Report errors matter-of-factly; no "Uh oh."
13. Cap lists at five; split and rank rather than truncate.
14. No preamble, recap, or closing pleasantries.
15. Explain for an intelligent adult; define a term in the sentence where it first appears.
16. State the limits of simplifications; no forced analogies.
17. On "I didn't follow that," re-explain rather than re-answer: keep facts verbatim, no new information, flatten structure.
18. Verify premises; keep sequence separate from cause; say what is unverified.
19. When asked to explain, give the full explanation.
20. Confirm before destructive actions unless the user waived confirmation and the action is low-risk and reversible.
21. After three "still broken" turns, stop patching; name one assumption and ask one diagnostic question.
22. When a rule fights the task, the task wins; keep the reply shape.
23. Do not use rule names as labels; say "this happened after that, not because of it" instead of "sequence, not cause."
24. If the reader asks for the next action, give it immediately; don't re-explain completed steps.
25. Keep the reply as short as it can be while still taking the next correct action.
```

7. Yes. Replace the brevity/fewest-steps language with this exact formulation:
   "Brevity means fewer words, not fewer necessary details. Cut filler, preamble, recap, and tangents. Never cut a command, a fallback branch, a time estimate, the current state, or a term's definition."
   That directly names the failure mode and reverses the model's current deletion bias.
8. S4 is necessary but not sufficient. It repeats the names while forbidding them, which still primes them. The skill should avoid quotable rule labels where possible.
   Exact replacement for S4:
   "Do not name the rule in the reply. Write the user-facing sentence instead: 'I can't verify that' rather than 'premise'; 'this happened after that, not because of it' rather than 'sequence, not cause.'"
   Confident: S4 alone will not stop leakage. Guessing: rewriting the rules with user-facing exemplars reduces leakage materially.
9. Not right for git branch -d on merged branches. The line should be risk/reversibility and blast radius, not the word "delete."
   Exact override replacement:
   "Confirm before destructive actions unless the user explicitly waived confirmation, the action is reversible or guarded, and the reply lists the exact targets. Still confirm for irreversible or broad actions: force push, git branch -D, rm -rf, database deletes, or anything outside the user's own branches."
   Confident: the current rule overblocks. Guessing: with this wording, the model would list candidates and execute git branch -d when the user says "just do it."
10. On Opus, I would expect the baseline to be closer to desired shape already, so the measured with-skill delta may shrink. Opus should also handle conflicting rules better, leak rule vocabulary less, and be less likely to overblock low-risk destructive actions.
    I distrust the destructive-action result most: it is n=1, the baseline stalled on the sandbox permission prompt, and risk-compliance is exactly where model-family differences matter. The Playwright length-cap result is also untrustworthy because the cap assertion was invalid.
    Confident: Opus will not need the skill for basic shape. Guessing: the skill's value will move from shape toward state restatement, fallback preservation, and override behavior.
11. Yes. Rules 1–3 and 5 can fight a deliverable-text request. If the user asks for edited prose, the first block should be the edited text, not an action; numbering edits as steps and adding a closing next action is noise.
    Exact routing addition:
    "For text-edit requests, put the edited text first, then any explanation. Action-first and closing-action rules apply only to wrapper prose, not to the deliverable."
    Confident: this is the main conflict beyond the five-item list cap. Guessing: state restatement is harmless for editing tasks.
12. Run a multi-turn simulated-user suite before iteration 4. Ten conversations, three to five turns each, forcing one of three overrides per conversation: "I didn't follow that," "still broken," or "just do it." Score whether each turn preserves facts/commands, gives one next action, and either resolves or correctly asks one diagnostic question. Judge with an external model.
    That would most change the skill because the current harness is mostly single-turn and scores shape, not recovery across turns.
    Confident: this would expose problems in S1 and the destructive override. Guessing: the largest changes would land in the fallback/still-broken rules, not in rule 1.
