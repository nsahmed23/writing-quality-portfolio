# Evaluation integration verification — 2026-09-28

**Status:** independent arithmetic recount complete; final integration integrity and CI status reserved for the integration controller's update. This entry records a computational audit by a delegated agent, not human adjudication and not a new model trial.

## Source and preservation boundary

- Main source commit: `28454c197246e6147da952b72d044273f6bb192f`.
- Reviewed evaluation tip: `ac6d52e1c57c71d43070884bb56335ee3176888f`.
- Original evaluation audit reference: `5d1f2b4cf83c54b5b70e5d10f16a85cbc07b9ba4`.
- Initial integration merge: `a4cd638e368f44bb6e1d6bb3c72a3671f9174587` (2,168 tracked files).

The historical source-review and pilot evidence, original sealed outputs, labels, and frozen report are immutable inputs for this verification. Neither the root `MANIFEST.sha256` nor any historical file is rewritten here. The independent script and this status note are new paths under `evaluation/status/`. Comparing both the working tree and the staged index against the original audit reference with `git diff --quiet 5d1f2b4cf83c54b5b70e5d10f16a85cbc07b9ba4 -- evaluation/source-review evaluation/pilot` (and `git diff --cached --quiet` with the same operands) gave exit status 0 for both. That scope includes 454 tracked paths in the audit tree. This path comparison does not certify the entire integrated repository.

## Observed baseline before final integration verification

These baseline observations identify the starting conditions; they are **not final integrity or CI results**:

| Baseline observation | Result |
|---|---:|
| Legacy unittest suite on Linux CPython 3.12.14 | 198 total; 187 passed, 11 skipped, 0 failures |
| Main root manifest | 1,691 entries; 1,373 Git-blob mismatches |
| Main mismatch decomposition | 1,372 CRLF-derived hashes and one separately stale `evals/communication/resume.md` |
| Reviewed evaluation tip root manifest | 562 entries; zero mismatches |
| Initial integrated tree at `a4cd638e` | 2,168 tracked files |

The controller supplied the unittest and manifest mismatch baseline for this entry. I separately confirmed the two manifest line counts and initial integration file count with `git show <source>:MANIFEST.sha256 | wc -l` and `git ls-tree -r --name-only a4cd638e | wc -l`. The root manifest's preexisting mismatch count must not be mistaken for newly introduced integration damage.

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

## Final integration status

Pending the integration controller's separately recorded verification and CI result. This entry does not close that gate.
