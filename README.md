# Writing Quality Portfolio 1.0.0

Seven distinct, source-grounded writing skills plus one coordinated routing contract and a Strunk/White negative control.

## Skills

1. `doc-typing`
2. `memo-structure`
3. `cohesion-emphasis`
4. `sentence-clarity`
5. `concision`
6. `sentence-variety`
7. `usage-adjudicator`

There is no `elements-of-style` or generic `writing-editor` skill.

## Second layer: `communication`

`skills/communication` is not an eighth editing skill. It governs how the model talks to the reader on every turn (lead with the next action, number multi-step work, define a term in the sentence it first appears, verify premises, state what is unverified, no preamble or closer). The seven skills above govern how the model edits a piece of text it is handed, and only when asked. The two meet at one seam: when text is handed over to edit, the portfolio owns the method, pass order, and preservation contract; `communication` owns how the result is reported. `portfolio-routing.md` records the same rule from the portfolio's side.

- `skills/communication/SKILL.md` — the skill (v5: the iteration-4 review fixes, evaluated against v4 in iteration 5; the deployed copy trims Credits and the why-list to stay under 200 lines).
- `skills/communication/references/eval-summary.md` — what the evals measured and what they do not establish.
- `evals/communication/` — the full eval workspace: 8 prompts across three iterations plus the 14-prompt three-arm run of iteration 4 (no skill, full v4, a 25-line candidate) on Opus 5 with blind pairwise judging; every reply, grade, verdict, and the scripts to rerun it. Start at `evals/communication/iteration-4/report.md` (three arms, corrected after three outside reviews) and `iteration-5/report.md` (v5 against v4).
- `evals/communication/consult-brief.md` and `consult-answers-*.md` — the questions put to outside reviewers and their answers.

`scripts/validate_portfolio.py` checks this skill separately from the seven editing skills: it requires `SKILL.md`, `agents/openai.yaml`, `references/eval-summary.md`, and a parseable `evals/evals.json`, and it reports the result as `companion_skill=communication`. The seven-skill checks (principle registry, evidence maps, behavioral fixtures) do not apply to it.

## Start here

- [Before-and-after gallery](examples/before-and-after.md): 14 single-skill demonstrations plus one coordinated portfolio pass.
- `RESEARCH_REPORT.md` — Parts I–XIV in the requested order.
- `source-manifest.md`, `source-access-ledger.csv`, `source-coverage-ledger.csv` — editions, lawful access, and every visible chapter/page/category.
- `principle-registry.json` / `.csv` — 252 fully fielded, explicitly disposed principles.
- `claim-to-source-ledger.csv` — high-consequence claim provenance.
- `portfolio-routing.md`, `portfolio-pass-order.md`, `trigger-matrix.csv`, `glossary.md`, `conflict-ledger.md`, `source-map.md` — shared architecture and evidence navigation.
- `skills/*` — canonical skill core, UI metadata, references, evidence map, and fixtures.
- `tests/` and `validation-results.md` — static, behavioral, negative-control, and end-to-end results.
- `negative-control/strunk-white-exclusion-dossier.md` — rule-level exclusion.
- `defect-and-change-report.md` — baseline audit, semantic diff, change IDs, consequences, tests, and residual uncertainty.
- `MANIFEST.sha256` — integrity hashes for every other packaged file.
- [Current evaluation status](evaluation/status/README.md): start here for the integrated audit, verification record, offline benchmark-v2 foundation, and pending human review. The editing pilot in `evaluation/` and reply-shape experiments in `evals/communication/` are separate evidence streams.

## Completeness label

The skills package is artifact-complete and build-ready. This describes the packaged artifacts; benchmark v2 is development-only, has no quality-readiness verdict, and does not unlock Stage 2. It is **not full-corpus-exhaustive** for copyrighted books that were not lawfully accessible. The completion statement does not convert TOCs, reviews, snippets, or previews into full-text inspection. See Part XIV and the access ledger for the exact acceptance results.

## Package form

This is a skills-only OpenAI plugin package. Individual skill folders are independently valid, while `.codex-plugin/plugin.json` distributes everything under `skills/`: the seven editing skills plus `communication`. The research infrastructure is not a skill. In Claude Code, copy the `skills/*` folders you want into `~/.claude/skills/`; the `agents/openai.yaml` files are Codex UI metadata and can be ignored there.
