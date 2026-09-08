# Iteration 4 plan (written 2026-09-08 after the Claude self-review; Kimi and GPT answers pending)

Source: consult-answers-claude.md, the author's self-review. Items marked DECIDE need the user's call before they are applied. Everything else is applied at iteration 4 unless Kimi or GPT argue otherwise.

## Applied already (this session, after iteration 3 launched)
- Validator covers `skills/communication` (SKILL.md, agents/openai.yaml, references/eval-summary.md, evals/evals.json; reports `companion_skill=communication`). README says so.
- Grader quote rule: iteration-3 graders must quote a verbatim span for every pass; `verify_quotes.py --apply` voids passes with no findable quote (Q2).
- `metrics.py`: median reply length and time-to-first-action per eval per arm, reported as distributions, no thresholds (Q1).

## Skill edits for v4 (replacement text from the review, to apply after iteration 3 is graded)
S1. Rule 1 ending: "If the first line uses a term the reader may not know, define it in that line or the next one: ..." (replaces the v3 parenthetical rule; Q5).
S2. Rule 3, whole rule: "The last line names the one thing to do now. Skip it only when the whole reply is a single action with nothing else open. A caveat about what is unverified belongs in the body, not last; when it matters, fold it into the closing line by saying what the action will settle: 'Next: run X; its output settles whether Y.'" (Q5; shorter than v3 S1 and merges caveat with action.)
S3. Rule 2 second paragraph: "Use the fewest steps that still work by merging steps that are one motion, never by dropping a command, a check, or a branch the reader needs. A merged step keeps its command. The test for filler: if removing it would make the reader ask a question, it was not filler." (Q7.)
S4. Rule 9 added sentence: "Brevity deletes from a fixed list: openers, closers, recaps, sidebars, hedges that carry no information, repeated propositions. Nothing else is cut for length. A long reply is split and ranked, not thinned." (Q7.)
S5. Causes-and-evidence second bullet rewritten with plain-language forms and "never use those words as labels in a reply"; keep the v3 pre-send item 6 (Q8). Extend CATEGORY_LABEL_RE to correlation, premise, mechanism.
S6. Pre-send check scope: "This check applies to your own words. Text you edit or quote keeps its voice, hedges, and idioms." (Q11; the real conflict with the portfolio's preservation contract.)
S7. Editing-request guards (Q11): a finished edit has nothing open (no "Next: paste the next section"); internal editing passes are not steps the reader takes, so rule 5 does not narrate them; no time estimate when there is nothing for the reader to execute.
S8. DECIDE: override 2 (destructive actions). Review's position: confirm only when irreversible or uncertain-scope; a local, reversible, clearly scoped action with an explicit waiver (git branch -d of merged branches) is done, listed, and given an undo. Iteration-3 data: with the skill 3/3 asked; without it 2/3 proceeded and reported cleanly. If accepted, the eval-6 assertion flips to "either asks first, or proceeds and reports the deleted names with an undo", and a second fixture with an unrecoverable action (git branch -D on an unmerged branch, or a force push) is added where asking is required. The user's own safe-prune rule (dry-run, confirm) argues for keeping "ask" for remote pruning; the review's line separates local reversible from remote or irreversible.

## Eval changes for iteration 4
V1. Drop the six [sanity] opener/closer assertions from the headline and report per-assertion discriminability; anything both arms pass or fail at 90%+ is a sanity check, not a score (Q1).
V2. Add preservation counts: for each fixture, enumerate required commands, paths, numbers, steps; count survivors in the reply (Q1). Start with evals 0, 1, 4, 5.
V3. Add the two missing prompts (Q3): expert reader ("I've run Kubernetes for six years; why does my HPA flap between 3 and 5 replicas?": no basic-term definitions, no baby steps, first line still an action) and non-code embedded premise ("My sourdough stopped rising after I switched flour brands; why does the new flour kill the starter?": sequence-not-cause without those words, first line something to do, concrete time estimate, no forced analogy).
V4. Demote JWT explain to a rule-1 over-application check (does the skill force a fake action line on an explanation?). Add rule-3 over-application (closed task: does it invent a next step?) and rule-9 over-application (a real seven-item inventory: does it truncate?).
V5. Blind pairwise judge on the flat evals (0, 2, 3, 7): order randomized, two-line answer key, judge states each reply's first step before choosing; question: "Which reply lets the reader take the correct first step sooner, without omitting anything they would need to know?" (Q4.)
V6. Reader-execution test on evals 1 and 5: a fresh agent gets only the fixture and the reply and performs the steps; count steps completed without a question (Q1). Defer if cost is a concern.
V7. Freeze assertions and the interpretation guide in a commit before the runs; no edits within an iteration (Q2).

## Experiment before or alongside iteration 4 (Q12)
Three arms on the target model (Opus 5): full skill v4, the 22-line CLAUDE.md version (consult-answers-claude.md Q6), and no skill, on the 8 prompts plus V3's two, scored with V2 preservation counts and V6. Decides whether the skill shrinks to what fits in CLAUDE.md. DECIDE: run on Opus (cost) or on Sonnet first.

## Open decisions for the user
1. S8: keep "ask first" for reversible local deletions with an explicit waiver, or adopt the review's line.
2. Deployment: wire the skill into CLAUDE.md as the 22-line version (pending Q12 result), as a one-line pointer to the full skill, or as an output style.
3. Q12 experiment on Opus now, or after Kimi and GPT answer.
