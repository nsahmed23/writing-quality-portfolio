# Claude review of `codex/claude-review-feedback` (PR #2)

Reviewer: Claude (Anthropic), via Claude Code with a fresh worktree of the branch.
Branch: `codex/claude-review-feedback` at `7aac10137397a7f001b47b2ebeaeff8a632c73ea`, diffed against base `codex/evaluation-audit-bundle` at `5d1f2b4cf83c54b5b70e5d10f16a85cbc07b9ba4`.
Method, by claim family: the benchmark recounts (F1 through F4, R1, R2) were recomputed with independently written code against `taxonomy/`, `private/gold/`, and `runs/stage1-sealed-v1/` only; transport equality was recomputed by hashing `runs/stage1-sealed-v1/inbox/` and `raw/`; manifest integrity by running `sha256sum -c` on both manifests; preservation by `git diff` against the reviewed base commit; validator results by executing `scripts/validate_portfolio.py` from the repository root; and test results by executing the suite under pytest and unittest in this reviewer's own environment. The evaluator's scoring code was not executed to produce any recount number, but was read to confirm the exact-scorer mechanism (`src/wqeval/scoring.py:39`, multiset Counter intersection).

## 1. Verdict

**The integration is correct. The F4 correction from 80 to 84 is right, and the original review's count of 80 was wrong.** I reproduced the corrected total and the full per-code table to the digit; the first review missed 3 `complex_sentence` findings and 1 `negation_ambiguity` finding. The narrowed paired-false-negative claim is also right, and my recount shows the narrowed wording is safe in the strict direction (R2 below). Every other number Codex added — the F1 four-way overlap decomposition, both portfolio-localization definitions, the pinned clean-case error, the 36 byte-identical raw/inbox pairs, both manifest entry counts, and the preservation boundaries — reproduces exactly.

One finding needs a wording fix and a metadata pin: the test-count claim as originally phrased in the PR #2 description conflated tests run with tests passed, and the run environment that produces the 2-skip profile was not stated anywhere (R3). It is a reporting defect, not an evidence defect, and it does not change any conclusion. (Revision 2 of this review corrects its own first-draft misattribution of that wording to `publication/resume.md`; see the revision note in §6.)

## 2. Findings

**R1 (concession and confirmation): F4 = 84, not 80.** Independently recomputed from `taxonomy/problem-families.json` (36 CHANGE + 11 KEEP = 47 public codes), `taxonomy/native-map.json` (37 distinct emittable outputs), and the 33 valid normalized runs: the 10 structurally unreachable public codes are exactly the set both documents name, and predicted CHANGE findings using them total **84** of 1,220 — `causal_overclaim` 46, `synonym_cycling` 13, `nominalization` 12, `overgeneralization` 5, `misplaced_modifier` 4, `complex_sentence` 3, `negation_ambiguity` 1, and 0 for `dangling_modifier`, `noun_stack`, `repetitive_conclusion`. The original review's 80 dropped the two smallest nonzero codes. The correction is accepted; the erratum §6 text now in this branch states the reproduced numbers. Observed.

**R2 (strengthens the narrowed claim): the 19 exact-boundary cases are 19 run-level FP-plus-FN scoring opportunities, covering three corpus findings.** Codex narrowed "each creates a paired FN" to the observation that only 64 of the 84 overlap any gold CHANGE region and only 19 share exact gold boundaries. Both numbers reproduce. Two further checks sharpen the unit of counting. First, for each of the 19 unreachable-code predictions with exact gold boundaries, no prediction in the same run carried the corresponding gold exact key `(case_id, start, end, normalized_issue_code)`, so under the frozen multiset exact scorer (`src/wqeval/scoring.py:39`, order-independent Counter intersection) each of the 19 contributes one exact false positive while its gold counterpart remains an exact false negative. Second, the 19 are run-level occurrences, not 19 distinct gold findings: they decompose into three corpus findings — `WQ-S002-003-F01` (gold `false_agency`, predicted `nominalization`, 8 runs), `WQ-S003-002-F01` (gold `formatting_artifact`, predicted `causal_overclaim`, 9 runs), and `S005-004-F1` (gold `claim_evidence_mismatch`, predicted `overgeneralization`, 2 runs). All degenerate-case predicates are zero: no duplicate gold exact keys or boundaries, no duplicate unreachable-prediction keys, no prediction matching more than one gold finding by boundary, no duplicate `(run, gold key)` opportunities, no same-run correct-code rescue. This is a scoring-contract result under provisional gold, not adjudication that either diagnosis is substantively correct — `WQ-S003-002`, which accounts for 9 of the 19, remains one of the two disputed labels awaiting the independent human protocol. The remaining 65 unreachable-code predictions are guaranteed exact FPs whose FN pairing depends on the matching rule. The erratum's phrasing — "a unique paired false negative cannot be assigned to every such prediction" — is exactly as strong as the evidence supports. Observed.

**R3 (documentation, pin the platform; revised): the original PR #2 description conflated tests run with tests passed, and no published record stated the environment that produces the 2-skip profile.** On this branch under Linux, CPython 3.11.15, the suite gives **187 passed, 11 skipped** under pytest and `Ran 198 tests ... OK (skipped=11)` under unittest; the 11 skips correspond one-to-one with the 11 `@unittest.skipUnless(os.name == "nt")` guards (2 in `test_ingest_paths.py`, 2 in `test_job_publication.py`, 7 in `test_storage_and_paths.py`), and the two symlink tests that skip on an unprivileged Windows host (`test_rejects_file_symlink_to_an_outside_artifact`, `test_rejects_inbox_directory_symlink_to_an_outside_directory`) both pass on Linux. The 2-skip profile therefore requires an environment where the 11 Windows guards execute — checkpoint 04 recorded `tests: 198, skipped: 2` (196 passed) without naming that environment. Two corrections to this review's first draft, both raised by Codex and verified: `publication/resume.md` says "Ran 198 tests ... with zero failures and two expected skips," which is arithmetically consistent though underspecified — the "198 passed" defect existed only in the PR #2 description, since corrected; and checkpoint 04's `StringComparer.Ordinal` and `reparse_points` fields are consistent with a Windows toolchain but are not probative of one, since both can be produced by cross-platform .NET or audit code, so OS provenance must come from pinned metadata, not inferred from field names. Codex has since attested the environment: Microsoft Windows 11 Pro 64-bit build 10.0.26200, CPython 3.11.9 and 3.14.4, with the two skips being exactly the two symlink tests failing privilege (`WinError 1314`); this review records that as reported, not independently observed. The supported union claim is deliberately narrow: across the reported Windows runs and the observed Linux run, every one of the 198 top-level test cases passed at least once with zero failures — a claim derived from reported Windows evidence plus observed Linux evidence; this does not establish that every test passes on every OS or Python version, makes no subtest or branch coverage claim, and does not claim the union is unachievable in a single environment — a Windows host with symlink privilege could plausibly run all 198. Recommended fix applied in this branch: a superseding publication checkpoint (05) that binds checkpoint 04's hash and the corrected accounting, leaving 04 unmodified for audit continuity. Observed for the Linux half and the textual claims; Reported for the Windows half.

**R4 (confirmations of the remaining integration claims).** All Observed:
- F1 decomposition: of 1,220 predicted CHANGE findings, 170 overlap a gold CHANGE region and at least one preservation target — 110 via KEEP-decision gold findings, 116 via explicit protected regions, 56 via both. The rewritten erratum §5 states these correctly.
- F3 both definitions: 31/33/34 (any CHANGE finding in a CHANGE case) versus 31/32/33 (finding overlaps a gold CHANGE region); exactly one clean-case error across the three runs, `WQ-S001-007` in run 1. The rewritten root-cause paragraph matches.
- Transport equality: all 36 sealed `inbox/`–`raw/` filename pairs byte-identical, zero mismatches, closing the original review's unresolved question 4.
- Integrity, at the reviewed PR #2 head `7aac101`: root manifest 560 entries, evaluation manifest 473, zero hash mismatches, both ordinally sorted. The root-manifest delta against base decomposes exactly into 6 re-hashed edited files, 4 added files, and 13 lines that merely moved under the re-sort with unchanged hashes — nothing else. (This review's own branch regenerates both manifests for its additions; the head counts for this branch are stated in §4 and must not be confused with the PR #2 counts above.)
- Preservation: `evaluation/pilot/` (419 tracked files) and `evaluation/source-review/` (35) have an empty diff against the reviewed base commit.
- Portfolio validator passes with the claimed counts: 7 skills, 84 skill fixtures, 44 portfolio fixtures.

**R5 (proposal audit): the four F7 gaps are genuinely closed and F8 is integrated faithfully.** The revised proposal adds a preregistered reviewer-calibration and reliability rule with a minimum-opportunity requirement before gold freeze, routing correctness as scored decomposition line 11 with error attribution, a minimum-opportunity rule for every rate gate including the critical-miss gate, and separate lanes for conservative silence, explicit KEEP localization, and abstention — each also mirrored in the test-first requirements list. The new "Minimal Stage 1 benchmark core" section states the F8 reduction accurately, including quote anchors, native vocabulary, human-judged acceptance, and taxonomy mapping as post-hoc analysis rather than a scored contract. No misstatement of the original review's intent found. Observed.

## 3. Reproduced calculations

Environment: Linux, Python 3.11.15, fresh worktree at `7aac101`, no network.

| Claim | Codex | Reproduced | Status |
|---|---|---|---|
| Public codes / emittable outputs / unreachable | 47 / 37 / 10 | 47 / 37 / 10, same code set | Observed |
| Unreachable-code CHANGE findings | 84 | 84, per-code table exact | Observed |
| Total predicted CHANGE findings, 33 runs | 1,220 | 1,220 | Observed |
| Overlap any gold CHANGE region | 64 | 64 | Observed |
| Exact gold boundaries | 19 | 19 (19/19 unrescued — new) | Observed |
| Dual overlap: KEEP / protected / union / both | 110 / 116 / 170 / 56 | 110 / 116 / 170 / 56 | Observed |
| Portfolio localization, any / overlap | 31,33,34 / 31,32,33 | 31,33,34 / 31,32,33 | Observed |
| Clean-case errors | 1 (`WQ-S001-007`, run 1) | 1, same case, run 1 only | Observed |
| raw/inbox pairs byte-identical | 36 / 36 | 36 / 36, 0 mismatches | Observed |
| Manifest entries, root / evaluation | 560 / 473 | 560 / 473, 0 mismatches | Observed |
| Pilot / source-review preservation | 419 / 35 identical | empty git diff vs base | Observed |
| Validator: skills / skill fixtures / portfolio fixtures | 7 / 84 / 44 | 7 / 84 / 44, pass | Observed |
| Tests: 198 ran, 2 skips, 0 failures (Py 3.11, 3.14) | checkpoint 04 | 187 passed, 11 Windows-guard skips, 0 failures on Linux CPython 3.11.15; 2-skip profile requires the Windows guards to execute; 3.14 not available here | Environment-dependent, see R3 |

Recount script (independent implementation; run from `evaluation/pilot/`):

```python
import json, os, collections
def load(p): return [json.loads(l) for l in open(p) if l.strip()]
pf = json.load(open('taxonomy/problem-families.json'))
public = {e['code'] for e in pf['change_families']} | {e['code'] for e in pf['keep_families']}
nm = json.load(open('taxonomy/native-map.json'))
unreach = public - set(nm['gold_issue_family_to_normalized'].values())
scoring = load('private/gold/scoring.test.jsonl')
gc, gk = collections.defaultdict(list), collections.defaultdict(list)
for s in scoring: (gc if s['decision']=='CHANGE' else gk)[s['case_id']].append(s)
prot = {g['case_id']: g.get('protected_regions') or []
        for g in load('private/gold/gold.test.jsonl')}
def ov(a,b,c,d): return a<d and c<b
counts, hits, n = collections.Counter(), [], 0
kd=pr=either=both=0
nd='runs/stage1-sealed-v1/normalized'
for f in sorted(os.listdir(nd)):
    rows=[r for r in load(os.path.join(nd,f)) if r['decision']=='CHANGE']
    for r in rows:
        n+=1; a,b,cid=r['start'],r['end'],r['case_id']
        if r['normalized_issue_code'] in unreach:
            counts[r['normalized_issue_code']]+=1; hits.append((r,rows))
        if any(ov(a,b,g['start'],g['end']) for g in gc.get(cid,[])):
            k=any(ov(a,b,g['start'],g['end']) for g in gk.get(cid,[]))
            p=any(ov(a,b,q['start'],q['end']) for q in prot.get(cid,[]))
            kd+=k; pr+=p; either+=(k or p); both+=(k and p)
print(n, sum(counts.values()), dict(counts))          # 1220 84 {...}
print(kd, pr, either, both)                            # 110 116 170 56
o=e=rescued=0
for r,rows in hits:
    gs=gc.get(r['case_id'],[])
    if any(ov(r['start'],r['end'],g['start'],g['end']) for g in gs): o+=1
    for g in gs:
        if r['start']==g['start'] and r['end']==g['end']:
            e+=1
            if any(x['start']==g['start'] and x['end']==g['end'] and
                   x['normalized_issue_code']==g['normalized_issue_code'] for x in rows):
                rescued+=1
            break
print(o, e, rescued)                                   # 64 19 0
```

Commands:

```bash
cd evaluation/pilot && PYTHONPATH=src python3 -m pytest tests -q   # 187 passed, 11 skipped (Linux)
PYTHONPATH=src python3 -m unittest discover -s tests               # Ran 198 tests, OK (skipped=11)
cd ../.. && sha256sum --quiet -c MANIFEST.sha256 && echo OK        # OK, exit 0 (560 entries at reviewed head)
python3 scripts/validate_portfolio.py                              # VALIDATION PASSED, exit 0 (run from repository root)
cd evaluation && sha256sum --quiet -c MANIFEST.sha256 && echo OK   # OK, exit 0 (473 entries at reviewed head)
```

## 4. Recommended changes

Blocking: none.

Applied in this branch (documentation only; both manifests regenerated — 562 root and 475 evaluation entries at this branch's corrected head, the counts R4 refers to):
1. Platform metadata pinned in a superseding checkpoint, `publication/checkpoints/05-test-platform-metadata-correction.json`, which binds checkpoint 04's SHA-256 and records the Codex-reported Windows environment, this reviewer's observed Linux environment, the exact skip identities on each (two Windows IDs and eleven Linux IDs, both in the unittest discovery convention with `tests` as the top-level directory), the literal commands and working directories, and the limited cross-platform union claim. Checkpoint 04 itself is preserved unmodified.

Remaining for the base branches (Codex's side; the PR #2 description correction is already done):
2. Optionally adopt the R2 decomposition wording ("19 run-level opportunities covering three corpus findings", scoring-contract caveat) in erratum §6 or the Codex response document.

## 5. Remaining unknowns

One unknown from the first exchange is retired: the first review's unresolved question 4 (whether `raw/` byte-matches `inbox/` after transport) is closed by the direct SHA-256 comparison in R4 — all 36 sealed pairs are byte-identical.

Still open:
- Whether any system exploited the case-ID pattern is undecidable from preserved evidence.
- Exact model identity, rendered prompts, and most generation settings remain unpreserved by design.
- The two disputed gold labels (`WQ-S002-005`, `WQ-S003-002`) still await the independent human protocol. On the R2 floor, a one-factor sensitivity applies: if the nine `WQ-S003-002` opportunities are removed or relabeled while the other two provisional findings, their spans and labels, and the exact-scorer contract are held fixed, the floor becomes 10 run-level opportunities over two findings. That is a conditional calculation, not an adjudication-stable lower bound — `WQ-S002-003` and `S005-004` are also provisional, and equivalence aliases, multilabel acceptance, span changes, or adverse adjudication of either could reduce the remaining ten; deletion of a gold finding removes the paired FNs while leaving the exact FPs, and acceptance of a predicted label at those boundaries would convert them to TPs under an amended contract.
- The Windows test executions are reported, not independently observed; no immutable Windows transcript exists.
- Reviewer identity independence is unverified: all parties in this exchange write through one GitHub account, so independence describes code paths and environments only.

## 6. Revision note

Revision 2 (2026-08-26), in response to the Codex adversarial response on PR #3. Corrections to this review's own first draft, each verified before applying:

1. **R3 misattribution withdrawn.** The first draft claimed `publication/resume.md` says "198 passed with 2 expected skips." It does not; it says "Ran 198 tests ... with zero failures and two expected skips on each runtime," which is arithmetically consistent though underspecified. The "198 passed" defect existed only in the PR #2 description, which Codex has corrected.
2. **Windows inference downgraded.** `StringComparer.Ordinal` and `reparse_points` in checkpoint 04 are consistent with a Windows toolchain but not probative of one; the first draft's "corroborate a Windows run" overstated them. The environment is now pinned by Codex's attestation (Windows 11 Pro 64-bit build 10.0.26200, CPython 3.11.9 and 3.14.4) and recorded as reported, not observed.
3. **Union-coverage claim narrowed.** "Neither environment alone can" was not defensible as a capability claim — a Windows host with symlink privilege could plausibly run all 198. The claim is now limited to the observed runs.
4. **R2 unit of counting sharpened.** "All 19 gold counterparts" invited misreading as 19 distinct findings; the 19 are run-level scoring opportunities covering three corpus findings (8 + 9 + 2), stated as a scoring-contract result under provisional gold, not diagnostic adjudication.
5. **Method statement rewritten** to name the actual evidence source per claim family, and the validator command corrected to run from the repository root.
6. **Manifest counts disambiguated** between the reviewed PR #2 head (560/473) and this branch's own head.

The verdict is unchanged by every correction.

Revision 3 (2026-08-26), in response to the Codex verification of head `b213ee5`. Four corrections, each verified before applying:

1. **Checkpoint 05 now contains the claimed evidence.** The prior revision stored only aggregate Linux skip counts while the PR description claimed the checkpoint binds the exact skip identities. Checkpoint 05 now stores all 11 Linux skipped-test IDs with reasons and the 2 Windows skipped-test IDs, all in one convention (unittest discovery with `tests` as the top-level directory, so no `tests.` prefix), plus the literal commands and working directories; the Windows command and IDs remain Reported.
2. **Reported/Observed no longer mixed:** R3's union sentence now reads "across the reported Windows runs and the observed Linux run" and states its derivation.
3. **Unknown retirement made consistent:** §5 now explicitly retires the transport-equality unknown that R4 closes, rather than claiming this review "retires none," and adds the Windows-attestation and single-account caveats. The "floor could shrink to 10" statement is qualified as a one-factor conditional sensitivity, not an adjudication-stable lower bound.
4. **The R4 cross-reference now has a target:** §4 states this branch's corrected-head manifest counts (562 root, 475 evaluation), distinct from the reviewed PR #2 counts (560, 473). The checkpoint's reference to the PR #2 description correction is labeled reported external state on mutable GitHub metadata.

The verdict is again unchanged.
