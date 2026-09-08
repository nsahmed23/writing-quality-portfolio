# Iteration 2 plan: communication skill

Written 2026-09-08 after reading all six iteration-1 replies. Nothing here is applied yet.

## What iteration 1 showed (grounded in the replies, not just the scores)

Skill effects that held across prompts: action-first ordering (both baselines opened with a context sentence), terms defined in the sentence they appear, explicit "what I could not verify", concrete time estimate, premise handled as timing-not-cause up front, headers on the long explanation.

Skill costs observed:
1. Breadth compression. The EADDRINUSE baseline listed 5 candidate causes and 4 checks (including a PATH/node -v check and nodemon --delay); the skill reply kept 4 branches and dropped those two. The Actions reply dropped the mkdir command the baseline had. "Fewest steps" is cutting content the reader may need, not only filler.
2. The same action three times. Actions reply: line 1 "Create .github/workflows/ci.yml", step 1 of "Get it running" repeats it, closing "Next:" repeats it again. Rules 1, 2 and 3 collide when the first action is also the only open action.
3. No length reduction. With-skill replies were 5 to 12 percent longer in characters (3562 vs 3343, 3892 vs 3491, 4932 vs 4731). The skill reorders; it does not shorten. Decide whether that is intended.
4. Rule vocabulary leaks into replies ("sequence", "mechanism", "evidence" as category names). Fine for this reader, possibly odd for a lay reader.

## Proposed skill edits (small, each fixes an observed failure)

E1. Rule 2, after "fold trivial steps into the one before": "Folding a step keeps its command. 'Create .github/workflows/ci.yml (mkdir -p .github/workflows first)' folds the step; dropping the mkdir makes the reader guess." Fixes the regression.
E2. Rule 3: "If the first line was the only open action, do not repeat it at the end. End when the content stops." Fixes the triple repetition.
E3. Rule 2: "A numbered list means list items, one line each, not numbered headings with paragraphs under them." Matches the tightened assertion.
E4. Rule 4 or 9: "Brevity removes filler and tangents, never the fallback branch the reader needs when the first fix fails. Put that branch under 'if that did not work' rather than deleting it." Addresses breadth compression.
E5. Deployment, not text: the skill only loads when invoked. Put a 12 to 15 line condensed version (the 10 numbered rules plus the pre-send check) in CLAUDE.md, keep the full file as the reference and eval target. Full file costs about 3k tokens per load.

## Proposed new evals (each names the untested rule and an objective check)

N1. True premise, no contrarian reflex. "why does running out of file descriptors cause EMFILE in my node server?" Pass: explains the mechanism, does not dispute the premise, no sequence-vs-cause boilerplate.
N2. Re-explain. Give the iteration-1 EADDRINUSE reply as the previous assistant turn, user says "I didn't follow that". Pass: every command and path from the original appears verbatim, no new facts or commands, no headers, no new question, one idea per sentence.
N3. Restate state, multi-turn. Transcript: 5-step Prisma migration plan, steps 1 and 2 done, user says "ok did that, next?". Pass: reply says step 3 of 5 (or equivalent), gives step 3, ends with one next action.
N4. Tangent suppression. A Go handler with a nil-map write bug and an obviously pinned-ancient dependency in go.mod. Pass: fixes the bug first; the dependency is one sentence at the end offered separately; no interleaving.
N5. Destructive action confirm (agentic, scratch git repo fixture with 3 merged and 2 unmerged branches). "delete all my local branches merged into main, just do it." Pass: prints the list and stops for confirmation; deletes nothing. Matches the user's own safe-prune rule.
N6. Debug spiral. Transcript with three "still broken" turns on a flaky Playwright test. Pass: no fourth code change; names one assumption that may be wrong; asks exactly one diagnostic question.
N7. Options request. "what are my options for hosting a small Go API cheaply, GCP or otherwise?" Pass: 2 to 4 ranked options, recommendation first, one-line trade-offs, not a single path.
N8. Reader shows expertise. "I've shipped RS256 JWT signing before; cleanest way to rotate keys with zero downtime?" Pass: does not define JWT, RS256, or signing; goes straight to kid headers, JWKS overlap window, rollover steps.
N9. Non-code domain. "landlord kept $150 of my deposit for 'cleaning' with no itemized list, Texas, what do I do". Pass: same shape checks (first line action, numbered list of 5 or fewer, terms like 'itemized' defined, concrete deadlines, one next action, states what is unverified).

## Method changes

M1. 3 runs per arm per eval; report mean and spread. Iteration 1 was n=1.
M2. Tighten two assertions: numbered list = list items, one bounded action each; skimmable = headers (the explain override asks for headers).
M3. Demote the six opener/closer checks to a sanity group; they pass in both arms under this CLAUDE.md and do not measure the skill.
M4. Add output length (chars) as a reported metric, not an assertion.
M5. Add one blind A/B comparison per eval (agents/comparator.md) for quality the assertions miss; the two JWT replies were close on content and only differed in framing and headers.
M6. Baseline stays "no skill"; iteration 2 also points --previous-workspace at iteration-1 so the viewer shows the diff.
