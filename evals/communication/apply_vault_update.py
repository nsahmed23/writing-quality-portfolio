"""Apply the staged routing-doctrine refresh to the Obsidian vault (raw filesystem write).

Run ONLY with the user's explicit go-ahead: the CLAUDE.md rule is that vault writes go through the
Obsidian MCP; this script is the fallback for when the MCP is down and Obsidian is not open.

Usage: py -3.11 apply_vault_update.py
Does: copy model-routing-2026-09-09.md over wiki/stacks/model-routing.md; write the fact-pack as
wiki/research/model-factpack-2026-09.md with frontmatter; bump the index.md row date; append a log.md line.
Backs up the previous routing page to wiki/stacks/model-routing.2026-08-20.bak.md first.
"""
import re
import shutil
from datetime import date
from pathlib import Path

WS = Path(__file__).resolve().parent
VAULT = Path("C:/nazeer-wiki")
TODAY = date.today().isoformat()

routing_dst = VAULT / "wiki/stacks/model-routing.md"
backup = VAULT / "wiki/stacks/model-routing.2026-08-20.bak.md"
if routing_dst.exists() and not backup.exists():
    shutil.copy2(routing_dst, backup)
shutil.copy2(WS / "model-routing-2026-09-09.md", routing_dst)

factpack_src = (WS / "model-factpack-2026-09.md").read_text(encoding="utf-8")
fm = f"""---
title: Frontier Model Benchmark Fact-Pack (Sep 2026)
type: research
mode: dev
tags:
  - llm
  - benchmarks
  - routing
created: {TODAY}
updated: {TODAY}
sources:
  - "https://platform.openai.com/docs/models"
  - "https://openai.com/index/gpt-6-astra/"
  - "https://deepmind.google/models/model-cards/gemini-3-8-flash/"
  - "https://deepmind.google/models/model-cards/gemini-3-7-flash/"
  - "https://www.anthropic.com/claude/fable"
  - "https://www.anthropic.com/pricing"
  - "https://www.vals.ai/benchmarks/swebench"
  - "https://huggingface.co/moonshotai/Kimi-K3"
---

"""
(VAULT / "wiki/research/model-factpack-2026-09.md").write_text(fm + factpack_src, encoding="utf-8")

idx = VAULT / "index.md"
t = idx.read_text(encoding="utf-8")
t2 = re.sub(r"\| Model Routing \| 2026-08-20 \| \[\[wiki/stacks/model-routing\]\] \|",
            f"| Model Routing | {TODAY} | [[wiki/stacks/model-routing]] |", t)
if "model-factpack-2026-09" not in t2:
    t2 = t2.rstrip("\n") + f"\n| Model Fact-Pack Sep 2026 | {TODAY} | [[wiki/research/model-factpack-2026-09]] |\n"
idx.write_text(t2, encoding="utf-8")

log = VAULT / "log.md"
with log.open("a", encoding="utf-8") as fh:
    fh.write(f"\n- {TODAY}: refreshed [[wiki/stacks/model-routing]] to v3 (GPT-6 Astra, Gemini 3.8 Flash, Fable 5.1; judging lane; lane mechanics) and added [[wiki/research/model-factpack-2026-09]]. Previous page backed up as model-routing.2026-08-20.bak.md.\n")
print("applied:", routing_dst, "|", VAULT / "wiki/research/model-factpack-2026-09.md", "| index + log updated")
