# Claude review of `codex/evaluation-audit-bundle` (PR #1)

Reviewer: Claude (Anthropic), via claude.ai chat with a sandboxed clone of the branch.
Branch: `codex/evaluation-audit-bundle` at `5d1f2b4cf83c54b5b70e5d10f16a85cbc07b9ba4`.
Method: fresh shallow clone; every quantitative claim in the erratum recomputed with independently written code against `corpus/`, `private/gold/`, and `runs/stage1-sealed-v1/` only. The evaluator's own scoring code was read to learn the registered contracts but never executed to produce any number in this review.

## 1. Verdict and scope

**The erratum survives an adversarial recount. Merge the branch as an evidence record.** I attempted to falsify the corrected diagnosis per the handoff and failed on every material quantitative claim. The corrected conclusion is the right one: the arithmetic is reproducible, and the benchmark cannot support ranking or general diagnostic-quality claims. Three wording defects in the erratum and root-cause analysis should be corrected before or at merge; none is blocking, and none changes a conclusion.

Scope limits: I could not verify the second Python version, the frozen-evidence replay path (absolute-path dependent by design), the original model calls (unpreserved by design), or the report's token and timing figures. These match the declared portability boundary and are treated as evidence gaps, not defects.

## 2. Findings ordered by severity

**F1 (documentation, fix wording): the "110" dual-overlap statistic is ambiguous and reproduces only under one reading.** Erratum §5 says 110 CHANGE findings overlapped "both a gold CHANGE region and a separate KEEP region." Recomputed: 110 when "KEEP region" means KEEP-decision gold findings only, 116 for protected regions only, 170 for the union. Because §5 is about protected regions, a reader will assume the wrong denominator. The union reading makes the problem worse, not better, so the direction stands; state the definition and preferably report the union figure (170). Observed.

**F2 (documentation, fix wording): "Five malformed records out of 2,592" mixes units.** The five defects are finding-level; 2,592 counts case records (36 runs x 72). Suggested wording: "five malformed findings across 2,592 case records." The five are now pinned exactly: `S005-004-F001` (bad offset, avoid-ai-writing run 2), `WQ-S003-007-f1` (span mismatch, kami-writing run 3), and three findings in no-ai-slop run 1 (`S004-005-F001`, `WQ-S002-002-F001`, `WQ-S003-007-F001`) whose `suggested_operation` lacks the `instruction` key required by the exact-keys contract in `src/wqeval/validation.py:167`. Observed.

**F3 (documentation, add one line): the root-cause localization counts (31, 33, 34) use the any-CHANGE-finding reading.** Under the stricter reading (a CHANGE finding overlapping a gold CHANGE region), run 2 is 32 and run 3 is 33. The doc's phrasing "localized a CHANGE somewhere" makes the any-finding reading fair; say which definition is in use. Clean-case errors: exactly 1 across the three runs (run 1), confirmed. Observed.

**F4 (strengthens the erratum, add to §6): the taxonomy asymmetry is quantifiable and worse than stated.** The public vocabulary has 47 codes; the private native map can emit only 37. Ten public codes are structurally unmatchable (`causal_overclaim`, `complex_sentence`, `dangling_modifier`, `misplaced_modifier`, `negation_ambiguity`, `nominalization`, `noun_stack`, `overgeneralization`, `repetitive_conclusion`, `synonym_cycling`). Across the 33 valid runs, systems spent 80 CHANGE findings on these never-awardable codes (causal_overclaim 46, synonym_cycling 13, nominalization 12, overgeneralization 5, misplaced_modifier 4), each a guaranteed exact FP plus a paired FN. That `nominalization` itself was never awardable is notable given the portfolio under test. Separately, the map collapses 24 gold families into `protected_region` and 11 into `author_quirk`; F5 shows the harm. Observed.

**F5 (confirms erratum §4): spot-checked disputed gold labels are genuinely wrong or misleading at the normalized layer.** Three of the five listed examples checked against case text:
- `S009-003`: normalized `actor_ambiguity` on "I designed the entire checkout flow." The actor is an explicit first person; the defect is an ownership claim conflicting with the project notes. Label misnames the fault. Observed.
- `WQ-S002-002`: normalized `passive_obscures_actor` on "The retention rule was changed on Tuesday by the compliance team." The by-phrase names the actor; nothing is obscured. The native family `avoidable_passive` is a defensible style call that the many-to-one map converted into a false factual claim. Under the portfolio's own cohesion contract this passive is arguably correct: topic in topic position, agent in stress position. Observed.
- `S008-004`: normalized `temporal_scope_missing` on "directly comparable," where both windows are stated; the real defect is asserting comparability of mismatched windows. Label misnames the fault. Observed.
These confirm that one exact label per finding cannot serve as settled ground truth without adjudication and an equivalence policy.

**F6 (process finding, matches erratum's own admission): the leak was preventable with the checks the pilot already had in spirit.** `assert_no_gold_leak` in `src/wqeval/jobs.py` rejects forbidden key names only; a value-level probe (train a trivial classifier on public metadata, require chance-level accuracy) would have caught the ID pattern before sealing. Every sealed job carries all 72 cases in one request (confirmed from `runs/stage1-sealed-v1/jobs/`), so the pattern was exploitable inside a single context. The erratum correctly stops short of claiming exploitation occurred; nothing in the preserved evidence can establish that either way. Observed for mechanism; Unknown for exploitation.

**F7 (proposal audit): the reoptimization proposal addresses all six failure classes it must, with four gaps to close before preregistration.** Leakage (opaque IDs, metadata-only classifier with preregistered ceiling), batching (one case per request), boundary (quote anchors resolved by a deterministic adapter, with local rejection so one bad anchor no longer voids a run), taxonomy (versioned human-approved crosswalk with aliases), provenance (prompt and response bytes), and partial ingestion are each covered. Gaps: (a) no preregistered inter-annotator agreement floor before gold freezes; record-the-dispute is necessary but not sufficient. (b) Routing correctness should be a scored layer with its own error attribution, not only a logged decision, or routed-architecture results will be as entangled as the F2 projection was. (c) The critical-miss gate needs a minimum-opportunity rule; with 4 critical items a 0.05 cap is a zero-miss gate in disguise (confirmed against `config/thresholds.json`). (d) State explicitly whether exact KEEP emission remains mandatory; conservative silence and exact protected-region reporting are different capabilities and should be scored in separate lanes with abstention allowed. Inferred (design judgment).

**F8 (answer to the smaller-design question): a leaner v2 achieves the same validity.** Stage 1's real question is whether any surface reliably localizes and names defects. Minimal valid design: one case per fresh request, opaque IDs, quote-anchored findings in each surface's native vocabulary, human adjudicators judging native-label acceptance, no shared taxonomy at generation time, no KEEP-emission requirement (clean-case false positives scored instead). This removes the crosswalk and one-label scorer from the critical path entirely; taxonomy mapping becomes post-hoc analysis rather than a scored contract. The full routed architecture is worth building for the portfolio itself, but benchmark validity does not depend on it. Inferred.

## 3. Reproduced calculations and commands

Environment: Python 3.12.3, fresh clone, no network beyond the clone.

| Claim | Erratum | Reproduced | Status |
|---|---|---|---|
| ID rule predicts decision, all 90 cases | all | 0 violations | Observed |
| ID rule predicts decision, 72 sealed | all | 0 violations | Observed |
| Exact TP/FP/FN | 307/913/914 | 307/913/914 (P .252, R .251) | Observed |
| Overlap same-code | 604/616/617 | 604/616/617 (P .495, R .495) | Observed |
| Overlap any-code | 1041/179/180 | 1041/179/180 (P .853, R .853) | Observed |
| Containment split of 297 | 199 enclose, 98 narrower | 199/98/0 partial | Observed |
| Critical opportunities | 132; 128 overlap; 4 none; 70 exact | 132/128/4/70 | Observed |
| Protected regions | 97 across 41 of 72; public all empty | 97/41; all public empty | Observed |
| Dual overlap | 110 | 110 (KEEP findings), 116 (protected), 170 (union) | Observed, wording fix |
| Malformed records | 5 across 3 runs; 216 discarded | 5 findings, 3 runs x 72 = 216 | Observed |
| Fidelity classes | 2 F1, 8/10 external F2, portfolio F2 | matches `systems/systems.json` | Observed |
| Sealed batching | all 72 per request | 72 cases per job file | Observed |
| Portfolio localization | 31, 33, 34; one clean-case error | 31/33/34 any-finding; 1 error | Observed |

Commands (from `evaluation/pilot/`):

```bash
PYTHONPATH=src python3 -m pytest tests -q        # 187 passed, 11 skipped, 174 subtests
cd ../.. && sha256sum -c MANIFEST.sha256          # 556 entries, all OK
cd evaluation && sha256sum -c MANIFEST.sha256     # 469 entries, all OK
```

Recount script (independent implementation, greedy one-to-one matching per case; run from `evaluation/pilot/`):

```python
import json, os, collections
def load(p): return [json.loads(l) for l in open(p) if l.strip()]
gold = [g for g in load('private/gold/scoring.test.jsonl') if g['decision']=='CHANGE']
byc = collections.defaultdict(list)
for g in gold: byc[g['case_id']].append(g)
def ov(a,b,c,d): return a<d and c<b
def score(preds, rule):
    tp=fp=0; matched=set()
    pc = collections.defaultdict(list)
    for p in preds: pc[p['case_id']].append(p)
    for cid, ps in pc.items():
        for p in ps:
            hit=None
            for g in byc.get(cid,[]):
                if id(g) in matched: continue
                if rule=='exact': ok = p['start']==g['start'] and p['end']==g['end'] and p['normalized_issue_code']==g['normalized_issue_code']
                elif rule=='same': ok = ov(p['start'],p['end'],g['start'],g['end']) and p['normalized_issue_code']==g['normalized_issue_code']
                else: ok = ov(p['start'],p['end'],g['start'],g['end'])
                if ok: hit=id(g); break
            if hit: matched.add(hit); tp+=1
            else: fp+=1
    return tp, fp, matched
tot={r:[0,0,0] for r in ('exact','same','any')}
nd='runs/stage1-sealed-v1/normalized'
for f in sorted(os.listdir(nd)):
    preds=[r for r in load(os.path.join(nd,f)) if r['decision']=='CHANGE']
    for rule in tot:
        tp,fp,m = score(preds, rule)
        tot[rule][0]+=tp; tot[rule][1]+=fp; tot[rule][2]+=len(gold)-len(m)
print(tot)   # exact [307,913,914], same [604,616,617], any [1041,179,180]
```

Leakage check (no model outputs used): parse the numeric suffix of every `case_id` in `corpus/cases.dev.jsonl` and `corpus/cases.test.jsonl`; predict CHANGE for 001-005 and KEEP for 006-010; compare to `case_decision` in `private/gold/`. Zero violations in 90 and in 72.

Malformed-record check: validate every finding in all 36 inbox files against case text (offset bounds, `span == text[start:end]`) and against the exact-keys operation contract in `validation.py`. Exactly the five findings named in F2 fail; no others.

## 4. Counterevidence sought and not found

- I attempted to break the leakage rule with the dev split, alternate suffix boundaries, and per-source subsets: no counterexample exists in the corpus.
- I attempted to produce different recount totals with an independent matcher (greedy, per-case, one-to-one): totals matched to the digit, and FN arithmetic is internally consistent (33 x 37 gold findings minus TP in every rule).
- I checked whether the three invalidated runs concealed better-performing systems: the surviving runs for those three systems still fail the frozen exact thresholds (exact precision pooled ~0.25 against a 0.8 gate), so run invalidation did not manufacture the universal failure. Observed.
- I checked whether the "favorable leak" framing was wrong (a leak that hurts would change the story): the leaked signal identifies which cases contain issues, which can only help case-level metrics. The erratum's direction is right.

## 5. Recommended changes

Blocking: none.

At merge (documentation only, do not touch frozen pilot files; both manifests must be regenerated if the erratum text changes):
1. Disambiguate the 110 statistic per F1 and report the union figure.
2. Fix the units in "five malformed records out of 2,592" per F2 and optionally pin the five finding IDs.
3. Note the localization-count definition per F3.
4. Add the F4 quantification to erratum §6; it converts a qualitative claim into an 80-finding structural floor on exact FPs.

Before v2 preregistration: close the four gaps in F7 (agreement floor, scored routing layer, critical-gate minimum opportunities, KEEP-lane policy) and consider the F8 reduction as the Stage 1 core, layering the routed architecture as the system under test rather than as benchmark machinery.

## 6. Tests run and exact results

- `PYTHONPATH=src python3 -m pytest tests -q` on Python 3.12.3: **187 passed, 11 skipped, 174 subtests passed, 6.66s.** All 11 skips are Windows-specific behavior guards (junctions, atomic rename, file identity), consistent on Linux. Collected total 198 matches the reported count. The second Python version was not available in this environment; that half of the claim is Unknown here.
- `sha256sum -c` on both manifests: 556 and 469 entries, zero mismatches.
- Branch SHA and tracked-file count match the report (`5d1f2b4...`, 557 files).
- Secret scan across the tree: all matches are prose examples inside skill reference files (e.g., a passive-voice exception about token signing). No credentials, no third-party repository clones, no embedded rendered prompts (`systems/prompt-manifest.json` is 1.5 KB of hashes). Third-party material stays within a citation and analysis boundary. Observed.

## 7. Unresolved questions

1. Whether any system exploited the ID pattern is undecidable from preserved evidence; only a leakage-controlled rerun answers it. Unknown.
2. Second-Python-version test results, exact model identity, generation settings, and rendered prompt bytes are unverifiable, consistent with the declared boundary. Unknown.
3. The remaining two disputed gold labels in erratum §4 (`WQ-S002-005`, `WQ-S003-002`) were structure-checked but not adjudicated here; genuine adjudication needs the independent human protocol in the proposal. Unknown pending Stage 6.
4. Whether `raw/` byte-matches `inbox/` after transport was not diffed in this review; both are manifest-bound, so any divergence would surface in the manifest check. Low risk, unverified directly.

All ten handoff steps are done. Writing up the review in the handoff's required format:

Review complete. Verdict: **the erratum survives adversarial recount; merge as an evidence record.** I cloned the branch fresh, reimplemented the scoring independently, and reproduced every material number to the digit: the case-ID leak holds with zero violations across all 90 and all 72 sealed cases, the 307/604/1041 recount table matches exactly, the 199/98 containment split, the 132/128/4/70 critical decomposition, 97 protected regions across 41 cases against an all-empty public field, and the five malformed findings (now pinned to exact finding IDs) that discarded 216 records. Tests: 187 passed, 11 skipped (all Windows guards), 198 collected on Python 3.12; both manifests verify clean; SHA and file count match your report.

Two things the recount added beyond confirmation. The "110" statistic only reproduces under one reading of "KEEP region" (KEEP findings: 110; protected regions: 116; union: 170), so the erratum needs a one-line disambiguation, and the union figure is actually worse. And the taxonomy defect is quantifiable: 10 of 47 public codes can never be emitted by the private map, and systems spent 80 findings on them, guaranteed FP+FN pairs. One of the unmatchable codes is `nominalization`, which is a grim detail given what the portfolio under test is.

No blocking findings. Four wording fixes at merge, four gaps to close in the v2 proposal before preregistration (agreement floor, scored routing layer, critical-gate minimum opportunities, KEEP-lane policy), and an F8 section arguing a leaner Stage 1 core gets the same validity without the crosswalk in the critical path.

One mechanical limit: this surface has no GitHub write access, so I can't post PR comments or push the feedback branch. The file above is `evaluation/CLAUDE_REVIEW.md` ready to commit exactly as the handoff's fallback path specifies (feedback branch, PR back to `codex/evaluation-audit-bundle`, regenerate both manifests on any later integration). Either push it from your side or hand it to Claude Code to post, then tell the Codex task to read it.
