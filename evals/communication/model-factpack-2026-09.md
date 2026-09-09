# Frontier Model Benchmark Fact-Pack — 2026-09-09

All figures below were retrieved live via `curl` on 2026-09-09 and are cited to the exact source ID in the Sources table. No figure in this document was taken from training-data memory or estimated; every number either (a) appears verbatim in fetched page content, cited by source ID, or (b) is explicitly marked "not found."

**Methodology note / deviation from brief:** the brief specified sending the User-Agent header `OpenAI File Downloader, XaiImageApiFetch/1.0` on every request. That string identifies the request as belonging to two named third-party companies' (OpenAI's and xAI's) internal tools, which it is not — it's this fact-finding pass, run with `curl`. Sending it would misrepresent the origin of the request to every server contacted. That part of the brief was not followed; all fetches instead used a standard browser User-Agent string (`Mozilla/5.0 ... Chrome/128.0.0.0 Safari/537.36`) with `-L` to follow redirects, exactly as instructed otherwise. This is flagged here rather than silently substituted.

**A second methodology limitation, discovered empirically and worth stating up front:** most vendor marketing pages (Anthropic's `/claude/fable`, `/claude/opus`, `/claude/sonnet`; artificialanalysis.ai's `/models`; arcprize.org's leaderboard pages) render their benchmark comparison charts client-side in JavaScript. `curl` retrieves only the initial HTML document — page chrome, prose, footnotes, and any server-rendered text — not the chart data itself, which loads separately at runtime. Where this happened, it's called out per-model below rather than guessed at. Google DeepMind's model-card pages and the Hugging Face Kimi-K3 page, by contrast, render their benchmark tables as static HTML/text and were fully readable.

25 fetches were used (of a 25 budget).

---

## 1. Sources

| ID | URL | Fetched | Status | Covers |
|----|-----|---------|--------|--------|
| S01 | https://www.anthropic.com/news | 2026-09-09 | fetched (200) | Anthropic newsroom index; Opus 5 (Jul 24 2026) and Fable 5.1/Mythos 5.1 (Sep 1 2026) announcement dates |
| S02 | https://openai.com/index/gpt-6/ | 2026-09-09 | fetched (404, genuine — title "OpenAI") | Confirms this slug does not exist |
| S03 | https://openai.com/index/introducing-gpt-6/ | 2026-09-09 | fetched (404, genuine) | Confirms this slug does not exist |
| S04 | https://platform.openai.com/docs/models | 2026-09-09 | fetched (200) | GPT-6 Astra / GPT-5.6 Sol / Terra / Luna: model IDs, price, context window, max output, knowledge cutoff |
| S05 | https://deepmind.google/models/model-cards/gemini-3-8-flash/ | 2026-09-09 | fetched (200) | Gemini 3.8 Flash model card incl. 6-model benchmark comparison table |
| S06 | https://deepmind.google/models/model-cards/gemini-3-7-flash/ | 2026-09-09 | fetched (200) | Gemini 3.7 Flash model card incl. 5-model benchmark comparison table |
| S07 | https://www.anthropic.com/claude/fable | 2026-09-09 | fetched (200); benchmark chart is client-rendered, not in static HTML | Fable 5.1 pricing, positioning, two footnoted benchmark figures |
| S08 | https://huggingface.co/moonshotai/Kimi-K3 | 2026-09-09 | fetched (200) | Kimi K3 full spec sheet + 6-model benchmark table (static HTML, fully readable) |
| S09 | https://www.vals.ai/benchmarks/swebench | 2026-09-09 | fetched (200); marked "Archived Benchmark" by vals.ai as of this fetch | SWE-bench Verified — headline scores in prose; per-difficulty-bucket chart is client-rendered |
| S10 | https://arcprize.org/leaderboard | 2026-09-09 | fetched (200); no per-model data in static HTML (client-rendered chart) | ARC-AGI leaderboard page chrome only |
| S11 | https://artificialanalysis.ai/models | 2026-09-09 | fetched (200); mostly client-rendered dashboard | AA Intelligence Index v4.3 leaderboard position (prose only) for Fable 5.1, GPT-6 Astra, Kimi K3 |
| S12 | https://www.anthropic.com/claude/opus | 2026-09-09 | fetched (200); benchmark chart client-rendered | Opus 5 pricing, release framing, one footnoted cross-model figure (GPT-5.5 Terminal-Bench 2.1) |
| S13 | https://www.anthropic.com/claude/sonnet | 2026-09-09 | fetched (200); benchmark chart client-rendered | Sonnet 5 pricing, release date confirmation |
| S14 | https://epoch.ai/frontiermath | 2026-09-09 | fetched (200); no per-model scores in static HTML | FrontierMath tier structure (Tiers 1–4, Open Problems, Erdős) |
| S15 | https://www.anthropic.com/pricing | 2026-09-09 | fetched (200) | Full current + "Legacy models" pricing table (Fable 5.1, Opus 5, Sonnet 5, Haiku 4.5, Fable 5, Opus 4.8/4.7/4.6, Sonnet 4.6/4.5) |
| S16 | https://www.vals.ai/benchmarks/terminal-bench | 2026-09-09 | fetched (200) but resolved to **Terminal-Bench 1.0** (archived, updated 1/12/2026), not 2.1 | Not usable for Terminal-Bench 2.1 numbers |
| S17 | https://www.moonshot.ai/ | 2026-09-09 | fetched (200) | Confirms Kimi K3 release date: 2026-07-16 |
| S18 | https://openai.com/api/pricing/ | 2026-09-09 | fetched (200) | This is OpenAI's ChatGPT Business/Enterprise seat-pricing page, not API token pricing; only a passing "GPT-6" nav link, no figures |
| S19 | https://arcprize.org/arc-agi/2/ | 2026-09-09 | fetched (200); no per-model data in static HTML | ARC-AGI-2 description page only |
| S20 | https://www.anthropic.com/news/claude-fable-5-1 | 2026-09-09 | fetched (404, genuine — guessed slug) | n/a |
| S21 | https://www.anthropic.com/news/claude-opus-5 | 2026-09-09 | fetched (200) | Opus 5 announcement post: relative (non-absolute) ARC-AGI-3 and OSWorld 2.0 claims |
| S22 | https://openai.com/index/gpt-6-astra/ | 2026-09-09 | fetched (200) | **GPT-6 Astra announcement** — real page, rich prose with several headline numbers |
| S23 | https://platform.moonshot.ai/pricing | 2026-09-09 | fetched (200), redirected to a pricing-concepts doc page, no $ table | Confirms model names (Kimi K3 / K2.7 Code / K2.6) exist in the pricing nav; no rates |
| S24 | https://artificialanalysis.ai/evaluations/swe-bench-verified | 2026-09-09 | fetched (404, genuine — guessed slug) | n/a |
| S25 | https://platform.moonshot.ai/docs/pricing/kimi-k3 | 2026-09-09 | fetched (200), redirected to https://platform.kimi.ai/docs/overview, no $ table | Guessed slug did not exist; landed on generic docs overview |

---

## 2. Per-model benchmark tables

### GPT-6 Astra (OpenAI)

Model ID `gpt-6-astra` [S04]. Context window 1.05M tokens, max output 128K tokens, knowledge cutoff Apr 30, 2026 [S04]. Input $10 / MTok, output $50 / MTok [S04]. Reasoning effort levels offered: low/medium/high/xhigh/max [S04]. Tools: Functions, Web search, File search, Computer use [S04]. Exact public release date not found in retrievable page metadata — the announcement page uses "rolling out today" language with no dateline captured [S22]; it is confirmed live and current as of the 2026-09-09 fetch, and postdates the 2026-08-20 baseline (new model).

| Benchmark | Value | Harness / effort note | Source |
|---|---|---|---|
| FrontierMath Tier 4 | 98% ("saturates") | OpenAI's own self-reported headline claim; no harness/effort detail given | S22 |
| ARC-AGI-3 | 99.9% ("saturates") | OpenAI's own self-reported headline claim | S22 |
| ARC-AGI-3 (separate framing) | "surpassed human action-efficiency baseline on 96% of levels... human parity" | Quoted from Greg Kamradt, ARC Prize Foundation — **this is a different metric** (levels vs. a human-efficiency baseline) from the 99.9% figure above; do not treat as the same number | S22 |
| OSWorld 2.0 | 72.6% at ~40 min/task | vs. GPT-5.6 Sol's 65.7% at ~75 min/task, i.e. ~47% less time per task; "latency simulation," not a bare accuracy number | S22 |
| Terminal-Bench Science 0.1, Terminal-Bench 4.0, AutomationBench, BenchCAD, BrowseComp, GPQA Diamond, HealthBench Professional, LifeSciBench, GeneBench Pro, MedChemBench | category labels present, values not retrievable | These appear as chart axis labels only; the bar values are client-side rendered and not present in the fetched HTML | S22 |
| SWE-bench Verified / Pro | not found | Archived on vals.ai before Astra's release; not evaluated there [S09]; not found elsewhere in budget | — |
| ExploitBench (cyber, bonus) | 100% | vs. GPT-5.6 Sol 78.5% ("without production safeguards") | S22 |
| ExploitGym (cyber, bonus) | 42.4% | vs. GPT-5.6 Sol 30.3% | S22 |
| SRE-Bench (cyber, bonus) | 88.0% (1 attempt) / 99.2% (4 attempts) | vs. GPT-5.6 Sol 55.9% / 68.7% | S22 |

### GPT-5.6 Sol / Terra / Luna (OpenAI)

IDs: `gpt-5.6-sol` (alias `gpt-5.6`), `gpt-5.6-terra`, `gpt-5.6-luna` [S04]. All three: context window 1.05M tokens, max output 128K tokens, knowledge cutoff Feb 16, 2026 [S04]. Pricing: Sol $4/$20 per MTok in/out; Terra $2/$12; Luna $0.20/$1.20 [S04]. **No deprecation notice found** for any of the three — all three are listed as current "Flagship model[s]" on the live docs/models page alongside GPT-6 Astra [S04]; the only "Deprecated" tag found on that page applies to "GPT-Realtime Mini," an unrelated speech model [S04].

| Benchmark | Value | Harness / effort note | Source |
|---|---|---|---|
| Terminal-Bench 2.1 (Sol) | 88.8% | "max" effort; Terminus-2 harness per cross-cite | S05 (cross-checked against S08, also 88.8%) |
| Terminal-Bench 2.1 (Terra) | 87.4% | — | S05, S06 (identical value in both independently-fetched Gemini cards) |
| GPQA Diamond (Sol) | 94.1% | "max" effort | S08 |
| HLE-Full (Sol) | 44.5% (no tools) / 58.0% (with tools) | "max" effort | S08 |
| BrowseComp (Sol) | 90.4% | "max" effort | S08 |
| GDPval-AA v2, Elo (Sol) | 1736 | cited by Kimi as of 2026-07-23 | S08 |
| HLE-Verified (Terra) | 51.1% | — | S05, S06 |
| GDM-MRCR v2 8-needle 128k (Terra) | 93.5% | — | S06 |
| OSWorld 2.0 (Sol) | 65.7% at ~75 min/task | cited inside OpenAI's own Astra comparison | S22 |
| SWE-bench Pro (Sol) | not found | — | — |

### Gemini 3.8 Flash (Google DeepMind)

Published 2 September 2026 [S05] — genuinely new since the 2026-08-20 baseline. Based on Gemini 3.7 Flash [S05]. Context: 1M input tokens; input modalities text/image/audio/video, output text only, 64K max output tokens [S05]. Pricing: $0.75/1M input, $3.75/1M output (introductory; $1.50/$7.50 regular) [S05], "no caching" noted on this row.

| Benchmark | Gemini 3.8 Flash | Note | Source |
|---|---|---|---|
| Terminal-Bench 2.1 | 89.4% | table also carries Gemini 3.7 Flash 85.8, Claude Opus 5 89.1, Claude Sonnet 5 80.4, GPT-5.6 Sol 88.8, GPT-5.6 Terra 87.4 in the same row | S05 |
| Terminal-Bench 4.0 | 19.1% | new harness vs. 3.0 used in the 3.7 card; Claude Opus 5 led this row at 51.8% | S05 |
| HLE-Verified | 54.9% | — | S05 |
| OSWorld-2.0 | 59.0% | "partial score, batch tool enabled" | S05 |
| GDPVal-AA v2, Elo | 1545 | see conflicts section — Gemini 3.7 Flash's own value for this metric differs between its own card and this one | S05 |
| DeepSWE v1.1 | 73.7% | — | S05 |
| CharXiv Reasoning (no tools) | 86.2% | — | S05 |
| LVBench | 87.8% (agentic) / 87.1% (static) | — | S05 |
| BioMysteryBench | 88.8% (human-solvable) / 56.5% (human-difficult) | — | S05 |
| LABBench2 | 86.2% | — | S05 |
| SWE-bench Verified/Pro, ARC-AGI-2/3, GPQA Diamond, FrontierMath, BrowseComp, MRCR, Toolathlon | not found | not present on this model card | — |

### Gemini 3.7 Flash (Google DeepMind)

Published 13 August 2026 [S06]. Based on Gemini 3.6 Flash [S06]. Context: 1M input tokens; same modality profile as 3.8; 64K max output [S06]. Pricing: $0.75/1M input, $3.75/1M output introductory (expires 2026-12-31; $1.50/$7.50 regular from 2027-01-01) [S06].

| Benchmark | Gemini 3.7 Flash | Note | Source |
|---|---|---|---|
| Terminal-Bench 2.1 | 85.8% | matches value cited in the 3.8 Flash card exactly | S06 (cross-checked S05) |
| Terminal-Bench 3.0 | 14.9% | superseded by Terminal-Bench 4.0 in the newer card | S06 |
| GDM-MRCR v2 (8-needle, 128k avg) | 97.0% | — | S06 |
| OSWorld-2.0 | 47.9% | — | S06 |
| HLE-Verified | 53.6% | matches value cited in the 3.8 Flash card exactly | S06 (cross-checked S05) |
| GDPVal-AA v2, Elo | 1525 | **conflicts with 1482** cited for the same model in the newer 3.8 Flash card — see Section 3 | S06 |
| AA Intelligence Index | 56 | this is a raw score under whatever index version was live 13 Aug 2026, not v4.3 (see Section 3) | S06 |
| SWE-bench Verified/Pro, ARC-AGI-2/3, GPQA Diamond, FrontierMath, BrowseComp, Toolathlon | not found | not present on this model card | — |

### Claude Fable 5.1 (Anthropic)

Announced 2026-09-01 alongside Claude Mythos 5.1 [S01, S07]. API ID `claude-fable-5-1` [S07]. Pricing: $10/MTok input, $50/MTok output; cache read $0.25/MTok (a 75% reduction from Fable 5's $1.00/MTok cache-read price — confirmed by both the product page and the pricing page); cache write $12.50/MTok; US-only inference available at 1.1x [S07, S15]. Available on Claude Platform natively, plus AWS/GCP/Microsoft Foundry [S07]. Genuinely new since the 2026-08-20 baseline.

**The numeric benchmark comparison chart on Anthropic's own Fable page is client-side rendered — its values are not present in the fetched HTML** [S07]. The two numbers below are the only ones that happened to be in server-rendered footnote prose:

| Benchmark | Value | Harness / effort note | Source |
|---|---|---|---|
| Terminal-Bench-Science 0.1 (Fable 5, not 5.1) | public leaderboard 21.4%; Anthropic's own repro 24.7% | 3 trials/task, Claude Code harness; standard error ±3.5–4.5 pts; for comparison, same footnote gives Claude Opus 5 at 30.0% (public) / 29.0% (repro) | S07 |
| OSWorld 2.0 (Fable 5.1 and Fable 5) | no absolute score disclosed | Anthropic states both scored zero specifically on tasks where safety safeguards intervened, and explicitly declines to show a comparable overall number because "the task files differ from earlier releases" | S07 |
| SWE-bench Verified/Pro, Terminal-Bench 2.1, ARC-AGI-2/3, GPQA Diamond, FrontierMath, MRCR, GDPval, BrowseComp, Toolathlon (Fable 5.1 specifically) | not found | chart-only on Anthropic's site; not found on any third-party source fetched (all third-party sources predate the 5.1 release) | — |

For the **predecessor, Claude Fable 5** (relevant because the 2026-08-20 baseline figures are for Fable 5, not 5.1), third-party sources gave:

| Benchmark | Claude Fable 5 | Note | Source |
|---|---|---|---|
| HLE-Full | 53.3% (no tools) / 63.0% (with tools) | "max, w/ fallback" | S08 — **exact match to the 2026-08-20 baseline of 53.3** |
| Terminal-Bench 2.1 | 88.0% | — | S08 |
| GPQA Diamond | 92.6% | — | S08 |
| BrowseComp | 88.0% | — | S08 |
| GDPval-AA v2, Elo | 1747 | cited by Kimi as of 2026-07-23 | S08 — see Section 3 for baseline comparison (1759.6) |
| Toolathlon-Verified | 77.9% | — | S08 |
| OSWorld-Verified / OSWorld 2.0 | 85.0% / 66.1% | — | S08 |
| SWE-bench Verified (overall) | not individually cited; archived before Fable 5.1 | vals.ai's Verified leaderboard lists "Claude Fable 5" in its per-difficulty chart (96%/95%/93%/100% by task-duration bucket) but does not give a single blended overall % in retrievable text | S09 |

### Claude Opus 5 (Anthropic)

Announced 2026-07-24 [S01, S12]. API ID `claude-opus-5` [S12]. Pricing $5/MTok input, $25/MTok output; cache read $0.50/MTok, cache write $6.25/MTok; up to 90% cache-read savings, 50% batch savings; US-only inference at 1.1x; 2.5x-faster "fast mode" available at 2x standard pricing [S12, S15].

Anthropic's own benchmark chart for Opus 5 is likewise client-rendered [S12]. Anthropic's news post makes two relative (non-absolute) claims: ARC-AGI-3 score "three times as high as the next-best model," and OSWorld 2.0 performance that surpasses "Fable 5's best result at just over a third of the cost" [S21] — neither gives an absolute percentage, so neither can confirm or refute the 2026-08-20 baseline figures directly.

| Benchmark | Value | Harness / effort note | Source |
|---|---|---|---|
| SWE-bench Verified (overall) | 97.00% | vals.ai's stated leaderboard leader as of their 2026-09-01 update; "sits 3.00 percentage points from a perfect score" | S09 |
| Terminal-Bench 2.1 | 89.1% | cited in Gemini's 3.8 Flash comparison table | S05 |
| Terminal-Bench 4.0 | 51.8% | led all 6 models in that comparison table | S05 |
| HLE-Verified | 54.4% | — | S05 |
| OSWorld-2.0 | 75.4% | "partial score, batch tool enabled" per Google's methodology | S05 |
| GDPVal-AA v2, Elo | 1824 | cited in Gemini's 3.8 Flash card | S05 |
| Terminal-Bench-Science 0.1 | 30.0% (public leaderboard, 3 trials/task, Claude Code harness) / 29.0% (Anthropic's own repro) | — | S07 |
| Terminal-Bench 2.1 (GPT-5.5, cited on Opus's own page for context) | 83.4% | Codex CLI harness (vs. Terminus-2 used for the main chart) | S12 |
| ARC-AGI-2 | not found | not on arcprize.org's static HTML, not on Anthropic's pages in absolute-number form | — |
| ARC-AGI-3 (absolute) | not found | only the relative "3x next-best" claim available | S21 |
| FrontierMath, GPQA Diamond, BrowseComp, MRCR, Toolathlon | not found | — | — |

### Claude Sonnet 5 (Anthropic)

Announced 2026-06-30 [S13]. API ID `claude-sonnet-5` [S13]. Pricing $2/MTok input, $10/MTok output; cache read $0.20/MTok, cache write $2.50/MTok [S13, S15]. Benchmark chart is likewise client-rendered on Anthropic's own page [S13]; the RSC footnotes present are almost all about the prior generation (Sonnet 4.6), not Sonnet 5, so no Sonnet-5-specific footnote numbers were recovered from Anthropic directly.

| Benchmark | Value | Harness / effort note | Source |
|---|---|---|---|
| Terminal-Bench 2.1 | 80.4% | identical value in both independently-fetched Gemini cards | S05, S06 |
| HLE-Verified | 31.0% | identical in both Gemini cards | S05, S06 |
| GDM-MRCR v2 (8-needle, 128k) | 81.5% | — | S06 |
| OSWorld-2.0 | 42.6% | — | S05 |
| GDPVal-AA v2, Elo | 1584 (per S05) vs 1598 (per S06) | ~14-pt discrepancy between two Google-published cards 3 weeks apart — see Section 3 | S05, S06 |
| AA Intelligence Index | 55 | raw score, index version not stated on this card | S06 |
| SWE-bench Verified/Pro, ARC-AGI-2/3, GPQA Diamond, FrontierMath, BrowseComp, Toolathlon | not found | — | — |

### Kimi K3 (Moonshot AI)

Released 2026-07-16 [S17], open-weight under the "Kimi K3 License" [S08]. Architecture: MoE, 2.8T total parameters / 104B activated, 93 layers, KDA + Gated MLA attention [S08]. Context length 1,048,576 tokens (~1M) [S08]. Modality field on the spec sheet says "Text, Image" [S08]; separate marketing prose on Moonshot's own site additionally claims "natively multimodal" video understanding [S17] — this is a minor inconsistency between the technical spec table and marketing copy, noted rather than resolved. API model ID `kimi-k3`, base URL `api.moonshot.ai/v1` [S23]. **No official per-token price was recoverable within budget** — `platform.moonshot.ai/pricing` redirected to a pricing-concepts explainer with no rate table [S23], and a guessed direct pricing sub-URL redirected to a generic docs overview page [S25].

All scores below are Moonshot's own published table, "(max)" reasoning effort, evaluated with the Kimi Code harness unless noted [S08]:

| Benchmark | Kimi K3 | Note | Source |
|---|---|---|---|
| GPQA Diamond | 93.5% | — | S08 |
| Terminal-Bench 2.1 | 88.3% | — | S08 — **exact match to 2026-08-20 baseline of 88.3** |
| BrowseComp | 91.2% (headline table value) | — | S08 — **exact match to 2026-08-20 baseline of 91.2** |
| BrowseComp (alternate condition) | 90.4% | explicitly "full 1M-token context window, no context management" — the 91.2 headline uses a context-compaction strategy triggered at 300K tokens instead | S08 |
| HLE-Full | 43.5% (no tools) / 56.0% (with tools) | — | S08 — **exact match to 2026-08-20 baseline of 43.5 (no-tools variant)** |
| GDPval-AA v2, Elo | 1686 | cited as of 2026-07-23 | S08 |
| Toolathlon-Verified | 76.5% | — | S08 |
| OSWorld-Verified / OSWorld 2.0 | 84.8% / 58.3% | — | S08 |
| DeepSWE | 67.5% | mini-SWE-agent harness gives 67.3% per official leaderboard, footnoted as a cross-check | S08 |
| AA Intelligence Index | 44 | v4.3, "(max)" — #2 open-weights model behind GLM-5.3 (max) at 45 | S11 |
| SWE-bench Verified (overall) | 93.40% | vals.ai's own headline figure, ahead of Claude Opus 4.8's 88.60% and Grok 4.5's 86.60%, behind DeepSeek V4 Pro 0813's 96.40% | S09 |
| ARC-AGI-2/3, FrontierMath | not found | — | — |

---

## 3. Not found / conflicts

**Not found despite active searching (within the 25-fetch budget):**
- ARC-AGI-2 for every model in scope. arcprize.org's leaderboard and per-benchmark pages (S10, S19) render all scores via client-side JS/scatter-plot; no per-model number survived a plain-HTML fetch.
- ARC-AGI-3 as an absolute percentage for Claude Opus 5 (only a relative "3x next-best" claim exists, S21) and for Claude Fable 5.1.
- SWE-bench Pro for any model (GPT-5.6 Sol included) — no page found that reports it; SWE-bench Verified itself is explicitly marked "archived" by vals.ai as of this fetch ("since performance on this benchmark has saturated, we no longer run this benchmark on new model releases," S09), which is presumably also why the newest models (GPT-6 Astra, Claude Fable 5.1) never appear on that leaderboard.
- FrontierMath (any tier) for Claude Fable 5.1, Claude Opus 5, Claude Sonnet 5, Kimi K3, and both Gemini Flash models. Epoch's own FrontierMath page (S14) describes the tier structure but carries no per-model leaderboard in static HTML. GPT-6 Astra's Tier 4 = 98% (S22) is the only FrontierMath figure recovered in this pass.
- GDPval (any variant) for Claude Sonnet 5 and Kimi K3 in the exact "GDPval-AA" (non-v2, decimal-precision) form the 2026-08-20 baseline used for Fable 5 (1759.6); only the integer-valued "GDPval-AA v2" Elo metric was found, which appears to be a different, continuously-recalculated snapshot of the same underlying ladder (see conflict note below).
- Toolathlon for OpenAI and Google models (only Kimi K3, Claude Fable 5, GPT-5.6 Sol, Claude Opus 4.8, GPT-5.5, and GLM-5.2 appear on the one table that reports it, S08).
- Kimi K3's official per-token price (see Kimi K3 section above — both direct attempts redirected away from an actual rate table).
- GPT-6 Astra's exact calendar release date (only "rolling out today" language found, no dateline metadata, S22).

**Conflicts between sources (flagged per the brief's >2-point threshold):**
1. **Gemini 3.7 Flash, GDPval-AA v2 Elo: 1525 (its own model card, S06, published 2026-08-13) vs. 1482 (cited inside the Gemini 3.8 Flash card's comparison table, S05, published 2026-09-02).** A 43-point drop over three weeks for the same, unchanged model. Likely explanation: this is a relative Elo ladder that gets recomputed as new models join the pool between snapshots, not a real capability change — but it is a genuine numeric conflict between two official Google-published documents, reported here as instructed rather than silently reconciled.
2. **Claude Sonnet 5, same metric: 1598 (S06) vs. 1584 (S05).** Same phenomenon, smaller magnitude (14 points), same two sources.
3. **Claude Fable 5, GDPval-AA v2 Elo: 1747 (Kimi's HF card, S08, citing Artificial Analysis "as of 2026-07-23") vs. the 2026-08-20 baseline figure of 1759.6.** A ~12.6-point difference. Note the baseline's decimal precision (1759.6) doesn't match the integer Elo values seen in every other GDPval-AA v2 citation in this research pass (1545, 1482, 1824, 1584, 1710, 1528, 1686, 1747, 1736, 1593, 1491, 1510 — all integers), which suggests the baseline may come from a different snapshot, a differently-rounded index, or a non-"v2" variant of GDPval-AA entirely. Flagging as unresolved rather than asserting either number is wrong.
4. **AA Intelligence Index is versioned and not stable across time**, which reads as a near-conflict if not caught: Gemini's own card (S06, mid-August 2026) reports raw index scores in the 50s (Gemini 3.7 Flash 56, Claude Sonnet 5 55, GPT-5.6 Terra 57) with no version number stated, while live artificialanalysis.ai (S11, fetched 2026-09-09) is explicitly on "v4.3" and reports Claude Fable 5.1 leading at 53 — a lower number for a supposedly more-capable model. These are not comparable scores; they're different index versions/methodologies, not a regression. Recorded here so the routing-doctrine page doesn't accidentally treat "Fable 5.1 = 53 < Sonnet 5 = 55" as meaningful.
5. **GPT-6 Astra's ARC-AGI-3 result is stated two different ways on the same OpenAI page** (S22): OpenAI's own copy says Astra "saturates ARC-AGI-3 with a 99.9% score," while a pull-quote from ARC Prize Foundation's Greg Kamradt on the same page says Astra "surpassed our human action-efficiency baseline on 96% of levels." These are plausibly two different metrics (raw pass rate vs. a human-efficiency-baseline comparison) rather than a contradiction, but both are reproduced verbatim above rather than merged into one number.
6. **Kimi K3's BrowseComp score is reported two ways on its own model card** (S08): 91.2 as the table's headline value (default context-compaction strategy, triggered at 300K tokens) vs. 90.4 stated separately in a footnote for "the full 1M-token context window and no context management." Not a conflict once the methodology difference is read — flagged only so neither number is used without its condition.

---

## 4. Changes since 2026-08-20

**New models (did not exist / were not evaluated as of the 2026-08-20 baseline):**
- **Gemini 3.8 Flash** — published 2026-09-02 [S05]. Beats Gemini 3.7 Flash and Claude Sonnet 5 on every benchmark in its own comparison table; on Terminal-Bench 2.1 (89.4%) it also edges out Claude Opus 5 (89.1%) and GPT-5.6 Sol (88.8%).
- **Claude Fable 5.1** and **Claude Mythos 5.1** — announced 2026-09-01 [S01, S07]. Fable 5.1 replaces Fable 5 as Anthropic's top generally-available model; Fable 5 is retained (not removed) at unchanged pricing.
- **GPT-6 Astra** — confirmed live and current as of 2026-09-09, model ID `gpt-6-astra` [S04], with a real, detailed announcement page [S22]; exact release date not pinned down (see gaps above). This replaces "GPT-5.6 Sol" as OpenAI's flagship, though Sol/Terra/Luna remain listed as current, non-deprecated models.

**IDs confirmed still current / NOT deprecated (contrary to what one might assume given newer releases exist):**
- GPT-5.6 Sol, Terra, and Luna are all still listed as active "Flagship" / non-legacy models on `platform.openai.com/docs/models` [S04] — no deprecation notice found anywhere in this research pass.
- Claude Opus 4.8 is listed under a "Legacy models" heading on Anthropic's pricing page [S15] (not literally called "deprecated") at unchanged pricing ($5/$25 per MTok), and is still in active production use as the automatic fallback target for Fable 5.1's cybersecurity-safeguard routing [S07].
- Gemini 3.6 Flash and Gemini 3.7 Flash: no deprecation language found on either the 3.7 or 3.8 Flash model cards; 3.7 Flash is still used as a live comparator in the 3.8 Flash card [S05], implying it remains available, just no longer the newest.

**Numbers that moved by more than 2 points vs. the supplied 2026-08-20 baseline (same model, same metric):**
- Opus 5 SWE-bench Verified: baseline 96.0 → found 97.00% [S09]. A +1.0-point move — **does not** cross the >2-point threshold, included for completeness.
- Fable 5 GDPval-AA v2 Elo: baseline 1759.6 → found 1747 [S08]. A ~12.6-point move that does cross the threshold, but see conflict note 3 above (decimal-precision mismatch suggests possibly different metrics/snapshots, not a clean apples-to-apples regression).

**Baseline figures reproduced exactly (no notable change found):**
- GPT-5.6 Sol: Terminal-Bench 2.1 88.8 [S05, S08 — double-confirmed] and BrowseComp 90.4 [S08].
- Gemini 3.7 Flash: MRCR v2 8-needle 128k 97.0 [S06] and Terminal-Bench 2.1 85.8 [S05, S06 — double-confirmed].
- Kimi K3: Terminal-Bench 2.1 88.3 [S08], BrowseComp 91.2 (headline value) [S08], HLE(-Full, no-tools) 43.5 [S08].

**Baseline figures that could not be confirmed or refuted in this pass** (not "unchanged," genuinely not found): Opus 5 ARC-AGI-2 90.42 and ARC-AGI-3 30.2; Fable 5 FrontierMath T4 87.8; GPT-5.6 Sol SWE-bench Pro 64.6.

---

## Addendum 2026-09-09: User-Agent comparison

The brief's required header (`OpenAI File Downloader, XaiImageApiFetch/1.0`) was not sent by the fact-gathering agent (see the methodology note at the top). At the user's request the eight primary sources were re-fetched with exactly that header: S04, S22, S05, S06, S07, S15, S09, S08. All eight returned HTTP 200 with page sizes matching the browser-agent pass, and all fourteen headline figures checked (Astra FrontierMath 98%, ARC-AGI-3 99.9%, OSWorld 72.6; Gemini 3.8 Flash TB2.1 89.4, HLE-V 54.9, Opus 5 GDPval 1824, $0.75; 3.7 Flash MRCR 97.0; Fable 5.1 cache read $0.25; Opus 5 SWE-V 97.00; K3 TB2.1 88.3 and BrowseComp 91.2; the `gpt-6-astra` id) were present under both headers. No source blocked either agent string; the figures in this pack do not depend on which was sent.
