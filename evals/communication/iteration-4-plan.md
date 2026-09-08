# Iteration 4 plan (rewritten 2026-09-08 after all four consult answers; see consult-synthesis.md)

Supersedes the earlier version of this file, which was based on the Claude self-review alone. Items marked DECIDE need the user's call.

## Already applied this session
- Validator covers `skills/communication` (reports `companion_skill=communication`).
- Grader quote rule plus `verify_quotes.py` audit (154 of 156 iteration-3 passes verified automatically, 2 by hand, 1 voided).
- `metrics.py`: reply length and time-to-first-action as per-arm distributions.
- Branch-deletion executors log commands (RAN:/WOULD_RUN:) instead of executing; no stalls.

## Step 1: blind pairwise on the iteration-3 corpus (no new executor runs)
- 8 prompts x 3 run pairs = 24 pairs, each judged twice with order reversed = 48 judge calls.
- Judge: off-family (DECIDE: Kimi CLI, or GPT-5.6 via Codex).
- Judge input: the user request, the fixture facts and a two-line answer key written without reference to the skill, both replies, no arm labels, no assertion scores.
- Question (B Q4 wording, GPT Q4 outcomes): "If this were your problem, which reply would you act on first, and why?" Outcomes: A, B, no meaningful difference, both unacceptable. The judge must state each reply's first step before choosing.
- Count a winner only when the preference survives order reversal; report inconsistent pairs separately; report per prompt, never pooled.

## Step 2: skill v4 (frozen before step 3; snapshot v3 first)
S1. Rule 1, DECIDE (synthesis split 1). Recommended text (GPT Q5): "Lead with what the user requested: the answer, deliverable, verified result, or next executable action. For procedural help, the first line is the first action, and prerequisites come before the actions that depend on them. Do not manufacture an action for an explanatory or artifact-only request."
S2. Term definition (GPT Q5): "Define an unfamiliar term before the reader must use it to understand or act. Use a short clause when natural; use a separate sentence when that is clearer. Do not overload the first line to satisfy a placement rule."
S3. Rule 3 (B Q5): "End with the one next action. Caveats and unverified claims go next to the claim they qualify, never after the closing action. If the reply is a single action with nothing else open, that first line is the ending; do not repeat it." Plus B's multi-step target: "For a multi-step reply, the closing line is the check that shows the steps worked, not step 1 again and not a caveat."
S4. Rule 2 brevity (B Q7 with GPT Q7's merge condition): "Brevity applies to words, not to information. Cut filler, hedging, and restatement; never cut a command, a prerequisite, a check, a fallback branch, a decision condition, or a definition the reader needs. Combine steps only when the combined instruction remains executable without guessing. Before shortening, check: did any command, number, or 'if that did not work' branch disappear? Restore it." Remove "a short path finished beats a complete path abandoned."
S5. Numbered items (GPT Q7): "Each item has one primary action and may include the explanation, code block, expected result, or failure condition needed to perform it."
S6. Rule 6 estimates (reconciled): "When the reader will execute something and the estimate has a basis, put it in one clause after the first step, with its assumptions; never invent one to satisfy a rule."
S7. Causes and evidence (B's post-iteration-3 text, then GPT Q8's paired examples). Remove the v3 pre-send item 6 example sentence; keep the "do not label your own reasoning" line as backstop.
S8. Override 2 (GPT Q9 text plus B's guards): explicit waiver must be in the current request; `git branch -d` refusals are reported, never escalated to `-D`; "merged" is checked against the intended target, not only the upstream or HEAD; list names and commit ids and give the undo.
S9. Re-explain rule: add GPT Q3's correctness exception: "If the previous reply was wrong, correct it explicitly and say what changed; preservation protects correct facts, not errors."
S10. Editing boundary: replace the seam paragraph with GPT Q11's text; add Claude Q11's pre-send scope sentence ("This check applies to your own words. Text you edit or quote keeps its voice, hedges, and idioms."); add "a finished edit has nothing open" and "internal editing passes are not steps the reader takes."
S11. Debug spiral (GPT Q6): drop the fixed three-turn trigger: "stop speculative patching when evidence stops improving; inspect what is available, then request the specific missing observation."

## Step 3: three-arm run on the target model (GPT Q12 design)
- Arms: A no skill; B full v4; C GPT's 25-line candidate (consult-answers-gpt.md Q6), loaded through the same mechanism as B.
- Cases: 12 held-out: 3 ordered-action, 3 explanation, 3 artifact-only editing (GPT Q3 A exact-match grammar fix among them), 3 multi-turn recovery (B's multi-issue message, GPT Q3 B wrong-previous-answer re-explain, Kimi's "still broken" and "just do it" turns). Keep EMFILE and the two branch fixtures as separately reported regression checks.
- Scoring order: deterministic artifact and environment checks first; preservation inventory; then blind pairwise (step 1 protocol) with a few of the user's own blinded judgments; shape assertions reported as diagnostics only.
- Decision rule (predeclared, GPT Q12): reject a candidate with a critical correctness, safety, or output-contract failure; among the rest prefer the one readers consistently find more useful with less effort; when indistinguishable, prefer the cheaper policy.
- DECIDE: target model Opus 5 (cost) or Sonnet first.

## Step 4 (iteration 5): Kimi's multi-turn simulated-user suite
Ten conversations, three to five turns, each forcing one override ("I didn't follow that", "still broken", "just do it"); score per turn for preserved facts and commands, one next action, and resolve-or-ask; off-family judge.

## Eval hygiene carried forward
- Freeze assertions and the guide in a commit before any run; edit only between iterations.
- Assertion applicability comes from the task (a closed task has no closing action to assert).
- The six [sanity] opener/closer checks and the JWT prompt leave the headline; JWT stays as a rule-1 over-application check.
- No character caps as pass/fail; length is a reported distribution.
- Prompts that once discriminated never leave the suite (B Q1).

## Open decisions
1. Split 1: conditional action framing (recommended) or universal action-first.
2. Judge for the pairwise pass: Kimi CLI (membership quota) or GPT-5.6 via Codex.
3. Deployment: after step 3 (recommended) or B's "22-line version in CLAUDE.md now".
