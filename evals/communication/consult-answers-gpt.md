# Consult brief answers (GPT-5.6 Sol, attribution inferred)

Provenance: forwarded by the user on 2026-09-08. Attribution to GPT-5.6 Sol is inferred from ChatGPT-style file citations and the "Download the 25-line candidate" artifact link in the text; the user has not confirmed it. The reviewer read the public repository at commit 334409b (post iteration 3) and the three saved with-skill true-premise replies. Reproduced verbatim below; citation artifacts left in place.

---

Keep the preservation safeguards, make action framing conditional on the task, and stop using shape compliance as the main measure of communication quality. The skill is learning to satisfy its rules; the unresolved question is whether those rules consistently help the reader.

Reviewed September 8, 2026. The public repository is ahead of the uploaded brief: commit 334409b includes reported iteration-3 results and a new true-premise regression. I inspected the current routing contract, evaluation summary, and all three saved with-skill replies for that regression. I did not rerun the models or independently recompute the aggregate scores.

1. Is assertion pass rate a sound measure?

Yes, as a measure of compliance with specified rules. No, as a sufficient measure of whether those rules improve communication.

The same-model, same-CLAUDE.md comparison is a sensible way to estimate the skill's incremental effect in that environment. Existing opener and closer bans do not invalidate the comparison; they mean those assertions measure shared behavior rather than the skill's added value. The reported iteration-2 difference is 10.8 percentage points of shape compliance, not a demonstrated improvement of that size in usefulness, accuracy, or comprehension.
C:\Users\nsahm\.claude\skills\communication-workspace\consult-brief.md

I would retain shape assertions as a diagnostic score and add the following:

Dimension	Automatable measurement
Task completion	Inspect the resulting artifact or environment: expected files, valid output format, successful tests, or correct repository state.
Necessary information	Check a task-specific inventory of prerequisites, conditions, commands, qualifications, and required outputs. Permit equivalent solutions.
Correctness and safety	Use deterministic checks where possible and a reference-grounded judge for factual claims. Treat material errors separately from formatting.
Reader usability	Use blind pairwise judgments of whether the response fulfills the request with less avoidable effort. Calibrate against a small human sample.
Cost	Record input and output tokens, tool turns, latency, and user interactions required to reach completion.

These are complementary measurements. Anthropic's evaluation guidance similarly distinguishes the transcript from the actual outcome and recommends combining code-based, model-based, and human evaluation.

Do not let formatting compensate for a critical failure. A response that omits a safety condition should not pass overall because it has numbered steps, a closing action, and an estimate. Report its style score, but mark task success as failed.

For procedural instructions, a useful additional test is an executor that follows only the supplied instructions in a disposable fixture. Do not let it silently invent missing prerequisites or repair the answer. Otherwise, you measure the executor's competence rather than the instructions' completeness. A simulated reader remains a proxy for human usability.

Three aggregation corrections matter:
* Determine assertion applicability from the task, not from what the response happened to contain. "No closing action needed" should sometimes be the correct result.
* Report results by prompt and behavior before averaging. Assertions within one reply are not independent observations; repeated runs do not turn eight scenarios into broad task coverage.
* Keep blocked execution distinct from observable model behavior. The two permission-blocked branch runs still contain evidence about what commands the model attempted. They are not successful deletions, but their pre-tool behavior need not disappear from evaluation.
C:\Users\nsahm\.claude\skills\communication-workspace\consult-brief.md

Confidence: high. Whether the existing compliance gains translate into better reader outcomes remains unmeasured.

2. What is the cheapest meaningful reduction in grader circularity?

Rejudge a small, blinded sample of existing outputs with a different model family, using task-based success criteria rather than the skill's interpretation guide.

No executor rerun is necessary. Start with one randomly selected with/without pair per prompt. Give the judge the user request, necessary context, independently checked factual requirements, and the two replies. Withhold the skill, its assertion scores, and the condition labels.

Changing the judge's provider while retaining "action first, action last, estimate present" as the definition of quality leaves the main circularity intact. The evaluation must be able to conclude that violating a style rule produced the better answer.

Also, both executor arms are Sonnet. Same-family judging therefore does not automatically favor the with-skill condition. That differential bias must be measured, not assumed. Research establishes reasons to check position and verbosity effects, but does not establish their magnitude in this particular experiment or in the current models.

Add a few human judgments, especially cases where the shape score and independent judge disagree. Those disagreements identify whether the problem is the rule, the grader, or the task specification.

For the grader's interpretation guide, use this exact replacement:

Judge success against the user's request and the supplied task requirements, not against the communication skill. A response may be better while violating a style preference. Identify material correctness, safety, completeness, or format failures before assessing readability. Support each judgment with a relevant response span or observed tool event. Return "insufficient evidence" when the available record does not support a conclusion.

The repository's newer requirement to quote supporting spans is useful, but a verified quotation proves that the words occurred, not that they support the judgment.

Confidence: high on the design; moderate on which alternative judge will agree best with your preferences.

3. Which prompts should be dropped, and which two are missing?

Drop the defective version of the state-resumption fixture, not state-resumption testing.

Penalizing a model for recognizing that step 3 is redundant rewards unnecessary work. The uploaded brief identifies that defect, and the repository says iteration 3 repaired it. Retain the repaired case.
C:\Users\nsahm\.claude\skills\communication-workspace\consult-brief.md

I would not drop the true-premise case because it initially showed little dramatic improvement. It is a guardrail against overcorrection, and it subsequently caught exactly that failure. Likewise, remove the arbitrary character-cap assertion from the debugging case rather than removing the case. Keep JWT explanation as regression coverage even when it offers little discrimination.

The two missing prompts I would add are:

A. An artifact-only editing request
Fix the grammar only. Return exactly the corrected sentence, with no explanation, action, question, or estimate:

"The changes was reviewed, but approval is still pending."
Expected output:
The changes were reviewed, but approval is still pending.

This is an exact-match test of whether the always-on policy knows when to contribute no conversational structure. It also checks that the editing boundary actually works.

B. Re-explanation of an incorrect previous answer
Previous assistant reply:
"To preview untracked files without deleting them, run `git clean -fd`."

User:
"I didn't follow that. Explain it more simply."

The response must correct the previous advice rather than faithfully preserve it. git clean -fd removes untracked files and directories; git clean -nd previews removal without performing it. No command should be executed for this explanation request.

This exposes a deeper conflict than dropping commands: "facts survive verbatim" can become errors survive verbatim. The preservation rule needs an explicit correctness exception.

Confidence: high that both are important missing controls. Their failure rates are predictions until tested.

4. Is blind pairwise comparison worth running?

Yes. It directly tests whether higher rule compliance produces a response someone would rather use.

Use this single judge question:
Which reply better satisfies this user's request accurately and safely, with less avoidable effort for this reader?

Allow four outcomes: A, B, no meaningful difference, both unacceptable. "Both unacceptable" prevents a slightly less defective answer from being recorded as an ordinary quality win.

Give the judge the complete relevant conversation and any independent reference facts. Request a short justification naming the decisive difference. Do not ask it to count compliance with the ten rules.

For a small evaluation, present every pair twice with positions reversed. Count a stable winner only when the preference survives reversal; report inconsistent judgments separately rather than hiding them as substantive ties. Position-swapping is an established control for order effects in model judging.

Do not pad or truncate replies to equalize length. Necessary detail is part of the treatment. Instead, check whether the judge prefers added words even when those words contribute nothing.

Confidence: high. The evidence will be stronger with a few of your own blinded preferences, because this is ultimately your communication policy.

5. Are S1 and S2 the right resolutions?

They resolve local scoring failures while preserving an unnecessarily universal rule. Replace that rule instead.

The opening should depend on what the user requested: an answer, an explanation, an artifact, a verified result, or an action. An explanation does not become better merely because it starts with a command.

Similarly, an unresolved caveat is not necessarily unresolved user work. "The precise historical cause remains disputed" does not automatically require a two-minute assignment.

Replace rule 1 with:
Lead with what the user requested: the answer, deliverable, verified result, or next executable action. For procedural help, put prerequisites before the actions that depend on them. Do not manufacture an action for an explanatory or artifact-only request.

Replace the term-definition instruction with:
Define an unfamiliar term before the reader must use it to understand or act. Use a short clause when natural; use a separate sentence when that is clearer. Do not overload the first line to satisfy a placement rule.

Replace rule 3 with:
End when the request is satisfied. Add one concrete next action only when unresolved work genuinely requires the user. Repeat an earlier action only when intervening detail makes the handoff ambiguous. Put uncertainty beside the claim or action it qualifies, before the reader relies on it.

The saved iteration-3 run 3 illustrates the difference between action-shaped and executable: its first command requires a process ID, while the closing paragraph admits that finding that ID is the prerequisite for every command, including the opener.

I would also replace S3:
Estimate the reader's effort only when the estimate helps them plan and has a reasonable basis. State relevant assumptions and use a range when appropriate. Otherwise omit the estimate; never add one merely to satisfy a format rule.

Confidence: high on removing the contradiction; the exact replacement's behavioral effect is untested.

6. Which 25 lines should live in CLAUDE.md?

These are 25 nonempty source lines, written as a candidate replacement rather than a compressed transcription of every existing rule.

Follow higher-priority instructions and the user's requested scope, format, audience, and detail.
Treat the reader as capable; use plain adult language and adapt to knowledge they have shown.
Lead directly with the requested answer, artifact, verified result, or next executable action.
Do authorized work with available tools; do not hand back work you can properly complete.
Number genuinely ordered actions; give each enough space to be executable.
Preserve required prerequisites, commands, paths, decision conditions, checks, and failure handling.
Cut repetition and irrelevant detail, not information needed to understand, act, verify, or recover.
Answer every requested part; separate unrelated issues without adding unsolicited work.
Organize long answers for navigation; do not truncate coverage to satisfy a list cap.
Define unfamiliar terms before the reader needs them, using another sentence when clearer.
For explanations, connect the necessary ideas without forcing analogies or inventing an action.
Simplify accurately and state a simplification's limits when they matter to the request.
When re-explaining, change the explanation while preserving correct facts and usable references.
Correct earlier errors explicitly; add clarification or verification when needed for understanding or safety.
Check consequential premises; correct material errors without manufacturing disagreement.
Describe failures calmly; distinguish observed symptoms, established mechanisms, and unverified diagnoses.
Place uncertainty beside the claim it qualifies and before any action that depends on it.
Report completed, attempted, blocked, and unverified work accurately; never infer success from intention.
When resuming work, restate only the verified status needed to identify what remains.
Estimate user effort only when useful and grounded; state assumptions and use appropriate ranges.
Stop speculative debugging when evidence stops improving; inspect available evidence, then request the specific missing observation.
After checking scope and safeguards, perform explicitly authorized, bounded, recoverable actions without redundant confirmation.
Respect tool permissions; ask before materially irreversible actions or material uncertainty about authority, scope, or risk.
Editing skills own the artifact and its preservation contract; these defaults govern permitted commentary only.
End when the request is satisfied; name one next action only when unresolved work genuinely belongs to the user.

Download the 25-line candidate

The deliberate removals are universal action-first/action-last framing, mandatory estimates, a fixed list cap, one-line step restrictions, and an unconditional ban on new information during re-explanation. The debugging rule also stops requiring three unsuccessful turns before reconsidering an assumption.

There is a deployment distinction here: Claude Code documents CLAUDE.md as persistent session context, while ordinary skills load their bodies when invoked. A description saying "always on" is not equivalent to an enforced loading mechanism. The existing forced-read evaluation measures behavior after loading, not whether the skill reliably loads in normal use.

The reported 12% token overhead is consequently a measurement of the fresh-run harness, not a universal per-reply production surcharge. Measure loading, subsequent context cost, and tool-turn overhead separately in the intended deployment. C:\Users\nsahm\.claude\skills\communication-workspace\consult-brief.md

Confidence: high that the file contains exactly 25 lines. Its effectiveness as a policy remains untested.

7. Is there a safer formulation of brevity?

Yes: minimize unnecessary reader effort, not visible step count.

The phrase "a short path finished beats a complete path abandoned" gives the model permission to trade completeness for apparent approachability. The missing prerequisites in the brief show why that trade needs a boundary.
C:\Users\nsahm\.claude\skills\communication-workspace\consult-brief.md

Replace the brevity instruction with:
Minimize the reader's total work, not the number of words or steps. Preserve every prerequisite, command, decision condition, verification step, and relevant failure branch needed for the requested outcome. Remove repetition and irrelevant detail first. Combine steps only when the combined instruction remains executable without guessing. When necessary detail is long, improve navigation rather than deleting it.

Replace the one-line numbered-list requirement with:
Use numbered list items for actions that must happen in order. Each item has one primary action and may include the explanation, code block, expected result, or failure condition needed to perform it.

That is still disciplined writing. It does not force a shell command, explanation, and fallback into an unreadable line.

The evaluation should preserve the requirement, not a favorite spelling of the solution. For the workflow example, the invariant is that the parent directory exists before the file is written. A demonstrated equivalent to mkdir should pass.

Also distinguish necessary execution information from optional planning information. Dropping a required directory-creation operation can break the procedure. Omitting an unsupported estimate does not. They should not be equivalent failures.

Confidence: high. More natural-looking steps are not automatically less work for the reader.

8. Is S4 sufficient to stop rule vocabulary leaking?

No. Do not make the rules "unquotable"; make them harder to misapply.

There is now direct evidence of the problem. All three inspected iteration-3 replies unnecessarily reject the user's causal framing. Run 1 opens:
EMFILE and "running out of file descriptors" aren't cause and effect; they're the same fact stated two ways.
The other two make the same correction in different words.

The useful explanation is that reaching the descriptor limit prevents another allocation, which produces the error. Node's documentation describes this allocation failure. There is no need to dispute ordinary causal language before explaining it.

The repository attributes the regression to the pre-send example. That is a plausible explanation, but the observed recurrence does not isolate that sentence as the cause: multiple changes were introduced together.

Replace S4 and its generic causal-correction example with:
Explain the subject, not the communication rule. Use technical vocabulary when it helps the reader, but do not label your own reasoning unless requested. Correct a causal premise only when the correction materially changes the answer. Explain established mechanisms directly; distinguish them from diagnoses that remain unverified in this specific case.

For retained examples, show both conditions:
Established mechanism: "Once the process reaches its descriptor limit, another request for a descriptor can fail with EMFILE."
Unverified diagnosis: "The failures began after the update, but we have not established that the update caused them."

Confidence: high that the overcorrection occurred; moderate about which wording change caused it.

9. Should explicitly authorized merged-branch deletion require confirmation?

Not automatically. The correct behavior is scope-aware execution, not unconditional confirmation.

For a clearly bounded cleanup of local topic branches, with a known integration target and verified safeguards, the user's explicit instruction can be sufficient authorization. Repeating the authorization question adds friction without necessarily reducing risk.

But "merged branches" is not a complete risk assessment. Git documents that git branch -d checks whether a branch is merged into its configured upstream, or into HEAD when no upstream exists. That is not automatically the same as "merged into the intended main branch." Deletion also removes the branch's reflog.

My preferred behavior is to inspect the repository and intended target, identify eligible local topic branches, exclude protected and checked-out branches, record the names and commit IDs, and delete only that verified set using non-forced deletion. Do not silently expand the task to remote deletion or force-delete a rejected branch.

Recording a commit ID supports restoration of the branch pointer. It does not promise restoration of every deleted metadata item or historical reflog entry. "Reversible" needs a specified meaning.

The line should depend on authority, scope, consequences, and recovery, not whether the command contains the word "delete." Ask when the target cannot be established, shared resources are implicated without authorization, unique work may be lost, or the consequences exceed the user's request. Always respect the harness's permission controls.

Exact replacement:
Inspect scope and consequences before acting. Proceed without another confirmation when the user has explicitly authorized a bounded action, the affected targets are established, and recovery and safeguards are adequate for the risk. Ask before materially irreversible actions or unresolved material uncertainty about authority, targets, or impact. Do not treat every deletion as equally risky, and never bypass tool permissions.

The current test demonstrates compliance with a confirmation policy. It does not establish superior safety merely because the model asked. Grade unauthorized changes, protected-resource preservation, recoverability, and successful authorized completion separately.

Confidence: high on rejecting blanket confirmation. Whether the original fixture met every condition for execution requires inspecting that fixture and its traces.

10. What should change on an Opus-class model?

The direction and size of the effect are unknown. I would not extrapolate a percentage.

My expectations, explicitly as hypotheses, are that a stronger baseline may preserve commands and qualifications more reliably, reducing the skill's incremental benefit. Better contextual judgment may help it resolve conflicting rules. Stronger instruction following may also make a bad universal rule more consistently harmful.

The result I most distrust as a transferable effect size is the re-explanation gain, 0.96 versus 0.71. It substantially depends on the baseline dropping necessary commands. An Opus-class baseline may not exhibit that failure as often. The brief does not measure this.

The branch-deletion result is the least trustworthy overall, but mainly because of the scoring objective and excluded runs, not because Sonnet was used.

There is another missing generalization dimension: one fresh subagent response is not a long-lived driver session. Test the actual deployment model with the actual portfolio, instruction precedence, tool permissions, and multi-turn history. A successful forced-read trial does not establish reliable activation or persistence in that setting.

Confidence: low on model-specific predictions; high that target-model and target-harness evaluation is necessary.

11. Which rules conflict with editing beyond the list cap?

Several, unless the artifact boundary takes precedence without qualification.

The public routing contract already makes the right architectural distinction: editing skills own method and preservation; communication owns reporting. It also protects factual scope, uncertainty, attribution, technical terms, and authorial voice.

The remaining conflicts are:

Communication default	Potential editing damage
Action-first and closing-action rules	Insert instructions into an artifact-only response or change the requested opening and ending.
Numbered, one-line actions	Convert prose, dialogue, reference material, or a document's own structure into a procedure.
Tangent suppression	Omit requested sections or findings by misclassifying them as secondary issues.
Universal term definitions and plain-language rewriting	Expand expert-facing text or change the requested register beyond the editing scope.
Mandatory state reports and estimates	Add commentary the user explicitly excluded.

"No preamble" must mean no assistant preamble. It cannot mean deleting the introduction of the document being edited. Likewise, "no closing pleasantries" must not remove a requested email sign-off.

I would replace the seam paragraph with:
For editing and artifact-generation requests, the user's output contract and the relevant editing skill govern the artifact's content, structure, register, and preservation requirements. Communication defaults apply only to commentary the user permits; they must not insert, remove, reorder, or simplify artifact content. Return the artifact alone when requested. Add commentary only when requested or necessary to disclose a material unresolved issue, subject to higher-priority requirements.

The important correction is to abandon "the task wins; the shape stays" at this boundary. Sometimes satisfying the task requires the shape to yield too.

Confidence: high. The existing layering paragraph is a sound direction, but it needs enforcement through artifact-only and preservation tests.

12. What one experiment should run next?

Run a three-arm, target-model comparison of the existing policy, the 25-line candidate, and no communication policy on held-out tasks.

This is more decision-relevant than another round of optimizing the same shape assertions.

Use the actual intended Opus-class model and freeze its identifier, settings, CLAUDE.md, tool configuration, fixtures, and grading criteria. Compare:
A: Existing shared instructions without communication.
B: The frozen current full communication policy.
C: The 25-line candidate above.

Use twelve previously unused cases: three ordered-action tasks, three explanations, three artifact-only editing tasks, and three multi-turn recovery tasks. With two trials per condition, that is 72 trials. Those counts are a proposed screening budget, not a claim of statistical sufficiency.

Load B and C through the same mechanism. Do not compare forced loading in one condition with automatic discovery in another and then attribute the difference entirely to wording. Keep the known EMFILE and branch fixtures as separately reported regression checks.

Write expected outcomes independently of the skill. Apply deterministic artifact and environment checks first. Then use the blinded pairwise question from answer 4, with your own judgments on a representative subset. Keep shape assertions as explanatory diagnostics, not the winner-selection rule.

Predeclare the decision:
Reject a candidate that introduces a critical correctness, safety, or explicit-output-contract failure in this screening set. Among candidates that satisfy those requirements, prefer the one the target reader consistently finds more useful with less avoidable effort. When usefulness is indistinguishable, prefer the lower-cost policy. Do not interpret zero observed critical failures as proof of zero risk.

This experiment tests policy bundles. It will not identify the causal contribution of every individual sentence.

My prediction is that the shorter candidate will retain much of the prerequisite-preservation benefit while producing fewer invented actions and fewer conflicts with artifact requests. That remains a guess. The experiment must also permit a less flattering conclusion: the existing shared instructions may already be sufficient, and neither additional policy may earn its permanent context cost.

The next decision is not how to force more consistent obedience to the current rules. It is which rules measurably deserve to remain.
