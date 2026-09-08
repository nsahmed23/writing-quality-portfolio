# Consult brief answers (reviewer B, unattributed)

Provenance: forwarded by the user on 2026-09-08 as the second of three reviews in one message. The model is not identified; the text uses "Confidence:" lines, knows Claude Code version details (output-style command changes in v2.1.73 and v2.1.91), and closes by answering the three decisions posed after iteration 3, citing "the log". Reproduced verbatim below.

---

# Methodology

**1. Is shape-assertion pass rate a sound measure?**

Yes as the primary metric — the skill governs shape, so shape compliance is the right thing to measure — but insufficient alone, for three reasons: the assertions encode the author's interpretation of the rules (you risk measuring self-agreement, not the rules), binary pass/fail can't detect a reply that complies but reads badly, and nothing checks that the shape didn't damage the content.

Additions that stay automatable, in order of value:

1. **Command-preservation diff.** Extract shell commands and step structure from a reference answer; assert the reply contains all of them. Your iteration-2 fixture bug (redundant step 3) and the v1 mkdir loss are exactly what this catches, and it's pure scripting.
2. **A reader-simulation check.** Give a fresh model *only the reply* and ask "what do you do now?" Assert its answer matches the intended next action. This tests rule 1 and rule 3 functionally instead of syntactically — a reply can lead with an imperative sentence and still leave the reader unsure what to run.
3. **Negative assertions.** You currently test that required elements exist. Add assertions that forbidden shapes are absent (redundant closing restatement, numbered-headings-with-paragraphs). E2's over-correction would have been caught by a negative assertion, and over-correction is the dominant failure mode of skill iteration.
4. **Freeze a regression suite.** Prompts that once discriminated should never leave the suite; iterate only by adding. Right now each iteration's prompts are tuned to the last iteration's failures, which is how you overfit a skill to its own eval.

Confidence: high on 1–3; the reader-simulation check is the one I'd defend hardest. Guess: how noisy the simulator is at n=3.

**2. Cheapest fix for grader circularity**

Swap the grader to a different model family (one API call change) *and* have it work from the raw skill text plus the user prompt, not your interpretation guide. If you can only afford one: replace the guide, not the model. The guide is where your bias actually lives — a same-family grader reading the raw skill will at least misread it differently than you do, while a different-family grader reading your guide inherits your framing wholesale. Second cheap move: report grader–assertion disagreement (run two grader variants, publish the split) so readers can see which assertions are judgment-dependent.

**3. Prompts to drop; two to add**

Drop:

- **"5-step plan, did 1 and 2, next?"** — non-discriminating (0.67 vs 0.71) and the fixture is buggy; a run that correctly flags the redundant step gets scored down. A prompt that punishes correct behavior is worse than no prompt.
- **"explain JWT auth"** — 0.93/0.89 near tie, and the explain-override means the skill barely governs this reply shape anyway. It measures CLAUDE.md more than the skill.

Add:

- **A multi-issue message** ("two things: my tests flake on CI, and also how should I structure this repo?"). Rule 4 (finish the first issue, offer the second separately) is currently untested by any prompt, and it's the rule most likely to be silently dropped under load.
- **An editing request** ("tighten this paragraph") — the exact task type the skill will sit next to in deployment. This is where you'll find out whether "lead with the action" mangles a deliverable-first task before the seven-skill portfolio has to absorb the conflict (see Q11).

Also missing but lower priority: a prompt whose honest answer is "this can't be verified from here," to stress "state what is unverified" against the closing-action rule.

**4. Blind pairwise — worth it?**

Yes, and it's nearly free: you already have 46 graded runs, so the only cost is judge calls. It answers the one question your assertion pipeline structurally cannot — whether the shaped reply is actually better for the reader, or merely better at satisfying assertions you wrote. Single question for the judge: **"If this were your problem, which reply would you act on first?"** Not "which is better" (invites prose-taste judgments), not "which follows the instructions" (leaks arm identity, since compliance is the manipulation). Randomize order, use an off-family judge, and report per-prompt, not pooled — a tie on JWT and a blowout on "I didn't follow that" is the informative result.

---

# Skill design

**5. S1/S2 vs a simpler rule**

S2 is right; keep it. S1 is an improvement over E2 but keeps the structure that caused the over-correction: a rule plus a multi-condition exception ("single action with nothing else open"). E2 taught you that Sonnet handles exception clauses by collapsing to the exception. The conflict between "end with the action" and "say what is unverified" isn't real — it's an artifact of letting the caveat sit at the end. Dissolve it by fixing placement, not by adding conditions:

> End with the one next action. Caveats and unverified claims go next to the claim they qualify, never after the closing action. If the reply is a single action with nothing else open, that first line is the ending — do not repeat it.

The first sentence is the rule; the second removes the conflict by making "caveat lands last" a violation rather than an exception case; the third preserves the E2 fix you actually wanted (no redundant restatement). Confidence: moderately high this reads better; whether it ends the over-correction is a guess iteration 3 will answer.

**6. The 25-line version**

1. First line: the next thing the reader can do, not context.
2. Number multi-step work; one action per step; fewest steps that work.
3. A folded step keeps its command — never make the reader reconstruct one.
4. A numbered list means one line per item, not numbered headings with paragraphs.
5. End with the one next action.
6. Skip the closing line only if the reply is one action with nothing open.
7. Caveats and unverified claims go beside the claim they qualify, never last.
8. Finish the reader's first issue before offering a second.
9. Restate state every turn: "step 3 of 5 done."
10. Give time estimates in concrete units, in a clause after the first step.
11. Show completed work concretely: what changed, what passed.
12. Errors in plain facts; no dramatizing.
13. Lists cap at five; split and rank the rest.
14. Cutting words never removes a command, a fallback, or a number the reader needs.
15. Keep the fallback branch under "if that didn't work."
16. No preamble, no recap, no closing pleasantries.
17. Define each term in the sentence where it first appears.
18. Simplify accurately and name the limit; no forced analogies.
19. "I didn't follow that": re-explain the same content, flatter structure, no new facts, every command kept verbatim.
20. Check the claim inside the question before answering; correct a false one first.
21. Keep sequence separate from cause, in plain words.
22. Asked to explain: explain fully; these shape rules yield.
23. Destructive or irreversible actions: confirm first, unless the user explicitly waived it for this action.
24. After three "still broken": stop patching, name your assumption, ask one diagnostic question.
25. A rule that fights the task loses; never quote rule names or vocabulary in a reply.

One honest caveat: cutting the rationale cuts generalization. The 190-line version earns its tokens on prompts unlike anything in your suite; the 25-line version will pattern-match. If footprint is the real problem, the better lever is loading the skill conditionally, not compressing it.

**7. A brevity formulation that doesn't eat load-bearing content**

Both failures (mkdir, time estimates) are the same bug: the model applies "fewest/briefest" to *information* instead of *words*, and low-salience details are the first to go. Define brevity over expression and completeness over content:

> Brevity applies to words, not to information. Cut filler, hedging, and restatement; never cut a command, a fallback branch, a time estimate, or a definition the reader needs. Before shortening, check: did any command, number, or "if that didn't work" branch disappear? Restore it.

The checklist sentence matters more than the principle — "fewest steps that still work" already *said* this abstractly and it failed twice. Models execute checks more reliably than they honor principles. Confidence: high that this is the right diagnosis; medium that the checklist phrasing survives Sonnet's tendency to drop trailing clauses.

**8. Vocabulary leaks**

S4 alone won't hold. Negative instructions ("do not say X") are the weakest lever you have when X is sitting in the context window as a named concept — you are asking the model to use a word in its reasoning and suppress it in output, reliably, every turn. The durable fix is upstream: write the skill so there is no label to leak. "Sequence, mechanism, correlation, premise" are coinages; replace them with imperative descriptions. Instead of a rule named *premise*, write "check whether the claim inside the question is true before explaining it." The model can then only leak a full sentence, which reads as plain advice, not jargon. Keep S4 as a backstop, but treat it as the seatbelt, not the brakes. Confidence: medium-high; this is the standard failure pattern for style guides in context, but I haven't tested it against your harness.

**9. "Delete my merged branches, just do it, don't ask"**

The skill's behavior was wrong for this case, and the eval is compounding it — the 0.94 scores *reward* asking, so your harness is training the skill toward the behavior you're now questioning. The line I'd draw: confirm when an action is destructive **and** (irreversible, wide-blast-radius, or ambiguous in scope); skip confirmation when the user has explicitly and specifically waived it for this action and the action is low-risk and recoverable. `git branch -d` on merged branches fails every prong of the confirm test: it refuses unmerged branches by design, branch tips are pointers recoverable via reflog, and "merged" is machine-checkable, so scope is unambiguous. The override should read:

> Confirm before destructive actions unless the user has explicitly told you to proceed without asking for this specific action and the action is reversible and well-scoped; then act, show what was affected, and state how to undo it.

Note the last clause does the safety work the confirmation was doing. Judgment call, stated as such: some users' "just do it" waivers shouldn't be honored (prod databases, force-pushes) — the reversibility-and-scope test, not the waiver alone, is what gates it. Also fix the assertion so both behaviors can pass when the waiver is explicit.

---

# Generalization and deployment

**10. Sonnet → Opus**

Expect: the baseline arm rises (stronger models already lead with actions and structure multi-step work), so the headline delta shrinks — 84.7 vs 73.9 compresses toward something like 90 vs 82; conditional exception clauses (S1's) are handled better, so v2-style over-corrections are less likely; vocabulary leakage and run-to-run variance both drop. The result I distrust most because of model choice is the **false-premise EADDRINUSE tie (0.81/0.81)**. Premise verification is the most capability-sensitive behavior in the suite; a stronger model challenges false premises natively, so on your actual deployment target the skill's marginal contribution there could be near zero — or the failure you observed (caveat-last, late definition) could vanish for reasons unrelated to S1/S2. That cell tells you almost nothing about the model you ship on. Runner-up: the destructive-action baseline at n=1, though that's a sample-size problem, not a model problem. This whole answer is extrapolation — treat it as a prior to test, not a finding.

**11. Rules that fight text-editing**

Two real conflicts beyond the list cap:

- **Rule 1 + Rule 3 vs deliverable-first tasks.** For "tighten this paragraph," the deliverable *is* the reply; leading with an action and closing with a next action wraps the edit in two lines of process the reader didn't ask for, and a mandated closing action degrades into "want me to also…" — an unsolicited scope expansion that directly fights the portfolio's preservation rules.
- **Rule 4 vs pass completeness.** "Finish the first issue, offer the second separately" is correct for troubleshooting and wrong for editing, where the task is the whole text and the pass order is the portfolio's contract; deferring issue two is a partial edit.

Fix at the routing layer, not in this skill: when the request is to produce or transform text, the portfolio owns shape and this skill's rules 1, 3, and 4 are suspended — in this skill's language, "when the task is a text deliverable, the deliverable is the first line and the ending." Confidence: medium — I haven't seen the portfolio's routing contract, so the split may already exist; if it does, the gap is that this skill never acknowledges it.

**12. The one experiment before iteration 4**

Run the blind pairwise from Q4 on the iteration-2 corpus you already have: off-family judge, randomized order, "which reply would you act on first," reported per prompt. Rationale: every number you've produced so far is asserted against your own interpretation of your own rules, graded by your guide's author's model family. If shaped replies win the pairwise, your assertions are validated as a proxy and iteration 4 can proceed on shape metrics with confidence. If they tie or lose on the prompts where the skill scored highest, then the skill is optimizing a signature, not a reader experience — and that changes *what the skill should say* more than any wording edit in S1–S4. It's also the cheapest experiment available: zero new executor runs. If budget allows exactly one more thing, a single Opus arm on the existing suite, to price the answer to Q10 before you iterate against the wrong model again.

---

Iteration 3 did what it should: the true-premise eval exists to catch over-application, and it caught it. The diagnosis (example sentences inside rules get echoed) is right, and it applies to the fix too. If iteration 4 pastes my plain-language forms in without their trigger conditions, they will be echoed the same way. Attach the condition to each form and add the positive case:

Say the relation in plain words, and only the one the evidence supports: "the errors started after the upgrade" when all you have is timing; "the update changed X, which produces Y" when you have a mechanism; "reverting it made the errors stop" when you have evidence. When the reader's causal claim is true, say so and give the mechanism; do not challenge a premise the evidence supports.

The Actions closing-action miss (6 of 6, both arms) is a different problem: for a multi-step reply, "the one thing to do now" is step 1, so the model either repeats it or trails off. Give it a distinct target:

For a multi-step reply, the closing line is the check that shows the steps worked ("Push, then open the Actions tab and watch the first run go green"), not step 1 again and not a caveat.

The three decisions:

1. Branch deletion: adopt the do-list-undo line, with two guards written in. The waiver must be in the current request, not inferred from tone, and if git branch -d refuses a branch as unmerged, report it and stop; never escalate to -D without asking. The iteration-3 baseline already shows the behavior is achievable (2 of 3 proceeded with clean reports). Add the second fixture (an unmerged branch or a force push) so "ask first" is tested where it belongs.

2. Deployment: the 22-line version in CLAUDE.md, now. Three reasons. It is always loaded and portable in spirit (the same text goes in AGENTS.md for Codex and in custom instructions for chat products), which is what "one skill whenever I work with an LLM" needs. It is the only always-on form the harness can measure: output styles apply to the main conversation only, since a subagent runs its own system prompt, so an output-style arm cannot be evaluated with subagent executors. And it composes: style rules in CLAUDE.md stack with an output style rather than replacing anything. Output styles do exist again in current Claude Code, but with a trap: custom styles leave out the built-in software engineering instructions unless keep-coding-instructions is set to true, and the /output-style command was deprecated in v2.1.73 and removed in v2.1.91; selection is now under /config. If you want a per-session switch later, the built-in Concise style is a reasonable base: it leads with the result, skips preamble, and always keeps error reports and destructive-action confirmations, which is rule 10 and override 2 already. The full skill stays in the repo as the reference and the eval subject; a pointer from CLAUDE.md costs a tool call per session and gives no always-on guarantee.

3. Sequence: v4 edit first, then the three-arm run on Opus, then Kimi and GPT for iteration 5. Running three arms on v3 confounds "do the examples matter" with "one bad example," because the 22-line version does not contain the echoed sentence. The v4 change is small (the two replacements above plus the branch-deletion override), so it does not delay the run. Kimi and GPT will critique method and wording; nothing they say changes what the three-arm experiment measures, and any prompts they propose slot into iteration 5.

Unverified by me: the iteration-3 numbers and the "2 of 3 proceeded" figure are from the log; I have not read the iteration-3 replies.
