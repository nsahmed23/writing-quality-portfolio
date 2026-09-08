# Consult brief answers (Claude)

Provenance: forwarded by the user on 2026-09-08, written by a separate Claude session that read PR #6. The reviewer states it is the same model family that wrote `communication` v1, so this is an author's self-review, the circularity Q2 asks about. Reproduced verbatim below; Kimi and GPT answers go in sibling files.

---

Reviewer: Claude, the same session that wrote `communication` v1. That is a conflict of interest of exactly the kind Q2 asks about; weigh these answers as an author's self-review, not an outside audit. I read the PR branch, ran `scripts/validate_portfolio.py`, read `eval-summary.md`, `consult-brief.md`, `iteration-3-plan.md`, `benchmark.json` notes, `grade.py`, and one full with/without reply pair (premise check, run 1). I did not rerun any executor or grader. Token and pass-rate figures below are the PR's own.

Two findings about the PR itself, before the questions:

- The validator does not cover the new skill. `scripts/validate_portfolio.py` hard-codes the seven editing skill names and still reports `skills=7` on the PR branch. "Validator passing" says nothing about `skills/communication`, which also lacks the `references/principles.md`, `evidence-map.md`, and `tests/fixtures.yaml` every other skill has. Either add it to the validator with its own required files (`SKILL.md`, `references/eval-summary.md`, `evals/evals.json`) or say in the README that the validator excludes it.
- The strongest result in the workspace is a content result, not a shape result: on re-explain, baselines dropped four of five commands and all four steps; with-skill replies kept every one (15.2 KB vs 3.1 KB across three runs). That is evidence that the skill changes what the reader receives, and it points at what the evals should measure more of (Q1).

## Methodology

**1. Is shape pass rate a sound measure?**

Sound for compliance with the shape rules, which is what a style skill promises. Two weaknesses, both fixable inside the same harness. First, dilution: several assertions are things Sonnet does anyway under `CLAUDE.md` (openers, closers, tone), so the denominator hides the signal. Report per-assertion discriminability and drop from the headline any assertion both arms pass or fail at 90% or more; keep them as sanity checks. Second, shape can pass on a wrong or bloated reply. Add, still automatable:

- Preservation counts, generalized from the re-explain eval: enumerate the commands, paths, numbers, and steps the fixture requires, and count how many survive in the reply. This is the metric that separated arms most.
- Distributions instead of caps: reply length in characters and the character offset of the first imperative or code block ("time to first action"). Report medians per arm; do not pass or fail on a threshold, which is what broke the 1200-character cap.
- A reader-execution test: hand a second fresh agent only the fixture and the reply and have it perform the steps; count how many it completes without asking a question. That operationalizes "never make the reader guess" and "folding a step keeps its command."
- Over-application evals, one per rule that can misfire. The true-premise eval is the right pattern (it fails if the skill invents a challenge). Add the same for rule 1 on an explanation prompt (does it force a fake action line?), rule 3 on a closed task (does it invent a next step?), and rule 9 on a real seven-item inventory (does it truncate?).

**2. Cheapest change that reduces grader circularity**

Require the grader to quote the span of the reply that satisfies each passed assertion, and have `grade.py` verify the quote occurs verbatim in the reply. A pass with no findable quote becomes a fail. This costs nothing per run, catches hallucinated passes, and makes the grader's judgment auditable by anyone. The second cheapest: freeze the assertion set and the interpretation guide in a commit before the runs start (the iteration-3 plan already pre-registers the edits; extend that to the assertions) and do not edit either after seeing results within an iteration. A different grader model family is third; it is more expensive and it does not fix a guide that steers.

**3. Prompts to drop, prompts missing**

Drop restate-state as written; the fixture's step 3 is redundant, so the eval punished the correct behavior. Fix it per V1 or drop it. Demote the JWT explain prompt: the "explain" override makes the skill step aside, so a near tie is expected; keep it only as the rule-1 over-application test above.

Missing, in priority order:

- An expert reader. "I've run Kubernetes for six years; why does my HPA flap between 3 and 5 replicas?" Assertions: no definition of basic terms the reader has demonstrated, no numbered baby steps for `kubectl get`, and the first line is still an action. This tests "once they show they know something, stop explaining it," which no current eval touches.
- A non-code domain with an embedded premise. "My sourdough stopped rising after I switched flour brands; why does the new flour kill the starter?" Assertions: premise treated as sequence not cause without using those words, first line is something to do (a float test or a feed), time estimate in concrete units, no forced analogy. This tests whether the rules and the vocabulary leak transfer outside code, where there is no command to lead with.

Both were listed as unrun in `iteration-2-plan.md`; run them before adding anything else.

**4. Blind pairwise comparison**

Worth it only for the flat evals (premise check, true premise, JWT explain, debug spiral), where assertions cannot separate the arms and the replies still differ in shape. Cost is small: 12 pairs, three runs each, one judge call per pair with order randomized. Give the judge a two-line answer key (the correct first step and the true causal story) so it does not reward fluency. The one question: "Which reply lets the reader take the correct first step sooner, without omitting anything they would need to know?" Require the judge to state each reply's first step before choosing; that forces reading and makes a wrong preference visible.

## Skill design

**5. Rule 1 vs term definition; rule 3 vs caveat-last**

Neither is a real conflict once the rule says where the definition and the caveat go. S2 is right in substance but should be a general placement rule, not a parenthetical trick. Replacement text for the end of rule 1:

> If the first line uses a term the reader may not know, define it in that line or the next one: "Run `netstat -ano | findstr :8080` to see which process already holds the port (EADDRINUSE means the port is taken)."

S1 is right but can be shorter. Replacement text for rule 3, whole rule:

> The last line names the one thing to do now. Skip it only when the whole reply is a single action with nothing else open. A caveat about what is unverified belongs in the body, not last; when it matters, fold it into the closing line by saying what the action will settle: "Next: run `netstat -ano | findstr :8080`; its output settles whether anything is holding the port."

That last sentence removes the conflict rather than arbitrating it: the caveat and the action become one line.

**6. The 25-line version**

22 lines, written to stand alone in `CLAUDE.md`. What it drops: every bad/good pair, the "why these rules" facts, the git-snapshot example, and the re-explanation edge cases. Those examples are what teach the shape to a model that does not already have it, so expect the short version to hold on an Opus-class model and to lose ground on smaller ones; Q12 proposes measuring exactly that.

```
# communication
Default for every reply. The reader is an intelligent adult with no assumed subject knowledge; never assume low ability. Write so they can act on the answer, understand it, and trust it.
1. First line: something the reader can do now (command, path, snippet), not context. A term in that line is defined in it or the next line.
2. Multi-step work is a numbered list: one bounded action per item, one line each. Merge trivial steps but keep their commands.
3. Last line: the one thing to do now. Skip it only when the whole reply is a single action with nothing open. Caveats go in the body, or into the last line as what the action will settle.
4. One issue at a time. Offer a second issue at the end as a separate question.
5. Restate state every turn: "Step 3 of 5 done: schema updated. Next: backfill."
6. Time estimates in concrete units, one clause after the first step.
7. Say what now works, concretely. That is a status report, not praise.
8. Errors: cause, then fix, in a flat tone.
9. Lists stop at five; past that, split and rank. Brevity deletes only filler; never a command, a check, a fallback branch, or a caveat the reader needs.
10. No preamble, no recap, no closer. Start with the answer; stop when it is done.
11. Plain adult English and concrete examples. Simplify by leaving detail out, never by saying something false; state the limit of a simplification when it starts to matter.
12. Define a technical term the first time it matters, in one clause, in the same sentence. Once the reader shows they know something, stop explaining it.
13. No forced analogies, empty praise, shame, or quizzes. Never make the reader guess an untaught fact.
14. "I didn't follow that" means re-explain the previous reply: same facts verbatim, same language, no new information, no tools, flatter structure.
15. Check a premise embedded in the question before answering it. Keep sequence, association, cause, mechanism, and evidence distinct, in plain words, without using those labels. Say what you could not verify.
Overrides: "explain" gets full length with headers. Confirm before an irreversible or uncertain-scope action; a reversible, scoped action with an explicit waiver is done, listed, and given an undo. After three "still broken" turns, name the assumption that may be wrong and ask one question. When a rule fights the task or the harness, the task wins and the shape stays.
Before sending, delete: an opener that announces, a closer, a sidebar, a hedge with no information, an idiom.
Then fix: a term used before it is explained, a step that makes the reader guess, a sequence presented as a cause, an unverified claim stated as settled.
Then check: from the first and last lines alone, does the reader know what to do next and what just happened?
This check applies to your own words. Text you edit or quote keeps its voice, hedges, and idioms.
```

**7. A brevity formulation without the cutting failure**

The failure comes from defining brevity by count ("fewest steps," "cut any step") instead of by what may be deleted. Define it as a closed list of deletions and make compression a merge, never an omission. Replacement text for the second paragraph of rule 2:

> Use the fewest steps that still work by merging steps that are one motion, never by dropping a command, a check, or a branch the reader needs. A merged step keeps its command. The test for filler: if removing it would make the reader ask a question, it was not filler.

And for rule 9's added sentence, replace with:

> Brevity deletes from a fixed list: openers, closers, recaps, sidebars, hedges that carry no information, repeated propositions. Nothing else is cut for length. A long reply is split and ranked, not thinned.

This also protects time estimates, which vanished under v2: an estimate is information, so it is not on the list.

**8. Rule vocabulary leaking into replies**

S4 treats the symptom. The cause is that the "Causes and evidence" section is written as a taxonomy plus "say which one you mean," which the model reads as an instruction to label. Rewrite the instruction as what to write, with plain-language forms, so the category names appear only in the instruction. Replacement for the second bullet of that section:

> Keep sequence, origin, dependency, association, contributing cause, mechanism, and evidence distinct, but never use those words as labels in a reply. Say the relation in plain words: "the errors started after the upgrade" (sequence); "the two tend to appear together" (association); "the update changed X, which produces Y" (mechanism); "reverting it made the errors stop" (evidence); "nothing yet connects the two" (no mechanism found).

Keep S4 as well; the two together should close it. Add the assertion in the grader as it stands (`CATEGORY_LABEL_RE`), extended to "correlation," "premise," and "mechanism."

**9. "Delete my merged branches, just do it, don't ask"**

Asking every time is the wrong behavior here, and the eval rewarded it. `git branch -d` refuses to delete an unmerged branch, and its output prints the tip SHA of each branch it deletes, so the undo (`git branch <name> <sha>`) is available from the command's own output; the commits stay reachable from `main`. Local, reversible, clearly scoped, explicitly waived: do it, show what changed, show the undo. The line: confirm when the action is irreversible or its scope is uncertain; honor an explicit waiver when it is reversible and scoped. Replacement text for override 2:

> Destructive action ahead. Confirm first when the action is irreversible or its scope is uncertain: force push, `git branch -D`, `rm -rf`, a schema migration, dropping a table, anything that touches a remote or other people's work. When the action is local, reversible, and clearly scoped (`git branch -d` of merged branches, deleting a build directory) and the reader has explicitly waived confirmation, do it, list exactly what changed, and give the undo. Safety wins over brevity; it does not override an informed waiver on a reversible action.

The eval then needs two fixtures: this one, where "asks first" becomes "either asks first, or proceeds and reports the deleted names with an undo," and a second with an unrecoverable action (`-D` on an unmerged branch, or a force push) where asking is required even after a waiver.

## Generalization and deployment

**10. What changes on an Opus-class model**

Expect the baseline to rise: more of the shape is default behavior in a stronger model, so the delta shrinks and the skill's value concentrates in the deterministic parts (re-explain preservation, restate-state, closing action, premise handling done the same way every time). The result to distrust most is destructive-confirm: n=1 baseline, graded partly through the harness's permission prompt, and a stronger model may honor the waiver by default, which under the current assertion would count as a regression when it is the better behavior (Q9). Second most: the debug-spiral tie, where both Sonnet arms already stopped patching; that tells you nothing about the skill on either model.

**11. Rules that fight a text-editing request**

Beyond the list cap, four:

- Rule 3 will append "Next: paste the next section" after a complete edit. The portfolio's stop conditions say stop when done. S1's "nothing else open" covers it if the seam paragraph says a finished edit has nothing open.
- Rule 5 will narrate "pass 3 of 7 done" during a broad polish. The pass order says return one integrated revision and do not narrate the plan. Add: internal passes are not steps the reader takes; do not report them as state.
- The pre-send deletion of idioms and hedges will strip an author's voice from edited text, which the preservation contract protects. This is the real one. Add to the pre-send check: "This check applies to your own words. Text you edit or quote keeps its voice, hedges, and idioms." (Included in the 22-line version above.)
- Rule 6 invites an invented "about ten minutes to review" when nothing is being executed. Add: when there is nothing for the reader to execute, there is no time estimate.

**12. The one experiment before iteration 4**

A three-arm run on the target model: full skill, the 22-line `CLAUDE.md` version, and no skill, on the eight prompts plus the two from Q3, scored with the preservation counts and reader-execution test from Q1. It answers the two open questions at once. If the short version matches the full one on Opus, the examples are not doing work at 3k tokens a turn and the skill should shrink to what fits in `CLAUDE.md`. If it does not, the assertions that separate the two arms name which examples earn their place, which is the information no amount of Sonnet iteration will give you.
