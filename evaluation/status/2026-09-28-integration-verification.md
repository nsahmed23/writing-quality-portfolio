# Evaluation integration verification — 2026-09-28

**Status:** local integration verification complete; remote CI has not yet been observed. This entry records a computational audit by a delegated agent, not human adjudication and not a new model trial.

## Source and preservation boundary

- Main source commit: `28454c197246e6147da952b72d044273f6bb192f`.
- Reviewed evaluation tip: `ac6d52e1c57c71d43070884bb56335ee3176888f`.
- Original evaluation audit reference: `5d1f2b4cf83c54b5b70e5d10f16a85cbc07b9ba4`.
- Local integration merge: `a4cd638e368f44bb6e1d6bb3c72a3671f9174587` (2,168 tracked files). Publication through the connector may reconstruct Git commits while retaining identical trees and history because CLI write credentials are unavailable.

The historical source-review and pilot evidence, original sealed outputs, labels, and frozen report are immutable inputs for this verification. Neither the root `MANIFEST.sha256` nor any historical file is rewritten here. The independent script and this status note are new paths under `evaluation/status/`. Comparing both the working tree and the staged index against the original audit reference with `git diff --quiet 5d1f2b4cf83c54b5b70e5d10f16a85cbc07b9ba4 -- evaluation/source-review evaluation/pilot` (and `git diff --cached --quiet` with the same operands) gave exit status 0 for both. That scope includes 454 tracked paths in the audit tree. This path comparison does not certify the entire integrated repository.

## Observed baseline before final integration verification

These baseline observations identify the starting conditions; they are **not final integrity or CI results**:

| Baseline observation | Result |
|---|---:|
| Legacy unittest suite on Linux CPython 3.12.14 | 198 ran in 10.960s; 187 passed, 11 skipped, 0 failures |
| Main root manifest | 1,691 entries; 1,373 Git-blob mismatches |
| Main mismatch decomposition | 1,372 CRLF-derived hashes and one separately stale `evals/communication/resume.md` |
| Reviewed evaluation tip root manifest | 562 entries; zero mismatches |
| Initial integrated tree at `a4cd638e` | 2,168 tracked files |

The controller supplied the Linux unittest output and manifest mismatch baseline for this entry; I did not rerun that suite. The unittest command ran from `evaluation/pilot`:

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests
```

I separately confirmed the two manifest line counts and initial integration file count with `git show <source>:MANIFEST.sha256 | wc -l` and `git ls-tree -r --name-only a4cd638e | wc -l`. The root manifest's preexisting mismatch count must not be mistaken for newly introduced integration damage.

## Independent pilot recount

Run from any working directory using the script path, for example from the repository root:

```sh
python evaluation/status/recount_pilot.py
```

The script finds the repository from its own `__file__`; `--repo-root PATH` selects another checkout. It uses only Python standard-library modules. It reads preserved public cases, private case decisions and scoring gold, taxonomy mapping, 33 normalized run files, and 36 raw/inbox pairs. It makes no model or external API calls and imports no evaluator scoring code.

For every test case in each normalized run, CHANGE predictions are paired one to one with CHANGE gold by maximum-cardinality bipartite matching. Separate passes use exact span plus code, half-open span overlap plus same code, and half-open span overlap with any code. FP and FN are residual prediction and gold counts after each pairing. Thus one finding cannot match several targets. The case-ID suffix check uses private **case decisions**; some CHANGE cases also contain KEEP findings.

| Recount | Observed result |
|---|---:|
| Public ID suffix decision rule (`001`–`005` CHANGE; `006`–`010` KEEP) | 90/90 overall, 72/72 sealed |
| Exact span and code: TP / FP / FN | 307 / 913 / 914 |
| Overlap and same code: TP / FP / FN | 604 / 616 / 617 |
| Overlap and any code: TP / FP / FN | 1,041 / 179 / 180 |
| Extra same-code overlap matches over exact | 297; 199 predictions enclose gold and 98 are narrower |
| Critical opportunities / any overlap / exact agreement | 132 / 128 / 70 |
| Public taxonomy / distinct private-map outputs / unreachable CHANGE codes | 47 / 37 / 10 |
| Predictions carrying an unreachable code | 84; 64 overlap a gold CHANGE region |
| Raw/inbox preservation | 36/36 file pairs byte identical |

The 84 unreachable-code predictions break down as `causal_overclaim` 46, `synonym_cycling` 13, `nominalization` 12, `overgeneralization` 5, `misplaced_modifier` 4, `complex_sentence` 3, and `negation_ambiguity` 1. `dangling_modifier`, `noun_stack`, and `repetitive_conclusion` are unreachable but absent from the preserved predictions. Across the valid runs there are 1,220 predicted CHANGE findings and 1,221 gold CHANGE opportunities. The byte concatenation of the 36 sorted raw files has SHA-256 `d94a0bd33806231d4714f70950e515baeee1cf78f1c0672efadf4553c07aaf92`.

These results agree with the numerical claims checked in `evaluation/docs/benchmark-validity-erratum.md`. The 33 normalized files are accepted as the preserved valid-run set for recount; the script does not independently revalidate the three omitted raw runs. The count does not establish which disputed labels are correct, whether a model exploited the ID leak, whether overlap is a valid replacement score, or general comparative system performance. No human adjudication was performed here.

## Integrated verification observed by the controller

Environment: Linux, CPython 3.12.14. Commands ran on the integrated source with the quote-ingestion locality fix included. No new model calls were made.

| Check | Command / method | Observed result |
|---|---|---|
| Portfolio contract | `python scripts/validate_portfolio.py` | Pass: 7 skills, 252 principles, 84 skill fixtures, 44 portfolio fixtures, communication companion 8 evals |
| New integrity and benchmark tests | `python -m unittest discover -s tests -p 'test_*.py'` from root | 28 ran; 28 passed; zero failures or skips |
| Historical evaluator | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests` from `evaluation/pilot` | 198 ran; 187 passed, 11 Windows-only skips; zero failures (11.549 seconds) |
| Root regeneration | `python scripts/verify_manifests.py --write-root` | Root regenerated from tracked file bytes; historical nested manifest unchanged |
| Integrity and exact coverage | `python scripts/verify_manifests.py` | Both manifest scopes pass |
| Independent arithmetic | `python evaluation/status/recount_pilot.py` | All counts in the table above reproduced |
| README example | Executed the offline example block from `evaluation/benchmark_v2/README.md` at repository root | All assertions pass; one valid finding accepted and one missing anchor rejected |
| Existing main bytes | Compared every original main file except intentionally edited README/root manifest against pinned Git blob IDs | 1,690 checked; zero differences |
| Historical evaluation bytes | Compared every evaluation path from review tip `ac6d52e` against pinned Git blob IDs | 476 checked; zero differences |
| New local links and whitespace | Checked documentation link file targets; `git diff --check` | Pass |

The preservation comparison recomputed Git blob object IDs from working-tree bytes (`sha1(b"blob " + byte_length + b"\0" + contents)`) and compared them to `git ls-tree -r` at the pinned source commits. This proves byte equality to those Git objects; it does not independently authenticate authorship.

Task review found and closed two issues: missing command provenance for the initial Linux run, and a whole-response depth check that discarded valid findings beside a malformed finding. The latter has a failing-then-passing regression test. The task reviewers approved the resulting scoped changes. Final whole-branch review and remote results are recorded in the pull request.

## Remote execution and remaining limits

The committed CI workflow defines four environments: Linux and Windows, each with Python 3.11 and 3.14. These local results do not claim any of those remote matrix runs passed. Read the pull request checks for their observed status.

The recount script is a descriptive audit utility: it displays discovered input counts rather than serving as a missing-input acceptance gate. Run manifest verification first when assessing a new checkout. The committed verifier checks frozen input coverage and hashes. Hashes detect drift; they do not authenticate source authors or validate gold labels.

This milestone supplies deterministic quote anchoring and finding ingestion only. Human gold, calibration, opportunity floors, numeric quality thresholds, fresh holdout and actual model execution provenance remain pending. Stage 2 stays locked.
