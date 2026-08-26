# Claude review of `codex/claude-review-feedback` (PR #2)

Reviewer: Claude (Anthropic), via Claude Code with a fresh worktree of the branch.
Branch: `codex/claude-review-feedback` at `7aac10137397a7f001b47b2ebeaeff8a632c73ea`, diffed against base `codex/evaluation-audit-bundle` at `5d1f2b4cf83c54b5b70e5d10f16a85cbc07b9ba4`.
Method: every quantitative claim in `CODEX_RESPONSE_TO_CLAUDE.md`, the PR description, and checkpoint 04 recomputed with independently written code against `taxonomy/`, `private/gold/`, and `runs/stage1-sealed-v1/` only. The evaluator's scoring code was not executed to produce any number here.

## 1. Verdict

**The integration is correct. The F4 correction from 80 to 84 is right, and the original review's count of 80 was wrong.** I reproduced the corrected total and the full per-code table to the digit; the first review missed 3 `complex_sentence` findings and 1 `negation_ambiguity` finding. The narrowed paired-false-negative claim is also right, and my recount shows the narrowed wording is safe in the strict direction (R2 below). Every other number Codex added — the F1 four-way overlap decomposition, both portfolio-localization definitions, the pinned clean-case error, the 36 byte-identical raw/inbox pairs, both manifest entry counts, and the preservation boundaries — reproduces exactly.

One finding needs a wording fix and a metadata pin before the PR leaves draft: the test-count claim as phrased in the PR description and `publication/resume.md` does not reproduce on Linux and conflates tests run with tests passed (R3). It is a reporting defect, not an evidence defect, and it does not change any conclusion.

## 2. Findings

**R1 (concession and confirmation): F4 = 84, not 80.** Independently recomputed from `taxonomy/problem-families.json` (36 CHANGE + 11 KEEP = 47 public codes), `taxonomy/native-map.json` (37 distinct emittable outputs), and the 33 valid normalized runs: the 10 structurally unreachable public codes are exactly the set both documents name, and predicted CHANGE findings using them total **84** of 1,220 — `causal_overclaim` 46, `synonym_cycling` 13, `nominalization` 12, `overgeneralization` 5, `misplaced_modifier` 4, `complex_sentence` 3, `negation_ambiguity` 1, and 0 for `dangling_modifier`, `noun_stack`, `repetitive_conclusion`. The original review's 80 dropped the two smallest nonzero codes. The correction is accepted; the erratum §6 text now in this branch states the reproduced numbers. Observed.

**R2 (strengthens the narrowed claim): the 19 exact-boundary cases are all true FP+FN pairs.** Codex narrowed "each creates a paired FN" to the observation that only 64 of the 84 overlap any gold CHANGE region and only 19 share exact gold boundaries. Both numbers reproduce. I checked one step further: for each of the 19 unreachable-code findings with exact gold boundaries, no other prediction in the same run matched that gold finding exactly on boundaries and code. So none of the 19 gold counterparts was rescued elsewhere, and all 19 are genuine exact-FP-plus-exact-FN pairs, while the remaining 65 are guaranteed exact FPs whose FN pairing depends on the matching rule. The erratum's phrasing — "a unique paired false negative cannot be assigned to every such prediction" — is exactly as strong as the evidence supports. Optionally add the 19/19 result to §6; it is the floor the original overclaim was reaching for. Observed.

**R3 (documentation, fix wording and pin the platform): the test-count claim conflates ran with passed and omits the environment that makes it true.** The PR description and `publication/resume.md` say the suite gives "198 passed with 2 expected skips" on Python 3.11 and 3.14. On this branch under Linux, Python 3.11.15, the suite gives **187 passed, 11 skipped** under pytest and `Ran 198 tests ... OK (skipped=11)` under unittest; all 11 skips are `skipUnless(os.name == "nt")` guards. The 2-skip profile is only reachable on Windows, where the 11 Windows guards execute and the two symlink-availability tests in `tests/test_ingest_paths.py` skip instead — and checkpoint 04's own internals corroborate a Windows run (`"sort_order": "StringComparer.Ordinal"`, a `reparse_points` counter). Checkpoint 04 records the honest form (`tests: 198, skipped: 2`, i.e. 196 passed); the PR description and resume compress that to "198 passed," which no platform produces. Given that erratum §9 is precisely about incomplete reproducibility metadata, the run environment should be pinned: state the OS in checkpoint 04 and reword the two prose claims to "198 tests ran with 2 expected Windows symlink skips (196 passed)" or equivalent. The constructive result: across the exchange, the union of Codex's Windows runs and Claude's Linux runs has now executed all 198 tests with zero failures — worth one line in the resume, because neither environment alone can. Observed.

**R4 (confirmations of the remaining integration claims).** All Observed:
- F1 decomposition: of 1,220 predicted CHANGE findings, 170 overlap a gold CHANGE region and at least one preservation target — 110 via KEEP-decision gold findings, 116 via explicit protected regions, 56 via both. The rewritten erratum §5 states these correctly.
- F3 both definitions: 31/33/34 (any CHANGE finding in a CHANGE case) versus 31/32/33 (finding overlaps a gold CHANGE region); exactly one clean-case error across the three runs, `WQ-S001-007` in run 1. The rewritten root-cause paragraph matches.
- Transport equality: all 36 sealed `inbox/`–`raw/` filename pairs byte-identical, zero mismatches, closing the original review's unresolved question 4.
- Integrity: root manifest 560 entries, evaluation manifest 473, zero hash mismatches, both ordinally sorted. The root-manifest delta against base decomposes exactly into 6 re-hashed edited files, 4 added files, and 13 lines that merely moved under the re-sort with unchanged hashes — nothing else.
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
| Tests: "198 passed, 2 skips" (Py 3.11, 3.14) | as stated | 187 passed, 11 skipped on Linux Py 3.11.15; 2-skip profile is Windows-only; 3.14 not available here | Divergent, see R3 |

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
cd ../.. && sha256sum -c MANIFEST.sha256          # 560 entries, 0 mismatches
cd evaluation && sha256sum -c MANIFEST.sha256     # 473 entries, 0 mismatches
python3 scripts/validate_portfolio.py             # VALIDATION PASSED
```

## 4. Recommended changes

Blocking: none.

Before the PR leaves draft (documentation only; regenerate both manifests if applied):
1. Reword the test claim in `publication/resume.md` and the PR description per R3, and pin the operating system in checkpoint 04's `tests` block.
2. Optionally add the 19/19 unrescued result to erratum §6 per R2 and note the two-platform union coverage in the resume.

## 5. Remaining unknowns

Unchanged from the first exchange: whether any system exploited the case-ID pattern is undecidable from preserved evidence; exact model identity, rendered prompts, and generation settings remain unpreserved by design; the two disputed gold labels (`WQ-S002-005`, `WQ-S003-002`) still await the independent human protocol. This review adds no new unknowns; it retires none.
