---
title: Model Routing Doctrine (our own automode)
type: concept
mode: dev
tags:
  - stacks
  - orchestration
  - llm
  - routing
  - benchmarks
  - runbook
created: 2026-08-20
updated: 2026-09-09
sources:
  - "https://platform.openai.com/docs/models"
  - "https://openai.com/index/gpt-6-astra/"
  - "https://deepmind.google/models/model-cards/gemini-3-8-flash/"
  - "https://deepmind.google/models/model-cards/gemini-3-7-flash/"
  - "https://www.anthropic.com/claude/fable"
  - "https://www.anthropic.com/pricing"
  - "https://www.vals.ai/benchmarks/swebench"
  - "https://huggingface.co/moonshotai/Kimi-K3"
  - "https://www-cdn.anthropic.com/c5fbac3f0b1280a933ebd26d3cb8bb9f5bdeaf48/Claude%20Opus%205%20System%20Card.pdf"
  - "https://www.trychroma.com/research/context-rot"
  - "[[wiki/research/llm-routing-research-2026-08]]"
  - "[[wiki/research/model-factpack-2026-09]]"
---

# Model Routing Doctrine

> STATUS (audit 2026-08-20, [[wiki/reviews/orchestration-audit-2026-08-20]]): this is a strong MANUAL routing runbook, NOT yet a safe autonomous control plane. The heart of an autonomous system is not model selection but: scoped task contract, isolated execution, observable resolved endpoint, objective gate, independent review, controlled integration. Treat the routing table below as PRIORS and tie-breakers, not deterministic rules; route by capability + difficulty + risk + phase first, topic only to break ties. Known corrections tracked in the audit: quota has a shadow cost (not zero), Ultra is an orchestration strategy not an effort level, benchmark rows need dates/harness/expiry, gemini-cli is account-disabled. Do not run unattended with danger-full-access / --dangerously-skip-permissions as the default posture.

> v3 (2026-09-09): refreshed for three new models (GPT-6 Astra, Gemini 3.8 Flash, Claude Fable 5.1), lane re-verification, and a judging lane learned from the communication-skill evals. Every number below carries a source id from [[wiki/research/model-factpack-2026-09]] (S-ids) or the August research page; numbers with no id are carried over from v2 unverified this pass and say so. The fetch pass could not read JavaScript-rendered vendor charts (Anthropic product pages, arcprize.org, artificialanalysis.ai); Google model cards, OpenAI's docs/models page, and the Kimi K3 card are static and were read in full.

Evidence-based routing across the four subscription lanes: our own "copilot automode" without the restrictions. v2 was rebuilt 2026-08-20 from nine research sweeps plus a blind extraction of official vendor model cards; v3 re-verifies the lanes and adds the September models. Full fact-packs: [[wiki/research/llm-routing-research-2026-08]] (August) and [[wiki/research/model-factpack-2026-09]] (September).

## The lanes we pay for (verified 2026-09-09)

| Lane | Sub | Models | Native inputs | Verified today |
|---|---|---|---|---|
| Claude Code (Max) | Claude Max | Fable 5.1 (1M, $10/$50, cache read $0.25), Opus 5 (1M, $5/$25), Sonnet 5 (1M, $2/$10), Haiku 4.5 (200K) [S07, S15] | text, images, PDF. NO audio, NO video | pin of record is `claude-opus-5[1m]`; this session drifted to Fable 5.1 |
| Codex CLI 0.153.4 | ChatGPT | GPT-6 Astra (`gpt-6-astra`, config default, 1.05M ctx, $10/$50) plus GPT-5.6 sol $4/$20, terra $2/$12, luna $0.20/$1.20, all still current, none deprecated [S04] | text, images; video frames-only | `codex exec` answered "OK" on the default model; `-m gpt-6` or `gpt-6-asta` is rejected for ChatGPT accounts, so leave the config default |
| Kimi CLI 0.37.2 | Moonshot membership | K3 (256K via CLI, 1M API-only), K2.7 Coding | text, images (card); marketing claims video; NO audio | `-p` on k3-256k answered "OK"; a 35-call burst of 14 KB prompts hit the 5-hour cap (HTTP 403) |
| agy (Antigravity) 1.1.17 | Google AI Pro $20 | Gemini 3.8 Flash high/medium/low (default 3.8 high), 3.7, 3.6, 3.1 Pro, claude-sonnet-4-6, claude-opus-4-6-thinking, gpt-oss-120b | text, images, RAW AUDIO, RAW VIDEO [S05] | `-p` on `gemini-3.8-flash-high` answered "OK"; the model id needs the effort suffix |
| Ollama (local) | free | mistral:7b-q4, phi3:mini (2024-era, stale) | offline fallback only | not re-verified |

Local-lane sizing: `uvx llmfit recommend --json` (github.com/AlexsJones/llmfit). Measured 2026-08-20: ~9.6 GB available, iGPU spills to RAM; best fits are 3-4B dense at Q8 (~21 tok/s), 300M embedding models (~436 tok/s), or a ~26B MoE with 4B active at Q4 (~32 tok/s). Q4-class local models are for drafting, embedding, and offline utility, never verdicts or long-context work.

## What the official numbers say (September 2026 refresh)

**Agentic coding: the frontier band is now Gemini 3.8 Flash, Opus 5, sol, K3, all within 1.1 points on Terminal-Bench 2.1.** TB2.1: Gemini 3.8 Flash 89.4, Opus 5 89.1, sol 88.8, K3 88.3, Fable 5 88.0, terra 87.4, 3.7 Flash 85.8, Sonnet 5 80.4 [S05, S06, S08]. Terminal-Bench 4.0 (new, much harder): Opus 5 51.8, 3.8 Flash 19.1 [S05]. SWE-bench Verified is now archived by vals.ai as saturated ("we no longer run this on new model releases"); last standings Opus 5 97.0, K3 93.4 [S09]; GPT-6 Astra and Fable 5.1 were never scored on it. SWE-bench Pro was not found for any model this pass; the August figures (Mythos 80.3, Fable 80.0, Opus 5 79.2, sol 64.6) stand unverified. Harness choice still moves scores as much as model choice.

**Deep reasoning: GPT-6 Astra claims saturation; Anthropic publishes relatives.** OpenAI's own page says Astra "saturates" FrontierMath Tier 4 at 98% and ARC-AGI-3 at 99.9%, while the ARC Prize quote on the same page frames it as beating the human action-efficiency baseline on 96% of levels, a different metric [S22]. Anthropic's Opus 5 post claims an ARC-AGI-3 score "three times the next-best model" with no absolute number [S21]; the August absolutes (Opus 5 ARC-AGI-2 90.42, ARC-AGI-3 30.2; Fable 5 FrontierMath T4 87.8) could not be confirmed or refuted because arcprize.org and Epoch render scores client-side. HLE-Verified: 3.8 Flash 54.9, Opus 5 54.4, 3.7 Flash 53.6, terra 51.1, Sonnet 5 31.0 [S05, S06]. HLE-Full no tools: Fable 5 53.3, sol 44.5, K3 43.5 [S08]. GPQA: sol 94.1, K3 93.5, Fable 5 92.6, saturated [S08]. Until ARC Prize or Epoch publish Astra's scores under their own harness, treat the saturation claims as self-reported.

**Tool use:** Toolathlon-Verified: Fable 5 77.9, K3 76.5 [S08]; Opus 5 80.6 and MCP-Atlas 85.8 are August figures. Astra's cyber rows are new and large: ExploitBench 100 vs sol 78.5, SRE-Bench 88.0 single-attempt vs sol 55.9 [S22].

**Long context:** GDM-MRCR v2 8-needle at 128k: 3.7 Flash 97.0, terra 93.5, Sonnet 5 81.5 [S06]; the 3.8 Flash card publishes no MRCR row, and 3.8 is "based on 3.7", so treat 3.8's retrieval as at least 3.7's until measured. August figures for 1M (3.6 Flash 54.0; sol OpenAI-MRCR 91.5 at 256-512K; GraphWalks Mythos 79.4, sol 77.1) are unverified this pass. Haiku remains a 200K model.

**Multimodal and computer use:** OSWorld 2.0 in Google's table (partial score, batch tool): Opus 5 75.4, 3.8 Flash 59.0, Sonnet 5 42.6 [S05]; OpenAI's framing: Astra 72.6 at about 40 min per task vs sol 65.7 at about 75 min [S22]; Kimi's table: Fable 5 66.1, K3 58.3 [S08]. Fable 5.1 discloses no OSWorld score because its safety safeguards zeroed the affected tasks [S07]. Gemini stays the only raw audio and video lane. K3 leads OmniDocBench (August figure).

**Professional deliverables, GDPval-AA v2 Elo:** Opus 5 1824, Fable 5 1747, sol 1736, K3 1686, Sonnet 5 1584 to 1598, 3.8 Flash 1545 [S05, S08]. This ladder drifts as models join: 3.7 Flash reads 1525 on its own card and 1482 three weeks later on the 3.8 card. Compare within one table only.

**Deep research and browsing:** BrowseComp: K3 91.2 with context compaction (90.4 at full 1M with none), sol 90.4, Fable 5 88.0 [S08]. Kimi is still a legitimate deep-research lane.

**Pricing that changed:** Fable 5.1 keeps Fable 5's $10/$50 but cuts cache read from $1.00 to $0.25 per MTok, which makes long orchestrator sessions markedly cheaper [S07, S15]. Gemini 3.8 Flash is $0.75/$3.75 introductory, $1.50/$7.50 regular, no caching [S05]. Kimi K3's official price was not recoverable. Opus 4.8 is now under "Legacy models" at unchanged price and is the safeguard fallback target for Fable 5.1 [S15, S07].

## The routing table (v3)

| Task | Route to | Why |
|---|---|---|
| Orchestration, gating, last-mile git | Opus 5 (pin of record) or Fable 5.1 when pinned | Opus 5 leads GDPval 1824, SWE-V 97.0, TB2.1 89.1 at half Fable's price; Fable 5.1's $0.25 cache read narrows the gap on long sessions |
| Root-cause debugging, architecture, algorithms | Opus 5 (deep-reasoner) | TB4.0 51.8 (next best 19.1), HLE-Verified 54.4, ARC-AGI-3 "3x next-best" |
| Well-specified features, tests, mechanical edits | Sonnet 5 (fast-worker) | $2/$10; TB2.1 80.4 is the bottom of the band, so gate its output |
| Recall sweeps, file reading, fact-packs | Haiku 4.5, chunked fan-out | $1/$5; chunk small, fan wide; never one giant document |
| Bulk mechanical on foreign quota | GPT-5.6 luna (Codex, `-m gpt-5.6-luna`) | $0.20/$1.20; still current; avoid long context |
| Sonnet-equivalent on foreign quota | GPT-5.6 terra | $2/$12; MRCR 93.5 at 128k; TB2.1 87.4 |
| Second implementation, adversarial gate, cyber review | GPT-6 Astra (Codex default, effort xhigh for gates, high for judging) | ExploitBench 100, SRE-Bench 88, OSWorld 72.6 at half sol's wall time; keep the METR rule: never accept its own "done" |
| High-stakes consult, outside judgment | GPT-6 Astra via Codex, or Sol Pro in ChatGPT web | flagship reasoning on lanes already paid for |
| Blind judging of eval outputs | Codex Astra (high) AND agy Gemini 3.8 Flash, every pair in both orders | verified 2026-09-09: the two agreed on 12 of 12 mutually stable pairs; Kimi as a judge showed recency bias and hit its 5-hour cap at ~35 calls, so use it only with order reversal and after the other two |
| Cheap frontier-grade terminal agent on foreign quota | agy Gemini 3.8 Flash | TB2.1 89.4 at $0.75/$3.75; headless tool use needs `--dangerously-skip-permissions`, which Claude Code's classifier blocks, so from here it is an analysis and judging lane, not an executor |
| Frontend/design implementation | Kimi K3 | August: #1 Arena Frontend Code and Design Arena; budget ~2x output verbosity; no new data this pass |
| Deep research, agentic browsing second lane | Kimi K3 | BrowseComp 91.2 [S08]; pair with Claude research for cross-checks |
| Games and interactivity | Fable/Opus first, K3 second | August Arena figures, unverified this pass |
| Creative writing | Opus 5 first, K3 second opinion | August EQ-Bench figures, unverified this pass |
| Audio: transcription, listening | agy Gemini 3.8 Flash ONLY | only raw-audio lane [S05] |
| Video review | agy first; K3 silent-video backup | native video files; K3 has no audio |
| Needle-critical mega-document reads (128K-1M) | agy Gemini 3.7 Flash (published MRCR 97 at 128k) or 3.8 Flash (based on 3.7, unpublished) for public docs; Opus or Fable for sensitive code | Claude for anything that must not leave approved lanes |
| Screenshots, PDFs, charts, computer use | in-house Claude; K3 for bulk document OCR | OSWorld 2.0 Opus 75.4; K3 OmniDocBench (August) |
| Fact-sensitive claims from ANY cheap or fast model | verify before trusting | AA-Omniscience (August): every frontier model hallucinates ~50%+ when it does not abstain |

## Sentiment-backed operating rules

1. Opus/Fable get long, checkable, tightly scoped autonomous jobs, never vague one-liners; the dominant Claude complaint is scope creep. Constrain with "touch only X".
2. Never accept a Codex model's self-reported success; gate on tests and output tails (METR reward-hacking finding, August; Astra unassessed).
3. Never route "tell me if this is a bad idea" to Gemini alone; agy stays perception, analysis, and judging.
4. Budget K3 by output tokens, not sticker price (~2x median verbosity), and by its 5-hour burst cap.
5. Sonnet 5 is the default fallback, not the specialist; tokenizer inflation ~1.3-1.4x.
6. (new) Fetch model cards, not product pages: Anthropic's, arcprize.org's, and artificialanalysis.ai's charts are JavaScript-rendered and invisible to curl; Google's cards, OpenAI's docs/models page, and Hugging Face cards are static.

## Routing-lab lessons (people who route for a living)

1. Route on task DIFFICULTY, not topic.
2. Grade-then-route: pick the cheapest model that clears the capability bar (vision? tools? context length? reasoning depth?).
3. Escalate on failure, not by default; a two-tier cheap/expensive split captures most oracle gains for a personal workload.
4. Session stickiness: once a session proves it needs a strong model, keep it there.
5. Reliability under load is a first-class signal: fall back across lanes on rate-limit (Kimi's cap is the live example).
6. Foreign lanes have their own swarms (Codex agents max_threads=5; Kimi Agent Swarm).

## Provider-variance rules (inference/quantization labs)

1. A model name means nothing without serving precision; FP8 is near-lossless, 4-bit degrades multi-step reasoning and 128K+ retrieval first.
2. Use official APIs for open-weight models (kimi CLI hits api.kimi.com directly).
3. After any quantized or self-hosted deployment, re-test multi-step reasoning, long-context retrieval at your real length, and tool-call JSON reliability.

## Lane mechanics learned 2026-09-09

- Codex: the npm `codex.cmd` shim truncates a multi-line argv prompt at the first newline; pipe prompts over stdin (`codex exec` reads instructions from stdin when no prompt is given). `-c model_reasoning_effort="high"` overrides the xhigh config default per call; a one-word probe costs ~22k tokens of harness context.
- Antigravity: model ids carry the effort (`gemini-3.8-flash-high`); text-only `-p` runs need no permission flag and take ~10 s.
- Kimi: `-p` on `kimi-code/k3-256k` takes ~15 s per 14 KB prompt; the 5-hour cap returns `provider.auth_error` 403 in ~3 s, so drivers must be resumable.
- Obsidian CLI needs a running Obsidian; without it the binary launches the app and returns no command output.

## Standing rules

0a. **The persistent state graph is the source of truth across sessions**, at `C:\Dev\Projects\orchestrator\state.db` (event-sourced SQLite). Resume orchestration work from the latest checkpoint's resume_instruction, not from prose.
0b. **No worker agent writes long-term memory directly.** Workers propose; the coordinator validates and commits.
1. Flagship gaps are 1-5 points; chase price, quota, and failure modes, not leaderboard deltas under ~5 points.
2. Effort tier moves rankings more than vendor choice; fix the budget first.
3. Escalate a tier only when a cheaper lane fails its gates.
4. Perception lanes report; the orchestrator adjudicates.
5. Kimi CLI K3 = 256K (config-verified); 1M is API-only.
6. Vendor self-published tables cherry-pick harnesses; cross-vendor numbers are comparable only within one publisher's table, and Elo ladders (GDPval-AA v2, AA Intelligence Index) are not comparable across snapshots or index versions.
7. Re-verify quarterly; this refresh was three weeks after v2 and three models had moved.
8. (new) Blind judging uses two off-family lanes with order reversal; count only pairs whose preference survives the reversal.
9. (new) Vendor "saturation" claims (Astra's FrontierMath 98, ARC-AGI-3 99.9) are self-reported until the benchmark's own maintainer publishes them; route on them as priors, not facts.

## Changes since v2 (2026-08-20)

- New: GPT-6 Astra (Codex default; sol/terra/luna remain current), Gemini 3.8 Flash (2026-09-02; TB2.1 89.4, HLE-Verified 54.9), Claude Fable 5.1 (2026-09-01; same price, cache read $0.25; no readable benchmarks).
- Moved: Opus 5 SWE-bench Verified 96.0 to 97.0 (benchmark now archived); Fable 5 GDPval-AA 1759.6 (August) vs 1747 (Kimi's table), likely a ladder snapshot difference.
- Confirmed unchanged: sol TB2.1 88.8 and BrowseComp 90.4; 3.7 Flash MRCR 97.0 and TB2.1 85.8; K3 TB2.1 88.3, BrowseComp 91.2, HLE 43.5.
- Not confirmable this pass: all ARC-AGI absolutes, SWE-bench Pro, FrontierMath tiers for non-OpenAI models, Kimi K3 price.
- Lane changes: judging row added; Gemini 3.8 Flash replaces 3.6/3.7 as the agy default; Kimi burst cap and Codex stdin rule recorded.
