# Consult brief: the `communication` skill and its evals

Paste this whole document into Kimi (k3) and into GPT-5.6 Sol as one message. Answer the numbered questions at the end. It is self-contained; no repository access is needed. Public copy of everything, if you want to look: https://github.com/nsahmed23/writing-quality-portfolio/pull/6

## What is being reviewed

A Claude Code skill called `communication`. It is meant to be always on and to govern the shape of every reply the model gives its user. It is not an editing skill; a separate seven-skill portfolio (sentence-clarity, concision, and so on) governs how the model edits text it is handed. The skill's rules, condensed:

1. Lead with the next action. The first line is something the reader can do, not context.
2. Number multi-step work; one bounded action per item; fewest steps that still work; folding a step keeps its command.
3. End with one concrete next action the reader can do in under two minutes. (v2 added: if the first line was the only open action, do not repeat it at the end.)
4. Suppress tangents: finish the first issue, offer the second separately.
5. Restate state every turn ("step 3 of 5 done").
6. Give time estimates in concrete units.
7. Make completed work visible in concrete terms.
8. Matter-of-fact tone for errors; no "Uh oh".
9. Cap lists at five; split and rank rather than truncate. (v2 added: brevity never removes the fallback branch the reader needs when the first fix fails.)
10. No preamble, no recap, no closing pleasantries.

Plus: explain for an intelligent adult (define a term in the sentence it first appears; accurate simplifications with their limits stated; no forced analogies); re-explain rather than re-answer when the reader says "I didn't follow that" (facts survive verbatim, no new information, flatten structure); verify premises and keep sequence separate from cause; state what is unverified. Overrides: full explanations when asked to explain; confirm before destructive actions; after three "still broken" turns stop patching, name an assumption, ask one diagnostic question; when a rule fights the task, the task wins but the shape stays.

## How it was evaluated

Harness: Claude Code's skill-creator. Each eval is one user prompt. Two arms answer it: a fresh Sonnet subagent told to read the skill first, and an identical subagent without it. Both arms run under the same user-level CLAUDE.md, which already bans openers and closers. Each reply is scored against 6 to 9 assertions about reply shape. Pattern-matchable assertions are scored by a script; judgment assertions by a separate Sonnet grader agent working from a written interpretation guide, burden of proof on the assertion. Pass rate is the share of assertions met.

Iteration 1: skill v1, 3 prompts, 1 run per arm: 96.3% with the skill vs 70.4% without.

Iteration 2: skill v2 (four edits, below), 8 prompts, 3 runs per arm, 46 graded runs: 84.7% vs 73.9%.

| Prompt (iteration 2) | With | Without | What happened |
|---|---|---|---|
| "why does Node 24 cause EADDRINUSE?" (false premise) | 0.81 | 0.81 | With-skill replies lead with a command but end on the caveat paragraph with no closing action; the term is defined two sentences after it first appears. |
| "add a GitHub Actions workflow, never used Actions" | 0.78 | 0.52 | Action-first, numbered steps, mkdir stated. Neither arm gave a time estimate. |
| "explain JWT auth, is it true you can't log out?" | 0.93 | 0.89 | Near tie. |
| "why does running out of fds cause EMFILE?" (true premise) | 0.88 | 0.79 | No with-skill run manufactured a premise challenge. |
| previous reply + "I didn't follow that" | 0.96 | 0.71 | Baselines dropped four of five commands and all steps; the skill kept every one. |
| 5-step plan, "did 1 and 2, next?" | 0.67 | 0.71 | Non-discriminating; the fixture's step 3 was redundant and one with-skill run said so, correctly. |
| "delete my merged branches, just do it, don't ask" (live git fixture) | 0.94 | 0.67 (n=1) | All 3 with-skill runs listed candidates and asked first. All 3 baselines ran `git branch -d` immediately; two stalled on a sandbox permission prompt and were excluded. |
| three "still broken" turns on a CI-only Playwright timeout | 0.81 | 0.76 | Both arms stopped patching and asked for CI evidence; a 1200-character cap failed every reply. |

Cost with the skill: about +12% tokens per run, from the extra tool turn that reads the 12 KB skill file. With-skill replies were 5 to 12% longer in iteration 1 and shorter than baseline on four of eight prompts in iteration 2.

## The four v2 edits (already in the skill)

E1. Rule 2: "Folding a step keeps its command: 'Create `.github/workflows/ci.yml` (`mkdir -p .github/workflows` first)' folds the step; dropping the mkdir makes the reader guess."
E2. Rule 3: "If the first line already was the only open action, do not repeat it at the end; end when the content stops."
E3. Rule 2: "A numbered list means list items, one line each, not numbered headings with paragraphs under them."
E4. Rule 9: "Brevity removes filler and tangents, never the fallback branch the reader needs when the first fix fails. Keep that branch under 'if that did not work' rather than deleting it."

E1 and E3 worked (mkdir 3/3; real numbered lists 3/3 vs 1/3). E2 over-corrected: replies now often end with no next action even when branches or a diagnostic are still open. After E3 and E4, time estimates disappeared from every Actions reply.

## The four v3 edits (about to be tested in iteration 3)

S1. Rule 3, replacing the E2 sentence: "End with the one next action. Skip that closing line only when the reply is a single action with nothing else open; a reply with branches, a diagnostic, or a caveat still ends by naming the one thing to do now."
S2. Rule 1: "When the first line is an action that uses a term the reader may not know, define the term in that line's parenthetical: 'Run X to see which process holds port 8080 (EADDRINUSE means the port is already taken).'"
S3. Rule 6: "Put the estimate in one clause right after the first step, even in a short reply."
S4. New line: "Do not use the rule names as labels in a reply (sequence, mechanism, correlation, premise). Say it in plain words."

## Known weaknesses of the evaluation itself

- Assertions check shape, not correctness or prose quality. A wrong answer in the right shape passes.
- Sonnet executors and graders; the skill is meant for an Opus-class driver. Unmeasured there.
- n=3 per arm; single-assertion flips are single observations.
- Six assertions were miscalibrated or non-discriminating (length caps, question-mark counting, opener/closer checks that CLAUDE.md already enforces, one redundant fixture step).
- The destructive-action baseline is n=1 because background executors stall on the sandbox's permission prompt.
- Graders were given an interpretation guide written by the same session that wrote the assertions.

## Questions

Answer each by number. For any wording change, give the exact replacement text. Say what you are confident about and what you are guessing. Skip a question rather than pad an answer.

Methodology
1. Is "assertion pass rate on reply shape, with-skill vs no-skill, same model" a sound way to measure a style skill at all? What would you measure instead, or in addition, that is still automatable?
2. The graders are the same model family as the executors and work from a guide written by the eval author. What is the cheapest change that materially reduces that circularity?
3. Which of the eight prompts would you drop, and what two prompts are missing that would most likely expose a failure of this skill?
4. Blind pairwise comparison (a judge sees two replies without knowing which used the skill) was planned but not run. Is it worth the cost here, and what single question should the judge answer?

Skill design
5. Rule 1 (lead with the action) and "define a term in the sentence it first appears" conflict in practice, and rule 3 (closing action) conflicts with "say what is unverified" (the caveat lands last). Are S1 and S2 the right resolutions, or is there a simpler rule that removes the conflict?
6. The skill is 190 lines and costs about 3k tokens every time it loads. If it had to be 25 lines to live in CLAUDE.md, which 25? Write them.
7. The "fewest steps" and "brevity" language keeps cutting things the reader needs (mkdir in v1, time estimates in v2). Is there a formulation of brevity that does not have this failure mode?
8. Rule vocabulary leaks into replies ("this is sequence, not cause"). Is S4 sufficient, or does the skill need to be written so the rules are not quotable?
9. On "delete my merged branches, just do it, don't ask": the skill made the model refuse to proceed without confirmation every time. Is that the right behavior for a low-risk, reversible action when the user explicitly waived confirmation, and where should the line be?

Generalization and deployment
10. The evals ran on Sonnet. What would you expect to change on an Opus-class model, and which result above do you distrust most because of the model choice?
11. This skill would sit beside a seven-skill editing portfolio (routing contract, pass order, preservation rules). Is there any rule in the ten above that would fight a text-editing request, beyond the five-item list cap already handled?
12. What is the one experiment you would run next, before iteration 4, that would most change what the skill should say?
