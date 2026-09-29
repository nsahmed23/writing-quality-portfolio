# Automated evaluator final review — 2026-09-28

The three implementation tasks had separate code/spec reviews and scoped reviews of fixes. A separate final reviewer inspected the complete change from `4f00130` to `526d7d9`, then reviewed the final correction at `2a4948c`. Reviews used the binding design, implementation plan and actual code, with focused local reproductions; they did not run a model benchmark.

| Final finding | Resolution |
|---|---|
| Identical same-split cases could be assigned different document IDs and counted as independent evidence. | Suite validation rejects normalized identical prompt/context/pair aliases under different document IDs across all splits. Repetitions within one document remain valid. Regression checks cover calibration and comparison aliases, reversed pairs and whitespace variants. |
| Codex final-message bytes were lost after nonzero exit or timeout. | The runner supplies a persistent per-call response path and recovers its bytes after process termination. The raw response, wrapper stdout and provider logs retain separate artifacts and truthful hashes. Invalid calls remain invalid and are not retried. |

The reviewer independently ran the three new regressions: all passed. The scoped rereview found both Important findings addressed, no new issue in the fix diff, and approved the corrected code subject to controller verification and packaging. Controller verification subsequently passed all 83 root tests. Full review and implementation records accompany the delivery archive.

## Review boundaries

No live quality result, authenticated provider compatibility, Windows process behavior, or family independence beyond declared configuration was established. The local-adapter/report trust boundary is explicit: hashes detect mismatch, not fabricated evidence or hostile executables. Semantic near-duplicate detection, full routed-portfolio execution, model-weight training, automatic skill deployment and human validation remain outside this milestone. Three new root test files follow the plan's explicit task ownership; no existing test file changed. Archive restoration and manifest verification are controller delivery checks.
