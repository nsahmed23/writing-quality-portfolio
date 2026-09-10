# Review of the iteration-4 report: the decision and v5 (reviewer C, unattributed)

Received 2026-09-09, forwarded by the user. Verbatim.

---

The decision holds, but for a narrower reason than "full wins," and the tables point at a cheaper v5 than the report suggests.

What the numbers say. Split the corpus the way the report does. On the two regression cases, full wins 7 to 0 across both judges because it carries the two fixes the other arms lack; that is expected and it is where the entire net-score gap comes from. On the twelve held-out cases, full beats none clearly under Codex (11 to 1) and not at all under Gemini (6 to 6), and full versus short is a wash: Codex 4 to 3 with 8 ties, Gemini 2 to 6 with 10 ties. So the ranking "full > short" is a Codex verdict on procedures plus the regressions; Gemini leans short on new material. The Q12 experiment answered its question: on Opus 5, the policy sentences do most of the work and the examples earn their tokens on ordered procedures (Codex 5 to 0; full is the only arm that opens on the action and ends on the check, 12 of 12) and nowhere else. The planned blinded judgments of your own on the disagreement pairs are now the tiebreaker between the two judges, and the corpus for them already exists.

Deployment follows from that. Full v5 in Claude Code, where it sits in system context and the read cost you measured (about 8k tokens and 20 seconds per run in the subagent path) mostly disappears under prompt caching. Short v5 everywhere with an instruction-size limit, regenerated from full after each iteration so it stays one skill in two sizes. The short candidate must carry the two policy sentences it lacked, because that is exactly where it lost 4 to 0.

v5 wording. Five edits, all small:

1. Case 12. The loophole is ordering: the proceed clause comes first and reads as the rule, the ask-first list reads as the exception. Reverse it and close the recovery argument: "Some actions are confirmed even after 'don't ask': git branch -D, force push, rm -rf, a schema migration, dropping a table, anything touching a remote or another person's work. Before any of these, show what would be lost (for a branch, git log main..<branch>) and ask once. Recovery through the reflog or a backup does not make an action reversible here; only recovery visible in the command's own output does. Outside this list, an explicit waiver in the current request is honored: do it, list what changed, give the undo." Keep the case's expected answer; twelve of twelve both-unacceptable verdicts agree with it.
2. Wireshark. "When the request is a question (why, how does, what is), the first line is the answer and the last line is the edge of the answer, the point where the simple model stops holding. Do not add a command or a check to give the reply an action; an explanation has none unless the reader asked what to do."
3. Sourdough labels. "Never classify the reader's statement with a category word: no 'that is a sequence, not a cause,' no 'that is an association.' Say what happened and what connects it in ordinary words: 'the loaf stopped rising the week you switched flour; nothing yet shows the flour did it.' Ordinary use of these words ('the mechanism is that...') is fine; the label applied to the reader's claim is not."
4. Two-issues loss. The skill picked an action, just not the best one. Add to rule 1: "The first action is the one that settles the most with the least work. When evidence already exists (a log, an artifact, a failing run), read it before reproducing it."
5. The sourdough answer key. Four both-unacceptable verdicts came from one prescribed first step. Rewrite the key as the property a good first step has (one variable changed, the starter not wasted) so it stops measuring key adherence.

What not to do next: another 84-run three-arm. v5 changes five places; rerun only the cases they touch (case 12, the two TCP explanations, sourdough, the two-issues message) on full and short, two runs each, about 20 runs, then the disagreement pairs by your own hand.

Unverified by me: I read the summary, the arm and pairwise tables, and case 1 in full; I did not read the other 78 replies, so the shape and preservation claims for those rest on the report's graders and its quote audit.
